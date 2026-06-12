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
    
    # 1. PURGA IMPERATIVA DE DATOS ANTERIORES
    cursor.execute("DELETE FROM Album_State WHERE StickerID LIKE 'INTRO-%'")
    cursor.execute("DELETE FROM Stickers WHERE StickerID LIKE 'INTRO-%'")
    conn.commit()
    
    # 2. LISTADO MAESTRO COMPLETO DE LAS 48 SELECCIONES OFICIALES
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
    
    valid_sections = ["Intro / Especiales"] + list(teams_map.values())
    placeholders = ",".join("?" for _ in valid_sections)
    cursor.execute(f"DELETE FROM Album_State WHERE StickerID IN (SELECT StickerID FROM Stickers WHERE Section NOT IN ({placeholders}))", valid_sections)
    cursor.execute(f"DELETE FROM Stickers WHERE Section NOT IN ({placeholders})", valid_sections)
    conn.commit()

    official_stickers = []
    
    # Intro / Especiales (FWC 1 a FWC 9) - Ahora el nombre almacena solo el código limpio
    for i in range(1, 10):
        official_stickers.append((f"FWC {i}", f"Postal FWC {i}", "Intro / Especiales"))
        
    # Inyección de las 48 Selecciones (Escudo -00 + 11 Casillas de códigos)
    for code, team_name in teams_map.items():
        official_stickers.append((f"{code}-00", "Escudo Oficial", team_name))
        for i in range(1, 12):
            sticker_id = f"{code}-{i:02d}"
            official_stickers.append((sticker_id, f"Postal {sticker_id}", team_name))
            
    # Forzamos la actualización de nombres en la tabla maestra para limpiar registros viejos
    cursor.execute("DROP TABLE IF EXISTS Stickers")
    cursor.execute('''
        CREATE TABLE Stickers (
            StickerID TEXT PRIMARY KEY,
            Name TEXT NOT NULL,
            Section TEXT NOT NULL
        )
    ''')
    cursor.executemany("INSERT INTO Stickers VALUES (?, ?, ?)", official_stickers)
    conn.commit()
    
    # Re-sincronización transaccional
    cursor.execute("SELECT UserID FROM Users")
    all_uids = [row[0] for row in cursor.fetchall()]
    for u_id in all_uids:
        cursor.execute("""
            INSERT OR IGNORE INTO Album_State (UserID, StickerID, Status) 
            SELECT ?, StickerID, 0 FROM Stickers
        """, (u_id,))
    conn.commit()
    conn.close()

# --- CONTROLADORES DE TRANSACCIONALIDAD ---
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

def update_user_status(user_id, sticker_id, new_status):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE Album_State SET Status = ? WHERE UserID = ? AND StickerID = ?", (new_status, user_id, sticker_id))
    conn.commit()
    conn.close()

# --- CONFIGURACIÓN DE ENTORNO VISUAL ---
st.set_page_config(page_title="Panini Matrix Tracker", layout="wide", initial_sidebar_state="expanded")
init_db()

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=Inter:wght@300;400;500&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0b0d12; color: #f3f4f6; }
    
    .premium-header { 
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); 
        border: 1px solid rgba(99, 102, 241, 0.2); 
        padding: 20px; 
        border-radius: 16px; 
        margin-bottom: 25px; 
    }
    .premium-title { font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 2rem; background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; }
    
    div.stButton > button { 
        font-family: 'Space Grotesk', sans-serif; 
        border-radius: 12px; 
        border: 1px solid rgba(255, 255, 255, 0.08) !important; 
        background: linear-gradient(145deg, #111827, #1f2937) !important; 
        color: #9ca3af !important; 
        height: 60px !important; 
        font-weight: 600; 
        font-size: 14px; 
        transition: all 0.2s ease-in-out !important; 
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important; 
    }
    div.stButton > button:hover { border-color: rgba(99, 102, 241, 0.6) !important; color: #ffffff !important; transform: translateY(-2px) scale(1.01) !important; }
    div.stButton > button[kind="primary"] { background: linear-gradient(145deg, #4f46e5, #4338ca) !important; color: #ffffff !important; box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4) !important; }
    
    section[data-testid="stSidebar"] { background-color: #090b0f; border-right: 1px solid rgba(255, 255, 255, 0.05); }
    .stMetric { background: #111318; padding: 15px; border-radius: 14px; border: 1px solid rgba(255, 255, 255, 0.05); }
    .lock-screen { text-align: center; padding: 30px; background: #111318; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.05); margin-top: 20px; }
    
    @media (max-width: 768px) {
        [data-testid="stHorizontalBlock"] { display: flex !important; flex-wrap: wrap !important; gap: 10px !important; }
        [data-testid="stHorizontalBlock"] > div { min-width: 100% !important; flex: 1 1 100% !important; padding: 0 !important; }
        .premium-title { font-size: 1.5rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="premium-header"><h1 class="premium-title">PANINI MATRIX TRACKER</h1><p style="color: #9ca3af; margin: 5px 0 0 0; font-size: 1.1em; font-weight: 300;">Plataforma de Intercambio — Control por Códigos de Postal (48 Selecciones)</p></div>', unsafe_allow_html=True)

# --- PANEL DE CONTROL DE IDENTIDAD (SIDEBAR) ---
st.sidebar.markdown("<h3 style='font-family: Space Grotesk;'>🆔 PANEL DE IDENTIDAD</h3>", unsafe_allow_html=True)

with st.sidebar.expander("🆕 Registrar Nuevo Alias Único"):
    new_username = st.text_input("Crea tu alias exclusivo:", key="new_user_input").strip()
    if st.button("Guardar en Base de Datos"):
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
    st.sidebar.info("No hay usuarios en la base de datos.")
else:
    options = ["-- Seleccionar Socio --"] + existing_users
    login_selection = st.sidebar.selectbox("Inicia sesión con tu alias:", options)
    selected_user = None if login_selection == "-- Seleccionar Socio --" else login_selection

if not selected_user:
    st.markdown("""
        <div class="lock-screen">
            <h2 style="font-family: Space Grotesk; color: #a855f7;">👤 IDENTIFICACIÓN REQUERIDA</h2>
            <p style="color: #9ca3af;">Selecciona tu alias en el menú de la barra lateral para desplegar tu matriz adaptativa de 48 selecciones.</p>
        </div>
    """, unsafe_allow_html=True)
else:
    uid = get_user_id(selected_user)
    df_album = get_user_album(uid)
    
    st.sidebar.markdown("---")
    sections_raw = list(df_album["Section"].unique())
    sections = sorted(sections_raw)
    if "Intro / Especiales" in sections: 
        sections.insert(0, sections.pop(sections.index("Intro / Especiales")))
    
    selected_section = st.sidebar.selectbox("Sección Activa:", sections)
    
    # KPIs globales
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

    tab_album, tab_trade, tab_clipboard = st.tabs(["🎴 PANEL DEL ÁLBUM", "🔄 PILA DE REPETIDAS", "📋 COPIAR LISTAS"])

    # --- TAB 1: PANEL DEL ÁLBUM (MUESTRA SOLO EL CÓDIGO) ---
    with tab_album:
        df_sec = df_album[df_album["Section"] == selected_section]
        cols = st.columns(4)
        for idx, row in enumerate(df_sec.itertuples()):
            col = cols[idx % 4]
            is_owned = row.Status >= 1
            # CORRECCIÓN: Los botones ahora despliegan únicamente el identificador único
            label = f"✨ {row.StickerID}" if is_owned else f"⬡ {row.StickerID}"
            if col.button(label, key=f"al_{row.StickerID}", type="primary" if is_owned else "secondary", use_container_width=True):
                update_user_status(uid, row.StickerID, 0 if is_owned else 1)
                st.rerun()

    # --- TAB 2: PILA DE REPETIDAS ---
    with tab_trade:
        df_owned = df_album[(df_album["Section"] == selected_section) & (df_album["Status"] >= 1)]
        if df_owned.empty:
            st.info("No tienes activos disponibles en esta sección para intercambio.")
        else:
            cols = st.columns(4)
            for idx, row in enumerate(df_owned.itertuples()):
                col = cols[idx % 4]
                is_dupe = row.Status == 2
                btn_type = "primary" if is_dupe else "secondary"
                label = f"🔥 REPETIDA ({row.StickerID})" if is_dupe else f"🔒 BLOQUEADA ({row.StickerID})"
                
                if col.button(label, key=f"tr_{row.StickerID}", type=btn_type, use_container_width=True):
                    update_user_status(uid, row.StickerID, 1 if is_dupe else 2)
                    st.rerun()

    # --- TAB 3: COPIAR LISTAS ---
    with tab_clipboard:
        st.subheader("📋 Generador de Listas de Intercambio")
        col_m, col_r = st.columns(2)
        with col_m:
            st.markdown(f"### 🔴 Mis Faltantes ({len(list_missing)})")
            st.code(str_missing, language="text")
        with col_r:
            st.markdown(f"### 🟢 Mis Repetidas ({len(list_repeated)})")
            st.code(str_repeated, language="text")