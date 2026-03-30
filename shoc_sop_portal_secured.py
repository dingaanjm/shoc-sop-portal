from __future__ import annotations

import base64
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
BASE_DIR = Path(__file__).resolve().parent / "SOPs" / "1.1"
MAIN_DIR = BASE_DIR
TOOLKIT_DIR = BASE_DIR / "Toolkit"
TEMPLATES_DIR = TOOLKIT_DIR / "Templates"

APP_TITLE = "SHOC SOP Portal"
APP_SUBTITLE = "Main SOPs, Toolkits and Templates"
APP_TAGLINE = "Secure access, in-app preview and download for SOP files"

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".xlsx", ".doc", ".xls"}

DOCX_PREVIEW_PARAGRAPHS = 60
PDF_PREVIEW_HEIGHT = 700

# =========================================================
# FIXED SHOC SOP ORDER
# =========================================================
FIXED_ORDER = [
    "SOP Governance Finance and Audit",
    "SOP Multi_Hazard Early Warning and Monitoring",
    "SOP Emergency Telecommunications",
    "SOP Emergency Response Teams",
    "SOPs Human Resources",
    "SOP Information Communication and Technology",
    "SOP Access Security and Assett Management",
    "SOP Supply Management and Logistics",
    "SOP Business Continuity Management",
    "SOP Training Manual",
]


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
    folder: Path
    main_word: Optional[FileItem] = None
    main_pdf: Optional[FileItem] = None
    annexes: List[FileItem] = field(default_factory=list)
    toolkit: List[FileItem] = field(default_factory=list)
    templates: List[FileItem] = field(default_factory=list)

    @property
    def icon(self) -> str:
        n = self.name.lower()
        if "finance" in n or "audit" in n:
            return "📘"
        if "warning" in n or "monitor" in n:
            return "⚠️"
        if "telecom" in n or "communication" in n:
            return "📡"
        if "response" in n:
            return "🚑"
        if "human" in n or "staff" in n:
            return "👥"
        if "ict" in n or "cyber" in n:
            return "🛡️"
        if "security" in n or "access" in n:
            return "🔐"
        if "supply" in n or "logistics" in n:
            return "📦"
        if "continuity" in n:
            return "🔄"
        return "📁"


# =========================================================
# HELPERS
# =========================================================
def normalize(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).strip().lower()


def list_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS],
        key=lambda x: x.name.lower(),
    )


def classify_main_files(sop_name: str, files: List[Path]):
    sop_norm = normalize(sop_name)
    word_files = [f for f in files if f.suffix.lower() in {".docx", ".doc"}]
    pdf_files = [f for f in files if f.suffix.lower() == ".pdf"]
    others = [f for f in files if f not in word_files + pdf_files]

    def rank(path: Path):
        stem = normalize(path.stem)
        exact = 0 if stem == sop_norm else 1
        annex = 1 if "annex" in stem else 0
        return (exact, annex, path.name.lower())

    main_word = None
    main_pdf = None
    annexes = []

    if word_files:
        chosen = sorted(word_files, key=rank)[0]
        main_word = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main Word")
        for f in word_files:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex"))

    if pdf_files:
        chosen = sorted(pdf_files, key=rank)[0]
        main_pdf = FileItem(chosen.name, chosen, chosen.suffix.lower(), "Main PDF")
        for f in pdf_files:
            if f != chosen:
                annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex"))

    for f in others:
        annexes.append(FileItem(f.name, f, f.suffix.lower(), "Annex"))

    return main_word, main_pdf, sorted(annexes, key=lambda x: x.name.lower())


def build_repository() -> List[SOPEntry]:
    entries = []

    if not MAIN_DIR.exists():
        return entries

    toolkit_map = {}
    if TOOLKIT_DIR.exists():
        for p in TOOLKIT_DIR.iterdir():
            if p.is_dir():
                toolkit_map[normalize(p.name)] = p

    template_map = {}
    if TEMPLATES_DIR.exists():
        for p in TEMPLATES_DIR.iterdir():
            if p.is_dir():
                template_map[normalize(p.name)] = p

    # Collect SOP folders (excluding Toolkit)
    folders = [p for p in MAIN_DIR.iterdir() if p.is_dir() and p.name.lower() != "toolkit"]

    # Sort using fixed SHOC order
    folders_sorted = sorted(
        folders,
        key=lambda p: FIXED_ORDER.index(p.name) if p.name in FIXED_ORDER else 999
    )

    for sop_folder in folders_sorted:
        sop_name = sop_folder.name
        files = list_files(sop_folder)
        main_word, main_pdf, annexes = classify_main_files(sop_name, files)

        toolkit_folder = toolkit_map.get(normalize(sop_name))
        template_folder = template_map.get(normalize(sop_name))

        toolkit_files = []
        if toolkit_folder:
            toolkit_files = [
                FileItem(f.name, f, f.suffix.lower(), "Toolkit")
                for f in list_files(toolkit_folder)
            ]

        template_files = []
        if template_folder:
            template_files = [
                FileItem(f.name, f, f.suffix.lower(), "Template")
                for f in list_files(template_folder)
            ]

        entries.append(
            SOPEntry(
                name=sop_name,
                folder=sop_folder,
                main_word=main_word,
                main_pdf=main_pdf,
                annexes=annexes,
                toolkit=toolkit_files,
                templates=template_files,
            )
        )

    return entries


# =========================================================
# PREVIEW RENDERING
# =========================================================
def read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def preview_pdf(path: Path):
    data = read_bytes(path)
    encoded = base64.b64encode(data).decode("utf-8")
    html = f"""
        <iframe
            src="data:application/pdf;base64,{encoded}"
            width="100%"
            height="{PDF_PREVIEW_HEIGHT}"
            style="border:1px solid #ccc; border-radius:10px;"
        ></iframe>
    """
    st.markdown(html, unsafe_allow_html=True)


def preview_docx(path: Path):
    if Document is None:
        st.info("Word preview unavailable (python-docx missing).")
        return

    try:
        doc = Document(path)
        text = []
        for p in doc.paragraphs:
            if p.text.strip():
                text.append(p.text.strip())
            if len(text) >= DOCX_PREVIEW_PARAGRAPHS:
                break
        if not text:
            st.info("No readable text found.")
            return
        st.text_area("Preview", "\n\n".join(text), height=450, disabled=True)
    except Exception as e:
        st.error(f"Could not preview Word file: {e}")


def render_file(file: FileItem, key: str):
    st.markdown(f"**{file.name}**")
    st.download_button("Download", read_bytes(file.path), file.name, key=f"{key}_dl")

    with st.expander("Preview"):
        if file.ext == ".pdf":
            preview_pdf(file.path)
        elif file.ext in {".docx", ".doc"}:
            preview_docx(file.path)
        else:
            st.info("Preview not supported for this file type.")


# =========================================================
# SECURITY
# =========================================================
def password_gate():
    st.markdown("### Secure Access")

    pwd = st.text_input("Enter main access password", type="password", key="main_pwd")

    if not pwd:
        st.stop()

    if "APP_PASSWORDS" not in st.secrets:
        st.error("APP_PASSWORDS missing in Streamlit secrets.")
        st.stop()

    allowed = st.secrets["APP_PASSWORDS"]
    if isinstance(allowed, str):
        allowed = [allowed]

    if pwd not in allowed:
        st.error("Incorrect password.")
        st.stop()


def role_gate(secret_key: str, label: str):
    pwd = st.text_input(f"Enter {label} password", type="password", key=f"{secret_key}_pwd")
    if pwd != st.secrets.get(secret_key):
        st.error("Access denied.")
        st.stop()


# =========================================================
# UI
# =========================================================
def header():
    st.markdown(
        f"""
        <div style='background:#1f4e8c; padding:1rem; border-radius:12px; color:white;'>
            <h2 style='margin:0;'>{APP_TITLE}</h2>
            <div>{APP_SUBTITLE}</div>
            <div style='opacity:0.9;'>{APP_TAGLINE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dashboard(repo: List[SOPEntry]):
    header()
    st.markdown("### SOP Catalogue")

    search = st.text_input("Search SOPs")
    if search:
        repo = [x for x in repo if search.lower() in x.name.lower()]

    rows = [repo[i:i + 3] for i in range(0, len(repo), 3)]
    for row in rows:
        cols = st.columns(3)
        for idx, sop in enumerate(row):
            with cols[idx]:
                st.markdown(
                    f"""
                    <div style='background:white; padding:1rem; border-radius:12px; border:1px solid #ddd;'>
                        <div style='font-size:2rem;'>{sop.icon}</div>
                        <strong>{sop.name}</strong>
                        <div style='font-size:0.9rem; opacity:0.7;'>{sop.folder}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open", key=f"open_{sop.name}"):
                    st.session_state.view = sop.name
                    st.rerun()


def sop_detail(entry: SOPEntry):
    if st.button("← Back"):
        st.session_state.view = "dashboard"
        st.rerun()

    st.markdown(f"## {entry.icon} {entry.name}")

    tab1, tab2, tab3 = st.tabs(["Main SOP", "Toolkit", "Templates"])

    with tab1:
        st.subheader("Main SOP Documents")
        if entry.main_word:
            render_file(entry.main_word, f"{entry.name}_word")
        if entry.main_pdf:
            render_file(entry.main_pdf, f"{entry.name}_pdf")

        st.subheader("Annexes")
        if entry.annexes:
            for i, f in enumerate(entry.annexes):
                render_file(f, f"{entry.name}_annex_{i}")
        else:
            st.info("No annex files.")

    with tab2:
        role_gate("TOOLKIT_PASSWORD", "Toolkit")
        st.subheader("Toolkit Files")
        if entry.toolkit:
            for i, f in enumerate(entry.toolkit):
                render_file(f, f"{entry.name}_toolkit_{i}")
        else:
            st.info("No toolkit files.")

    with tab3:
        role_gate("TEMPLATE_PASSWORD", "Templates")
        st.subheader("Template Files")
        if entry.templates:
            for i, f in enumerate(entry.templates):
                render_file(f, f"{entry.name}_template_{i}")
        else:
            st.info("No template files.")


# =========================================================
# MAIN
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    password_gate()

    repo = build_repository()

    if "view" not in st.session_state:
        st.session_state.view = "dashboard"

    if st.session_state.view == "dashboard":
        dashboard(repo)
    else:
        entry = next((x for x in repo if x.name == st.session_state.view), None)
        if entry:
            sop_detail(entry)
        else:
            st.session_state.view = "dashboard"
            st.rerun()


if __name__ == "__main__":
    main()
