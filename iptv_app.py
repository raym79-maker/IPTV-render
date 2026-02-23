import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy
import urllib.parse

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="IPTV Pro Admin", layout="wide", page_icon="🔐")

# --- 2. SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    # Leemos las variables de Railway eliminando espacios accidentales
    admin_user = os.getenv("ADMIN_USER", "").strip()
    admin_pass = os.getenv("ADMIN_PASSWORD", "").strip()

    with st.form("login_form"):
        st.title("🔐 Acceso Administrativo")
        u = st.text_input("Usuario").strip()
        p = st.text_input("Contraseña", type="password").strip()
        
        if st.form_submit_button("Entrar"):
            if admin_user and admin_pass and u == admin_user and p == admin_pass:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
                if not admin_user or not admin_pass:
                    st.warning("⚠️ Railway no detecta ADMIN_USER o ADMIN_PASSWORD en Variables.")
    return False

if not check_password():
    st.stop()

# --- 3. CONEXIÓN A BASE DE DATOS ---
def get_engine():
    url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def load_data():
    engine = get_engine()
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    if 'Observaciones' in df_c.columns:
        df_c['Observaciones'] = df_c['Observaciones'].astype(str).replace(['None', 'nan', '<NA>', 'nan '], '')
    return df_c, df_f

# --- 4. CARGA DE DATOS ---
df_cli, df_fin = load_data()
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli

# --- 5. INTERFAZ PRINCIPAL ---
st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({"password_correct": False}))
st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Clientes", "🛒 Ventas y Renovación", "📊 Finanzas"])

# PESTAÑA 1: GESTIÓN DE CLIENTES
with t1:
    st.subheader("Clientes Activos")
    busqueda = st.text_input("🔍 Buscar por nombre:")
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
                conn.execute(
                    sqlalchemy.text('UPDATE clientes SET "WhatsApp"=:w, "Observaciones"=:o WHERE "Usuario"=:u'),
                    {"w": str(r["WhatsApp"]), "o": str(r["Observaciones"]), "u": r["Usuario"]}
                )
            conn.commit()
        st.success("¡Base de Datos Actualizada!")
        st.rerun()

# PESTAÑA 2: VENTAS Y RENOVACIÓN
with t2:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🔄 Registrar Renovación")
        u_renov = st.selectbox("Elegir cliente:", ["---"] + list(df_cli['Usuario'].unique()), key="sel_renov")
        with st.form("form_renov"):
            prod = st.selectbox("Producto:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            meses = st.number_input("Meses:", 1, 12, 1)
            pago = st.number_input("Monto cobrado ($):", 0.0)
            if st.form_submit_button("💰 Confirmar Pago"):
                if u_renov != "---":
                    fv = (datetime.now() + timedelta(days=meses*30)).strftime('%d-%b').lower()
                    with get_engine().connect() as conn:
                        # LÍNEA CORREGIDA Y CERRADA:
                        conn.execute(
                            sqlalchemy.text('UPDATE clientes SET "Vencimiento"=:v, "Servicio"=:s WHERE "Usuario"=:u'),
                            {"v": fv, "s": prod, "u": u_renov}
                        )
                        conn.execute(
                            sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                            {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Renovación {prod}: {u_renov}", "m": pago}
                        )
                        conn.commit()
                    st.rerun()

    with c2:
        st.subheader("📲 Recordatorio WhatsApp")
        if u_renov != "---":
            row_sel = df_cli[df_cli['Usuario'] == u_renov].iloc[0]
            tel = str(row_sel['WhatsApp']).replace(" ", "").replace("+", "")
            msg = urllib.parse.quote(f"Hola {u_renov}, tu servicio de IPTV vence el {row_sel['Vencimiento']}. ¿Deseas renovar?")
            st.link_button(f"Enviar mensaje a {u_renov}", f"https://wa.me/{tel}?text={msg}")

# PESTAÑA 3: REPORTES FINANCIEROS
with t3:
    st.subheader("📊 Balance")
    if not df_fin.empty:
        df_fin['Monto'] = pd.to_numeric(df_fin['Monto'], errors='coerce')
        ingresos = df_fin[df_fin['Tipo']=="Ingreso"]['Monto'].sum()
        egresos = df_fin[df_fin['Tipo']=="Egreso"]['Monto'].sum()
        st.metric("Balance Neto", f"${ingresos - egresos
