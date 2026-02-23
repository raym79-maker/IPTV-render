import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy
import urllib.parse

# Configuración de página
st.set_page_config(page_title="IPTV Pro Admin", layout="wide", page_icon="🔐")

# --- 1. SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    with st.form("login_form"):
        st.title("🔐 Acceso Administrativo")
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if user_input == os.getenv("ADMIN_USER") and pass_input == os.getenv("ADMIN_PASSWORD"):
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
    return False

if not check_password():
    st.stop()

# --- 2. CONFIGURACIÓN DE BASE DE DATOS ---
def get_engine():
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def load_data():
    engine = get_engine()
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    if 'Observaciones' in df_c.columns:
        df_c['Observaciones'] = df_c['Observaciones'].astype(str).replace(['None', 'nan', 'nan ', '<NA>'], '')
    return df_c, df_f

# --- 3. CARGA DE DATOS ---
df_cli, df_fin = load_data()
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli

# --- 4. INTERFAZ ---
st.sidebar.success(f"Sesión activa: {os.getenv('ADMIN_USER')}")
if st.sidebar.button("Log Out"):
    st.session_state["password_correct"] = False
    st.rerun()

st.title("🖥️ Administración IPTV Pro")
t1, t2, t3 = st.tabs(["📋 Clientes", "🛒 Ventas y Renovación", "📊 Finanzas"])

# PESTAÑA 1: GESTIÓN DE CLIENTES
with t1:
    st.subheader("Lista de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente:")
    df_m = df_cli_view.copy()
    if busqueda:
        df_m = df_m[df_m['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            val_str = str(val).strip().lower()
            fecha_v = datetime.strptime(f"{val_str}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fecha_v - datetime.now()).days
            if dias <= 2: return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: return 'background-color: #ffeb3b; color: black'
            return ''
        except: return ''

    # EDITOR DE DATOS CORREGIDO
    df_editado = st.data_editor(
        df_m.style.applymap(color_vencimiento, subset=['Vencimiento']),
        column_config={
            "WhatsApp": st.column_config.TextColumn("WhatsApp"),
            "Observaciones": st.column_config.TextColumn("Observaciones"),
            "Usuario": st.column_config.Column(disabled=True),
            "Servicio": st.column_config.Column(disabled=True),
            "Vencimiento": st.column_config.Column(disabled=True)
        },
        use_container_width=True, hide_index=True
    )

    if st.button("💾 Guardar Cambios"):
        engine = get_engine()
        with engine.connect() as conn:
            for _, r in df_editado.iterrows():
                conn.execute(sqlalchemy.text('UPDATE clientes SET "WhatsApp"=:w, "Observaciones"=:o WHERE "Usuario"=:u'),
                             {"w": str(r["WhatsApp"]), "o": str(r["Observaciones"]), "u": r["Usuario"]})
            conn.commit()
        st.success("¡Datos actualizados!")
        st.rerun()

    st.divider()
    st.subheader("📲 Recordatorio WhatsApp")
    u_wa = st.selectbox("Seleccionar cliente para mensaje:", ["---"] + list(df_cli['Usuario'].unique()))
    if u_wa != "---":
        row_wa = df_cli[df_cli['Usuario'] == u_wa].iloc[0]
        tel = str(row_wa['WhatsApp']).replace(" ", "").replace("+", "")
        msg = urllib.parse.quote(f"Hola {u_wa}, tu servicio de IPTV vence el {row_wa['Vencimiento']}. ¿Gustas renovar?")
        st.link_button(f"Enviar mensaje a {u_wa}", f"https://wa.me/{tel}?text={msg}")

# PESTAÑA 2: VENTAS
with t2:
    c1, c2 = st.columns(2)
    engine = get_engine()
    with c1:
        st.subheader("🔄 Renovación")
        u_ren = st.selectbox("Cliente:", ["---"] + list(df_cli['Usuario'].unique()), key="renov_sel")
        with st.form("f_renov"):
            prod = st.selectbox("Panel:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            meses = st.number_input("Meses:", min_value=1, value=1)
            pago = st.number_input("Precio ($):", min_value=0.0)
            if st.form_submit_button("💰 Registrar"):
                if u_ren != "---":
                    fv = (datetime.now() + timedelta(days=meses*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('UPDATE clientes SET "Vencimiento"=:v, "Servicio"=:s WHERE "Usuario"=:u'),
                                     {"v": fv, "s": prod, "u": u_ren})
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                     {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Renov {meses}m {prod}: {u_ren}", "m": pago})
                        conn.commit()
                    st.rerun()
    with c2:
        st.subheader("🗑️ Eliminar")
        u_del = st.selectbox("Borrar usuario:", ["---"] + list(df_cli['Usuario'].unique()))
        if st.button("❌ Eliminar"):
            if u_del != "---":
                with engine.connect() as conn:
                    conn.execute(sqlalchemy.text('DELETE FROM clientes WHERE "Usuario"=:u'), {"u": u_del})
                    conn.commit()
                st.rerun()

# PESTAÑA 3: FINANZAS
with t3:
    st.subheader("📊 Balance")
    if not df_fin.empty:
        df_fin['Monto'] = pd.to_numeric(df_fin['Monto'], errors='coerce')
        ing = df_fin[df_fin['Tipo']=="Ingreso"]['Monto'].sum()
        egr = df_fin[df_fin['Tipo']=="Egreso"]['Monto'].sum()
        st.metric("Utilidad Total", f"${ing - egr:,.2f}", delta=f"Gastos: ${egr}")
        st.dataframe(df_fin.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
