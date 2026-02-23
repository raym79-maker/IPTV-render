import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy
import urllib.parse

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="IPTV Pro Admin", layout="wide", page_icon="🖥️")

# --- 2. CONEXIÓN A BASE DE DATOS ---
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

# --- 3. CARGA DE DATOS ---
df_cli, df_fin = load_data()
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Gestión", "📊 Reporte Financiero"])

# PESTAÑA 1: LISTA DE CLIENTES
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

    if st.button("💾 Guardar Cambios en Notas"):
        engine = get_engine()
        with engine.connect() as conn:
            for _, r in df_editado.iterrows():
                conn.execute(
                    sqlalchemy.text('UPDATE clientes SET "WhatsApp"=:w, "Observaciones"=:o WHERE "Usuario"=:u'),
                    {"w": str(r["WhatsApp"]), "o": str(r["Observaciones"]), "u": r["Usuario"]}
                )
            conn.commit()
        st.success("¡Datos actualizados!")
        st.rerun()

# PESTAÑA 2: VENTAS Y CRÉDITOS (LAS 3 COLUMNAS)
with t2:
    c1, c2, c3 = st.columns(3)
    engine = get_engine()

    # COLUMNA 1: RENOVACIÓN
    with c1:
        st.subheader("🔄 Renovación")
        u_renov = st.selectbox("Elegir cliente:", ["---"] + list(df_cli['Usuario'].unique()), key="renov_u")
        with st.form("form_renov"):
            prod_r = st.selectbox("Producto:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            meses_r = st.number_input("Meses:", 1, 12, 1)
            pago_r = st.number_input("Precio ($):", 0.0)
            if st.form_submit_button("💰 Registrar Renovación"):
                if u_renov != "---":
                    fv = (datetime.now() + timedelta(days=meses_r*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('UPDATE clientes SET "Vencimiento"=:v, "Servicio"=:s WHERE "Usuario"=:u'),
                                     {"v": fv, "s": prod_r, "u": u_renov})
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                     {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Renovación {prod_r}: {u_renov}", "m": pago_r})
                        conn.commit()
                    st.rerun()

    # COLUMNA 2: NUEVO REGISTRO
    with c2:
        st.subheader("➕ Nuevo Registro")
        with st.form("form_nuevo"):
            new_u = st.text_input("Usuario")
            new_p = st.selectbox("Panel", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            new_w = st.text_input("WhatsApp")
            new_m = st.number_input("Meses iniciales", 1, 12, 1)
            new_i = st.number_input("Precio cobrado ($)", 0.0)
            if st.form_submit_button("💾 Crear Cliente"):
                if new_u:
                    fv_n = (datetime.now() + timedelta(days=new_m*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO clientes ("Usuario", "Servicio", "Vencimiento", "WhatsApp", "Observaciones") VALUES (:u, :s, :v, :w, :o)'),
                                     {"u": new_u, "s": new_p, "v": fv_n, "w": new_w, "o": ""})
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                     {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Nuevo: {new_u} ({new_p})", "m": new_i})
                        conn.commit()
                    st.rerun()

    # COLUMNA 3: EGRESOS / CRÉDITOS
    with c3:
        st.subheader("💳 Egresos / Créditos")
        with st.form("form_egreso"):
            det_e = st.text_input("Detalle (Ej: Compra créditos)")
            costo_e = st.number_input("Costo pagado ($):", 0.0)
            if st.form_submit_button("📦 Registrar Gasto"):
                if det_e:
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo
