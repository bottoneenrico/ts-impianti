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


# --- CONFIGURAZIONE DATABASE (TURSO CLOUD + FALLBACK LOCALE) ---
def get_db_connection():
    """
    Stabilisce la connessione con Turso Cloud DB usando HTTPS/libsql-client.
    Se la libreria o i dati mancano, effettua il fallback su SQLite locale.
    """
    turso_url = st.secrets.get("TURSO_DATABASE_URL", "")
    turso_token = st.secrets.get("TURSO_AUTH_TOKEN", "")

    if turso_url.startswith("libsql://"):
        turso_url = turso_url.replace("libsql://", "https://")

    if TURSO_AVAILABLE and turso_url and turso_token:
        try:
            conn = libsql_client.create_client_sync(url=turso_url, auth_token=turso_token)
            return conn
        except Exception as e:
            st.error(f"Errore di connessione a Turso Cloud: {e}")
            return sqlite3.connect("gestionale.db", check_same_thread=False)
    else:
        return sqlite3.connect("gestionale.db", check_same_thread=False)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabella Utenti
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name TEXT,
            pin TEXT,
            raw_pin TEXT,
            role TEXT
        )
    ''')
    
    # Tabella Clienti
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            group_name TEXT,
            address TEXT,
            phone TEXT
        )
    ''')
    
    # Tabella Rapportini
    cursor.execute('''
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
    
    # 1. Utente DEV
    dev_pin_raw = "enricobottone@"
    dev_pin_hash = hashlib.sha256(dev_pin_raw.encode()).hexdigest()
    cursor.execute("DELETE FROM users WHERE username = 'ADMIN'")
    cursor.execute("SELECT * FROM users WHERE username = 'DEV'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                       ("DEV", "Enrico Bottone", dev_pin_hash, dev_pin_raw, "sviluppatore"))
    else:
        cursor.execute("UPDATE users SET name = 'Enrico Bottone', pin = ?, raw_pin = ?, role = 'sviluppatore' WHERE username = 'DEV'", (dev_pin_hash, dev_pin_raw))

    # 2. Utente Salvatore
    salvatore_username = "Salvatore"
    salvatore_name = "Salvatore Tammaro"
    salvatore_pin_raw = "TSimpianti@"
    salvatore_pin_hash = hashlib.sha256(salvatore_pin_raw.encode()).hexdigest()
    cursor.execute("DELETE FROM users WHERE username = 'SALVATORE'")
    cursor.execute("SELECT * FROM users WHERE username = ?", (salvatore_username,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                       (salvatore_username, salvatore_name, salvatore_pin_hash, salvatore_pin_raw, "amministratore"))
    else:
        cursor.execute("UPDATE users SET name = ?, pin = ?, raw_pin = ?, role = 'amministratore' WHERE username = ?", (salvatore_name, salvatore_pin_hash, salvatore_pin_raw, salvatore_username))

    # 3. Utente Pietro
    pietro_username = "Pietro"
    pietro_name = "Pietro"
    pietro_pin_raw = "121207@"
    pietro_pin_hash = hashlib.sha256(pietro_pin_raw.encode()).hexdigest()
    cursor.execute("SELECT * FROM users WHERE username = ?", (pietro_username,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                       (pietro_username, pietro_name, pietro_pin_hash, pietro_pin_raw, "collaboratore"))
    else:
        cursor.execute("UPDATE users SET name = ?, pin = ?, raw_pin = ?, role = 'collaboratore' WHERE username = ?", (pietro_name, pietro_pin_hash, pietro_pin_raw, pietro_username))

    conn.commit()
    cursor.close()
    conn.close()

# Inizializzazione DB
init_db()

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="TS Impianti — Gestionale",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stile Grafico CSS
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

# Gestione della sessione utente
if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "last_generated_pdf" not in st.session_state:
    st.session_state.last_generated_pdf = None

if "edit_report_num" not in st.session_state:
    st.session_state.edit_report_num = None


def delete_single_report(report_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reports WHERE number = ?", (report_number,))
    conn.commit()
    cursor.close()
    conn.close()
    
    pdf_filename = f"Rapportino_{report_number}.pdf"
    if os.path.exists(pdf_filename):
        try:
            os.remove(pdf_filename)
        except Exception:
            pass


# --- GENERAZIONE PDF DINAMICA (NASCONDE I CAMPI NON COMPILATI) ---
def generate_pdf(report, client):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    filename = f"Rapportino_{report['number']}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Intestazione TS Impianti
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
    
    # --- COLONNA SINISTRA: DATI INTERVENTO (DINAMICA) ---
    c.setFont("Helvetica", 10)
    y_left = height - 130
    
    if report.get('date'):
        c.drawString(50, y_left, f"Data Intervento: {report['date']}")
        y_left -= 15

    # Mostra la durata solo se è stata inserita ed è diversa da stringa vuota o "N/D"
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

    # --- COLONNA DESTRA: DATI CLIENTE (DINAMICA) ---
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

    # Calcola l'altezza da cui far partire la descrizione lavori
    y_next = min(y_left, y_right) - 20

    # --- DESCRIZIONE LAVORI ---
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

    # --- SPESE VIVE E FOTO (MOSTRATE SOLO SE PRESENTI) ---
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
            c.drawString(70, y_next - 5, f"Totale Spese: € {total_expense:.2f}")
            y_next -= 25

    # Se c'era solo la foto salvata senza testi di spesa
    if not photo_to_draw and expenses_list:
        for e in expenses_list:
            if e.get('photo') and os.path.exists(e['photo']):
                photo_to_draw = e['photo']

    if photo_to_draw:
        try:
            c.setFont("Helvetica-Bold", 11)
            c.drawString(50, y_next - 10, "FOTO ALLEGATA:")
            c.drawImage(photo_to_draw, 50, y_next - 150, width=180, height=120, preserveAspectRatio=True, anchor='nw')
        except Exception:
            pass

    # --- FIRME ---
    c.setFont("Helvetica", 10)
    c.line(50, 90, 200, 90)
    c.drawString(50, 75, "Firma Tecnico")

    c.line(350, 90, 500, 90)
    c.drawString(350, 75, "Firma Cliente")

    c.save()
    return filename


# --- SISTEMA DI LOGIN ---
if not st.session_state.logged_user:
    st.markdown("<h2 style='text-align: center; margin-bottom: 25px;'>⚡ TS IMPIANTI</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        with st.form("login_form"):
            st.markdown("<h3 style='text-align: center; margin-bottom: 20px; color: #38bdf8;'>ACCESSO RISERVATO</h3>", unsafe_allow_html=True)
            
            username_input = st.text_input("Nome Utente (es. Salvatore / Pietro)").strip()
            pin_input = st.text_input("Password / PIN", type="password")
            
            st.write("") 
            submit_login = st.form_submit_button("Accedi al Gestionale", use_container_width=True)
            
            if submit_login:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT name, pin, role FROM users WHERE username = ?", (username_input,))
                user_record = cursor.fetchone()
                cursor.close()
                conn.close()
                
                hashed_input_pin = hashlib.sha256(pin_input.encode()).hexdigest()
                
                if user_record and user_record[1] == hashed_input_pin:
                    st.session_state.logged_user = {
                        "username": username_input,
                        "name": user_record[0],
                        "role": user_record[2]
                    }
                    st.success(f"Accesso riuscito! Benvenuto, {user_record[0]}")
                    st.rerun()
                else:
                    st.error("Nome utente o password errati.")
    st.stop()


# --- BARRA DI NAVIGAZIONE ---
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
    "📊 &nbsp; Riepilogo Mensile": "Riepilogo Mensile",
    "✏️ &nbsp; Modifica Rapportino": "Modifica Rapportino"
}

if user["role"] in ["sviluppatore", "amministratore"]:
    menu_options["👥 &nbsp; Gestione Utenti"] = "Gestione Utenti"

selected_label = st.sidebar.radio("Navigazione", list(menu_options.keys()), label_visibility="collapsed")
selected_page = menu_options[selected_label]

st.sidebar.markdown("---")
if st.sidebar.button("🔒 &nbsp; Effettua il Logout", use_container_width=True):
    st.session_state.logged_user = None
    st.rerun()


# ==========================================
# 1. ARCHIVIO CLIENTI
# ==========================================
if selected_page == "Archivio Clienti":
    st.title("📁 Archivio Clienti & Commesse")
    st.write("Seleziona o cerca un cliente per visualizzare la sua anagrafica e lo storico completo dei rapportini.")
    
    with st.expander("➕ Aggiungi Nuovo Cliente / Cartella"):
        with st.form("new_client_form"):
            c_name = st.text_input("Nome Cliente / Azienda")
            c_group = st.text_input("Gruppo / Commessa")
            c_address = st.text_input("Indirizzo")
            c_phone = st.text_input("Telefono")
            
            submit_client = st.form_submit_button("Crea Cartella Cliente")
            if submit_client and c_name:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO clients (name, group_name, address, phone) VALUES (?, ?, ?, ?)",
                               (c_name, c_group, c_address, c_phone))
                conn.commit()
                cursor.close()
                conn.close()
                st.success(f"Cartella per '{c_name}' creata con successo!")
                st.rerun()

    st.markdown("---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, group_name, address, phone FROM clients")
    clients_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
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
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT number, date, duration, technician, type, description, expenses, author FROM reports WHERE client = ? ORDER BY number DESC", (c_name,))
                        client_reports = cursor.fetchall()
                        cursor.close()
                        conn.close()
                        
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
                                pdf_path = generate_pdf(rep_dict, client_obj)
                                
                                col_dl, col_edit, col_del_rep = st.columns([2, 2, 2])
                                with col_dl:
                                    with open(pdf_path, "rb") as f:
                                        st.download_button(
                                            label=f"📥 Scarica N. {rep_num}",
                                            data=f, file_name=pdf_path, mime="application/pdf",
                                            key=f"dl_rep_{rep_num}"
                                        )
                                with col_edit:
                                    if st.button(f"✏️ Modifica N. {rep_num}", key=f"edit_from_client_{rep_num}"):
                                        st.session_state.edit_report_num = rep_num
                                        st.rerun()
                                with col_del_rep:
                                    if st.button(f"🗑️ Elimina N. {rep_num}", key=f"del_rep_client_{rep_num}"):
                                        delete_single_report(rep_num)
                                        st.success(f"Rapportino N. {rep_num} eliminato.")
                                        st.rerun()

                    if user["role"] in ["amministratore", "sviluppatore"]:
                        if st.button(f"🗑️ Elimina Cartella Cliente e Rapportini: {c_name}", key=f"del_cli_{client_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
                            cursor.execute("DELETE FROM reports WHERE client = ?", (c_name,))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"Cartella cliente '{c_name}' eliminata.")
                            st.rerun()


# ==========================================
# 2. NUOVO RAPPORTINO
# ==========================================
elif selected_page == "Nuovo Rapportino":
    st.title("📝 Compila Nuovo Rapportino")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, address, phone FROM clients")
    db_clients = cursor.fetchall()
    
    cursor.execute("SELECT name FROM users WHERE role IN ('collaboratore', 'amministratore')")
    db_users = cursor.fetchall()
    cursor.close()
    conn.close()
    
    available_technicians = [u[0] for u in db_users]
    
    if not db_clients:
        st.
