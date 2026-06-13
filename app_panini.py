import threading
import webbrowser
import time
import os
from flask import Flask, render_template_string, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# --- CONTROL DE ENTORNO ESTRICTO ---
DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("CRÍTICO: La variable de entorno DATABASE_URL no está configurada.")
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1) if DATABASE_URL.startswith("postgres://") else DATABASE_URL
    return psycopg2.connect(url)

# --- CAPA DE DATOS (Dialecto PostgreSQL) ---
def init_db():
    if not DATABASE_URL:
        return
        
    conn = get_db_connection()
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
            UserID SERIAL PRIMARY KEY, 
            Username TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Album_State (
            UserID INTEGER, 
            StickerID TEXT, 
            Status INTEGER DEFAULT 0, 
            PRIMARY KEY (UserID, StickerID), 
            FOREIGN KEY(UserID) REFERENCES Users(UserID) ON DELETE CASCADE, 
            FOREIGN KEY(StickerID) REFERENCES Stickers(StickerID) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM Stickers")
    if cursor.fetchone()[0] == 0:
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
        official_stickers = [(f"FWC {i}", f"Postal FWC {i}", "Intro / Especiales") for i in range(1, 10)]
        for code, team in teams_map.items():
            official_stickers.append((f"{code}-00", "Escudo Oficial", team))
            for i in range(1, 12):
                official_stickers.append((f"{code}-{i:02d}", f"Postal {code}-{i:02d}", team))
        
        cursor.executemany("INSERT INTO Stickers VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", official_stickers)
        conn.commit()
    conn.close()

if DATABASE_URL:
    init_db()

# --- CAPA GRÁFICA (PWA PREMIUM LIGHT) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Panini Tracker</title>
    <style>
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        body { font-family: system-ui, -apple-system, sans-serif; background-color: #F8FAFC; color: #0F172A; margin: 0; padding: 0 0 90px 0; overscroll-behavior-y: none; }
        
        .app-header { position: sticky; top: 0; z-index: 100; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(12px); padding: 16px 20px; border-bottom: 1px solid #E2E8F0; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); }
        .app-title { font-weight: 800; font-size: 20px; margin: 0; color: #1D4ED8; letter-spacing: -0.5px; }
        .app-subtitle { font-size: 11px; color: #64748B; margin: 4px 0 0 0; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }

        .view-section { display: none; padding: 20px; animation: fadeIn 0.2s ease-out; }
        .view-section.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

        .card { background: #FFFFFF; padding: 20px; border-radius: 16px; margin-bottom: 20px; border: 1px solid #F1F5F9; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.03), 0 4px 6px -2px rgba(0,0,0,0.02); }
        
        .control-label { display: block; font-size: 12px; color: #64748B; margin-bottom: 8px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; }
        select, input, .btn-primary { width: 100%; padding: 16px; border-radius: 12px; font-family: inherit; font-size: 15px; font-weight: 600; outline: none; }
        select, input { background: #F8FAFC; border: 1px solid #E2E8F0; color: #0F172A; appearance: none; transition: border-color 0.2s; }
        select:focus, input:focus { border-color: #3B82F6; background: #FFFFFF; }
        
        .btn-primary { background: #2563EB; color: #FFFFFF; border: none; cursor: pointer; margin-top: 10px; transition: transform 0.1s, background 0.2s; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2); }
        .btn-primary:active { transform: scale(0.96); background: #1D4ED8; }

        .filter-bar { display: flex; gap: 8px; margin-bottom: 20px; background: #F1F5F9; padding: 6px; border-radius: 12px; border: 1px solid #E2E8F0; }
        .filter-btn { flex: 1; padding: 10px 0; border-radius: 8px; border: none; background: transparent; color: #64748B; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s; }
        .filter-btn.active { background: #FFFFFF; color: #0F172A; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }

        .matrix-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
        .matrix-btn { 
            height: 72px; border-radius: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 14px; font-weight: 700; 
            display: flex; align-items: center; justify-content: center; cursor: pointer; 
            transition: transform 0.05s cubic-bezier(0.4, 0, 0.2, 1), background 0.15s ease, border 0.15s ease; border: none; outline: none; 
        }
        .matrix-btn:active { transform: scale(0.9) !important; }

        .state-0 { background: #F1F5F9; color: #64748B; border: 1px solid #E2E8F0; }
        .state-1 { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.1); }
        .state-2 { background: #FFF7ED; color: #9A3412; border: 1px solid #FDBA74; box-shadow: 0 4px 10px rgba(249, 115, 22, 0.1); }
        .shield { border: 2px solid #F59E0B !important; font-size: 15px; background-image: linear-gradient(to bottom right, rgba(253, 230, 138, 0.2), transparent); }

        .stats-box { display: flex; justify-content: space-between; background: #FFFFFF; padding: 20px; border-radius: 16px; margin-bottom: 20px; border: 1px solid #F1F5F9; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02); }
        .stat-item { text-align: center; flex: 1; }
        .stat-val { font-size: 22px; font-weight: 800; display: block; letter-spacing: -0.5px; }
        .stat-lbl { font-size: 11px; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-top: 4px; display: block; }

        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(20px); border-top: 1px solid #E2E8F0; display: flex; justify-content: space-around; padding: 12px 10px 25px 10px; z-index: 1000; }
        .nav-item { flex: 1; text-align: center; padding: 8px 0; color: #94A3B8; font-size: 11px; font-weight: 700; text-transform: uppercase; cursor: pointer; transition: color 0.2s; letter-spacing: 0.5px; }
        .nav-item.active { color: #2563EB; }
        .nav-icon { display: block; font-size: 22px; margin-bottom: 4px; filter: grayscale(100%) opacity(0.5); transition: filter 0.2s; }
        .nav-item.active .nav-icon { filter: grayscale(0%) opacity(1); }
        
        textarea.export-box { width: 100%; height: 160px; background: #F8FAFC; color: #334155; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; font-family: ui-monospace, monospace; font-size: 13px; resize: none; margin-bottom: 20px; line-height: 1.5; }
        textarea.export-box:focus { border-color: #3B82F6; background: #FFFFFF; outline: none; }
    </style>
</head>
<body>

    <div class="app-header">
        <h1 class="app-title">PANINI TRACKER</h1>
        <p class="app-subtitle" id="currentUserDisplay">NO HAY SOCIO ACTIVO</p>
    </div>

    <div id="view-album" class="view-section">
        <div class="card">
            <label class="control-label">SECCIÓN ACTUAL</label>
            <select id="sectionSelect" onchange="renderMatrix()">
                {% for section in sections %}
                    <option value="{{ section }}">{{ section }}</option>
                {% endfor %}
            </select>
        </div>

        <div class="stats-box">
            <div class="stat-item"><span class="stat-val" id="statOwned" style="color:#059669;">0</span><span class="stat-lbl">TENGO</span></div>
            <div class="stat-item"><span class="stat-val" id="statProg" style="color:#0F172A;">0%</span><span class="stat-lbl">PROGRESO</span></div>
            <div class="stat-item"><span class="stat-val" id="statDupes" style="color:#EA580C;">0</span><span class="stat-lbl">REPETIDAS</span></div>
        </div>

        <div class="filter-bar">
            <button class="filter-btn active" onclick="setFilter('ALL', this)">TODO</button>
            <button class="filter-btn" onclick="setFilter('MISSING', this)">FALTAN</button>
            <button class="filter-btn" onclick="setFilter('DUPES', this)">REPETIDAS</button>
        </div>

        <div id="matrixGrid" class="matrix-grid"></div>
    </div>

    <div id="view-account" class="view-section active">
        <div class="card">
            <label class="control-label">INICIAR SESIÓN</label>
            <select id="userSelect" onchange="switchUser()">
                <option value="">-- SELECCIONA ALIAS --</option>
                {% for user in users %}
                    <option value="{{ user.userid }}">{{ user.username }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="card">
            <label class="control-label">NUEVO PERFIL DE SOCIO</label>
            <input type="text" id="newUsername" placeholder="Escribe un alias único" autocomplete="off">
            <button class="btn-primary" onclick="createUser()">CREAR PERFIL</button>
        </div>
    </div>

    <div id="view-export" class="view-section">
        <div class="card">
            <label class="control-label">FALTANTES PARA ENVIAR</label>
            <textarea id="exportMissing" class="export-box" readonly></textarea>
            
            <label class="control-label">REPETIDAS PARA CAMBIAR</label>
            <textarea id="exportDupes" class="export-box" readonly></textarea>
        </div>
    </div>

    <div class="bottom-nav">
        <div class="nav-item" onclick="switchView('view-album', this)" id="navAlbum">
            <span class="nav-icon">🎛️</span>MATRIZ
        </div>
        <div class="nav-item active" onclick="switchView('view-account', this)" id="navAccount">
            <span class="nav-icon">👤</span>PERFIL
        </div>
        <div class="nav-item" onclick="switchView('view-export', this)" id="navExport">
            <span class="nav-icon">📋</span>EXPORTAR
        </div>
    </div>

    <script>
        let currentUserId = null;
        let albumData = [];
        let activeFilter = 'ALL';

        function switchView(viewId, navElement) {
            if(viewId !== 'view-account' && !currentUserId) {
                alert("DEBES INICIAR SESIÓN PRIMERO");
                return;
            }
            document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            document.getElementById(viewId).classList.add('active');
            navElement.classList.add('active');
            
            if(viewId === 'view-export') generateExportLists();
            window.scrollTo(0,0);
        }

        async function switchUser() {
            const select = document.getElementById('userSelect');
            currentUserId = select.value;
            if(!currentUserId) return;
            
            const username = select.options[select.selectedIndex].text;
            document.getElementById('currentUserDisplay').innerText = `SOCIO: ${username}`;
            
            await fetchAlbumData();
            switchView('view-album', document.getElementById('navAlbum'));
        }

        async function createUser() {
            const name = document.getElementById('newUsername').value.trim();
            if(!name) return alert("EL ALIAS NO PUEDE ESTAR VACÍO");
            const res = await fetch('/api/user', { method: 'POST', headers:{'Content-Type': 'application/json'}, body: JSON.stringify({username: name})});
            if(res.ok) location.reload();
            else alert("ERROR: EL ALIAS YA EXISTE");
        }

        async function fetchAlbumData() {
            const res = await fetch('/api/album/' + currentUserId);
            albumData = await res.json();
            updateStats();
            renderMatrix();
        }

        function updateStats() {
            const total = albumData.length;
            const owned = albumData.filter(s => s.status >= 1).length;
            const dupes = albumData.filter(s => s.status === 2).length;
            const prog = total > 0 ? Math.round((owned/total)*100) : 0;
            
            document.getElementById('statOwned').innerText = owned;
            document.getElementById('statProg').innerText = `${prog}%`;
            document.getElementById('statDupes').innerText = dupes;
        }

        function setFilter(filterType, btnElement) {
            activeFilter = filterType;
            document.querySelectorAll('.filter-btn').forEach(el => el.classList.remove('active'));
            btnElement.classList.add('active');
            renderMatrix();
        }

        function renderMatrix() {
            const section = document.getElementById('sectionSelect').value;
            const grid = document.getElementById('matrixGrid');
            grid.innerHTML = '';

            let targetData = albumData.filter(s => s.section === section);
            if(activeFilter === 'MISSING') targetData = targetData.filter(s => s.status === 0);
            if(activeFilter === 'DUPES') targetData = targetData.filter(s => s.status === 2);

            targetData.forEach(sticker => {
                const btn = document.createElement('button');
                btn.className = `matrix-btn state-${sticker.status}`;
                if (sticker.stickerid.includes('-00')) btn.classList.add('shield');
                btn.innerText = sticker.stickerid;

                btn.onclick = () => {
                    sticker.status = (sticker.status + 1) % 3;
                    btn.className = `matrix-btn state-${sticker.status}`;
                    if (sticker.stickerid.includes('-00')) btn.classList.add('shield');
                    
                    updateStats();
                    
                    fetch('/api/update', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ user_id: currentUserId, sticker_id: sticker.stickerid, status: sticker.status })
                    });

                    if(activeFilter !== 'ALL') {
                        setTimeout(() => { renderMatrix(); }, 150);
                    }
                };
                grid.appendChild(btn);
            });
        }

        function generateExportLists() {
            document.getElementById('exportMissing').value = albumData.filter(s => s.status === 0).map(s => s.stickerid).join(', ');
            document.getElementById('exportDupes').value = albumData.filter(s => s.status === 2).map(s => s.stickerid).join(', ');
        }
    </script>
</body>
</html>
"""

# --- ENDPOINTS API REST ---
@app.route('/')
def index():
    if not DATABASE_URL:
        return "Servidor activo. Falta configurar la variable DATABASE_URL localmente."
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM Users ORDER BY Username ASC")
    users = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT DISTINCT Section FROM Stickers")
    sections_raw = [row['section'] for row in cursor.fetchall()]
    sections = sorted(sections_raw)
    if "Intro / Especiales" in sections:
        sections.insert(0, sections.pop(sections.index("Intro / Especiales")))
    conn.close()
    return render_template_string(HTML_TEMPLATE, users=users, sections=sections)

@app.route('/api/user', methods=['POST'])
def create_user():
    username = request.json.get('username')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Users (Username) VALUES (%s) RETURNING UserID", (username,))
        uid = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Album_State (UserID, StickerID, Status) SELECT %s, StickerID, 0 FROM Stickers ON CONFLICT DO NOTHING", (uid,))
        conn.commit()
        return jsonify({"success": True})
    except psycopg2.IntegrityError:
        return jsonify({"error": "Exists"}), 400
    finally:
        conn.close()

@app.route('/api/album/<int:user_id>')
def get_album(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = "SELECT s.StickerID, s.Section, a.Status FROM Stickers s JOIN Album_State a ON s.StickerID = a.StickerID WHERE a.UserID = %s"
    cursor.execute(query, (user_id,))
    album = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(album)

@app.route('/api/update', methods=['POST'])
def update_sticker():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Album_State SET Status = %s WHERE UserID = %s AND StickerID = %s", (data['status'], data['user_id'], data['sticker_id']))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5005")

if __name__ == '__main__':
    if not DATABASE_URL:
        print("⚠️ ALERTA: No has definido la variable DATABASE_URL localmente.")
    else:
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=5005, debug=True, use_reloader=False)