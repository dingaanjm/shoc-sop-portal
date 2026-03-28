from __future__ import annotations

import base64
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import streamlit as st

try:
    from docx import Document
except Exception:
    Document = None


# =========================================================
# CONFIGURATION
# =========================================================
# Actual structure confirmed by user:
# SOPs/
#   1.1/
#       <Main SOP folders...>
#       Toolkit/
#           <Toolkit SOP folders...>
#           Templates/
#               <Template SOP folders...>
BASE_DIR = Path(__file__).resolve().parent / "SOPs" / "1.1"
MAIN_DIR = BASE_DIR
TOOLKIT_DIR = BASE_DIR / "Toolkit"
TEMPLATES_DIR = TOOLKIT_DIR / "Templates"

APP_TITLE = "SHOC SOP Portal"
APP_SUBTITLE = "Main SOPs, Toolkits and Templates"
ALLOWED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".doc", ".xls"}

DOCX_PREVIEW_PARAGRAPHS = 60
PDF_PREVIEW_HEIGHT = 700

# Optional branding assets:
# Place image files next to this script if you want real logos
LEFT_LOGO_PATH = Path(__file__).resolve().parent / "sadc_logo.png"
RIGHT_LOGO_PATH = Path(__file__).resolve().parent / "shoc_logo.png"


# =========================================================
# DATA MODELS
# =========================================================
@dataclass
class FileItem:
    name: str
    path: Path
    ext: str
    category: str


@dataclass
class SOPEntry:
    name: str
    main_folder: Path
    main_word: Optional[FileItem] = None
    main_pdf: Optional[FileItem] = None
    annex_files: List[FileItem] = field(default_factory=list)
    toolkit_files: List[FileItem] = field(default_factory=list)
    template_files: List[FileItem] = field(default_factory=list)


# =========================================================
# HELPERS
# =========================================================
def normalize_name(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).strip().lower()


def get_all_files(folder: Optional[Path]) -> List[Path]:
    if folder is None or not folder.exists() or not folder.is_dir():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS],
        key=lambda p: p.name.lower(),
    )


def image_to_base64(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")
    except Exception:
        return None


def classify_main_files(sop_name: str, files: List[Path]) -> tuple[Optional[FileItem], Optional[FileItem], List[FileItem]]:
    """
    Main SOP folder rules:
    - one main Word document
    - one main PDF document
    - anything else is treated as annex / supporting
    Preference is given to filenames closest to the SOP folder name.
    """
    sop_norm = normalize_name(sop_name)
    word_candidates: List[Path] = []
    pdf_candidates: List[Path] = []
    other_files: List[Path] = []

    for f in files:
        if f.suffix.lower() == ".pdf":
            pdf_candidates.append(f)
        elif f.suffix.lower() in {".docx", ".doc"}:
            word_candidates.append(f)
        else:
            other_files.append(f)

    def rank_word(path: Path):
        stem_norm = normalize_name(path.stem)
        exact = 0 if stem_norm == sop_norm else 1
        contains_annex = 1 if "annex" in stem_norm else 0
        return (exact, contains_annex, path.name.lower())

    def rank_pdf(path: Path):
        stem_norm = normalize_name(path.stem)
        exact = 0 if stem_norm == sop_norm else 1
        contains_annex = 1 if "annex" in stem_norm else 0
        return (exact, contains_annex, path.name.lower())

    main_word = None
    main_pdf = None
    annexes: List[FileItem] = []

    if word_candidates:
        chosen = sorted(word_candidates, key=rank_word)[0]
        main_word = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main SOP Word")
        for f in word_candidates:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    if pdf_candidates:
        chosen = sorted(pdf_candidates, key=rank_pdf)[0]
        main_pdf = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main SOP PDF")
        for f in pdf_candidates:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    for f in other_files:
        annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    annexes = sorted(annexes, key=lambda x: x.name.lower())
    return main_word, main_pdf, annexes


def folder_fileitems(folder: Optional[Path], category: str) -> List[FileItem]:
    return [
        FileItem(f.name, f, f.suffix.lower(), category)
        for f in get_all_files(folder)
    ]


def build_repository() -> List[SOPEntry]:
    """
    Structure:
      SOPs/1.1/<SOP Name>
      SOPs/1.1/Toolkit/<SOP Name>
      SOPs/1.1/Toolkit/Templates/<SOP Name>
    """
    entries: List[SOPEntry] = []

    if not MAIN_DIR.exists():
        return entries

    toolkit_map = {}
    if TOOLKIT_DIR.exists():
        for p in TOOLKIT_DIR.iterdir():
            if p.is_dir():
                toolkit_map[normalize_name(p.name)] = p

    templates_map = {}
    if TEMPLATES_DIR.exists():
        for p in TEMPLATES_DIR.iterdir():
            if p.is_dir():
                templates_map[normalize_name(p.name)] = p

    for sop_folder in sorted([p for p in MAIN_DIR.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        # Skip shared Toolkit and Templates infrastructure folders
        if normalize_name(sop_folder.name) in {"toolkit", "templates"}:
            continue

        sop_name = sop_folder.name
        sop_key = normalize_name(sop_name)

        main_files = get_all_files(sop_folder)
        main_word, main_pdf, annex_files = classify_main_files(sop_name, main_files)

        toolkit_folder = toolkit_map.get(sop_key)
        templates_folder = templates_map.get(sop_key)

        toolkit_files = folder_fileitems(toolkit_folder, "Toolkit")
        template_files = folder_fileitems(templates_folder, "Template")

        entries.append(
            SOPEntry(
                name=sop_name,
                main_folder=sop_folder,
                main_word=main_word,
                main_pdf=main_pdf,
                annex_files=annex_files,
                toolkit_files=toolkit_files,
                template_files=template_files,
            )
        )

    return entries


def read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def open_file_windows(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        st.error(f"Could not open file: {exc}")


def render_pdf_preview(path: Path) -> None:
    pdf_bytes = read_bytes(path)
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f"""
        <iframe
            src="data:application/pdf;base64,{encoded}"
            width="100%"
            height="{PDF_PREVIEW_HEIGHT}"
            type="application/pdf"
            style="border:1px solid #d0d7de; border-radius:10px; background:white;"
        ></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)


def extract_docx_text(path: Path, max_paragraphs: int = DOCX_PREVIEW_PARAGRAPHS) -> str:
    if Document is None:
        return "python-docx is not installed, so Word preview is unavailable."

    try:
        doc = Document(path)
        parts: List[str] = []
        count = 0
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)
                count += 1
            if count >= max_paragraphs:
                break

        if not parts:
            return "No readable text found in this Word document preview."

        preview = "\n\n".join(parts)
        if count >= max_paragraphs:
            preview += "\n\n[Preview truncated]"
        return preview
    except Exception as exc:
        return f"Could not preview this Word file: {exc}"


def render_file_actions(file_item: Optional[FileItem], key_prefix: str) -> None:
    if not file_item:
        st.info("File not available.")
        return

    c1, c2, c3 = st.columns([1.2, 1.2, 1.8])

    with c1:
        st.download_button(
            "Download",
            data=read_bytes(file_item.path),
            file_name=file_item.name,
            mime="application/octet-stream",
            use_container_width=True,
            key=f"{key_prefix}_download",
        )

    with c2:
        if st.button("Open Read Only", key=f"{key_prefix}_open", use_container_width=True):
            open_file_windows(file_item.path)

    with c3:
        st.caption(file_item.name)


def render_preview_block(file_item: Optional[FileItem], key_prefix: str, default_expand: bool = False) -> None:
    if not file_item:
        st.info("No file available for preview.")
        return

    with st.expander(f"Preview: {file_item.name}", expanded=default_expand):
        if file_item.ext == ".pdf":
            render_pdf_preview(file_item.path)
        elif file_item.ext in {".docx", ".doc"}:
            preview_text = extract_docx_text(file_item.path)
            st.text_area(
                "Read-only preview",
                preview_text,
                height=450,
                disabled=True,
                key=f"{key_prefix}_preview_text",
            )
        else:
            st.info("Preview is not supported for this file type inside the portal. Use Open Read Only or Download.")


def render_file_card(file_item: FileItem, key_prefix: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{file_item.name}**")
        st.caption(file_item.category)
        render_file_actions(file_item, key_prefix)
        render_preview_block(file_item, key_prefix, default_expand=False)


# =========================================================
# LOOK AND FEEL
# =========================================================
def render_header_band() -> None:
    left_logo = image_to_base64(LEFT_LOGO_PATH)
    right_logo = image_to_base64(RIGHT_LOGO_PATH)

    left_html = ""
    if left_logo:
        left_html = f'<img src="data:image/png;base64,{left_logo}" class="shoc-logo" alt="Left logo" />'
    else:
        left_html = '<div class="shoc-logo-fallback">🌍</div>'

    right_html = ""
    if right_logo:
        right_html = f'<img src="data:image/png;base64,{right_logo}" class="shoc-logo" alt="Right logo" />'
    else:
        right_html = '<div class="shoc-logo-fallback">🛡️</div>'

    st.markdown(
        f"""
        <div class="shoc-hero">
            <div class="shoc-hero-logo">{left_html}</div>
            <div class="shoc-hero-center">
                <div class="shoc-hero-title">{APP_TITLE}</div>
                <div class="shoc-hero-subtitle">{APP_SUBTITLE}</div>
                <div class="shoc-hero-tagline">Structured access to Main SOPs, Toolkit files, Templates, preview and read-only opening.</div>
            </div>
            <div class="shoc-hero-logo">{right_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(46,111,183,0.12), transparent 25%),
                radial-gradient(circle at bottom left, rgba(31,78,140,0.10), transparent 20%),
                linear-gradient(180deg, #f4f8fc 0%, #eef4fb 100%);
        }

        .shoc-hero {
            display: grid;
            grid-template-columns: 110px 1fr 110px;
            align-items: center;
            gap: 1rem;
            background: linear-gradient(120deg, #123a69 0%, #1f5b99 50%, #2e6fb7 100%);
            color: white;
            border-radius: 20px;
            padding: 1.15rem 1.25rem;
            margin-bottom: 1rem;
            border: 1px solid #d8e3f2;
            box-shadow: 0 8px 24px rgba(16, 55, 105, 0.16);
        }

        .shoc-hero-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.25rem;
        }

        .shoc-hero-subtitle {
            font-size: 1rem;
            opacity: 0.96;
            margin-bottom: 0.18rem;
        }

        .shoc-hero-tagline {
            font-size: 0.92rem;
            opacity: 0.90;
        }

        .shoc-hero-logo {
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .shoc-logo {
            max-width: 82px;
            max-height: 82px;
            border-radius: 12px;
            background: rgba(255,255,255,0.10);
            padding: 0.25rem;
        }

        .shoc-logo-fallback {
            width: 82px;
            height: 82px;
            border-radius: 14px;
            background: rgba(255,255,255,0.12);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            border: 1px solid rgba(255,255,255,0.18);
        }

        .shoc-card {
            border: 1px solid #dbe5f0;
            border-radius: 18px;
            padding: 1rem 1rem 0.9rem 1rem;
            background: rgba(255, 255, 255, 0.96);
            box-shadow: 0 6px 16px rgba(15, 45, 90, 0.08);
            min-height: 250px;
            backdrop-filter: blur(2px);
        }

        .shoc-card h4 {
            margin: 0 0 0.45rem 0;
            color: #163d73;
            font-size: 1.12rem;
            line-height: 1.25;
            font-weight: 700;
        }

        .shoc-muted {
            color: #5b6572;
            font-size: 0.92rem;
            line-height: 1.45;
            margin-bottom: 0.6rem;
        }

        .shoc-chip {
            display: inline-block;
            padding: 0.20rem 0.48rem;
            border-radius: 999px;
            background: #eef4fb;
            color: #1c5a94;
            font-size: 0.78rem;
            margin-right: 0.35rem;
            margin-bottom: 0.30rem;
            border: 1px solid #d8e6f4;
            font-weight: 600;
        }

        .shoc-panel {
            background: rgba(255,255,255,0.96);
            border-radius: 16px;
            padding: 1rem 1rem 0.8rem 1rem;
            border: 1px solid #dbe5f0;
            box-shadow: 0 6px 16px rgba(15, 45, 90, 0.06);
            margin-bottom: 0.85rem;
        }

        .shoc-mini-title {
            color: #163d73;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.96);
            border: 1px solid #dbe5f0;
            padding: 0.65rem 0.8rem;
            border-radius: 16px;
            box-shadow: 0 6px 16px rgba(15, 45, 90, 0.05);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: white;
            border-radius: 12px 12px 0 0;
            border: 1px solid #dbe5f0;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 12px !important;
            border: 1px solid #c8d7e8 !important;
            font-weight: 600 !important;
        }

        .stTextInput > div > div {
            border-radius: 12px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# STATE
# =========================================================
def init_state() -> None:
    st.session_state.setdefault("view", "dashboard")
    st.session_state.setdefault("selected_sop", None)


def goto_dashboard() -> None:
    st.session_state.view = "dashboard"
    st.session_state.selected_sop = None


def goto_sop(sop_name: str) -> None:
    st.session_state.view = "sop_detail"
    st.session_state.selected_sop = sop_name


# =========================================================
# VIEWS
# =========================================================
def render_dashboard(repo: List[SOPEntry]) -> None:
    total_toolkits = sum(1 for x in repo if x.toolkit_files)
    total_templates = sum(1 for x in repo if x.template_files)
    total_annex_files = sum(len(x.annex_files) for x in repo)

    render_header_band()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Main SOPs", len(repo))
    m2.metric("With Toolkit Files", total_toolkits)
    m3.metric("With Template Files", total_templates)
    m4.metric("Annex / Support Files", total_annex_files)

    st.markdown('<div class="shoc-panel">', unsafe_allow_html=True)
    st.markdown('<div class="shoc-mini-title">Search</div>', unsafe_allow_html=True)
    search = st.text_input("Search SOP name", placeholder="Type part of an SOP name...", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    if search:
        repo = [x for x in repo if search.lower() in x.name.lower()]

    rows = [repo[i:i + 3] for i in range(0, len(repo), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx, sop in enumerate(row):
            with cols[idx]:
                st.markdown(
                    f"""
                    <div class="shoc-card">
                        <h4>{sop.name}</h4>
                        <div class="shoc-muted">Main folder: 1.1/{sop.name}</div>
                        <div class="shoc-chip">Word: {"Yes" if sop.main_word else "No"}</div>
                        <div class="shoc-chip">PDF: {"Yes" if sop.main_pdf else "No"}</div>
                        <div class="shoc-chip">Annexes: {len(sop.annex_files)}</div>
                        <div class="shoc-chip">Toolkit files: {len(sop.toolkit_files)}</div>
                        <div class="shoc-chip">Template files: {len(sop.template_files)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open SOP Workspace", key=f"open_{sop.name}", use_container_width=True):
                    goto_sop(sop.name)
                    st.rerun()


def render_sop_detail(entry: SOPEntry) -> None:
    c1, c2 = st.columns([1, 6])
    with c1:
        if st.button("← Back", use_container_width=True):
            goto_dashboard()
            st.rerun()
    with c2:
        st.markdown(
            f"""
            <div class="shoc-panel">
                <div class="shoc-mini-title">{entry.name}</div>
                <div class="shoc-muted">Main SOP folder: {entry.main_folder}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    tab1, tab2, tab3 = st.tabs(["Main SOP", "Toolkit", "Templates"])

    with tab1:
        st.subheader("Main SOP Documents")

        w1, w2 = st.columns(2)
        with w1:
            st.markdown("#### Main Word Document")
            if entry.main_word:
                render_file_actions(entry.main_word, f"{entry.name}_main_word")
                render_preview_block(entry.main_word, f"{entry.name}_main_word", default_expand=True)
            else:
                st.info("Main Word document not found.")

        with w2:
            st.markdown("#### Main PDF Document")
            if entry.main_pdf:
                render_file_actions(entry.main_pdf, f"{entry.name}_main_pdf")
                render_preview_block(entry.main_pdf, f"{entry.name}_main_pdf", default_expand=True)
            else:
                st.info("Main PDF document not found.")

        st.markdown("#### Annex / Supporting Documents")
        if entry.annex_files:
            for i, file_item in enumerate(entry.annex_files):
                render_file_card(file_item, f"{entry.name}_annex_{i}")
        else:
            st.info("No annex or supporting files found in this main SOP folder.")

    with tab2:
        st.subheader("Toolkit Files")
        if entry.toolkit_files:
            for i, file_item in enumerate(entry.toolkit_files):
                render_file_card(file_item, f"{entry.name}_toolkit_{i}")
        else:
            st.info("No toolkit files available for this SOP.")

    with tab3:
        st.subheader("Template Files")
        if entry.template_files:
            for i, file_item in enumerate(entry.template_files):
                render_file_card(file_item, f"{entry.name}_template_{i}")
        else:
            st.info("No template files available for this SOP.")


def render_repository_index(repo: List[SOPEntry]) -> None:
    rows = []
    for entry in repo:
        rows.append({
            "SOP": entry.name,
            "Main Word": entry.main_word.name if entry.main_word else "",
            "Main PDF": entry.main_pdf.name if entry.main_pdf else "",
            "Annex Count": len(entry.annex_files),
            "Toolkit Count": len(entry.toolkit_files),
            "Template Count": len(entry.template_files),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# =========================================================
# APP
# =========================================================
def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
    apply_custom_css()
    init_state()

    repo = build_repository()

    with st.sidebar:
        st.title(APP_TITLE)
        st.caption(APP_SUBTITLE)
        st.write(f"Base folder: `{BASE_DIR}`")

        if st.button("Dashboard", use_container_width=True):
            goto_dashboard()
            st.rerun()

        show_index = st.button("Repository Index", use_container_width=True)

        st.divider()
        st.markdown("**Expected structure**")
        st.code(
            "SOPs/\n"
            "└── 1.1/\n"
            "    ├── <Main SOP folders>\n"
            "    └── Toolkit/\n"
            "        ├── <Toolkit SOP folders>\n"
            "        └── Templates/\n"
            "            └── <Template SOP folders>",
            language="text",
        )

        st.divider()
        st.caption("Tip: Put sadc_logo.png and shoc_logo.png next to this script for branded header logos.")

    if show_index:
        render_header_band()
        st.subheader("Repository Index")
        render_repository_index(repo)
        return

    if not MAIN_DIR.exists():
        render_header_band()
        st.error(f"Main SOP folder not found: {MAIN_DIR}")
        st.info("Create the folder structure first, then rerun the app.")
        return

    if st.session_state.view == "dashboard":
        render_dashboard(repo)
    elif st.session_state.view == "sop_detail":
        selected = st.session_state.selected_sop
        entry = next((x for x in repo if x.name == selected), None)
        if entry is None:
            render_header_band()
            st.error("Selected SOP could not be found.")
            goto_dashboard()
        else:
            render_sop_detail(entry)
    else:
        render_dashboard(repo)


if __name__ == "__main__":
    main()
