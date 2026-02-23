import streamlit as st
import os

# --- SISTEMA DE SEGURIDAD ---
def check_password():
    def login_form():
        with st.form("login"):
            st.subheader("🔐 Acceso Administrativo")
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Entrar")
            if submit:
                # Comparamos con las variables de Railway
                if user == os.getenv("ADMIN_USER") and password == os.getenv("ADMIN_PASSWORD"):
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")

    if "password_correct" not in st.session_state:
        login_form()
        return False
    return True

if not check_password():
    st.stop() # Bloquea el resto de la app si no hay login

# --- CONFIGURACIÓN DE BASE DE DATOS POSTGRES ---
def get_engine():
    # Railway inyecta automáticamente la variable DATABASE_URL
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def inicializar_tablas():
    engine = get_engine()
    # SQL para crear las tablas con las columnas originales
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                "Usuario" TEXT UNIQUE,
                "Servicio" TEXT,
                "Vencimiento" TEXT,
                "WhatsApp" TEXT,
                "Observaciones" TEXT
            );
        """))
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS finanzas (
                id SERIAL PRIMARY KEY,
                "Fecha" TEXT,
                "Tipo" TEXT,
                "Detalle" TEXT,
                "Monto" FLOAT
            );
        """))
        conn.commit()

def load_data():
    engine = get_engine()
    inicializar_tablas()
    
    # Leemos los datos directamente a DataFrames
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    
    # CORRECCIÓN DE ERROR DE TIPO DE DATOS
    if 'Observaciones' in df_c.columns:
        df_c['Observaciones'] = df_c['Observaciones'].astype(str).replace(['None', 'nan', 'nan ', '<NA>'], '')
    
    return df_c, df_f

# Cargamos los datos globales
df_cli, df_fin = load_data()

# Limpiamos DF para visualización (quitando ID)
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli
df_fin_view = df_fin.drop(columns=['id']) if 'id' in df_fin.columns else df_fin

st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Créditos", "📊 Reporte Financiero"])

# --- PESTAÑA 1: CLIENTES ---
with t1:
    st.subheader("📝 Gestión de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente:", "")
    
    df_mostrar = df_cli_view.copy()
    if busqueda:
        df_mostrar = df_cli_view[df_cli_view['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            val_str = str(val).strip().lower()
            fecha_v = datetime.strptime(f"{val_str}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fecha_v - datetime.now()).days
            if dias <= 2: 
                return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: 
                return 'background-color: #ffeb3b; color: black'
            return ''
        except:
            return ''

    # Editor de datos
    df_editado = st.data_editor(
        df_mostrar.style.applymap(color_vencimiento, subset=['Vencimiento']),
        column_config={
            "WhatsApp": st.column_config.TextColumn("WhatsApp"),
            "Observaciones": st.column_config.TextColumn("Observaciones"),
            "Usuario": st.column_config.Column(disabled=True),
            "Servicio": st.column_config.Column(disabled=True),
            "Vencimiento": st.

