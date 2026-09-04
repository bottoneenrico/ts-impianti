import os
import hashlib
import json
from datetime import datetime
import streamlit as st
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DB_FILE = "gestionale.db"

# --- CONFIGURAZIONE DATABASE LOCALE ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

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
            technician TEXT,
            type TEXT,
            description TEXT,
            expenses TEXT,
            author TEXT
        )
    ''')
    
    # Inserisci utente admin di default se non esiste
    cursor.execute("SELECT * FROM users WHERE username = 'ADMIN'")
    if not cursor.fetchone():
        admin_pin_hash = hashlib.sha256("2231eb".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)", 
                       ("ADMIN", "Enrico Bottone", admin_pin_hash, "2231eb", "amministratore"))
    
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# Configurazione della pagina
st.set_page_config(
    page_title="TS Impianti — Gestionale",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAZIONE STILE CSS ---
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
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.5);
        transform: translateY(-1px);
    }

    /* Fix visibilità input e textarea */
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stTextArea>div>div>textarea {
        background-color: #0b1329 !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
        color: #ffffff !important;
        border-radius: 10px !important;
    }
    
    .stTextArea textarea {
        color: #ffffff !important;
        font-size: 1rem !important;
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

# Gestione sessione utente
if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

if "last_generated_pdf" not in st.session_state:
    st.session_state.last_generated_pdf = None


# --- FUNZIONE GENERAZIONE PDF ---
def generate_pdf(report, client):
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
    c.drawString(50, height - 130, f"Data Intervento: {report['date']}")
    c.drawString(50, height - 145, f"Tipo Intervento: {report['type']}")
    c.drawString(50, height - 160, f"Tecnico Incaricato: {report['technician']}")
    c.drawString(50, height - 175, f"Compilato da: {report['author']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(300, height - 130, "DATI CLIENTE:")
    c.setFont("Helvetica", 10)
    c.drawString(300, height - 145, f"Cliente: {client['name']}")
    c.drawString(300, height - 160, f"Indirizzo: {client['address']}")
    c.drawString(300, height - 175, f"Telefono: {client['phone']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 215, "DESCRIZIONE DEI LAVORI ESEGUITI:")
    c.setFont("Helvetica", 10)
    
    text_object = c.beginText(50, height - 235)
    text_object.setFont("Helvetica", 10)
    for line in report['description'].split('\n'):
        text_object.textLine(line)
    c.drawText(text_object)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 330, "SPESE VIVE E MATERIALI:")
    y_pos = height - 350
    total_expense = 0
    expenses_list = json.loads(report['expenses'])
    for expense in expenses_list:
        c.setFont("Helvetica", 10)
        c.drawString(70, y_pos, f"- {expense['item']}")
        c.drawString(350, y_pos, f"€ {expense['amount']:.2f}")
        total_expense += expense['amount']
        y_pos -= 15
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, y_pos - 10, f"Totale Spese: € {total_expense:.2f}")

    c.line(50, 120, 200, 120)
    c.drawString(50, 105, "Firma Tecnico")

    c.line(350, 120, 500, 120)
    c.drawString(350, 105, "Firma Cliente")

    c.save()
    return filename


# --- SISTEMA DI LOGIN ---
if not st.session_state.logged_user:
    st.markdown("<h2 style='text-align: center; margin-bottom: 25px;'>⚡ TS IMPIANTI</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h3 style='text-align: center; margin-bottom: 20px; color: #38bdf8;'>ACCESSO RISERVATO</h3>", unsafe_allow_html=True)
            username_input = st.text_input("Nome Utente").upper()
            pin_input = st.text_input("PIN Personale", type="password")
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
                    st.rerun()
                else:
                    st.error("Nome utente o PIN errati.")
    st.stop()


# --- BARRA DI NAVIGAZIONE ---
user = st.session_state.logged_user

st.sidebar.markdown(f"👤 **{user['name']}**")
st.sidebar.markdown(f"Ruolo: `{user['role'].upper()}`")
st.sidebar.markdown("---")

menu_options = {
    "📁 &nbsp; Archivio Clienti": "Archivio Clienti",
    "📝 &nbsp; Nuovo Rapportino": "Nuovo Rapportino",
    "📊 &nbsp; Riepilogo Mensile": "Riepilogo Mensile"
}

if user["role"] == "amministratore":
    menu_options["👥 &nbsp; Gestione Utenti"] = "Gestione Utenti"
    menu_options["⚙️ &nbsp; Gestione Backup (Admin)"] = "Gestione Backup"

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
                st.success(f"Cartella per '{c_name}' creata!")
                st.rerun()

    st.markdown("---")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, group_name, address, phone FROM clients")
    clients_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if clients_data:
        search_query = st.text_input("🔍 Cerca cliente o commessa...").lower()
        for client_id, c_name, c_group, c_address, c_phone in clients_data:
            if search_query in c_name.lower() or search_query in (c_group or "").lower():
                with st.expander(f"🏢 {c_name} — Commessa: {c_group or 'N/D'}"):
                    st.write(f"**Indirizzo:** {c_address or 'N/D'} | **Telefono:** {c_phone or 'N/D'}")
                    if user["role"] == "amministratore":
                        if st.button(f"🗑️ Elimina Cartella: {c_name}", key=f"del_{client_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.rerun()


# ==========================================
# 2. NUOVO RAPPORTINO (Corretto)
# ==========================================
elif selected_page == "Nuovo Rapportino":
    st.title("📝 Compila Nuovo Rapportino")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, address, phone FROM clients")
    db_clients = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not db_clients:
        st.warning("Prima crea almeno un cliente nell'Archivio Clienti!")
    else:
        client_names = [c[0] for c in db_clients]
        
        with st.form("new_report_form"):
            selected_client_name = st.selectbox("Seleziona Cliente", client_names)
            report_date = st.date_input("Data Esecuzione", datetime.today())
            technician_name = st.text_input("Tecnico Incaricato", value=user["name"])
            report_type = st.selectbox("Tipo Intervento", ["Ordinario", "Straordinario", "Collaudo", "Guasto"])
            
            # Casella di descrizione con visibilità forzata del testo
            description = st.text_area("Descrizione dettagliata dei lavori eseguiti", placeholder="Scrivi qui i dettagli dell'intervento...")
            
            st.markdown("---")
            st.subheader("Spese Vive / Materiali")
            expense_item = st.text_input("Voce Spesa")
            expense_amount = st.number_input("Importo (€)", min_value=0.0, step=0.5)

            submit_report = st.form_submit_button("Genera Rapportino e Salva")
            
            if submit_report:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(number) FROM reports")
                max_num_res = cursor.fetchone()[0]
                new_number = (max_num_res + 1) if max_num_res else 1001
                
                expenses_json = json.dumps([{"item": expense_item, "amount": expense_amount}] if expense_item else [])
                
                cursor.execute("INSERT INTO reports (number, client, date, technician, type, description, expenses, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (new_number, selected_client_name, str(report_date), technician_name, report_type, description, expenses_json, user["name"]))
                conn.commit()
                cursor.close()
                conn.close()
                
                client_tuple = next((c for c in db_clients if c[0] == selected_client_name), None)
                client_obj = {"name": client_tuple[0], "address": client_tuple[1], "phone": client_tuple[2]}
                
                new_rep_dict = {
                    "number": new_number, "client": selected_client_name, "date": str(report_date),
                    "technician": technician_name, "type": report_type, "description": description,
                    "expenses": expenses_json, "author": user["name"]
                }
                
                st.session_state.last_generated_pdf = generate_pdf(new_rep_dict, client_obj)

        if st.session_state.last_generated_pdf and os.path.exists(st.session_state.last_generated_pdf):
            st.success("Rapportino salvato con successo!")
            with open(st.session_state.last_generated_pdf, "rb") as f:
                st.download_button(
                    label="📥 Scarica PDF Rapportino Ufficiale", 
                    data=f, file_name=st.session_state.last_generated_pdf, mime="application/pdf"
                )


# ==========================================
# 3. RIEPILOGO MENSILE
# ==========================================
elif selected_page == "Riepilogo Mensile":
    st.title("📊 Riepilogo e Statistiche")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clients")
    total_clients = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='card' style='text-align: center;'><h4>Totale Rapportini</h4><h2>{total_reports}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card' style='text-align: center;'><h4>Clienti in Archivio</h4><h2>{total_clients}</h2></div>", unsafe_allow_html=True)


# ==========================================
# 4. GESTIONE UTENTI
# ==========================================
elif selected_page == "Gestione Utenti":
    if user["role"] == "amministratore":
        st.title("👥 Gestione Utenti")
        with st.form("new_user_form"):
            new_username = st.text_input("Nome Utente").upper()
            new_name = st.text_input("Nome e Cognome Completo")
            new_pin = st.text_input("PIN Personale", type="password")
            new_role = st.selectbox("Ruolo", ["collaboratore", "amministratore"])
            if st.form_submit_button("Crea Utente") and new_username and new_pin:
                conn = get_db_connection()
                cursor = conn.cursor()
                pin_hash = hashlib.sha256(new_pin.encode()).hexdigest()
                cursor.execute("INSERT OR REPLACE INTO users (username, name, pin, raw_pin, role) VALUES (?, ?, ?, ?, ?)",
                               (new_username, new_name, pin_hash, new_pin, new_role))
                conn.commit()
                cursor.close()
                conn.close()
                st.success("Utente creato!")
                st.rerun()


# ==========================================
# 5. GESTIONE BACKUP
# ==========================================
elif selected_page == "Gestione Backup":
    if user["role"] == "amministratore":
        st.title("⚙️ Gestione Backup Database")
        col_bk1, col_bk2 = st.columns(2)
        with col_bk1:
            st.subheader("1. Scarica Backup")
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    st.download_button("📥 Scarica File `gestionale.db`", data=f, file_name="gestionale.db", mime="application/octet-stream", use_container_width=True)
        with col_bk2:
            st.subheader("2. Ripristina Backup")
            uploaded_db = st.file_uploader("Carica file `gestionale.db`", type=["db"])
            if uploaded_db is not None and st.button("🔄 Conferma Ripristino", use_container_width=True):
                with open(DB_FILE, "wb") as f:
                    f.write(uploaded_db.getbuffer())
                st.success("Ripristinato con successo!")
                st.rerun()
