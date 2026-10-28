import os
import io
import hashlib
import json
import time
import secrets
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3

# Tenta di importare il client leggero per Turso
try:
    import libsql_client
    TURSO_AVAILABLE = True
except ImportError:
    TURSO_AVAILABLE = False

# Logo aziendale (metti logo.png nella stessa cartella di app.py)
LOGO_PATH = "logo.png"

MESI = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
TIPI_INTERVENTO = ["Ordinario", "Straordinario", "Collaudo", "Guasto"]
MIN_PASSWORD_LEN = 6


# --- WRAPPER DI COMPATIBILITÀ PER UNIFICARE SQLITE E TURSO ---
class DatabaseWrapper:
    def __init__(self, conn, is_turso=False):
        self.conn = conn
        self.is_turso = is_turso

    def cursor(self):
        return self if self.is_turso else self.conn.cursor()

    def execute(self, query, params=()):
        if self.is_turso:
            res = self.conn.execute(query, params)
            return ResultSetWrapper(res)
        else:
            return self.conn.cursor().execute(query, params)

    def commit(self):
        if not self.is_turso:
            self.conn.commit()

    def close(self):
        if self.is_turso:
            self.conn.close()
        else:
            self.conn.close()


class ResultSetWrapper:
    def __init__(self, result):
        self.result = result
        self.rows = result.rows if hasattr(result, 'rows') else []
        self._index = 0

    def fetchone(self):
        if self._index < len(self.rows):
            row = self.rows[self._index]
            self._index += 1
            return row
        return None

    def fetchall(self):
        return self.rows


# --- CONFIGURAZIONE DATABASE (TURSO CLOUD + FALLBACK LOCALE) ---
def get_db_connection():
    turso_url = st.secrets.get("TURSO_DATABASE_URL", "")
    turso_token = st.secrets.get("TURSO_AUTH_TOKEN", "")

    if turso_url.startswith("libsql://"):
        turso_url = turso_url.replace("libsql://", "https://")

    if TURSO_AVAILABLE and turso_url and turso_token:
        try:
            conn = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)
            return DatabaseWrapper(conn, is_turso=True)
        except Exception as e:
            st.error(f"Errore di connessione a Turso Cloud: {e}")
            conn = sqlite3.connect("gestionale.db", check_same_thread=False)
            return DatabaseWrapper(conn, is_turso=False)
    else:
        conn = sqlite3.connect("gestionale.db", check_same_thread=False)
        return DatabaseWrapper(conn, is_turso=False)


def get_secret(key):
    try:
        return st.secrets.get(key, "") or ""
    except Exception:
        return ""


def seed_user(conn, username, name, role, secret_key):
    """Crea l'utente iniziale solo se manca, con la password presa dai secrets.
    Se esiste già, aggiorna nome e ruolo ma NON tocca la password."""
    exists = conn.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
    if not exists:
        password = get_secret(secret_key)
        if password:
            conn.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)",
                         (username, name, hashlib.sha256(password.encode()).hexdigest(), "", role))
    else:
        conn.execute("UPDATE users SET name = ?, role = ? WHERE username = ?", (name, role, username))


def init_db():
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            pin TEXT,
            raw_pin TEXT,
            role TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            group_name TEXT,
            address TEXT,
            phone TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            number INTEGER PRIMARY KEY,
            client TEXT,
            date TEXT,
            duration TEXT,
            technician TEXT,
            type TEXT,
            description TEXT,
            expenses TEXT,
            author TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            username TEXT,
            expires TEXT
        )
    ''')
    
    conn.execute("DELETE FROM users WHERE username = 'ADMIN'")
    conn.execute("DELETE FROM users WHERE username = 'SALVATORE'")

    seed_user(conn, "DEV", "Enrico Bottone", "sviluppatore", "DEV_PASSWORD")
    seed_user(conn, "Salvatore", "Salvatore Tammaro", "amministratore", "SALVATORE_PASSWORD")
    seed_user(conn, "Pietro", "Pietro", "collaboratore", "PIETRO_PASSWORD")

    # Le password non vengono più conservate in chiaro: cancello quelle già salvate
    conn.execute("UPDATE users SET raw_pin = ''")

    conn.commit()
    conn.close()

init_db()

st.set_page_config(
    page_title="TS Impianti — Gestionale",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- TEMA GRAFICO (solo colori e aspetto, posizioni invariate) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #0b1017;
        --bg-2: #101722;
        --surface: #151e2b;
        --surface-2: #1b2636;
        --line: rgba(148, 163, 184, 0.14);
        --text: #e8eef6;
        --muted: #8fa0b5;
        --accent: #22d3ee;
        --accent-2: #3b82f6;
    }

    html, body, .stApp, .stApp * {
        font-family: 'Manrope', 'Inter', sans-serif;
    }
    /* Le icone di Streamlit usano un font speciale: va lasciato intatto */
    .stApp [data-testid="stIconMaterial"],
    .stApp [class*="material-symbols"],
    .stApp [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }
    .stApp {
        background:
            radial-gradient(900px 500px at 85% -10%, rgba(34, 211, 238, 0.08), transparent 60%),
            radial-gradient(700px 420px at -5% 10%, rgba(59, 130, 246, 0.10), transparent 60%),
            var(--bg);
        color: var(--text);
    }
    [data-testid="stHeader"] { background: transparent; }

    h1, h2, h3, h4 {
        letter-spacing: -0.02em;
        color: var(--text);
    }
    h1 {
        font-weight: 800;
        background: linear-gradient(120deg, #e8eef6 30%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .card, [data-testid="stForm"] {
        background: linear-gradient(180deg, var(--surface-2) 0%, var(--surface) 100%);
        padding: 24px;
        border-radius: 18px;
        border: 1px solid var(--line);
        box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 18px 40px -22px rgba(0, 0, 0, 0.7);
        margin-bottom: 20px;
    }

    .stButton>button, [data-testid="stFormSubmitButton"]>button, [data-testid="stDownloadButton"]>button {
        background: linear-gradient(135deg, var(--accent-2) 0%, #2563eb 100%);
        color: #fff;
        border-radius: 12px;
        font-weight: 700;
        letter-spacing: 0.01em;
        border: 1px solid rgba(255, 255, 255, 0.10);
        padding: 10px 24px;
        box-shadow: 0 8px 20px -10px rgba(59, 130, 246, 0.8);
        transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
        width: 100%;
    }
    .stButton>button:hover, [data-testid="stFormSubmitButton"]>button:hover, [data-testid="stDownloadButton"]>button:hover {
        background: linear-gradient(135deg, #4f94ff 0%, var(--accent-2) 100%);
        box-shadow: 0 12px 26px -10px rgba(34, 211, 238, 0.55);
        transform: translateY(-1px);
        color: #fff;
        border-color: rgba(34, 211, 238, 0.45);
    }
    .stButton>button:active, [data-testid="stFormSubmitButton"]>button:active {
        transform: translateY(0);
        filter: brightness(.95);
    }
    .stButton>button:focus-visible, [data-testid="stFormSubmitButton"]>button:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
    }

    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"]>div {
        background-color: var(--bg-2) !important;
        border: 1px solid var(--line) !important;
        border-radius: 12px !important;
        transition: border-color .15s ease, box-shadow .15s ease;
    }
    [data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"]>div:focus-within {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.15) !important;
    }
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        color: var(--text) !important;
    }
    label, [data-testid="stWidgetLabel"] p {
        color: var(--muted) !important;
        font-weight: 600;
    }

    [data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 16px;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary { padding: 14px 18px; font-weight: 700; }
    [data-testid="stExpander"] summary:hover { background: var(--surface-2); }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d141e 0%, #090e15 100%);
        border-right: 1px solid var(--line);
        padding-top: 10px;
    }
    [data-testid="stSidebar"] .stRadio label {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 10px 14px;
        color: #b6c3d4;
        font-weight: 600;
        width: 100%;
        transition: background .15s ease, border-color .15s ease, color .15s ease;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(148, 163, 184, 0.08);
        color: var(--text);
    }
    [data-testid="stSidebar"] .stRadio label:has(input:checked) {
        background: linear-gradient(90deg, rgba(34, 211, 238, 0.16), rgba(59, 130, 246, 0.08));
        border-color: rgba(34, 211, 238, 0.35);
        color: #fff;
    }

    [data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--line); }
    hr { border-color: var(--line) !important; }
    code {
        background: rgba(34, 211, 238, 0.10);
        color: #7ee7f7;
        border-radius: 6px;
        padding: 2px 6px;
    }
    [data-testid="stFileUploader"] section {
        background: var(--bg-2);
        border: 1px dashed rgba(34, 211, 238, 0.35);
        border-radius: 14px;
    }

    @media (prefers-reduced-motion: reduce) {
        * { transition: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "last_generated_pdf" not in st.session_state:
    st.session_state.last_generated_pdf = None

if "edit_report_num" not in st.session_state:
    st.session_state.edit_report_num = None


# --- LOGIN PERSISTENTE (cookie + codice nell'indirizzo) ---
SESSION_COOKIE = "ts_session"
SESSION_DAYS = 30


def set_session_cookie(value, days):
    components.html(f"""
        <script>
        const d = new Date();
        d.setTime(d.getTime() + ({days}) * 24 * 60 * 60 * 1000);
        const secure = window.parent.location.protocol === 'https:' ? '; Secure' : '';
        window.parent.document.cookie = "{SESSION_COOKIE}={value}; expires=" + d.toUTCString() + "; path=/; SameSite=Lax" + secure;
        </script>
    """, height=0)


def get_session_token():
    try:
        token = st.query_params.get("s")
        if token:
            return token
    except Exception:
        pass
    try:
        return st.context.cookies.get(SESSION_COOKIE)
    except Exception:
        return None


def restore_session():
    token = get_session_token()
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db_connection()
    row = conn.execute("SELECT username, expires FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
    if not row:
        conn.close()
        return None
    if datetime.fromisoformat(row[1]) < datetime.now():
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        conn.commit()
        conn.close()
        return None
    usr = conn.execute("SELECT name, role FROM users WHERE username = ?", (row[0],)).fetchone()
    conn.close()
    if not usr:
        return None
    return {"username": row[0], "name": usr[0], "role": usr[1]}


if not st.session_state.logged_user:
    restored_user = restore_session()
    if restored_user:
        st.session_state.logged_user = restored_user


# --- FUNZIONI DI SUPPORTO: SPESE ---
def parse_expenses(exp_json):
    if not exp_json:
        return []
    try:
        data = json.loads(exp_json)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def to_float(value):
    try:
        number = float(value)
        return 0.0 if number != number else number
    except Exception:
        return 0.0


def expenses_total(exp_json):
    return sum(to_float(e.get("amount", 0)) for e in parse_expenses(exp_json))


def existing_photo(exp_json):
    for e in parse_expenses(exp_json):
        if e.get("photo"):
            return e["photo"]
    return None


def expenses_to_df(exp_json):
    rows = []
    for e in parse_expenses(exp_json):
        amount = to_float(e.get("amount", 0))
        if e.get("item") or amount > 0:
            rows.append({"Voce": e.get("item") or "", "Importo (€)": amount})
    df = pd.DataFrame(rows, columns=["Voce", "Importo (€)"])
    df["Voce"] = df["Voce"].astype(str)
    df["Importo (€)"] = df["Importo (€)"].astype(float)
    return df


def expenses_editor(key, exp_json=""):
    return st.data_editor(
        expenses_to_df(exp_json),
        num_rows="dynamic",
        key=key,
        column_config={
            "Voce": st.column_config.TextColumn("Voce Spesa o Materiale", width="large"),
            "Importo (€)": st.column_config.NumberColumn("Importo (€)", min_value=0.0, step=0.5, format="%.2f"),
        },
    )


def build_expenses_json(df, photo_path=None):
    items = []
    for row in df.to_dict("records"):
        item = row.get("Voce")
        if item is None or (isinstance(item, float) and item != item):
            item = ""
        item = str(item).strip()
        amount = to_float(row.get("Importo (€)"))
        if item or amount > 0:
            items.append({"item": item, "amount": amount, "photo": None})
    if photo_path:
        if items:
            items[0]["photo"] = photo_path
        else:
            items.append({"item": "", "amount": 0.0, "photo": photo_path})
    return json.dumps(items)


def parse_date(text):
    try:
        return datetime.strptime((text or "").strip(), "%d/%m/%Y")
    except Exception:
        return None


def delete_single_report(report_number):
    conn = get_db_connection()
    conn.execute("DELETE FROM reports WHERE number = ?", (report_number,))
    conn.commit()
    conn.close()
    
    pdf_filename = f"Rapportino_{report_number}.pdf"
    if os.path.exists(pdf_filename):
        try:
            os.remove(pdf_filename)
        except Exception:
            pass


# --- GENERAZIONE PDF ---
def build_pdf(report, client):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, Image, KeepTogether)

    PRIMARY = colors.HexColor("#1d4ed8")
    DARK = colors.HexColor("#0f172a")
    MUTED = colors.HexColor("#64748b")
    LIGHT = colors.HexColor("#f1f5f9")
    LINE = colors.HexColor("#cbd5e1")

    page_w = A4[0] - 36 * mm

    def esc(value):
        return escape(str(value or "")).replace("\n", "<br/>")

    st_normal = ParagraphStyle("n", fontName="Helvetica", fontSize=10, leading=14, textColor=DARK)
    st_label = ParagraphStyle("l", parent=st_normal, fontSize=9.5, leading=15)
    st_title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=DARK)
    st_brand = ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=PRIMARY)
    st_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9.5, leading=13, textColor=MUTED)
    st_sec = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=colors.white)
    st_box_title = ParagraphStyle("bt", fontName="Helvetica-Bold", fontSize=9.5, leading=15, textColor=PRIMARY)
    st_right = ParagraphStyle("r", parent=st_normal, alignment=TA_RIGHT)
    st_right_b = ParagraphStyle("rb", parent=st_right, fontName="Helvetica-Bold")
    st_bold = ParagraphStyle("bd", parent=st_normal, fontName="Helvetica-Bold")
    st_hdr = ParagraphStyle("h", parent=st_normal, fontName="Helvetica-Bold", textColor=colors.white)
    st_hdr_r = ParagraphStyle("hr", parent=st_hdr, alignment=TA_RIGHT)

    def section(title):
        t = Table([[Paragraph(title, st_sec)]], colWidths=[page_w])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    def kv(label, value):
        return Paragraph(f"<b>{label}:</b> {esc(value)}", st_label)

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            canvas.Canvas.__init__(self, *args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(total)
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

        def _draw_footer(self, total):
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
            self.setFont("Helvetica", 8.5)
            self.setFillColor(MUTED)
            self.drawString(18 * mm, 9.5 * mm, "TS Impianti — di Tammaro Salvatore")
            self.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"Pagina {self._pageNumber} di {total}")

    story = []

    # Intestazione con logo
    brand_block = [
        Paragraph("TS IMPIANTI", st_brand),
        Paragraph("di Tammaro Salvatore", st_sub),
        Paragraph("Impianti Elettrici Civili e Industriali", st_sub),
    ]
    logo = None
    if os.path.exists(LOGO_PATH):
        try:
            iw, ih = ImageReader(LOGO_PATH).getSize()
            logo_w = 32 * mm
            logo = Image(LOGO_PATH, width=logo_w, height=logo_w * ih / iw)
        except Exception:
            logo = None
    if logo:
        header = Table([[logo, brand_block]], colWidths=[38 * mm, page_w - 38 * mm])
    else:
        header = Table([[brand_block]], colWidths=[page_w])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 1.4, PRIMARY),
    ]))
    story += [header, Spacer(1, 12)]

    story += [Paragraph(f"RAPPORTINO DI INTERVENTO N. {report['number']}", st_title), Spacer(1, 8)]

    # Dati intervento e cliente
    left = []
    if report.get("date"):
        left.append(kv("Data intervento", report["date"]))
    duration_val = (report.get("duration") or "").strip()
    if duration_val and duration_val.upper() != "N/D":
        left.append(kv("Durata servizio", duration_val))
    if report.get("type"):
        left.append(kv("Tipo intervento", report["type"]))
    if report.get("technician"):
        left.append(kv("Tecnici incaricati", report["technician"]))
    if report.get("author"):
        left.append(kv("Compilato da", report["author"]))

    right = [Paragraph("DATI CLIENTE", st_box_title)]
    if client.get("name"):
        right.append(kv("Cliente", client["name"]))
    address_val = (client.get("address") or "").strip()
    if address_val and address_val.upper() != "N/D":
        right.append(kv("Indirizzo", address_val))
    phone_val = (client.get("phone") or "").strip()
    if phone_val and phone_val.upper() != "N/D":
        right.append(kv("Telefono", phone_val))

    info = Table([[left or [Paragraph("", st_label)], right]], colWidths=[page_w * 0.55, page_w * 0.45])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBEFORE", (1, 0), (1, 0), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [info, Spacer(1, 14)]

    # Descrizione lavori
    desc_text = (report.get("description") or "").strip()
    if desc_text:
        story += [section("DESCRIZIONE DEI LAVORI ESEGUITI"), Spacer(1, 6),
                  Paragraph(esc(desc_text), st_normal), Spacer(1, 14)]

    # Spese e materiali
    expenses = parse_expenses(report.get("expenses"))
    valid = [e for e in expenses if e.get("item") or to_float(e.get("amount")) > 0]
    if valid:
        rows = [[Paragraph("Voce", st_hdr), Paragraph("Importo", st_hdr_r)]]
        total = 0.0
        for e in valid:
            amount = to_float(e.get("amount"))
            total += amount
            rows.append([Paragraph(esc(e.get("item") or "Spesa generica"), st_normal),
                         Paragraph(f"€ {amount:.2f}", st_right)])
        rows.append([Paragraph("Totale spese", st_bold), Paragraph(f"€ {total:.2f}", st_right_b)])
        table = Table(rows, colWidths=[page_w - 40 * mm, 40 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, PRIMARY),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story += [section("SPESE VIVE E MATERIALI"), Spacer(1, 6), table, Spacer(1, 14)]

    # Foto allegata
    photo = None
    for e in expenses:
        p = e.get("photo")
        if p and os.path.exists(p):
            photo = p
            break
    if photo:
        try:
            iw, ih = ImageReader(photo).getSize()
            scale = min((85 * mm) / iw, (70 * mm) / ih)
            story.append(KeepTogether([
                section("FOTO ALLEGATA"), Spacer(1, 6),
                Image(photo, width=iw * scale, height=ih * scale, hAlign="LEFT"),
            ]))
            story.append(Spacer(1, 14))
        except Exception:
            pass

    # Firme
    sig = Table(
        [["", "", ""], [Paragraph("Firma Tecnico", st_sub), "", Paragraph("Firma Cliente", st_sub)]],
        colWidths=[65 * mm, page_w - 130 * mm, 65 * mm],
        rowHeights=[16 * mm, None],
    )
    sig.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.8, DARK),
        ("LINEABOVE", (2, 1), (2, 1), 0.8, DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [Spacer(1, 10), KeepTogether([sig])]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=20 * mm,
        title=f"Rapportino {report['number']}", author="TS Impianti",
    )
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


@st.cache_data(show_spinner=False, max_entries=300)
def _cached_pdf(report_json, client_json, photo_sig):
    return build_pdf(json.loads(report_json), json.loads(client_json))


def get_pdf_bytes(report, client):
    # Il PDF viene creato una sola volta e riutilizzato finché il rapportino non cambia
    sig = []
    for e in parse_expenses(report.get("expenses")):
        p = e.get("photo")
        sig.append(os.path.getmtime(p) if p and os.path.exists(p) else 0)
    return _cached_pdf(
        json.dumps(report, sort_keys=True, default=str),
        json.dumps(client, sort_keys=True, default=str),
        tuple(sig),
    )


def pdf_download(report, client, key, label, lazy=False):
    ready_key = f"pdf_ready_{key}"
    if lazy and not st.session_state.get(ready_key):
        if st.button(f"📄 Prepara PDF N. {report['number']}", key=f"prep_{key}"):
            st.session_state[ready_key] = True
            st.rerun()
        return
    st.download_button(
        label=label,
        data=get_pdf_bytes(report, client),
        file_name=f"Rapportino_{report['number']}.pdf",
        mime="application/pdf",
        key=f"dl_{key}",
    )


# --- CONFERMA ELIMINAZIONE ---
@st.dialog("Conferma eliminazione")
def confirm_delete(kind, key, label, extra=None):
    st.warning(f"Stai per eliminare {label}. L'operazione non si può annullare.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Sì, elimina", key=f"yes_{kind}_{key}"):
            if kind == "report":
                delete_single_report(key)
                st.session_state.edit_report_num = None
            elif kind == "client":
                conn = get_db_connection()
                conn.execute("DELETE FROM clients WHERE id = ?", (key,))
                conn.execute("DELETE FROM reports WHERE client = ?", (extra,))
                conn.commit()
                conn.close()
            elif kind == "user":
                conn = get_db_connection()
                conn.execute("DELETE FROM users WHERE username = ?", (key,))
                conn.execute("DELETE FROM sessions WHERE username = ?", (key,))
                conn.commit()
                conn.close()
            st.session_state.flash = "Eliminazione completata."
            st.rerun()
    with col_no:
        if st.button("Annulla", key=f"no_{kind}_{key}"):
            st.rerun()


if not st.session_state.logged_user:
    st.markdown("<h2 style='text-align: center; margin-bottom: 25px;'>⚡ TS IMPIANTI</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        _conn = get_db_connection()
        _n_users = _conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        _conn.close()
        if _n_users == 0:
            st.warning("Nessun utente configurato. Imposta DEV_PASSWORD (e le altre) nei Secrets dell'app e riavviala.")
        with st.form("login_form"):
            st.markdown("<h3 style='text-align: center; margin-bottom: 20px; color: #38bdf8;'>ACCESSO RISERVATO</h3>", unsafe_allow_html=True)
            
            username_input = st.text_input("Nome Utente").strip()
            pin_input = st.text_input("Password", type="password")
            
            st.write("") 
            submit_login = st.form_submit_button("Accedi al Gestionale", use_container_width=True)
            
            if submit_login:
                conn = get_db_connection()
                res = conn.execute("SELECT name, pin, role FROM users WHERE username = ?", (username_input,))
                user_record = res.fetchone()
                conn.close()
                
                hashed_input_pin = hashlib.sha256(pin_input.encode()).hexdigest()
                
                if user_record and user_record[1] == hashed_input_pin:
                    st.session_state.logged_user = {
                        "username": username_input,
                        "name": user_record[0],
                        "role": user_record[2]
                    }
                    token = secrets.token_urlsafe(32)
                    expires = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat()
                    conn = get_db_connection()
                    conn.execute("DELETE FROM sessions WHERE expires < ?", (datetime.now().isoformat(),))
                    conn.execute("INSERT INTO sessions (token_hash, username, expires) VALUES (?, ?, ?)",
                                 (hashlib.sha256(token.encode()).hexdigest(), username_input, expires))
                    conn.commit()
                    conn.close()
                    set_session_cookie(token, SESSION_DAYS)
                    st.query_params["s"] = token
                    st.success(f"Accesso riuscito! Benvenuto, {user_record[0]}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Nome utente o password errati.")
    st.stop()


user = st.session_state.logged_user

st.sidebar.markdown("""
    <div style='background: rgba(30, 41, 59, 0.5); padding: 14px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.06); margin-bottom: 20px;'>
        <div style='font-size: 0.75rem; color: #38bdf8; font-weight: 600; text-transform: uppercase;'>Utente Connesso</div>
        <div style='font-size: 1.05rem; font-weight: 700; color: #f8fafc; margin-top: 2px;'>⚡ TS IMPIANTI</div>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"👤 **{user['name']}**")
st.sidebar.markdown(f"Ruolo: `{user['role'].upper()}`")
st.sidebar.markdown("---")

menu_options = {
    "📁 &nbsp; Archivio Clienti": "Archivio Clienti",
    "📝 &nbsp; Nuovo Rapportino": "Nuovo Rapportino",
    "📊 &nbsp; Riepilogo Mensile": "Riepilogo Mensile"
}

if user["role"] in ["sviluppatore", "amministratore"]:
    menu_options["✏️ &nbsp; Modifica Rapportino"] = "Modifica Rapportino"
    menu_options["👥 &nbsp; Gestione Utenti"] = "Gestione Utenti"

selected_label = st.sidebar.radio("Navigazione", list(menu_options.keys()), label_visibility="collapsed")
selected_page = menu_options[selected_label]

st.sidebar.markdown("---")
if st.sidebar.button("🔒 &nbsp; Effettua il Logout", use_container_width=True):
    token = get_session_token()
    if token:
        conn = get_db_connection()
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()
        conn.close()
    set_session_cookie("", -1)
    st.query_params.clear()
    st.session_state.logged_user = None
    time.sleep(1)
    st.rerun()

if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))


# ==========================================
# 1. ARCHIVIO CLIENTI
# ==========================================
if selected_page == "Archivio Clienti":
    st.title("📁 Archivio Clienti & Commesse")
    st.write("Seleziona o cerca un cliente per visualizzare la sua anagrafica e lo storico completo dei rapportini.")
    
    if user["role"] in ["sviluppatore", "amministratore"]:
        with st.expander("➕ Aggiungi Nuovo Cliente / Cartella"):
            with st.form("new_client_form"):
                c_name = st.text_input("Nome Cliente / Azienda")
                c_group = st.text_input("Gruppo / Commessa")
                c_address = st.text_input("Indirizzo")
                c_phone = st.text_input("Telefono")
                
                submit_client = st.form_submit_button("Crea Cartella Cliente")
                if submit_client and c_name:
                    conn = get_db_connection()
                    conn.execute("INSERT INTO clients (name, group_name, address, phone) VALUES (?, ?, ?, ?)",
                                 (c_name, c_group, c_address, c_phone))
                    conn.commit()
                    conn.close()
                    st.success(f"Cartella per '{c_name}' creata con successo!")
                    st.rerun()

    st.markdown("---")
    
    conn = get_db_connection()
    res_clients = conn.execute("SELECT id, name, group_name, address, phone FROM clients")
    clients_data = res_clients.fetchall()
    res_all_reports = conn.execute("SELECT number, date, duration, technician, type, description, expenses, author, client FROM reports ORDER BY number DESC")
    all_reports_rows = res_all_reports.fetchall()
    conn.close()

    reports_by_client = {}
    for r in all_reports_rows:
        reports_by_client.setdefault(r[8], []).append(r[:8])
    
    if not clients_data:
        st.info("Nessun cliente presente nell'archivio.")
    else:
        search_query = st.text_input("🔍 Cerca cliente o commessa...").lower()
        
        for client_id, c_name, c_group, c_address, c_phone in clients_data:
            if search_query in c_name.lower() or search_query in (c_group or "").lower():
                with st.container():
                    with st.expander(f"🏢 {c_name} — Commessa: {c_group or 'N/D'}"):
                        st.markdown(f"""
                            <p style='color: #94a3b8; margin-bottom: 15px;'>
                                <b>Indirizzo:</b> {c_address or 'Non specificato'} &nbsp;|&nbsp; <b>Telefono:</b> {c_phone or 'Non specificato'}
                            </p>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("#### 📜 Storico Rapportini")
                        
                        client_reports = reports_by_client.get(c_name, [])
                        
                        if not client_reports:
                            st.info("Nessun rapportino registrato per questo cliente.")
                        else:
                            for rep_num, rep_date, rep_dur, rep_tech, rep_type, rep_desc, rep_exp, rep_auth in client_reports:
                                st.markdown(f"""
                                    <div style='background: rgba(15, 23, 42, 0.5); padding: 16px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 12px;'>
                                        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                                            <b style='color: #38bdf8;'>Rapportino N. {rep_num}</b>
                                            <span style='background: rgba(37, 99, 235, 0.2); color: #60a5fa; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;'>{rep_type}</span>
                                        </div>
                                        <p style='margin: 4px 0; color: #cbd5e1; font-size: 0.9rem;'><b>Data:</b> {rep_date} &nbsp;|&nbsp; <b>Tecnici:</b> {rep_tech}</p>
                                        <p style='margin: 8px 0 4px 0; color: #94a3b8; font-size: 0.9rem;'><b>Lavori:</b> {rep_desc}</p>
                                    </div>
                                """, unsafe_allow_html=True)
                                
                                rep_dict = {
                                    "number": rep_num, "client": c_name, "date": rep_date, "duration": rep_dur,
                                    "technician": rep_tech, "type": rep_type, "description": rep_desc,
                                    "expenses": rep_exp, "author": rep_auth
                                }
                                client_obj = {"name": c_name, "address": c_address, "phone": c_phone}
                                
                                if user["role"] in ["amministratore", "sviluppatore"]:
                                    col_dl, col_del_rep = st.columns([1, 1])
                                    with col_dl:
                                        pdf_download(rep_dict, client_obj, f"arch_{rep_num}", f"📥 Scarica N. {rep_num}", lazy=True)
                                    with col_del_rep:
                                        if st.button(f"🗑️ Elimina N. {rep_num}", key=f"del_rep_client_{rep_num}"):
                                            confirm_delete("report", rep_num, f"il rapportino N. {rep_num}")
                                else:
                                    pdf_download(rep_dict, client_obj, f"arch_{rep_num}", f"📥 Scarica N. {rep_num}", lazy=True)

                    if user["role"] in ["amministratore", "sviluppatore"]:
                        if st.button("🗑️ Elimina Cartella e Rapportini", key=f"del_cli_{client_id}"):
                            confirm_delete("client", client_id, f"la cartella di {c_name} con tutti i suoi rapportini", extra=c_name)


# ==========================================
# 2. NUOVO RAPPORTINO
# ==========================================
elif selected_page == "Nuovo Rapportino":
    st.title("📝 Compila Nuovo Rapportino")
    
    conn = get_db_connection()
    res_cli = conn.execute("SELECT name, address, phone FROM clients")
    db_clients = res_cli.fetchall()
    
    res_usr = conn.execute("SELECT name FROM users WHERE role IN ('collaboratore', 'amministratore')")
    db_users = res_usr.fetchall()
    conn.close()
    
    available_technicians = [u[0] for u in db_users]
    
    if not db_clients:
        st.warning("Prima crea almeno un cliente nell'Archivio Clienti!")
    else:
        client_names = [c[0] for c in db_clients]
        
        with st.form("new_report_form"):
            selected_client_name = st.selectbox("Seleziona Cliente", client_names)
            
            raw_report_date = st.date_input("Data Esecuzione", datetime.today())
            report_date = raw_report_date.strftime("%d/%m/%Y")
            
            report_duration = st.text_input("Durata del Servizio (opzionale, es. 2 ore, 09:00 - 11:30)")
            
            selected_technicians = st.multiselect(
                "Tecnici Incaricati (seleziona uno o più operatori)", 
                options=available_technicians,
                default=[user["name"]] if user["name"] in available_technicians else []
            )
            
            report_type = st.selectbox("Tipo Intervento", TIPI_INTERVENTO)
            description = st.text_area("Descrizione dettagliata dei lavori eseguiti")
            
            st.markdown("---")
            st.subheader("Spese Vive / Materiali e Foto (Opzionale)")
            expenses_df = expenses_editor("new_expenses_editor")
            st.caption("Tocca + in fondo alla tabella per aggiungere altre voci.")
            
            uploaded_photo = st.file_uploader("Aggiungi Foto (Scatta o seleziona dalla galleria)", type=["jpg", "jpeg", "png"])

            submit_report = st.form_submit_button("Genera Rapportino e Salva")
            
            if submit_report:
                if not selected_technicians:
                    st.error("Seleziona almeno un tecnico incaricato!")
                else:
                    technicians_str = ", ".join(selected_technicians)
                    
                    conn = get_db_connection()
                    res_max = conn.execute("SELECT MAX(number) FROM reports")
                    max_row = res_max.fetchone()
                    max_num_res = max_row[0] if max_row and max_row[0] is not None else None
                    new_number = (max_num_res + 1) if max_num_res else 1001
                    
                    photo_filename = None
                    if uploaded_photo is not None:
                        os.makedirs("uploads", exist_ok=True)
                        photo_filename = f"uploads/foto_rep_{new_number}_{uploaded_photo.name}"
                        with open(photo_filename, "wb") as f_foto:
                            f_foto.write(uploaded_photo.getbuffer())

                    expenses_json = build_expenses_json(expenses_df, photo_filename)
                    
                    conn.execute("INSERT INTO reports (number, client, date, duration, technician, type, description, expenses, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (new_number, selected_client_name, report_date, report_duration, technicians_str, report_type, description, expenses_json, user["name"]))
                    conn.commit()
                    conn.close()
                    
                    client_tuple = next((c for c in db_clients if c[0] == selected_client_name), None)
                    client_obj = {"name": client_tuple[0], "address": client_tuple[1], "phone": client_tuple[2]}
                    
                    new_rep_dict = {
                        "number": new_number, "client": selected_client_name, "date": report_date,
                        "duration": report_duration, "technician": technicians_str, "type": report_type, 
                        "description": description, "expenses": expenses_json, "author": user["name"]
                    }
                    
                    st.session_state.last_generated_pdf = (
                        get_pdf_bytes(new_rep_dict, client_obj),
                        f"Rapportino_{new_number}.pdf",
                    )

        if isinstance(st.session_state.last_generated_pdf, tuple):
            pdf_bytes, pdf_name = st.session_state.last_generated_pdf
            st.success("Rapportino salvato con successo!")
            st.download_button(
                label="📥 Scarica PDF Rapportino Ufficiale", 
                data=pdf_bytes, file_name=pdf_name, mime="application/pdf"
            )


# ==========================================
# 3. RIEPILOGO MENSILE
# ==========================================
elif selected_page == "Riepilogo Mensile":
    st.title("📊 Riepilogo e Statistiche")
    
    conn = get_db_connection()
    res_cnt_cli = conn.execute("SELECT COUNT(*) FROM clients")
    total_clients = res_cnt_cli.fetchone()[0]
    
    res_all = conn.execute("SELECT number, client, date, duration, technician, type, description, expenses, author FROM reports ORDER BY number DESC")
    all_reports = res_all.fetchall()

    res_cli_all = conn.execute("SELECT name, address, phone FROM clients")
    clients_info = {c[0]: (c[1], c[2]) for c in res_cli_all.fetchall()}
    res_dev = conn.execute("SELECT name FROM users WHERE role = 'sviluppatore'")
    hidden_names = {d[0] for d in res_dev.fetchall()}
    conn.close()

    records = []
    for rep in all_reports:
        rep_num, rep_client, rep_date, rep_dur, rep_tech, rep_type, rep_desc, rep_exp, rep_auth = rep
        records.append({
            "row": rep, "number": rep_num, "client": rep_client or "", "date": rep_date,
            "dt": parse_date(rep_date), "tech": rep_tech or "", "type": rep_type or "",
            "desc": rep_desc or "", "total": expenses_total(rep_exp),
        })

    today = datetime.today()
    years = sorted({r["dt"].year for r in records if r["dt"]}, reverse=True)
    year_options = ["Tutti"] + years
    month_options = ["Tutti"] + MESI
    default_year_idx = year_options.index(today.year) if today.year in years else 0
    default_month_idx = today.month if today.year in years else 0

    col_year, col_month = st.columns(2)
    with col_year:
        sel_year = st.selectbox("Anno", year_options, index=default_year_idx)
    with col_month:
        sel_month = st.selectbox("Mese", month_options, index=default_month_idx)

    with st.expander("🔎 Altri filtri e ricerca"):
        all_clients_names = sorted({r["client"] for r in records if r["client"]})
        all_techs = sorted({t.strip() for r in records for t in r["tech"].split(",") if t.strip() and t.strip() not in hidden_names})
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            f_client = st.selectbox("Cliente", ["Tutti"] + all_clients_names)
        with col_f2:
            f_tech = st.selectbox("Tecnico", ["Tutti"] + all_techs)
        with col_f3:
            f_type = st.selectbox("Tipo intervento", ["Tutti"] + TIPI_INTERVENTO)
        f_text = st.text_input("🔍 Cerca per numero, cliente o descrizione").strip().lower()

    def matches(r):
        if sel_year != "Tutti" and (not r["dt"] or r["dt"].year != sel_year):
            return False
        if sel_month != "Tutti" and (not r["dt"] or r["dt"].month != MESI.index(sel_month) + 1):
            return False
        if f_client != "Tutti" and r["client"] != f_client:
            return False
        if f_tech != "Tutti" and f_tech not in [t.strip() for t in r["tech"].split(",")]:
            return False
        if f_type != "Tutti" and r["type"] != f_type:
            return False
        if f_text and f_text not in str(r["number"]) and f_text not in r["client"].lower() and f_text not in r["desc"].lower():
            return False
        return True

    filtered = [r for r in records if matches(r)]
    period_expenses = sum(r["total"] for r in filtered)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='card' style='text-align: center;'><h4 style='color: #94a3b8;'>Rapportini</h4><h2>{len(filtered)}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card' style='text-align: center;'><h4 style='color: #94a3b8;'>Spese Totali</h4><h2>€ {period_expenses:.2f}</h2></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='card' style='text-align: center;'><h4 style='color: #94a3b8;'>Clienti in Archivio</h4><h2>{total_clients}</h2></div>", unsafe_allow_html=True)
    
    st.markdown("### 📋 Elenco Rapportini")
    
    if not filtered:
        st.info("Nessun rapportino trovato con i filtri selezionati.")
    else:
        lazy_mode = len(filtered) > 10
        for r in filtered:
            rep_num, rep_client, rep_date, rep_dur, rep_tech, rep_type, rep_desc, rep_exp, rep_auth = r["row"]
            
            with st.expander(f"📄 Rapportino N. {rep_num} — Cliente: {rep_client} ({rep_date})"):
                lines = [
                    f"* **Tipo Intervento:** {rep_type}",
                    f"* **Durata Servizio:** {rep_dur if rep_dur else 'Non inserita'}",
                    f"* **Tecnici Incaricati:** {rep_tech}",
                    f"* **Compilato da:** {rep_auth}",
                    f"* **Descrizione Lavori:** {rep_desc}",
                ]
                if r["total"] > 0:
                    lines.append(f"* **Spese:** € {r['total']:.2f}")
                st.markdown("\n".join(lines))
                
                addr, phone = clients_info.get(rep_client, ("", ""))
                cli_obj = {"name": rep_client, "address": addr or "", "phone": phone or ""}
                rep_obj = {
                    "number": rep_num, "client": rep_client, "date": rep_date, "duration": rep_dur,
                    "technician": rep_tech, "type": rep_type, "description": rep_desc, "expenses": rep_exp, "author": rep_auth
                }
                
                pdf_download(rep_obj, cli_obj, f"sum_{rep_num}", f"📥 Scarica PDF N. {rep_num}", lazy=lazy_mode)


# ==========================================
# 4. MODIFICA RAPPORTINO
# ==========================================
elif selected_page == "Modifica Rapportino":
    if user["role"] not in ["sviluppatore", "amministratore"]:
        st.error("Accesso negato. Sezione riservata agli amministratori.")
    else:
        st.title("✏️ Modifica o Elimina Rapportino")
        
        conn = get_db_connection()
        res_list = conn.execute("SELECT number, client, date FROM reports ORDER BY number DESC")
        reports_list = res_list.fetchall()
        
        res_techs = conn.execute("SELECT name FROM users WHERE role IN ('collaboratore', 'amministratore')")
        tech_res = res_techs.fetchall()
        conn.close()
        
        available_technicians = [t[0] for t in tech_res]
        
        if not reports_list:
            st.info("Nessun rapportino disponibile da modificare.")
        else:
            report_options = {f"N. {r[0]} — {r[1]} ({r[2]})": r[0] for r in reports_list}
            
            default_index = 0
            if st.session_state.edit_report_num:
                for i, (label, num) in enumerate(report_options.items()):
                    if num == st.session_state.edit_report_num:
                        default_index = i
                        break
            
            selected_key = st.selectbox("Seleziona il Rapportino da Modificare o Gestire", list(report_options.keys()), index=default_index)
            target_rep_num = report_options[selected_key]
            
            conn = get_db_connection()
            res_rep_data = conn.execute("SELECT client, date, duration, technician, type, description, expenses, author FROM reports WHERE number = ?", (target_rep_num,))
            rep_data = res_rep_data.fetchone()
            
            res_db_cli = conn.execute("SELECT name, address, phone FROM clients")
            db_clients = res_db_cli.fetchall()
            conn.close()
            
            if rep_data:
                c_name, c_date, c_dur, c_tech, c_type, c_desc, c_exp, c_auth = rep_data
                client_names = [c[0] for c in db_clients]
                
                ex_photo_val = existing_photo(c_exp)

                with st.form("edit_report_form"):
                    st.subheader(f"Modifica Completa Rapportino N. {target_rep_num}")
                    
                    new_client = st.selectbox("Cliente", client_names, index=client_names.index(c_name) if c_name in client_names else 0)
                    new_date = st.text_input("Data Intervento (DD/MM/YYYY)", value=c_date)
                    new_duration = st.text_input("Durata Servizio", value=c_dur or "")
                    
                    current_techs_list = [t.strip() for t in c_tech.split(",")]
                    default_techs = [t for t in current_techs_list if t in available_technicians]
                    
                    new_technicians = st.multiselect("Tecnici Incaricati", options=available_technicians, default=default_techs)
                    
                    type_idx = TIPI_INTERVENTO.index(c_type) if c_type in TIPI_INTERVENTO else 0
                    new_type = st.selectbox("Tipo Intervento", TIPI_INTERVENTO, index=type_idx)
                    
                    new_desc = st.text_area("Descrizione dei Lavori Eseguiti", value=c_desc)
                    
                    st.markdown("---")
                    st.subheader("Gestione Spese / Materiali e Foto")
                    new_expenses_df = expenses_editor(f"edit_expenses_editor_{target_rep_num}", c_exp)
                    st.caption("Tocca + in fondo alla tabella per aggiungere altre voci.")
                    
                    new_uploaded_photo = st.file_uploader("Sostituisci o Aggiungi Foto", type=["jpg", "jpeg", "png"])
                    
                    submit_edit = st.form_submit_button("💾 Salva Tutte le Modifiche")
                    
                    if submit_edit:
                        if not new_technicians:
                            st.error("Seleziona almeno un tecnico!")
                        else:
                            techs_string = ", ".join(new_technicians)
                            
                            # Gestione foto salvata
                            photo_filename = ex_photo_val
                            if new_uploaded_photo is not None:
                                os.makedirs("uploads", exist_ok=True)
                                photo_filename = f"uploads/foto_rep_{target_rep_num}_{new_uploaded_photo.name}"
                                with open(photo_filename, "wb") as f_foto:
                                    f_foto.write(new_uploaded_photo.getbuffer())

                            expenses_json = build_expenses_json(new_expenses_df, photo_filename)

                            conn = get_db_connection()
                            conn.execute("""
                                UPDATE reports 
                                SET client = ?, date = ?, duration = ?, technician = ?, type = ?, description = ?, expenses = ?
                                WHERE number = ?
                            """, (new_client, new_date, new_duration, techs_string, new_type, new_desc, expenses_json, target_rep_num))
                            conn.commit()
                            conn.close()
                            
                            st.success(f"Rapportino N. {target_rep_num} aggiornato con successo in tutti i campi!")
                            st.session_state.edit_report_num = None

                st.markdown("---")
                if st.button(f"🗑️ Elimina Definitivamente il Rapportino N. {target_rep_num}", key=f"del_single_from_edit_{target_rep_num}"):
                    confirm_delete("report", target_rep_num, f"il rapportino N. {target_rep_num}")


# ==========================================
# 5. GESTIONE UTENTI
# ==========================================
elif selected_page == "Gestione Utenti":
    if user["role"] not in ["sviluppatore", "amministratore"]:
        st.error("Accesso negato. Sezione riservata.")
    else:
        st.title("👥 Gestione Utenti")
        
        with st.form("new_user_form"):
            st.subheader("➕ Aggiungi Nuovo Utente")
            new_username = st.text_input("Nome Utente")
            new_name = st.text_input("Nome e Cognome Completo")
            new_pin = st.text_input("Password", type="password")
            
            if user["role"] == "sviluppatore":
                new_role = st.selectbox("Ruolo", ["collaboratore", "amministratore", "sviluppatore"])
            else:
                new_role = st.selectbox("Ruolo", ["collaboratore", "amministratore"])
            
            if st.form_submit_button("Crea Utente") and new_username and new_pin:
                new_username = new_username.strip()
                conn = get_db_connection()
                already = conn.execute("SELECT 1 FROM users WHERE username = ?", (new_username,)).fetchone()
                if already:
                    conn.close()
                    st.error("Esiste già un utente con questo nome. Per cambiare la password usa «Reimposta password» nell'elenco qui sotto.")
                elif len(new_pin) < MIN_PASSWORD_LEN:
                    conn.close()
                    st.error(f"La password deve avere almeno {MIN_PASSWORD_LEN} caratteri.")
                else:
                    pin_hash = hashlib.sha256(new_pin.encode()).hexdigest()
                    conn.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)",
                                 (new_username, new_name, pin_hash, "", new_role))
                    conn.commit()
                    conn.close()
                    st.session_state.flash = "Utente creato con successo!"
                    st.rerun()

        st.markdown("---")
        st.subheader("📋 Elenco Utenti Registrati")

        conn = get_db_connection()
        res_usr_list = conn.execute("SELECT username, name, role FROM users")
        db_users = res_usr_list.fetchall()
        conn.close()
        
        for uname, u_name, u_role in db_users:
            if user["role"] == "amministratore" and u_role == "sviluppatore":
                continue

            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.markdown(f"<b>{u_name}</b> (Username: <code>{uname}</code>) - Ruolo: <em>{u_role}</em>", unsafe_allow_html=True)
            with col_del:
                if uname not in ["DEV", "Salvatore", "Pietro"] and u_role != "sviluppatore":
                    if st.button("🗑️ Elimina", key=f"del_u_{uname}"):
                        confirm_delete("user", uname, f"l'utente {u_name}")

            with st.expander(f"🔑 Reimposta password di {u_name}"):
                with st.form(f"reset_form_{uname}"):
                    reset_pw = st.text_input("Nuova password", type="password", key=f"reset_pw_{uname}")
                    if st.form_submit_button("Salva nuova password"):
                        if len(reset_pw) < MIN_PASSWORD_LEN:
                            st.error(f"La password deve avere almeno {MIN_PASSWORD_LEN} caratteri.")
                        else:
                            conn = get_db_connection()
                            conn.execute("UPDATE users SET pin = ?, raw_pin = '' WHERE username = ?",
                                         (hashlib.sha256(reset_pw.encode()).hexdigest(), uname))
                            conn.execute("DELETE FROM sessions WHERE username = ?", (uname,))
                            conn.commit()
                            conn.close()
                            st.session_state.flash = f"Password di {u_name} aggiornata."
                            st.rerun()
