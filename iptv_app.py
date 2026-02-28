import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Administración IPTV Pro", layout="wide")

# --- 2. CONFIGURACIÓN DE BASE DE DATOS (RAILWAY) ---
def get_engine():
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def inicializar_tablas():
    engine = get_engine()
    with engine.connect() as conn:
        # Crea tablas si no existen
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
        # FIX: Forzamos que WhatsApp sea TEXTO para evitar el error de "double precision"
        try:
            conn.execute(sqlalchemy.text('ALTER TABLE clientes ALTER COLUMN "WhatsApp" TYPE TEXT'))
        except:
            pass
        conn.commit()

def load_data():
    engine = get_engine()
    inicializar_tablas()
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    # Limpieza de nulos para evitar errores en el editor
    for col in ['WhatsApp', 'Observaciones']:
        if col in df_c.columns:
            df_c[col] = df_c[col].astype(str).replace(['None', 'nan', '<NA>'], '')
    return df_c, df_f

df_cli, df_fin = load_data()
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli

# --- 3. INTERFAZ ---
st.title("🖥️ Administración IPTV Pro")
t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Créditos", "📊 Reporte Financiero"])

# --- PESTAÑA 1: GESTIÓN ---
with t1:
    st.subheader("📝 Gestión de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente:", "")
    df_mostrar = df_cli_view.copy()
    if busqueda:
        df_mostrar = df_cli_view[df_cli_view['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            fecha_v = datetime.strptime(f"{str(val)}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fecha_v - datetime.now()).days
            if dias <= 2: return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: return 'background-color: #ffeb3b; color: black'
            return ''
        except: return ''

    df_editado = st.data_editor(
        df_mostrar.style.applymap(color_vencimiento, subset=['Vencimiento']),
        column_config={
            "Usuario": st.column_config.Column(disabled=True),
            "Servicio": st.column_config.Column(disabled=True),
            "Vencimiento": st.column_config.Column(disabled=True)
        },
        use_container_width=True, hide_index=True, key="editor_final"
    )

    if st.button("💾 Guardar Cambios"):
        engine = get_engine()
        with engine.connect() as conn:
            for _, row in df_editado.iterrows():
                conn.execute(sqlalchemy.text('UPDATE clientes SET "WhatsApp"=:w, "Observaciones"=:o WHERE "Usuario"=:u'),
                             {"w": str(row["WhatsApp"]), "o": str(row["Observaciones"]), "u": row["Usuario"]})
            conn.commit()
        st.success("¡Base de Datos Actualizada!")
        st.rerun()

    st.divider()
    st.subheader("🗑️ Eliminar Usuario")
    u_del = st.selectbox("Selecciona para borrar:", ["---"] + list(df_cli['Usuario'].unique()))
    if st.button("❌ Confirmar Eliminación"):
        if u_del != "---":
            with get_engine().connect() as conn:
                conn.execute(sqlalchemy.text('DELETE FROM clientes WHERE "Usuario"=:u'), {"u": u_del})
                conn.commit()
            st.rerun()

# --- PESTAÑA 2: VENTAS (CON FIX DE PRECIO) ---
with t2:
    c1, c2, c3 = st.columns(3)
    engine = get_engine()
    
    with c1:
        st.subheader("🔄 Renovación")
        u_renov = st.selectbox("Elegir cliente:", ["---"] + list(df_cli['Usuario'].unique()), key="sb_ren")
        with st.form("f_renov"):
            pr = st.selectbox("Producto:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            cant_c = st.number_input("Meses a renovar:", min_value=1, value=1)
            vl = st.number_input("Precio cobrado ($):", min_value=0.0)
            if st.form_submit_button("💰 Registrar Renovación"):
                if u_renov != "---":
                    fv = (datetime.now() + timedelta(days=cant_c*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('UPDATE clientes SET "Vencimiento"=:v, "Servicio"=:s WHERE "Usuario"=:u'), {"v":fv, "s":pr, "u":u_renov})
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'), 
                                     {"f":datetime.now().strftime("%Y-%m-%d"), "t":"Ingreso", "d":f"Renov {cant_c}m: {u_renov}", "m":float(vl)})
                        conn.commit()
                    st.rerun()

    with c2:
        st.subheader("➕ Nuevo Registro")
        with st.form("f_nuevo"):
            nu = st.text_input("Nombre de Usuario")
            np = st.selectbox("Elegir Panel", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            nw = st.text_input("Número de WhatsApp")
            cant_c_n = st.number_input("Meses comprados:", min_value=1, value=1)
            ni_val = st.number_input("Precio de venta ($)", min_value=0.0)
            if st.form_submit_button("💾 Crear Usuario"):
                if nu:
                    fv_n = (datetime.now() + timedelta(days=cant_c_n*30)).strftime('%d-%b').lower()
                    # Limpiamos el WhatsApp para que sea texto
                    nw_clean = str(nw).strip()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO clientes ("Usuario", "Servicio", "Vencimiento", "WhatsApp", "Observaciones") VALUES (:u, :s, :v, :w, :o)'),
                                     {"u": nu, "s": np, "v": fv_n, "w": nw_clean, "o": ""})
                        if ni_val > 0:
                            conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                         {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Nuevo {cant_c_n}m: {nu}", "m": float(ni_val)})
                        conn.commit()
                    st.rerun()

    with c3:
        st.subheader("💳 Egresos / Créditos")
        with st.form("f_egr"):
            det_e = st.text_input("Detalle (Ej: Créditos M327)")
            mnt_e = st.number_input("Costo pagado ($)", min_value=0.0)
            if st.form_submit_button("📦 Registrar Compra"):
                if det_e and mnt_e > 0:
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                     {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Egreso", "d": det_e, "m": float(mnt_e)})
                        conn.commit()
                    st.rerun()

# --- PESTAÑA 3: FINANZAS ---
with t3:
    st.subheader("📊 Resumen Financiero")
    df_fin['Monto'] = pd.to_numeric(df_fin['Monto'], errors='coerce').fillna(0.0)
    ing, egr = df_fin[df_fin['Tipo']=="Ingreso"]['Monto'].sum(), df_fin[df_fin['Tipo']=="Egreso"]['Monto'].sum()
    st.metric("Utilidad Neta", f"${ing - egr:,.2f}", delta=f"Gastos: ${egr}")
    st.dataframe(df_fin.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
