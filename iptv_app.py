import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy
import urllib.parse

# Configuración inicial
st.set_page_config(page_title="IPTV Pro Admin", layout="wide", page_icon="🔐")

# --- 1. SEGURIDAD (LOGIN) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    with st.form("login"):
        st.title("🔐 Acceso Administrativo")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u == os.getenv("ADMIN_USER") and p == os.getenv("ADMIN_PASSWORD"):
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    return False

if not check_password():
    st.stop()

# --- 2. BASE DE DATOS ---
def get_engine():
    url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def load_data():
    engine = get_engine()
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    if 'Observaciones' in df_c.columns:
        df_c['Observaciones'] = df_c['Observaciones'].astype(str).replace(['None', 'nan', '<NA>'], '')
    return df_c, df_f

# --- 3. LÓGICA PRINCIPAL ---
df_cli, df_fin = load_data()
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli

st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({"password_correct": False}))
st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Clientes", "🛒 Ventas", "📊 Finanzas"])

with t1:
    busqueda = st.text_input("🔍 Buscar cliente:")
    df_m = df_cli_view.copy()
    if busqueda:
        df_m = df_m[df_m['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            fv = datetime.strptime(f"{val.strip().lower()}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fv - datetime.now()).days
            if dias <= 2: return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: return 'background-color: #ffeb3b; color: black'
            return ''
        except: return ''

    # EDITOR CORREGIDO (Línea 85-95 aprox)
    df_editado = st.data_editor(
