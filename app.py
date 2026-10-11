import os
import hashlib
import json
from datetime import datetime
import streamlit as st
import sqlite3

# Tenta di importare il client leggero per Turso
try:
    import libsql_client
    TURSO_AVAILABLE = True
except ImportError:
    TURSO_AVAILABLE = False


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
    
    dev_pin_raw = "enricobottone@"
    dev_pin_hash = hashlib.sha256(dev_pin_raw.encode()).hexdigest()
    conn.execute("DELETE FROM users WHERE username = 'ADMIN'")
    res = conn.execute("SELECT * FROM users WHERE username = 'DEV'")
    if not res.fetchone():
        conn.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                     ("DEV", "Enrico Bottone", dev_pin_hash, dev_pin_raw, "sviluppatore"))
    else:
        conn.execute("UPDATE users SET name = 'Enrico Bottone', pin = ?, raw_pin = ?, role = 'sviluppatore' WHERE username = 'DEV'", (dev_pin_hash, dev_pin_raw))

    salvatore_username = "Salvatore"
    salvatore_name = "Salvatore Tammaro"
    salvatore_pin_raw = "TSimpianti@"
    salvatore_pin_hash = hashlib.sha256(salvatore_pin_raw.encode()).hexdigest()
    conn.execute("DELETE FROM users WHERE username = 'SALVATORE'")
    res = conn.execute("SELECT * FROM users WHERE username = ?", (salvatore_username,))
    if not res.fetchone():
        conn.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                     (salvatore_username, salvatore_name, salvatore_pin_hash, salvatore_pin_raw, "amministratore"))
    else:
        conn.execute("UPDATE users SET name = ?, pin = ?, raw_pin = ?, role = 'amministratore' WHERE username = ?", (salvatore_name, salvatore_pin_hash, salvatore_pin_raw, salvatore_username))

    pietro_username = "Pietro"
    pietro_name = "Pietro"
    pietro_pin_raw = "121207@"
    pietro_pin_hash = hashlib.sha256(pietro_pin_raw.encode()).hexdigest()
    res = conn.execute("SELECT * FROM users WHERE username = ?", (pietro_username,))
    if not res.fetchone():
        conn.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                     (pietro_username, pietro_name, pietro_pin_hash, pietro_pin_raw, "collaboratore"))
    else:
        conn.execute("UPDATE users SET name = ?, pin = ?, raw_pin = ?, role = 'collaboratore' WHERE username = ?", (pietro_name, pietro_pin_hash, pietro_pin_raw, pietro_username))

    conn.commit()
    conn.close()

init_db()

st.set_page_config(
    page_title="TS Impianti — Gestionale",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        background: radial-gradient(circle at 10% 20%, #0f172a 0%, #020617 90%);
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    
    .card, [data-testid="stForm"] {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }

    .stButton>button, [data-testid="stFormSubmitButton"]>button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border-radius: 10px;
        font-weight: 600;
        border: none;
        padding: 10px 24px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton>button:hover, [data-testid="stFormSubmitButton"]>button:hover {
        background: linear-gradient(135deg, #1d4ed8 100%, #1e40af 100%);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.5);
        transform: translateY(-1px);
    }

    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stTextArea>div>div>textarea {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #f1f5f9 !important;
        border-radius: 10px !important;
    }

    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: #f8fafc;
    }
    h1 {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    [data-testid="stSidebar"] {
        background-color: #080c14;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        padding-top: 10px;
    }
    
    [data-testid="stSidebar"] .stRadio label {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-radius: 10px;
        padding: 10px 14px;
        color: #cbd5e1;
        font-weight: 500;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "last_generated_pdf" not in st.session_state:
    st.session_state.last_generated_pdf = None

if "edit_report_num" not in st.session_state:
    st.session_state.edit_report_num = None


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


def generate_pdf(report, client):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    filename = f"Rapportino_{report['number']}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.14, 0.38, 0.92) 
    c.drawString(50, height - 50, "TS IMPIANTI — di Tammaro Salvatore")
    
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, height - 65, "Impianti Elettrici Civili e Industriali")
    
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.line(50, height - 75, width - 50, height - 75)

    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, height - 105, f"RAPPORTINO DI INTERVENTO N. {report['number']}")
    
    c.setFont("Helvetica", 10)
    y_left = height - 130
    
    if report.get('date'):
        c.drawString(50, y_left, f"Data Intervento: {report['date']}")
        y_left -= 15

    duration_val = (report.get('duration') or "").strip()
    if duration_val and duration_val.upper() != "N/D":
        c.drawString(50, y_left, f"Durata Servizio: {duration_val}")
        y_left -= 15

    if report.get('type'):
        c.drawString(50, y_left, f"Tipo Intervento: {report['type']}")
        y_left -= 15

    if report.get('technician'):
        c.drawString(50, y_left, f"Tecnici Incaricati: {report['technician']}")
        y_left -= 15

    if report.get('author'):
        c.drawString(50, y_left, f"Compilato da: {report['author']}")
        y_left -= 15

    c.setFont("Helvetica-Bold", 11)
    c.drawString(320, height - 130, "DATI CLIENTE:")
    c.setFont("Helvetica", 10)
    
    y_right = height - 145
    if client.get('name'):
        c.drawString(320, y_right, f"Cliente: {client['name']}")
        y_right -= 15

    address_val = (client.get('address') or "").strip()
    if address_val and address_val.upper() != "N/D":
        c.drawString(320, y_right, f"Indirizzo: {address_val}")
        y_right -= 15

    phone_val = (client.get('phone') or "").strip()
    if phone_val and phone_val.upper() != "N/D":
        c.drawString(320, y_right, f"Telefono: {phone_val}")
        y_right -= 15

    y_next = min(y_left, y_right) - 20

    desc_text = (report.get('description') or "").strip()
    if desc_text:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y_next, "DESCRIZIONE DEI LAVORI ESEGUITI:")
        y_next -= 18

        c.setFont("Helvetica", 10)
        text_object = c.beginText(50, y_next)
        text_object.setFont("Helvetica", 10)
        lines = desc_text.split('\n')
        for line in lines:
            text_object.textLine(line)
        c.drawText(text_object)
        y_next -= (len(lines) * 14) + 15

    expenses_list = []
    if report.get('expenses'):
        try:
            expenses_list = json.loads(report['expenses'])
        except Exception:
            expenses_list = []

    photo_to_draw = None
    total_expense = 0

    valid_expenses = [e for e in expenses_list if e.get('item') or (e.get('amount', 0) > 0)]
    
    if valid_expenses:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y_next, "SPESE VIVE E MATERIALI:")
        y_next -= 18

        for expense in valid_expenses:
            c.setFont("Helvetica", 10)
            item_name = expense.get('item', 'Spesa generica')
            amt = expense.get('amount', 0.0)
            c.drawString(70, y_next, f"- {item_name}")
            c.drawString(350, y_next, f"€ {amt:.2f}")
            total_expense += amt
            y_next -= 15

            if expense.get('photo') and os.path.exists(expense['photo']):
                photo_to_draw = expense['photo']

        if total_expense > 0:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(70, y_
