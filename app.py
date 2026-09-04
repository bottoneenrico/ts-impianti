import os
import hashlib
from datetime import datetime
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Configurazione della pagina (deve essere il primo comando Streamlit)
st.set_page_config(
    page_title="TS Impianti — Gestionale",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONFIGURAZIONE STILE CSS (Tema Modern Dark Glassmorphism) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        background: radial-gradient(circle at 10% 20%, #0f172a 0%, #020617 90%);
        color: #f1f5f9;
        font-family: 'Inter', sans-serif;
    }
    
    /* Stile Card Moderno */
    .card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .card:hover {
        border-color: rgba(56, 189, 248, 0.3);
    }

    /* Bottoni moderni */
    .stButton>button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border-radius: 10px;
        font-weight: 600;
        border: none;
        padding: 10px 24px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.5);
        transform: translateY(-1px);
    }

    /* Input e form puliti */
    .stTextInput>div>div>input, .stSelectbox>div>div>select, .stTextArea>div>div>textarea {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #f1f5f9 !important;
        border-radius: 10px !important;
    }
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>select:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2) !important;
    }

    /* Tipografia */
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
    
    /* Sidebar personalizzata */
    [data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- GESTIONE DATI IN SESSIONE (Database temporaneo in memoria per test) ---
if "users" not in st.session_state:
    admin_pin_hash = hashlib.sha256("2231eb".encode()).hexdigest()
    st.session_state.users = {
        "ADMIN": {"name": "Salvatore Tammaro", "pin": admin_pin_hash, "role": "amministratore"}
    }

if "clients" not in st.session_state:
    st.session_state.clients = []

if "reports" not in st.session_state:
    st.session_state.reports = []

if "logged_user" not in st.session_state:
    st.session_state.logged_user = None


# --- FUNZIONE GENERAZIONE PDF (ReportLab) ---
def generate_pdf(report, client):
    filename = f"Rapportino_{report['number']}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Intestazione Aziendale
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.14, 0.38, 0.92) # Blu tecnico
    c.drawString(50, height - 50, "TS IMPIANTI — di Salvatore Tammaro")
    
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, height - 65, "Impianti Elettrici Civili e Industriali")
    
    # Linea divisoria
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.line(50, height - 75, width - 50, height - 75)

    # Dati Rapportino
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, height - 105, f"RAPPORTINO DI INTERVENTO N. {report['number']}")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 130, f"Data Intervento: {report['date']}")
    c.drawString(50, height - 145, f"Tipo Intervento: {report['type']}")
    c.drawString(50, height - 160, f"Tecnico Incaricato: {report['technician']}")
    c.drawString(50, height - 175, f"Compilato da: {report['author']}")

    # Dati Cliente
    c.setFont("Helvetica-Bold", 11)
    c.drawString(300, height - 130, "DATI CLIENTE:")
    c.setFont("Helvetica", 10)
    c.drawString(300, height - 145, f"Cliente: {client['name']}")
    c.drawString(300, height - 160, f"Indirizzo: {client['address']}")
    c.drawString(300, height - 175, f"Telefono: {client['phone']}")

    # Descrizione Lavori
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 215, "DESCRIZIONE DEI LAVORI ESEGUITI:")
    c.setFont("Helvetica", 10)
    
    text_object = c.beginText(50, height - 235)
    text_object.setFont("Helvetica", 10)
    for line in report['description'].split('\n'):
        text_object.textLine(line)
    c.drawText(text_object)

    # Spese Vive
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 330, "SPESE VIVE E MATERIALI:")
    y_pos = height - 350
    total_expense = 0
    for expense in report['expenses']:
        c.setFont("Helvetica", 10)
        c.drawString(70, y_pos, f"- {expense['item']}")
        c.drawString(350, y_pos, f"€ {expense['amount']:.2f}")
        total_expense += expense['amount']
        y_pos -= 15
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, y_pos - 10, f"Totale Spese: € {total_expense:.2f}")

    # Spazio Firme
    c.line(50, 120, 200, 120)
    c.drawString(50, 105, "Firma Tecnico")

    c.line(350, 120, 500, 120)
    c.drawString(350, 105, "Firma Cliente")

    c.save()
    return filename


# --- SISTEMA DI LOGIN ---
if not st.session_state.logged_user:
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px;'>⚡ TS IMPIANTI</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; margin-bottom: 20px;'>Accesso Riservato</h4>", unsafe_allow_html=True)
        username_input = st.text_input("Nome Utente").upper()
        pin_input = st.text_input("PIN Personale", type="password")
        
        if st.button("Accedi al Gestionale", use_container_width=True):
            user_data = st.session_state.users.get(username_input)
            hashed_input_pin = hashlib.sha256(pin_input.encode()).hexdigest()
            
            if user_data and user_data["pin"] == hashed_input_pin:
                st.session_state.logged_user = {
                    "username": username_input,
                    "name": user_data["name"],
                    "role": user_data["role"]
                }
                st.success(f"Accesso riuscito! Benvenuto, {user_data['name']}")
                st.rerun()
            else:
                st.error("Nome utente o PIN errati.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# --- BARRA DI NAVIGAZIONE E MENU PRINCIPALE ---
user = st.session_state.logged_user
st.sidebar.markdown(f"### ⚡ TS IMPIANTI")
st.sidebar.markdown(f"👤 **{user['name']}**\n\nRuolo: `{user['role'].upper()}`")
st.sidebar.markdown("---")

menu_options = ["Archivio Clienti", "Nuovo Rapportino", "Riepilogo Mensile"]
if user["role"] == "amministratore":
    menu_options.append("Gestione Utenti")

selected_page = st.sidebar.radio("Navigazione", menu_options)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Disconnetti", use_container_width=True):
    st.session_state.logged_user = None
    st.rerun()


# ==========================================
# 1. ARCHIVIO CLIENTI (HOME)
# ==========================================
if selected_page == "Archivio Clienti":
    st.title("📁 Archivio Clienti & Commesse")
    st.write("Gestisci l'anagrafica dei clienti e le relative schede d'intervento.")
    
    # Sezione Creazione Nuovo Cliente
    with st.expander("➕ Aggiungi Nuovo Cliente / Cartella"):
        with st.form("new_client_form"):
            c_name = st.text_input("Nome Cliente / Azienda")
            c_group = st.text_input("Gruppo / Commessa (es. Pietrabianca Resort)")
            c_address = st.text_input("Indirizzo")
            c_phone = st.text_input("Telefono")
            
            submit_client = st.form_submit_button("Crea Cartella Cliente")
            if submit_client and c_name:
                st.session_state.clients.append({
                    "id": len(st.session_state.clients) + 1,
                    "name": c_name,
                    "group": c_group,
                    "address": c_address,
                    "phone": c_phone
                })
                st.success(f"Cartella per '{c_name}' creata con successo!")
                st.rerun()

    st.markdown("---")
    
    # Visualizzazione Clienti in Griglia / Schede
    if not st.session_state.clients:
        st.info("Nessun cliente presente nell'archivio. Aggiungine uno qui sopra.")
    else:
        search_query = st.text_input("🔍 Cerca cliente o commessa...").lower()
        
        for client in st.session_state.clients:
            if search_query in client["name"].lower() or search_query in client["group"].lower():
                with st.container():
                    st.markdown(f"""
                        <div class='card'>
                            <h3 style='margin-bottom: 10px;'>🏢 {client['name']}</h3>
                            <p style='color: #94a3b8; margin: 0;'><b>Commessa/Gruppo:</b> {client['group'] or 'N/D'} &nbsp;|&nbsp; <b>Indirizzo:</b> {client['address'] or 'N/D'} &nbsp;|&nbsp; <b>Tel:</b> {client['phone'] or 'N/D'}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    if user["role"] == "amministratore":
                        if st.button(f"🗑️ Elimina Cartella", key=f"del_{client['id']}"):
                            st.session_state.clients = [c for c in st.session_state.clients if c["id"] != client["id"]]
                            st.warning("Cartella eliminata.")
                            st.rerun()


# ==========================================
# 2. NUOVO RAPPORTINO
# ==========================================
elif selected_page == "Nuovo Rapportino":
    st.title("📝 Compila Nuovo Rapportino")
    
    if not st.session_state.clients:
        st.warning("Prima di compilare un rapportino, devi creare almeno un cliente nell'Archivio Clienti!")
    else:
        client_names = [c["name"] for c in st.session_state.clients]
        
        with st.form("new_report_form"):
            selected_client_name = st.selectbox("Seleziona Cliente", client_names)
            report_date = st.date_input("Data Esecuzione", datetime.today())
            technician_name = st.text_input("Tecnico Incaricato", value=user["name"])
            
            report_type = st.selectbox("Tipo Intervento", ["Ordinario", "Straordinario", "Collaudo", "Guasto"])
            
            col1, col2 = st.columns(2)
            with col1:
                start_time = st.time_input("Ora Inizio")
            with col2:
                end_time = st.time_input("Ora Fine")
                
            description = st.text_area("Descrizione dettagliata dei lavori eseguiti")
            
            st.markdown("---")
            st.subheader("Spese Vive / Materiali")
            expense_item = st.text_input("Voce Spesa (es. Materiale elettrico / Scontrino)")
            expense_amount = st.number_input("Importo (€)", min_value=0.0, step=0.5)
            
            uploaded_photo = st.file_uploader("Carica Foto Materiali / Scontrini", type=["jpg", "png", "jpeg"])

            submit_report = st.form_submit_button("Genera Rapportino e Salva")
            
            if submit_report:
                client_obj = next((c for c in st.session_state.clients if c["name"] == selected_client_name), None)
                
                new_rep = {
                    "number": len(st.session_state.reports) + 1001,
                    "client": selected_client_name,
                    "date": str(report_date),
                    "technician": technician_name,
                    "type": report_type,
                    "description": description,
                    "expenses": [{"item": expense_item, "amount": expense_amount}] if expense_item else [],
                    "author": user["name"]
                }
                
                st.session_state.reports.append(new_rep)
                st.success("Rapportino salvato con successo!")
                
                pdf_file = generate_pdf(new_rep, client_obj)
                with open(pdf_file, "rb") as f:
                    st.download_button("📥 Scarica PDF Rapportino Ufficiale", f, file_name=pdf_file, mime="application/pdf")


# ==========================================
# 3. RIEPILOGO MENSILE
# ==========================================
elif selected_page == "Riepilogo Mensile":
    st.title("📊 Riepilogo e Statistiche")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
            <div class='card' style='text-align: center;'>
                <h4 style='color: #94a3b8; margin-bottom: 5px;'>Totale Rapportini</h4>
                <h2 style='font-size: 2.5rem; margin: 0;'>{len(st.session_state.reports)}</h2>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class='card' style='text-align: center;'>
                <h4 style='color: #94a3b8; margin-bottom: 5px;'>Clienti in Archivio</h4>
                <h2 style='font-size: 2.5rem; margin: 0;'>{len(st.session_state.clients)}</h2>
            </div>
        """, unsafe_allow_html=True)
    
    st.subheader("Storico Rapportini")
    if not st.session_state.reports:
        st.info("Nessun rapportino registrato.")
    else:
        for rep in st.session_state.reports:
            st.markdown(f"""
                <div class='card'>
                    <b>N. {rep['number']}</b> &nbsp;|&nbsp; Cliente: <b>{rep['client']}</b> &nbsp;|&nbsp; Data: {rep['date']} &nbsp;|&nbsp; Compilato da: {rep['author']}
                </div>
            """, unsafe_allow_html=True)


# ==========================================
# 4. GESTIONE UTENTI (Solo Admin)
# ==========================================
elif selected_page == "Gestione Utenti":
    if user["role"] != "amministratore":
        st.error("Accesso negato: sezione riservata all'amministratore.")
    else:
        st.title("👥 Gestione Utenti e Collaboratori")
        
        with st.form("new_user_form"):
            new_username = st.text_input("Nome Utente (es. MARIO)").upper()
            new_name = st.text_input("Nome e Cognome Completo")
            new_pin = st.text_input("PIN Personale (min. 4 caratteri)", type="password")
            new_role = st.selectbox("Ruolo", ["collaboratore", "amministratore"])
            
            submit_user = st.form_submit_button("Crea Utente")
            if submit_user and new_username and new_pin:
                if new_username in st.session_state.users:
                    st.error("Questo nome utente esiste già!")
                else:
                    st.session_state.users[new_username] = {
                        "name": new_name,
                        "pin": hashlib.sha256(new_pin.encode()).hexdigest(),
                        "role": new_role
                    }
                    st.success(f"Utente {new_name} creato con successo!")
                    st.rerun()
                    
        st.markdown("### Utenti Attivi")
        for uname, udata in st.session_state.users.items():
            st.markdown(f"""
                <div class='card'>
                    <b>{udata['name']}</b> &nbsp;(`{uname}`) &nbsp;|&nbsp; Ruolo: <em>{udata['role']}</em>
                </div>
            """, unsafe_allow_html=True)
 
