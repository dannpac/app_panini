import streamlit as st
import sqlite3
import pandas as pd

DB_NAME = "panini_tracker.db"

# --- MODELADO BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Stickers (
            StickerID TEXT PRIMARY KEY,
            Name TEXT NOT NULL,
            Section TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY AUTOINCREMENT,
            Username TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Album_State (
            UserID INTEGER,
            StickerID TEXT,
            Status INTEGER DEFAULT 0,
            PRIMARY KEY (UserID, StickerID),
            FOREIGN KEY(UserID) REFERENCES Users(UserID),
            FOREIGN KEY(StickerID) REFERENCES Stickers(StickerID)
        )
    ''')
    conn.commit()
    
    # Catálogo maestro oficial de 48 selecciones
    teams_map = {
        "MEX": "México", "RSA": "Sudáfrica", "KOR": "República de Corea", "CZE": "República Checa",
        "CAN": "Canadá", "BIH": "Bosnia y Herzegovina", "QAT": "Catar", "SUI": "Suiza",
        "BRA": "Brasil", "MAR": "Marruecos", "HAI": "Haití", "SCO": "Escocia",
        "USA": "EE. UU.", "PAR": "Paraguay", "AUS": "Australia", "TUR": "Turquía",
        "GER": "Alemania", "CUW": "Curacao", "CIV": "Costa de Marfil", "ECU": "Ecuador",
        "NED": "Países Bajos", "JPN": "Japón", "SWE": "Suecia", "TUN": "Túnez",
        "BEL": "Bélgica", "EGY": "Egipto", "IRN": "RI de Irán", "NZL": "Nueva Zelanda",
        "ESP": "España", "CPV": "Cabo Verde", "KSA": "Arabia Saudí", "URU": "Uruguay",
        "FRA": "Francia", "SEN": "Senegal", "IRQ": "Irak", "NOR": "Noruega",
        "ARG": "Argentina", "ALG": "Argelia", "AUT": "Austria", "JOR": "Jordania",
        "POR": "Portugal", "COD": "República Democrática del Congo", "UZB": "Uzbekistán", "COL": "Colombia",
        "ENG": "Inglaterra", "CRO": "Croacia", "GHA": "Ghana", "PAN": "Panamá"
    }
    
    cursor.execute("SELECT COUNT(*) FROM Stickers")
    if cursor.fetchone()[0] == 0:
        official_stickers = []
        for i in range(1, 10):
            official_stickers.append((f"FWC {i}", f"Postal FWC {i}", "Intro / Especiales"))
        for code, team_name in teams_map.items():
            official_stickers.append((f"{code}-00", "Escudo Oficial", team_name))
            for i in range(1, 12):
                sticker_id = f"{code}-{i:02d}"
                official_stickers.append((sticker_id, f"Postal {sticker_id}", team_name))
        cursor.executemany("INSERT INTO Stickers VALUES (?, ?, ?)", official_stickers)
        conn.commit()
        
    cursor.execute("SELECT UserID FROM Users")
    all_uids = [row[0] for row in cursor.fetchall()]
    for u_id in all_uids:
        cursor.execute("INSERT OR IGNORE INTO Album_State (UserID, StickerID, Status) SELECT ?, StickerID, 0 FROM Stickers", (u_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT Username FROM Users ORDER BY Username ASC")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def create_unique_user(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Users (Username) VALUES (?)", (username,))
        uid = cursor.lastrowid
        cursor.execute("INSERT OR IGNORE INTO Album_State (UserID, StickerID, Status) SELECT ?, StickerID, 0 FROM Stickers", (uid,))
        conn.commit()
        conn.close()
        return True, uid
    except sqlite3.IntegrityError:
        conn.close()
        return False, None

def get_user_id(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT UserID FROM Users WHERE Username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_album(user_id):
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT s.StickerID, s.Name, s.Section, a.Status 
        FROM Stickers s
        JOIN Album_State a ON s.StickerID = a.StickerID
        WHERE a.UserID = ?
    """
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df

def update_user_status(user_id, sticker_id, current_status):
    new_status = (current_status + 1) % 3
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE Album_State SET Status = ? WHERE UserID = ? AND StickerID = ?", (new_status, user_id, sticker_id))
    conn.commit()
    conn.close()

# --- CONFIGURACIÓN VISUAL Y TRATAMIENTO DE INTERFAZ ---
st.set_page_config(page_title="Panini Matrix Tracker", layout="wide", initial_sidebar_state="expanded")
init_db()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #080a10; color: #f3f4f6; }
    
    .premium-header { 
        background: linear-gradient(135deg, #101524 0%, #05070a 100%); 
        border: 1px solid rgba(99, 102, 241, 0.2); 
        padding: 24px; 
        border-radius: 18px; 
        margin-bottom: 15px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }
    .premium-title { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 2.3rem; background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; text-transform: uppercase; letter-spacing: 1.5px; }
    
    /* Contenedor Premium Estilizado para el Selector de Países en el Panel Principal */
    .main-navigation-box {
        background-color: #0f1322;
        border: 1px solid rgba(99, 102, 241, 0.3) !important;
        padding: 16px;
        border-radius: 16px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.25);
    }
    
    .ux-tutorial-bar {
        background-color: #0f121d;
        border-left: 4px solid #6366f1;
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-size: 0.98rem;
    }
    
    /* Configuración de Botones Base */
    div.stButton > button { 
        font-family: 'Space Grotesk', sans-serif; 
        border-radius: 16px; 
        transition: all 0.1s ease-in-out !important; 
        box-shadow: 0 5px 8px rgba(0, 0, 0, 0.25) !important; 
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    .st-sticker-missing button { border: 1px solid #374151 !important; background: linear-gradient(145deg, #1f2937, #111827) !important; color: #d1d5db !important; height: 74px !important; font-weight: 600; font-size: 16px !important; }
    .st-sticker-owned button { background: linear-gradient(145deg, #10b981, #059669) !important; color: #ffffff !important; border: 1px solid #34d399 !important; box-shadow: 0 4px 18px rgba(16, 185, 129, 0.45) !important; height: 74px !important; font-weight: 700; font-size: 16px !important; }
    .st-sticker-dupe button { background: linear-gradient(145deg, #f97316, #ea580c) !important; color: #ffffff !important; border: 1px solid #fb923c !important; box-shadow: 0 4px 18px rgba(249, 115, 22, 0.5) !important; height: 74px !important; font-weight: 700; font-size: 16px !important; }
    .st-sticker-shield button { border: 2px solid #fbbf24 !important; background: linear-gradient(145deg, #111422, #07090e) !important; color: #fbbf24 !important; font-size: 17px !important; box-shadow: 0 4px 20px rgba(251, 191, 36, 0.25) !important; }
    
    div.stButton > button:active { transform: scale(0.95) !important; }
    section[data-testid="stSidebar"] { background-color: #05070a; border-right: 1px solid rgba(255, 255, 255, 0.03); }
    .stMetric { background: #0f121d; padding: 18px; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.04); }
    .lock-screen { text-align: center; padding: 50px 20px; background: #0f121d; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.04); margin-top: 20px; }
    
    /* Controladores para forzar el Dropdown a verse gigante y accesible en celular */
    div[data-testid="stSelectbox"] label { font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important; color: #6366f1 !important; font-size: 15px !important; text-transform: uppercase; letter-spacing: 0.5px; }
    
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { display: flex !important; flex-wrap: wrap !important; gap: 12px !important; }
        [data-testid="stHorizontalBlock"] > div { min-width: 100% !important; flex: 1 1 100% !important; padding: 0 !important; }
        div.stButton > button { height: 78px !important; font-size: 17px !important; }
        .premium-title { font-size: 1.7rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="premium-header"><h1 class="premium-title">🚀 PANINI MATRIX TRACKER</h1><p style="color: #9ca3af; margin: 5px 0 0 0; font-size: 1.1em; font-weight: 300;">Plataforma Homologada de Intercambio — UI de Mandos Centralizados</p></div>', unsafe_allow_html=True)

# --- PANEL DE CONTROL DE IDENTIDAD (SIDEBAR) ---
st.sidebar.markdown("<h3 style='font-family: Space Grotesk;'>🆔 PERFIL DE ACCESO</h3>", unsafe_allow_html=True)

with st.sidebar.expander("🆕 Registrar Nuevo Alias Único"):
    new_username = st.text_input("Crea tu alias exclusivo:", key="new_user_input").strip()
    if st.button("Guardar en Sistema"):
        if new_username:
            success, _ = create_unique_user(new_username)
            if success:
                st.success(f"Alias '{new_username}' registrado.")
                st.rerun()
            else:
                st.error("Ese alias ya está ocupado.")
        else:
            st.warning("El alias no puede quedar vacío.")

st.sidebar.markdown("---")

existing_users = get_all_users()
if not existing_users:
    selected_user = None
    st.sidebar.info("No hay usuarios registrados.")
else:
    options = ["-- Seleccionar Socio --"] + existing_users
    login_selection = st.sidebar.selectbox("Inicia sesión con tu alias:", options)
    selected_user = None if login_selection == "-- Seleccionar Socio --" else login_selection

if not selected_user:
    st.markdown("""
        <div class="lock-screen">
            <h2 style="font-family: Space Grotesk; color: #6366f1;">👤 IDENTIFICACIÓN REQUERIDA</h2>
            <p style="color: #9ca3af; font-size: 1.15em; margin-top: 10px;">
                Por favor, selecciona tu alias en el menú desplegable de la barra lateral izquierda para activar tu matriz de intercambio interactiva.
            </p>
        </div>
    """, unsafe_allow_html=True)
else:
    uid = get_user_id(selected_user)
    df_album = get_user_album(uid)
    
    # Renderizado y ordenamiento de las secciones del álbum
    sections_raw = list(df_album["Section"].unique())
    sections = sorted(sections_raw)
    if "Intro / Especiales" in sections: 
        sections.insert(0, sections.pop(sections.index("Intro / Especiales")))
    
    # =========================================================================
    # REINGENIERÍA UX: EL DROPDOWN SE MUEVE AL PANEL CENTRAL COMO COMANDO TOP
    # =========================================================================
    st.markdown('<div class="main-navigation-box">', unsafe_allow_html=True)
    selected_section = st.selectbox("📂 SECCIÓN ACTIVA DEL ÁLBUM (SELECCIONA PAÍS):", sections)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # KPIs Globales en la Sidebar (Uso informativo)
    total = len(df_album)
    owned = len(df_album[df_album["Status"] >= 1])
    dupes = len(df_album[df_album["Status"] == 2])
    prog = int((owned/total)*100) if total > 0 else 0

    st.sidebar.metric(f"ÁLBUM DE {selected_user.upper()}", f"{prog}%", f"{owned} / {total} slots")
    st.sidebar.metric("TU PILA DE REPETIDAS", f"{dupes} uds")
    st.sidebar.progress(prog/100)
    
    list_missing = df_album[df_album["Status"] == 0]["StickerID"].tolist()
    list_repeated = df_album[df_album["Status"] == 2]["StickerID"].tolist()
    str_missing = ", ".join(list_missing) if list_missing else "¡Ninguna! Álbum completo."
    str_repeated = ", ".join(list_repeated) if list_repeated else "No tienes repetidas aún."

    st.markdown("""
        <div class="ux-tutorial-bar">
            <strong>🎮 Guía Táctil Rápida:</strong> Cada toque sobre una postal cambia su estado:<br>
            <span style="color: #9ca3af; font-weight: 600;">⬡ Gris = Falta</span> | 
            <span style="color: #34d399; font-weight: 600;">✅ Verde = Tengo</span> | 
            <span style="color: #fb923c; font-weight: 600;">🔥 Naranja = Repetida</span>
        </div>
    """, unsafe_allow_html=True)

    tab_panel, tab_clipboard = st.tabs(["🎴 MATRIZ INTERACTIVA", "📋 EXPORTAR LISTAS PARA WHATSAPP"])

    with tab_panel:
        if "filter_state" not in st.session_state:
            st.session_state.filter_state = "ALL"
            
        col_f1, col_f2, col_f3 = st.columns(3)
        if col_f1.button("👁️ Ver Todo", use_container_width=True):
            st.session_state.filter_state = "ALL"
            st.rerun()
        if col_f2.button("🔴 Solo Faltantes", use_container_width=True):
            st.session_state.filter_state = "MISS"
            st.rerun()
        if col_f3.button("🔥 Solo Repetidas", use_container_width=True):
            st.session_state.filter_state = "DUPE"
            st.rerun()
            
        if st.session_state.filter_state == "MISS":
            st.markdown("<p style='color: #ef4444; font-weight: 600; margin-bottom: 15px;'>Filtro Activo: Mostrando únicamente lo que te FALTA 🔴</p>", unsafe_allow_html=True)
        elif st.session_state.filter_state == "DUPE":
            st.markdown("<p style='color: #f97316; font-weight: 600; margin-bottom: 15px;'>Filtro Activo: Mostrando únicamente tus REPETIDAS 🔥</p>", unsafe_allow_html=True)

        df_sec = df_album[df_album["Section"] == selected_section]
        
        if st.session_state.filter_state == "MISS":
            df_sec = df_sec[df_sec["Status"] == 0]
        elif st.session_state.filter_state == "DUPE":
            df_sec = df_sec[df_sec["Status"] == 2]

        if df_sec.empty:
            st.info("No hay postales que coincidan con el filtro seleccionado en esta sección.")
        else:
            cols = st.columns(4)
            for idx, row in enumerate(df_sec.itertuples()):
                col = cols[idx % 4]
                
                if row.Status == 0:
                    label = f"⬡ {row.StickerID}   (Falta)"
                    wrapper_class = "st-sticker-missing"
                elif row.Status == 1:
                    label = f"✅ {row.StickerID}   (Tengo)"
                    wrapper_class = "st-sticker-owned"
                else:
                    label = f"🔥 {row.StickerID}   (Repetida)"
                    wrapper_class = "st-sticker-dupe"
                
                if "-00" in row.StickerID:
                    wrapper_class = "st-sticker-shield"
                    label = f"👑 {row.StickerID} ESCUDO"
                
                st.markdown(f'<div class="{wrapper_class}">', unsafe_allow_html=True)
                if col.button(label, key=f"al_{row.StickerID}", use_container_width=True):
                    update_user_status(uid, row.StickerID, row.Status)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    with tab_clipboard:
        st.subheader("📋 Generador Automatizado de Listas de Intercambio")
        st.write("Copia estas listas y pégalas directamente en el grupo de WhatsApp de tus amigos.")
        col_m, col_r = st.columns(2)
        with col_m:
            st.markdown(f"### 🔴 Mis Faltantes ({len(list_missing)})")
            st.code(str_missing, language="text")
        with col_r:
            st.markdown(f"### 🟢 Mis Repetidas ({len(list_repeated)})")
            st.code(str_repeated, language="text")