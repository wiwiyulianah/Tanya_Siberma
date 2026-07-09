import time
import base64
import html
import re
from pathlib import Path

import streamlit as st

from build_index import build_index
from rag_engine import answer_question, check_ollama_status


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="Tanya Siberma",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "UNMA2026"

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
INDEX_DIR = Path("indexes")

MASCOT_PATH = Path("assets/mascot.png")
LOGO_UNMA_PATH = Path("assets/logo_unma.png")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# =========================================================
# SESSION
# =========================================================
APP_VERSION = "tanya-siberma-clean-input-admin-v70"

if st.session_state.get("_app_version") != APP_VERSION:
    st.session_state.clear()
    st.session_state["_app_version"] = APP_VERSION

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hai! Ada yang ingin kamu ketahui tentang UNMA? Tanya aku apa saja, ya! ✨",
        }
    ]

if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

if "splash_done" not in st.session_state:
    st.session_state.splash_done = False

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# =========================================================
# HELPER
# =========================================================
def image_to_base64(path: Path):
    if not path.exists():
        return ""

    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


MASCOT_B64 = image_to_base64(MASCOT_PATH)
LOGO_UNMA_B64 = image_to_base64(LOGO_UNMA_PATH)


def html_view(code: str):
    st.markdown(code, unsafe_allow_html=True)


def img_tag(image_b64, size=60, class_name="", alt="image"):
    if image_b64:
        return (
            f"<img class='{class_name}' "
            f"src='data:image/png;base64,{image_b64}' "
            f"style='width:{size}px;height:auto;' alt='{alt}'>"
        )

    return f"<span class='{class_name}' style='font-size:{size // 2}px;'>🤖</span>"


def mascot(size=80, class_name=""):
    return img_tag(MASCOT_B64, size=size, class_name=class_name, alt="Siberma")


def logo_unma(size=54, class_name=""):
    if LOGO_UNMA_B64:
        return img_tag(LOGO_UNMA_B64, size=size, class_name=class_name, alt="Logo UNMA")

    return f"<span class='{class_name}' style='font-size:{size // 2}px;'>🎓</span>"


def get_current_page():
    return st.query_params.get("page", "user")


def set_page(page_name):
    st.query_params.clear()
    st.query_params["page"] = page_name
    st.rerun()


def list_documents():
    allowed_ext = [".pdf", ".txt", ".md"]
    docs = []

    for file in DATA_DIR.rglob("*"):
        if file.is_file() and file.suffix.lower() in allowed_ext:
            docs.append(file)

    return sorted(docs, key=lambda item: item.name.lower())


def safe_check_ollama():
    try:
        return check_ollama_status()
    except Exception:
        return False


def safe_text(text):
    return html.escape(str(text)).replace("\n", "<br>")


def split_table_row(line: str):
    line = line.strip()

    if line.startswith("|"):
        line = line[1:]

    if line.endswith("|"):
        line = line[:-1]

    return [cell.strip() for cell in line.split("|")]


def is_table_separator(line: str):
    return bool(
        re.match(
            r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$",
            line.strip(),
        )
    )

def answer_to_html(text):
    text = str(text).strip()
    lines = text.splitlines()
    html_parts = []
    i = 0

    def is_numbered(line):
        return re.match(r"^\s*(\d+)[\.\)]\s+(.+)", line.strip())

    def is_bullet(line):
        return re.match(r"^\s*[-•]\s+(.+)", line.strip())

    def is_heading(line):
        return line.strip().startswith("## ")

    def is_table_start(index):
        return (
            index + 1 < len(lines)
            and lines[index].strip().startswith("|")
            and is_table_separator(lines[index + 1])
        )

    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if is_table_start(i):
            header = split_table_row(line)
            i += 2
            rows = []

            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i]))
                i += 1

            table_html = "<div class='table-scroll'><table class='md-table'><thead><tr>"

            for cell in header:
                table_html += f"<th>{html.escape(cell)}</th>"

            table_html += "</tr></thead><tbody>"

            for row in rows:
                table_html += "<tr>"

                for cell in row:
                    table_html += f"<td>{html.escape(cell)}</td>"

                table_html += "</tr>"

            table_html += "</tbody></table></div>"
            html_parts.append(table_html)
            continue

        if is_heading(line):
            heading = line.strip().replace("## ", "")
            html_parts.append(f"<h4>{html.escape(heading)}</h4>")
            i += 1
            continue

        if is_numbered(line):
            first_match = is_numbered(line)
            start_number = first_match.group(1)

            html_parts.append(f"<ol class='answer-list' start='{start_number}'>")

            while i < len(lines):
                current = lines[i].strip()
                match = is_numbered(current)

                if not match:
                    break

                item_text = match.group(2).strip()
                i += 1

                while (
                    i < len(lines)
                    and lines[i].strip()
                    and not is_numbered(lines[i])
                    and not is_bullet(lines[i])
                    and not lines[i].strip().startswith("|")
                    and not is_heading(lines[i])
                ):
                    item_text += " " + lines[i].strip()
                    i += 1

                html_parts.append(f"<li>{html.escape(item_text)}</li>")

            html_parts.append("</ol>")
            continue

        if is_bullet(line):
            html_parts.append("<ul class='answer-list'>")

            while i < len(lines):
                current = lines[i].strip()
                match = is_bullet(current)

                if not match:
                    break

                item_text = match.group(1).strip()
                i += 1

                while (
                    i < len(lines)
                    and lines[i].strip()
                    and not is_numbered(lines[i])
                    and not is_bullet(lines[i])
                    and not lines[i].strip().startswith("|")
                    and not is_heading(lines[i])
                ):
                    item_text += " " + lines[i].strip()
                    i += 1

                html_parts.append(f"<li>{html.escape(item_text)}</li>")

            html_parts.append("</ul>")
            continue

        paragraph_lines = []

        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip().startswith("|")
            and not is_numbered(lines[i])
            and not is_bullet(lines[i])
            and not is_heading(lines[i])
        ):
            paragraph_lines.append(lines[i].strip())
            i += 1

        paragraph = " ".join(paragraph_lines)

        if paragraph:
            html_parts.append(f"<p>{html.escape(paragraph)}</p>")

    return f"<div class='answer-html'>{''.join(html_parts)}</div>"

def answer_pending_question():
    question = st.session_state.pending_question

    if not question:
        return

    try:
        answer, sources = answer_question(question)

        if not answer or len(str(answer).strip()) == 0:
            answer = (
                "Maaf, informasi tersebut belum tersedia pada dokumen PMB yang saya miliki. "
                "Silakan ajukan pertanyaan lain seputar PMB Universitas Majalengka."
            )
            sources = []

    except FileNotFoundError:
        answer = (
            "Data pengetahuan chatbot belum dibuat. Silakan admin mengunggah atau memperbarui dokumen PMB, "
            "kemudian melakukan proses Bangun Ulang Index."
        )
        sources = []

    except Exception:
        answer = (
            "Maaf, informasi tersebut belum tersedia pada dokumen PMB yang saya miliki. "
            "Silakan ajukan pertanyaan lain seputar PMB Universitas Majalengka."
        )
        sources = []

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )

    st.session_state.last_sources = sources
    st.session_state.pending_question = None
    st.rerun()
    
# =========================================================
# CSS
# =========================================================
def load_css():
    st.markdown(
        """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}
[data-testid="stToolbar"] {display: none;}
[data-testid="stDecoration"] {display: none;}

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"], .main {
    overflow-x: hidden !important;
    width: 100% !important;
    max-width: 100vw !important;
}

html, body, [class*="css"] {
    font-family: "Segoe UI", sans-serif;
}

.stApp {
    background: #eefaff !important;
}

.block-container {
    max-width: 1080px !important;
    padding: 16px !important;
}

/* HILANGKAN BORDER DEFAULT INPUT STREAMLIT */
[data-baseweb="input"] {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

[data-baseweb="input"] > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

input {
    outline: none !important;
    box-shadow: none !important;
}

/* ICON MATA PASSWORD ADMIN */
[data-testid="stTextInput"] svg {
    color: #003366 !important;
    fill: #003366 !important;
    opacity: 1 !important;
    width: 24px !important;
    height: 24px !important;
}

/* ======================================================
   TOP BAR USER
====================================================== */
.topbar {
    background: #0b4d95;
    color: white;
    border-radius: 24px;
    padding: 13px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 10px 24px rgba(0,0,0,.12);
    margin-bottom: 12px;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

.brand-row {
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-logo {
    width: 42px;
    height: 42px;
    border-radius: 0;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: visible;
}

.brand-logo img {
    width: 35px !important;
}

.brand-title {
    font-size: 18px;
    font-weight: 900;
    letter-spacing: .5px;
}

.brand-subtitle {
    font-size: 12px;
    color: rgba(255,255,255,.86);
}

.unma-logo-top {
    width: 54px;
    height: 54px;
    border-radius: 0;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: visible;
}

.brand-logo img,
.unma-logo-top img {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ======================================================
   HERO
====================================================== */
.hero-section {
    background: linear-gradient(135deg, #35aefe 0%, #7bd7ff 100%);
    border-radius: 30px;
    padding: 12px 20px 12px 20px;
    text-align: center;
    color: white;
    margin-bottom: 10px;
    box-shadow: 0 12px 28px rgba(0,0,0,.10);
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}

.mascot-area {
    position: relative;
    display: inline-block;
}

.mascot-float {
    animation: floatBot 2.8s ease-in-out infinite;
}

@keyframes floatBot {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-7px); }
    100% { transform: translateY(0px); }
}

.speech-bubble {
    position: absolute;
    top: 8px;
    left: 125px;
    background: white;
    color: #222;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 999px;
    box-shadow: 0 7px 18px rgba(0,0,0,.12);
    white-space: nowrap;
}

.speech-bubble::before {
    content: "";
    position: absolute;
    left: -5px;
    top: 16px;
    width: 11px;
    height: 11px;
    background: white;
    transform: rotate(45deg);
}

.hero-title {
    font-size: 30px;
    font-weight: 950;
    margin-top: 2px;
    margin-bottom: 5px;
}

.hero-desc {
    font-size: 14px;
    color: rgba(255,255,255,.96);
    max-width: 700px;
    margin: 0 auto 7px auto;
}

.quick-title {
    font-size: 14px;
    font-weight: 850;
    color: white;
}

.quick-menu-wrap {
    margin-bottom: 12px;
    width: 100% !important;
    box-sizing: border-box !important;
}

.stButton > button {
    border-radius: 999px !important;
    height: 40px !important;
    font-weight: 850 !important;
    border: none !important;
    background: #061d38 !important;
    color: white !important;
    box-shadow: 0 7px 16px rgba(0,0,0,.12);
}

.stButton > button:hover {
    background: #0d57a1 !important;
    color: white !important;
}

/* ======================================================
   CHAT
====================================================== */
.chat-card {
    background: #bfeaff;
    border-radius: 30px;
    padding: 18px;
    box-shadow: 0 12px 30px rgba(0,0,0,.10);
    margin-top: 8px;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

.chat-head {
    background: #0b4d95;
    border-radius: 22px;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: white;
    margin-bottom: 14px;
}

.chat-head-avatar {
    width: 42px;
    height: 42px;
    min-width: 42px;
    border-radius: 50%;
    background: rgba(255,255,255,.16);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.chat-head-avatar img {
    width: 33px !important;
}

.chat-head-title {
    font-size: 18px;
    font-weight: 900;
}

.chat-head-subtitle {
    font-size: 12px;
    color: rgba(255,255,255,.86);
}

.chat-body {
    background: #bfeaff;
    min-height: 260px;
    max-height: 390px;
    overflow-y: auto;
    padding: 4px 0 8px 0;
}

.msg-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 12px;
}

.msg-row.user {
    justify-content: flex-end;
}

.bot-avatar {
    width: 38px;
    height: 38px;
    min-width: 38px;
    border-radius: 50%;
    background: #0d57a1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.bot-avatar img {
    width: 30px !important;
}

.bot-bubble {
    background: white;
    color: #111;
    border-radius: 17px 17px 17px 4px;
    padding: 12px 15px;
    max-width: 78%;
    font-size: 14px;
    line-height: 1.5;
    box-shadow: 0 5px 13px rgba(0,0,0,.08);
}

.answer-html {
    width: 100%;
    line-height: 1.65;
    font-size: 14px;
    color: #111;
}

.answer-html p {
    margin: 0 0 10px 0;
}

.answer-html ol,
.answer-html ul {
    margin: 8px 0 12px 0;
    padding-left: 22px;
    list-style-position: outside;
}

.answer-html li {
    margin: 7px 0;
    padding-left: 6px;
    line-height: 1.65;
    text-align: left;
}

.answer-html ol li::marker,
.answer-html ul li::marker {
    color: #111;
    font-weight: 700;
}

.answer-html h4 {
    margin: 8px 0 10px 0;
    font-size: 15px;
    font-weight: 800;
}

.table-scroll {
    width: 100%;
    overflow-x: auto;
    margin: 10px 0;
    border-radius: 14px;
    border: 1px solid #d7eaf5;
    background: white;
}

.md-table {
    border-collapse: collapse;
    min-width: 720px;
    width: max-content;
    font-size: 12px;
    background: white;
}

.md-table th {
    background: #0b4d95;
    color: white;
    font-weight: 800;
    padding: 10px 12px;
    border: 1px solid #0b4d95;
    white-space: nowrap;
    text-align: left;
}

.md-table td {
    color: #111;
    padding: 9px 12px;
    border: 1px solid #d7eaf5;
    white-space: nowrap;
}

.md-table tr:nth-child(even) td {
    background: #f6fbff;
}

.user-bubble {
    background: #0d57a1;
    color: white;
    border-radius: 17px 17px 4px 17px;
    padding: 12px 15px;
    max-width: 78%;
    font-size: 14px;
    line-height: 1.5;
    box-shadow: 0 5px 13px rgba(0,0,0,.08);
}

.typing-bubble {
    background: white;
    color: #555;
    border-radius: 17px 17px 17px 4px;
    padding: 12px 15px;
    font-size: 14px;
    box-shadow: 0 5px 13px rgba(0,0,0,.08);
}

.dot {
    display: inline-block;
    animation: blink 1.2s infinite;
}

@keyframes blink {
    0% { opacity: .2; }
    50% { opacity: 1; }
    100% { opacity: .2; }
}

/* ======================================================
   INPUT CHAT MODERN RESPONSIVE WITH FLEXBOX
====================================================== */
.input-box {
    margin-top: 10px;
    background: transparent;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}

[data-testid="stForm"] {
    background: #ffffff !important;
    border: none !important;
    padding: 6px 10px !important;
    border-radius: 999px !important;
    box-shadow: 0 8px 22px rgba(0,0,0,.08) !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 6px !important;
    width: 100% !important;
}

[data-testid="stForm"] div[data-testid="column"]:first-child {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

[data-testid="stForm"] div[data-testid="column"]:last-child {
    flex: 0 0 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
}

.stTextInput > div {
    border: none !important;
    box-shadow: none !important;
}

.stTextInput > div > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

.stTextInput > div > div > input {
    height: 44px !important;
    border-radius: 999px !important;
    border: none !important;
    background: #ffffff !important;
    color: #111 !important;
    padding-left: 14px !important;
    font-size: 14px !important;
    box-shadow: none !important;
    width: 100% !important;
}

.stTextInput > div > div > input:focus {
    border: none !important;
    box-shadow: none !important;
}

.stTextInput > div > div > input::placeholder {
    color: #9aa6b2 !important;
}

.stForm button {
    height: 40px !important;
    width: 40px !important;
    min-width: 40px !important;
    border-radius: 50% !important;
    background: #0b4d95 !important;
    color: #ffffff !important;
    font-size: 18px !important;
    font-weight: 900 !important;
    box-shadow: none !important;
    border: none !important;
    padding: 0 !important;
    line-height: 1 !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.stForm button:hover {
    background: #0d57a1 !important;
    color: #ffffff !important;
}

/* ======================================================
   ADMIN DESIGN
====================================================== */
.admin-bg-card {
    background:
        radial-gradient(circle at top left, rgba(255,255,255,.22), transparent 30%),
        linear-gradient(135deg, #0b4d95 0%, #0d6fc2 48%, #38bdf8 100%);
    border-radius: 32px;
    padding: 32px;
    color: white;
    box-shadow: 0 18px 42px rgba(0,0,0,.18);
    margin-bottom: 24px;
}

.admin-login-card {
    max-width: 540px;
    margin: 42px auto 24px auto;
    background:
        radial-gradient(circle at top left, rgba(255,255,255,.22), transparent 35%),
        linear-gradient(135deg, #0b4d95 0%, #0d6fc2 100%);
    border-radius: 30px;
    padding: 36px 28px;
    text-align: center;
    color: white;
    box-shadow: 0 18px 42px rgba(0,0,0,.22);
}

.admin-login-card h2 {
    font-size: 32px;
    margin: 10px 0 10px 0;
    font-weight: 900;
}

.admin-login-card p {
    font-size: 15px;
    line-height: 1.6;
    color: rgba(255,255,255,.92);
}

.admin-title-box {
    background:
        radial-gradient(circle at top right, rgba(255,255,255,.20), transparent 35%),
        linear-gradient(135deg, #0b4d95 0%, #0d6fc2 100%);
    color: white;
    border-radius: 26px;
    padding: 26px;
    box-shadow: 0 14px 35px rgba(0,0,0,.16);
    margin-bottom: 20px;
}

.admin-title-box h1 {
    margin: 0 0 8px 0;
    font-size: 30px;
    font-weight: 900;
}

.admin-title-box p {
    margin: 0;
    color: rgba(255,255,255,.92);
}

.metric-card {
    background: white;
    color: #0f2440;
    border-radius: 20px;
    padding: 22px;
    text-align: center;
    box-shadow: 0 10px 24px rgba(0,0,0,.10);
    border-top: 5px solid #0b4d95;
}

.metric-card h2 {
    margin: 0;
    color: #0b4d95;
    font-size: 30px;
    font-weight: 900;
}

.metric-card p {
    margin: 6px 0 0 0;
    color: #345;
    font-weight: 700;
}

.admin-section-title {
    color: #0b4d95;
    font-size: 22px;
    font-weight: 900;
    margin: 22px 0 10px 0;
}

.doc-card {
    background: white;
    color: #0f2440;
    padding: 14px 16px;
    border-radius: 16px;
    border-left: 5px solid #0b4d95;
    box-shadow: 0 6px 14px rgba(0,0,0,.08);
    margin-bottom: 10px;
}

.admin-note {
    background: #dff3ff;
    color: #0f2440;
    border-radius: 16px;
    padding: 14px 16px;
    font-weight: 700;
    margin-top: 14px;
}

/* INPUT ADMIN LEBIH BERSIH */
.stTextInput label,
.stFileUploader label {
    color: #0f2440 !important;
    font-weight: 800 !important;
}

div[data-testid="stTextInput"] input {
    border: none !important;
    box-shadow: none !important;
    background: white !important;
}

/* SPLASH */
.splash-screen {
    width: 100%;
    min-height: 84vh;
    background: linear-gradient(180deg, #52b9ff 0%, #4b8ff7 100%);
    border-radius: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    text-align: center;
    box-shadow: 0 18px 42px rgba(0,0,0,.18);
}

.splash-screen img {
    width: 110px !important;
    animation: floatBot 2.4s ease-in-out infinite;
}

.splash-title {
    color: white;
    font-size: 30px;
    font-weight: 900;
    line-height: 1.15;
    letter-spacing: 1px;
    margin-top: 10px;
}

/* MOBILE RESPONSIVE FIXES */
@media (max-width: 768px) {
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"], .main {
        margin: 0 !important;
        padding: 0 !important;
        overflow-x: hidden !important;
        width: 100% !important;
    }

    .main .block-container {
        margin: 0 !important;
        padding: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
    }

    .stApp {
        background: #bfeaff !important;
    }

    .topbar {
        border-radius: 0;
        margin-bottom: 0;
        padding: 10px 14px;
    }

    .brand-logo {
        width: 32px;
        height: 32px;
    }

    .brand-logo img {
        width: 25px !important;
    }

    .brand-title {
        font-size: 13px;
    }

    .brand-subtitle {
        display: none;
    }

    .unma-logo-top {
        width: 38px;
        height: 38px;
    }

    .unma-logo-top img {
        width: 36px !important;
    }

    .hero-section {
        border-radius: 0 0 26px 26px;
        box-shadow: none;
        background: #a9d8ee;
        color: #111;
        padding: 14px 12px 10px 12px;
        margin-bottom: 6px;
    }

    .mascot-area img {
        width: 112px !important;
    }

    .speech-bubble {
        top: 5px;
        left: 78px;
        font-size: 10px;
        padding: 6px 9px;
    }

    .hero-title {
        font-size: 22px !important;
        color: #000;
    }

    .hero-desc {
        font-size: 12px !important;
        color: #111;
        padding: 0 10px;
    }

    .quick-title {
        color: #111;
        font-size: 13px;
    }

    .quick-menu-wrap {
        padding: 0 10px;
        margin-bottom: 6px;
    }

    .stButton > button {
        height: 38px !important;
        font-size: 13px !important;
        width: 100% !important;
    }

    .chat-card {
        border-radius: 0;
        box-shadow: none;
        padding: 8px 10px 12px 10px;
        background: #bfeaff;
        margin-top: 0;
    }

    .chat-head {
        display: none;
    }

    .chat-body {
        min-height: 350px !important;
        max-height: none;
        background: #bfeaff;
        padding: 4px 0 8px 0;
    }

    .bot-bubble, .user-bubble {
        font-size: 13px !important;
        max-width: 92% !important;
    }

    .bot-avatar {
        width: 34px;
        height: 34px;
        min-width: 34px;
    }

    .bot-avatar img {
        width: 26px !important;
    }

    .input-box {
        background: #bfeaff;
        padding: 0 10px 12px 10px;
        margin-top: 0;
    }

    [data-testid="stForm"] {
        padding: 6px 8px !important;
        box-shadow: none !important;
    }

    [data-testid="stForm"] div[data-testid="column"]:first-child {
        flex: 1 1 auto !important;
    }

    [data-testid="stForm"] div[data-testid="column"]:last-child {
        flex: 0 0 42px !important;
        max-width: 42px !important;
        min-width: 42px !important;
    }

    .stTextInput > div > div > input {
        height: 40px !important;
        font-size: 13px !important;
    }

    .stForm button {
        height: 38px !important;
        width: 38px !important;
        min-width: 38px !important;
        font-size: 16px !important;
        margin: 0 !important;
    }

    .splash-screen {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        margin: 0 !important;
        padding: 0 !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        z-index: 99999 !important;
    }

    .admin-login-card {
        margin: 20px 14px;
        padding: 28px 20px;
    }

    .admin-bg-card, .admin-title-box {
        border-radius: 0;
        margin: 0;
    }

    .answer-html {
        font-size: 13px;
        line-height: 1.6;
    }

    .answer-html ol, .answer-html ul {
        padding-left: 20px;
        margin: 7px 0 10px 0;
    }

    .answer-html li {
        padding-left: 4px;
        margin: 6px 0;
    }

    * {
        box-sizing: border-box !important;
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def load_admin_background_css():
    st.markdown(
        """
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(255,255,255,.45), transparent 25%),
        linear-gradient(135deg, #dff6ff 0%, #bdefff 35%, #eaf8ff 100%) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )

# =========================================================
# USER PAGE
# =========================================================
def render_user_page():
    load_css()

    if not st.session_state.splash_done:
        html_view(
            "<div class='splash-screen'>"
            f"{mascot(110)}"
            "<div class='splash-title'>TANYA<br>SIBERMA</div>"
            "</div>"
        )
        time.sleep(1.1)
        st.session_state.splash_done = True
        st.rerun()

    html_view(
        "<div class='topbar'>"
        "<div class='brand-row'>"
        f"<div class='brand-logo'>{mascot(36)}</div>"
        "<div>"
        "<div class='brand-title'>TANYA SIBERMA</div>"
        "<div class='brand-subtitle'>Chatbot PMB Universitas Majalengka</div>"
        "</div>"
        "</div>"
        f"<div class='unma-logo-top'>{logo_unma(54)}</div>"
        "</div>"
    )

    html_view(
        "<div class='hero-section'>"
        "<div class='mascot-area'>"
        f"{mascot(132, 'mascot-float')}"
        "<div class='speech-bubble'>Sampurasun Maba UNMA💙</div>"
        "</div>"
        "<div class='hero-title'>Halo! Aku SIBERMA 👋</div>"
        "<div class='hero-desc'>Siap bantu kamu cari informasi seputar PMB Universitas Majalengka dengan cepat dan mudah.</div>"
        "<div class='quick-title'>Quick Menu:</div>"
        "</div>"
    )

    quick_question = None

    st.markdown("<div class='quick-menu-wrap'>", unsafe_allow_html=True)

    q1, q2, q3, q4 = st.columns(4)

    with q1:
        if st.button("💰 Biaya Kuliah", use_container_width=True):
            quick_question = "Berapa biaya kuliah PMB Universitas Majalengka?"

    with q2:
        if st.button("📍 Lokasi Kampus", use_container_width=True):
            quick_question = "Di mana lokasi kampus Universitas Majalengka?"

    with q3:
        if st.button("📝 Cara Daftar", use_container_width=True):
            quick_question = "Bagaimana cara daftar PMB Universitas Majalengka?"

    with q4:
        if st.button("🎓 Fakultas UNMA", use_container_width=True):
            quick_question = "Apa saja fakultas atau program studi di Universitas Majalengka?"

    st.markdown("</div>", unsafe_allow_html=True)

    messages_html = ""

    for message in st.session_state.messages:
        role = message.get("role", "assistant")
        raw_content = message.get("content", "")

        if role == "assistant":
            content = answer_to_html(raw_content)

            messages_html += (
                "<div class='msg-row'>"
                f"<div class='bot-avatar'>{mascot(30)}</div>"
                f"<div class='bot-bubble'>{content}</div>"
                "</div>"
            )
        else:
            content = safe_text(raw_content)

            messages_html += (
                "<div class='msg-row user'>"
                f"<div class='user-bubble'>{content}</div>"
                "</div>"
            )

    if st.session_state.pending_question:
        messages_html += (
            "<div class='msg-row'>"
            f"<div class='bot-avatar'>{mascot(30)}</div>"
            "<div class='typing-bubble'>Tanya Siberma sedang mengetik<span class='dot'>...</span></div>"
            "</div>"
        )

    chat_html = (
        "<div class='chat-card'>"
        "<div class='chat-head'>"
        f"<div class='chat-head-avatar'>{mascot(35)}</div>"
        "<div>"
        "<div class='chat-head-title'>Obrolan PMB UNMA</div>"
        "<div class='chat-head-subtitle'>Tanyakan jalur masuk, biaya, prodi, beasiswa, dan syarat daftar.</div>"
        "</div>"
        "</div>"
        f"<div class='chat-body'>{messages_html}</div>"
        "</div>"
    )

    html_view(chat_html)

    st.markdown("<div class='input-box'>", unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        input_col, send_col = st.columns([10, 1])

        with input_col:
            prompt = st.text_input(
                "Pertanyaan",
                placeholder="Ketik pertanyaan di sini...",
                label_visibility="collapsed",
            )

        with send_col:
            submitted = st.form_submit_button("➤", use_container_width=True)

        if submitted and prompt.strip():
            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": prompt.strip(),
                }
            )
            st.session_state.pending_question = prompt.strip()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    if quick_question:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": quick_question,
            }
        )
        st.session_state.pending_question = quick_question
        st.rerun()

    if st.session_state.pending_question:
        time.sleep(0.5)
        answer_pending_question()

# =========================================================
# ADMIN LOGIN
# =========================================================
def render_admin_login():
    load_css()
    load_admin_background_css()

    html_view(
        "<div class='admin-login-card'>"
        f"{mascot(105, 'mascot-float')}"
        "<h2>Admin Tanya Siberma</h2>"
        "<p>Login untuk mengelola dokumen PMB terbaru dan membangun ulang index RAG.</p>"
        "</div>"
    )

    username = st.text_input("Username Admin")
    password = st.text_input("Password Admin", type="password")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("⬅️ Kembali ke User", use_container_width=True):
            set_page("user")

    with c2:
        if st.button("Masuk Admin", use_container_width=True):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("Login admin berhasil.")
                st.rerun()
            else:
                st.error("Username atau password salah.")

    html_view(
        "<div class='admin-note'>"
        "Default login: username = admin | password = UNMA2026"
        "</div>"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================
def render_admin_dashboard():
    load_css()
    load_admin_background_css()

    documents = list_documents()
    ollama_active = safe_check_ollama()
    index_ready = (INDEX_DIR / "faiss.index").exists()

    html_view(
        "<div class='admin-title-box'>"
        "<h1>🛠️ Admin Panel Tanya Siberma</h1>"
        "<p>Kelola dokumen PMB, hapus dokumen lama, dan bangun ulang index RAG.</p>"
        "</div>"
    )

    a, b, c = st.columns(3)

    with a:
        if st.button("⬅️ Kembali ke User", use_container_width=True):
            set_page("user")

    with b:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    with c:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.write("")

    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            f"<div class='metric-card'><h2>{len(documents)}</h2><p>Total Dokumen</p></div>",
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f"<div class='metric-card'><h2>{'Aktif' if ollama_active else 'Belum'}</h2><p>Status Ollama</p></div>",
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown(
            f"<div class='metric-card'><h2>{'Siap' if index_ready else 'Belum'}</h2><p>Status Index</p></div>",
            unsafe_allow_html=True,
        )

    html_view("<div class='admin-section-title'>📤 Upload Dokumen PMB Terbaru</div>")

    uploaded_files = st.file_uploader(
        "Pilih dokumen PMB",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )

    if st.button("Simpan Dokumen", use_container_width=True):
        if uploaded_files:
            for uploaded_file in uploaded_files:
                save_path = UPLOAD_DIR / uploaded_file.name
                with open(save_path, "wb") as file:
                    file.write(uploaded_file.getbuffer())
            st.success(f"{len(uploaded_files)} dokumen berhasil disimpan.")
        else:
            st.warning("Silakan pilih file terlebih dahulu.")

    if st.button("Bangun Ulang Index Sekarang", use_container_width=True):
        try:
            with st.spinner("Sedang membangun ulang index RAG..."):
                total_chunks = build_index()
            st.success(f"Index berhasil dibangun ulang. Total chunk: {total_chunks}")
        except Exception as error:
            st.error(f"Gagal membangun index: {error}")

    html_view("<div class='admin-section-title'>📂 Daftar Dokumen PMB</div>")

    if not documents:
        st.info("Belum ada dokumen PMB.")
    else:
        for doc in documents:
            st.markdown(
                f"<div class='doc-card'><b>{safe_text(doc.name)}</b><br><small>{safe_text(str(doc))}</small></div>",
                unsafe_allow_html=True,
            )

            if st.button(f"🗑️ Hapus {doc.name}", key=f"delete_{doc}", use_container_width=True):
                try:
                    doc.unlink()
                    st.success(f"Dokumen {doc.name} berhasil dihapus.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Gagal menghapus dokumen: {error}")


# =========================================================
# ROUTER
# =========================================================
current_page = get_current_page()

if current_page == "admin":
    if st.session_state.admin_logged_in:
        render_admin_dashboard()
    else:
        render_admin_login()
else:
    render_user_page()
