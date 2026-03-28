
from __future__ import annotations

import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import streamlit as st

APP_TITLE = "SHOC SOP Portal"
APP_SUBTITLE = "Main SOP → Toolkit → Templates"
DEFAULT_BASE_DIR = Path(__file__).resolve().parent / "SOPs"

# Folder-root-level logic from updated structure:
# 1.1 = files in the main SOP folder root
# 1.2 = files in the Toolkit subfolder
# 1.3 = files in the Templates subfolder (under Toolkit)

PREFERRED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt", ".csv"]

MAIN_SOP_METADATA = {
    1: {"title": "Governance, Finance and Audit", "icon": "📘", "owner": "Finance Lead"},
    2: {"title": "Multi-Hazard Early Warning System", "icon": "⚠️", "owner": "Early Warning Lead"},
    3: {"title": "Emergency Telecommunications", "icon": "📡", "owner": "Telecoms Lead"},
    4: {"title": "Emergency Response Teams", "icon": "🚑", "owner": "Operations Lead"},
    5: {"title": "Human Resources and Surge Staffing", "icon": "👥", "owner": "HR Lead"},
    6: {"title": "ICT, Data Management and Cybersecurity", "icon": "🛡️", "owner": "ICT Lead"},
    7: {"title": "Security and Access Control", "icon": "🔐", "owner": "Security Lead"},
    8: {"title": "Supply Chain Management", "icon": "📦", "owner": "Supply Chain Lead"},
    9: {"title": "Business Continuity Management", "icon": "✅", "owner": "BCM Lead"},
}


@dataclass
class RepoFile:
    title: str
    path: Path
    level_code: str
    category: str

    @property
    def ext(self) -> str:
        return self.path.suffix.lower()

    @property
    def mime(self) -> str:
        return mimetypes.guess_type(str(self.path))[0] or "application/octet-stream"


@dataclass
class MainSOP:
    number: int
    title: str
    icon: str
    owner: str
    folder_path: Path
    root_files: List[RepoFile] = field(default_factory=list)      # 1.1
    toolkit_files: List[RepoFile] = field(default_factory=list)   # 1.2
    template_files: List[RepoFile] = field(default_factory=list)  # 1.3

    @property
    def short_name(self) -> str:
        return f"SOP {self.number}"

    @property
    def display_name(self) -> str:
        return f"SOP {self.number}: {self.title}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def natural_sort_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    out = []
    for p in parts:
        out.append(int(p) if p.isdigit() else p)
    return out


def is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PREFERRED_EXTENSIONS


def file_label(path: Path) -> str:
    stem = path.stem.replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def list_files_sorted(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if is_supported_file(p)], key=natural_sort_key)


def find_child_folder(parent: Path, keyword: str) -> Optional[Path]:
    if not parent.exists():
        return None
    keyword = keyword.lower()
    for p in sorted(parent.iterdir(), key=natural_sort_key):
        if p.is_dir() and keyword in p.name.lower():
            return p
    return None


def list_top_level_sop_folders(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    folders = []
    for p in sorted(base_dir.iterdir(), key=natural_sort_key):
        if p.is_dir():
            folders.append(p)
    return folders


def infer_sop_number(folder_name: str, fallback_number: int) -> int:
    m = re.match(r"^\s*(\d+)", folder_name)
    if m:
        return int(m.group(1))
    return fallback_number


def build_repository(base_dir: Path) -> List[MainSOP]:
    repo: List[MainSOP] = []
    folders = list_top_level_sop_folders(base_dir)

    for idx, folder in enumerate(folders, start=1):
        sop_number = infer_sop_number(folder.name, idx)
        meta = MAIN_SOP_METADATA.get(
            sop_number,
            {"title": folder.name.replace("_", " "), "icon": "📁", "owner": "SHOC"},
        )

        toolkit_folder = find_child_folder(folder, "toolkit")
        templates_folder = None
        if toolkit_folder:
            templates_folder = find_child_folder(toolkit_folder, "template")
        if templates_folder is None:
            templates_folder = find_child_folder(folder, "template")

        # 1.1 = root files only (exclude files inside toolkit/templates)
        root_files = [
            RepoFile(file_label(p), p, "1.1", "Main SOP / Index / Annex")
            for p in list_files_sorted(folder)
        ]

        # 1.2 = toolkit direct files
        toolkit_files: List[RepoFile] = []
        if toolkit_folder:
            toolkit_files = [
                RepoFile(file_label(p), p, "1.2", "Toolkit")
                for p in list_files_sorted(toolkit_folder)
            ]

        # 1.3 = templates direct files
        template_files: List[RepoFile] = []
        if templates_folder:
            template_files = [
                RepoFile(file_label(p), p, "1.3", "Template")
                for p in list_files_sorted(templates_folder)
            ]

        repo.append(
            MainSOP(
                number=sop_number,
                title=meta["title"],
                icon=meta["icon"],
                owner=meta["owner"],
                folder_path=folder,
                root_files=root_files,
                toolkit_files=toolkit_files,
                template_files=template_files,
            )
        )

    repo.sort(key=lambda x: x.number)
    return repo


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1rem; padding-bottom: 2rem;}
        .shoc-band {
            background: linear-gradient(90deg, #1f4e8c 0%, #2e6fb7 100%);
            color: white;
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
            border: 1px solid #d8e3f2;
        }
        .shoc-card {
            border: 1px solid #dfe6ef;
            border-radius: 14px;
            padding: 0.95rem 1rem 0.85rem 1rem;
            background: white;
            box-shadow: 0 1px 8px rgba(15, 45, 90, 0.06);
            min-height: 240px;
        }
        .shoc-card h4 {
            margin: 0 0 0.35rem 0;
            color: #163d73;
            font-size: 1.15rem;
            line-height: 1.25;
        }
        .shoc-muted {
            color: #5b6572;
            font-size: 0.92rem;
            line-height: 1.45;
            margin-bottom: 0.55rem;
        }
        .shoc-chip {
            display: inline-block;
            padding: 0.18rem 0.45rem;
            border-radius: 999px;
            background: #eef4fb;
            color: #1c5a94;
            font-size: 0.8rem;
            margin-right: 0.35rem;
            margin-bottom: 0.25rem;
            border: 1px solid #d8e6f4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_base_dir() -> Path:
    raw = os.getenv("SHOC_SOP_BASE_DIR", str(DEFAULT_BASE_DIR))
    return Path(raw)


def init_state() -> None:
    st.session_state.setdefault("view", "dashboard")
    st.session_state.setdefault("selected_main", None)


def goto_dashboard():
    st.session_state.view = "dashboard"
    st.session_state.selected_main = None


def goto_main(main_number: int):
    st.session_state.view = "main_sop"
    st.session_state.selected_main = main_number


def file_action_block(file: RepoFile, key_prefix: str) -> None:
    c1, c2 = st.columns([1.4, 1.1])
    with c1:
        st.markdown(f"**{file.title}**")
        st.caption(f"Level {file.level_code} · {file.category} · {file.path.name}")
    with c2:
        data = read_bytes(file.path)
        st.download_button(
            "Download",
            data=data,
            file_name=file.path.name,
            mime=file.mime,
            use_container_width=True,
            key=f"{key_prefix}_{file.path.name}",
        )


def render_file_section(title: str, files: List[RepoFile], empty_message: str) -> None:
    st.markdown(f"### {title}")
    if not files:
        st.info(empty_message)
        return

    for i, file in enumerate(files):
        with st.container(border=True):
            file_action_block(file, f"{title}_{i}")


def repository_metrics(repo: List[MainSOP]) -> dict:
    return {
        "Main SOPs": len(repo),
        "Root Files (1.1)": sum(len(x.root_files) for x in repo),
        "Toolkit Files (1.2)": sum(len(x.toolkit_files) for x in repo),
        "Template Files (1.3)": sum(len(x.template_files) for x in repo),
    }


def render_dashboard(repo: List[MainSOP]) -> None:
    metrics = repository_metrics(repo)

    st.markdown(
        f"""
        <div class="shoc-band">
            <h2 style="margin:0;">{APP_TITLE}</h2>
            <div style="opacity:0.95; margin-top:0.2rem;">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Main SOPs", metrics["Main SOPs"])
    c2.metric("1.1 Files", metrics["Root Files (1.1)"])
    c3.metric("1.2 Toolkit Files", metrics["Toolkit Files (1.2)"])
    c4.metric("1.3 Template Files", metrics["Template Files (1.3)"])

    st.markdown("### Main SOP Dashboard")
    rows = [repo[i:i+3] for i in range(0, len(repo), 3)]
    for row in rows:
        cols = st.columns(3)
        for i, sop in enumerate(row):
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="shoc-card">
                        <div style="font-size:2rem;">{sop.icon}</div>
                        <h4>{sop.display_name}</h4>
                        <div class="shoc-muted">Folder: {sop.folder_path.name}</div>
                        <div class="shoc-chip">1.1 Files: {len(sop.root_files)}</div>
                        <div class="shoc-chip">1.2 Toolkit: {len(sop.toolkit_files)}</div>
                        <div class="shoc-chip">1.3 Templates: {len(sop.template_files)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open SOP Repository", key=f"open_{sop.number}", use_container_width=True):
                    goto_main(sop.number)
                    st.rerun()


def render_main_sop(repo: List[MainSOP], main_number: int) -> None:
    sop = next((x for x in repo if x.number == main_number), None)
    if sop is None:
        st.error("Main SOP not found.")
        return

    st.button("← Back to Dashboard", on_click=goto_dashboard)
    st.markdown(
        f"""
        <div class="shoc-band">
            <h2 style="margin:0;">{sop.display_name}</h2>
            <div style="margin-top:0.35rem;">Owner: {sop.owner}</div>
            <div style="margin-top:0.35rem;">Folder: {sop.folder_path}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_file_section(
        "Folder Root Level 1.1 — Main SOPs, Annexes and Indices",
        sop.root_files,
        "No root-level files found for this SOP.",
    )

    render_file_section(
        "Folder Root Level 1.2 — Toolkit",
        sop.toolkit_files,
        "No toolkit files found. This is expected for SOPs that currently have no toolkit.",
    )

    render_file_section(
        "Folder Root Level 1.3 — Templates",
        sop.template_files,
        "No template files found under the toolkit/templates structure.",
    )


def render_repository(repo: List[MainSOP]) -> None:
    rows = []
    for sop in repo:
        for f in sop.root_files:
            rows.append({"SOP": sop.display_name, "Level": f.level_code, "Category": f.category, "File": f.path.name})
        for f in sop.toolkit_files:
            rows.append({"SOP": sop.display_name, "Level": f.level_code, "Category": f.category, "File": f.path.name})
        for f in sop.template_files:
            rows.append({"SOP": sop.display_name, "Level": f.level_code, "Category": f.category, "File": f.path.name})

    st.subheader("Repository Index")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_search(repo: List[MainSOP]) -> None:
    st.subheader("Search")
    query = st.text_input("Search by SOP title or file name")
    if not query:
        return

    q = query.lower()
    rows = []
    for sop in repo:
        if q in sop.title.lower():
            rows.append({"SOP": sop.display_name, "Level": "-", "File": "-", "Match": "SOP Title"})
        for group in [sop.root_files, sop.toolkit_files, sop.template_files]:
            for f in group:
                if q in f.path.name.lower() or q in f.title.lower():
                    rows.append({"SOP": sop.display_name, "Level": f.level_code, "File": f.path.name, "Match": f.category})

    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.warning("No matches found.")


def render_admin(base_dir: Path) -> None:
    st.subheader("Admin")
    st.write(f"Repository root: `{base_dir}`")
    st.markdown("#### Recommended deployed folder structure")
    st.code(
        """
repo-root/
├── shoc_sop_portal_app.py
├── requirements.txt
├── .streamlit/
│   └── config.toml
└── SOPs/
    ├── 01_Governance_Finance_Audit/
    │   ├── SHOC_SOP Finance and Audit_v5_Aligned.pdf                # 1.1
    │   ├── SHOC_SOP Finance and Audit_v5_Aligned.docx               # 1.1
    │   ├── SHOC_SOP Finance and Audit Annexes Ver_5.docx            # 1.1
    │   └── Toolkit/
    │       └── Templates/
    │           ├── SHOC_Finance_Audit_Annexes_Master_Index.docx     # 1.3
    │           ├── SOP_1-A_Financial_Control_Matrix.docx            # 1.3
    │           └── ...
    ├── 02_Multi_Hazard_Early_Warning_System/
    │   ├── SOP_Early_Warning_Monitoring_MAIN.pdf                    # 1.1
    │   ├── SOP_Early_Warning_Monitoring_MAIN.docx                   # 1.1
    │   ├── SOP_Annexes_and_Ancillaries.docx                         # 1.1
    │   └── Toolkit/
    │       ├── SOP_Annexes_and_Ancillaries.docx                     # 1.2
    │       ├── SOP_Early_Warning_Monitoring_MAIN.docx               # 1.2
    │       └── Templates/
    │           ├── Annex_2.1-A_Data_Source_Registry.docx            # 1.3
    │           └── ...
    └── 03_... through 09_...
        """.strip(),
        language="text"
    )


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
    apply_custom_css()
    init_state()

    base_dir = get_base_dir()
    repo = build_repository(base_dir)

    with st.sidebar:
        st.title(APP_TITLE)
        st.caption(APP_SUBTITLE)
        st.write(f"Repository Root: `{base_dir}`")

        if st.button("Dashboard", use_container_width=True):
            goto_dashboard()
            st.rerun()
        if st.button("Repository", use_container_width=True):
            st.session_state.view = "repository"
            st.rerun()
        if st.button("Search", use_container_width=True):
            st.session_state.view = "search"
            st.rerun()
        if st.button("Admin", use_container_width=True):
            st.session_state.view = "admin"
            st.rerun()

    if st.session_state.view == "dashboard":
        render_dashboard(repo)
    elif st.session_state.view == "main_sop":
        render_main_sop(repo, st.session_state.selected_main)
    elif st.session_state.view == "repository":
        render_repository(repo)
    elif st.session_state.view == "search":
        render_search(repo)
    elif st.session_state.view == "admin":
        render_admin(base_dir)
    else:
        render_dashboard(repo)


if __name__ == "__main__":
    main()
