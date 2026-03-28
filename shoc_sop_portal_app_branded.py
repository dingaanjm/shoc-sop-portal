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
# Confirmed structure:
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
APP_TAGLINE = "Read-only opening, in-app preview and download for SOP files"
ALLOWED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".doc", ".xls"}

DOCX_PREVIEW_PARAGRAPHS = 60
PDF_PREVIEW_HEIGHT = 700


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

    @property
    def icon(self) -> str:
        name = self.name.lower()
        if "finance" in name or "audit" in name:
            return "📘"
        if "early warning" in name or "monitor" in name:
            return "⚠️"
        if "telecom" in name or "communication" in name:
            return "📡"
        if "response" in name or "emergency response" in name:
            return "🚑"
        if "human resource" in name or "staff" in name:
            return "👥"
        if "ict" in name or "cyber" in name or "data" in name:
            return "🛡️"
        if "security" in name or "access" in name:
            return "🔐"
        if "supply" in name or "logistics" in name:
            return "📦"
        if "continuity" in name:
            return "✅"
        return "📁"


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


def _svg_badge(label_top: str, label_bottom: str, color1: str, color2: str) -> str:
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="{color1}"/>
          <stop offset="100%" stop-color="{color2}"/>
        </linearGradient>
      </defs>
      <circle cx="60" cy="60" r="54" fill="url(#g)" stroke="rgba(255,255,255,0.7)" stroke-width="4"/>
      <circle cx="60" cy="60" r="40" fill="rgba(255,255,255,0.16)" stroke="rgba(255,255,255,0.35)" stroke-width="2"/>
      <text x="60" y="52" text-anchor="middle" font-size="28" font-weight="700" fill="white" font-family="Arial">{
          label_top
      }</text>
      <text x="60" y="77" text-anchor="middle" font-size="18" font-weight="700" fill="white" font-family="Arial">{
          label_bottom
      }</text>
    </svg>
    """
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("utf-8")


def get_brand_logo(kind: str) -> str:
    if kind == "sadc":
        return _svg_badge("SADC", "PORTAL", "#1f4e8c", "#2e6fb7")
    return _svg_badge("SHOC", "DRM", "#0f6a7f", "#27a2b8")


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

    def rank_path(path: Path):
        stem_norm = normalize_name(path.stem)
        exact = 0 if stem_norm == sop_norm else 1
        contains_annex = 1 if "annex" in stem_norm else 0
        return (exact, contains_annex, path.name.lower())

    main_word = None
    main_pdf = None
    annexes: List[FileItem] = []

    if word_candidates:
        chosen = sorted(word_candidates, key=rank_path)[0]
        main_word = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main SOP Word")
        for f in word_candidates:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    if pdf_candidates:
        chosen = sorted(pdf_candidates, key=rank_path)[0]
        main_pdf = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main SOP PDF")
        for f in pdf_candidates:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    for f in other_files:
        annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex / Supporting"))

    annexes = sorted(annexes, key=lambda x: x.name.lower())
    return main_word, main_pdf, annexes


def folder_fileitems(folder: Optional[Path], category: str) -> List[FileItem]:
    return [FileItem(f.name, f, f.suffix.lower(), category) for f in get_all_files(folder)]


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
        if normalize_name(sop_folder.name) in {"toolkit", "templates"}:
            continue

        sop_name = sop_folder.name
        sop_key = normalize_name(sop_name)

        main_files = get_all_files(sop_folder)
        main_word, main_pdf, annex_files = classify_main_files(sop_name, main_files)

        toolkit_folder = toolkit_map.get(sop_key)
        templates_folder = templates_map.get(sop_key)

        entries.append(
            SOPEntry(
                name=sop_name,
                main_folder=sop_folder,
                main_word=main_word,
                main_pdf=main_pdf,
                annex_files=annex_files,
                toolkit_files=folder_fileitems(toolkit_folder, "Toolkit"),
                template_files=folder_fileitems(templates_folder, "Template"),
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
# STYLING
# =========================================================
def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1rem; padding-bottom: 2rem;}

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(46,111,183,0.12), transparent 25%),
                radial-gradient(circle at bottom left, rgba(31,78,140,0.10), transparent 20%),
                linear-gradient(180deg, #f4f8fc 0%, #eef4fb 100%);
        }

        .shoc-band {
            background: linear-gradient(90deg, #1f4e8c 0%, #2e6fb7 55%, #4b87c8 100%);
            color: white;
            border-radius: 18px;
            padding: 1rem 1.2rem;
            margin-bottom: 1rem;
            border: 1px solid #d8e3f2;
            box-shadow: 0 8px 24px rgba(15, 45, 90, 0.12);
        }

        .shoc-hero {
            display: grid;
            grid-template-columns: 110px 1fr 110px;
            align-items: center;
            gap: 1rem;
        }

        .shoc-hero-logo {
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .shoc-hero-logo img {
            max-width: 82px;
            max-height: 82px;
            border-radius: 12px;
            background: rgba(255,255,255,0.08);
            padding: 0.18rem;
        }

        .shoc-title {
            margin: 0;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.05;
        }

        .shoc-subtitle {
            opacity: 0.96;
            margin-top: 0.2rem;
            font-size: 1rem;
        }

        .shoc-tagline {
            opacity: 0.90;
            margin-top: 0.3rem;
            font-size: 0.92rem;
        }

        .shoc-card {
            border: 1px solid #dfe6ef;
            border-radius: 16px;
            padding: 0.95rem 1rem 0.85rem 1rem;
            background: rgba(255,255,255,0.97);
            box-shadow: 0 6px 18px rgba(15, 45, 90, 0.08);
            min-height: 245px;
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


def render_header_band() -> None:
    left_logo = get_brand_logo("sadc")
    right_logo = get_brand_logo("shoc")
    st.markdown(
        f"""
        <div class="shoc-band">
            <div class="shoc-hero">
                <div class="shoc-hero-logo">
                    <img src="{left_logo}" alt="SADC logo"/>
                </div>
                <div>
                    <h2 class="shoc-title">{APP_TITLE}</h2>
                    <div class="shoc-subtitle">{APP_SUBTITLE}</div>
                    <div class="shoc-tagline">{APP_TAGLINE}</div>
                </div>
                <div class="shoc-hero-logo">
                    <img src="{right_logo}" alt="SHOC logo"/>
                </div>
            </div>
        </div>
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
                        <div style="font-size:2rem;">{sop.icon}</div>
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
                <div class="shoc-mini-title">{entry.icon} {entry.name}</div>
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
