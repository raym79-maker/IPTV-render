import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Administración IPTV Pro", layout="wide")

def get_engine():
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def inicializar_y_migrar():
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY, "Usuario" TEXT UNIQUE, "Servicio" TEXT, 
                "Vencimiento" TEXT, "WhatsApp" TEXT, "Observaciones" TEXT
            );
            CREATE TABLE IF NOT EXISTS finanzas (
                id SERIAL PRIMARY KEY, "Fecha" TEXT, "Tipo" TEXT, "Detalle" TEXT, "Monto" FLOAT
            );
        """))
        # Migración forzada para evitar el error de "double precision"
        try:
            conn.execute(sqlalchemy.text('ALTER TABLE clientes ALTER COLUMN "WhatsApp" TYPE TEXT'))
            conn.execute(sqlalchemy.text('ALTER TABLE clientes ALTER COLUMN "Observaciones" TYPE TEXT'))
        except: pass
        conn.commit()

def load_data():
    engine = get_engine()
    inicializar_y_migrar()
    df_c = pd.read_sql("SELECT * FROM clientes", engine)
    df_f = pd.read_sql("SELECT * FROM finanzas", engine)
    for col in ['WhatsApp', 'Observaciones']:
        if col in df_c.columns: df_c[col] = df_c[col].astype(str).replace(['None', 'nan', '<NA>'], '')
    return df_c, df_f

df_cli, df_fin = load_data()

# --- 2. INTERFAZ ---
st.title("🖥️ Administración IPTV Pro")
t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Créditos", "📊 Reporte Financiero"])

# --- PESTAÑA 1: CLIENTES (CON ORDEN Y ELIMINACIÓN) ---
with t1:
    st.subheader("📝 Gestión de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente:", "")
    
    # Lógica de Ordenamiento Cronológico
    def parse_fecha(val):
        try: return datetime.strptime(f"{str(val)}-{datetime.now().year}", "%d-%b-%Y")
        except: return datetime(2099, 1, 1)

    df_mostrar = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli.copy()
    df_mostrar['temp_sort'] = df_mostrar['Vencimiento'].apply(parse_fecha)
    df_mostrar = df_mostrar.sort_values(by='temp_sort', ascending=True).drop(columns=['temp_sort'])

    if busqueda:
        df_mostrar = df_mostrar[df_mostrar['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            fv = datetime.strptime(f"{str(val)}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fv - datetime.now()).days
            if dias <= 2: return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: return 'background-color: #ffeb3b; color: black'
            return ''
        except: return ''

    df_editado = st.data_editor(
        df_mostrar.style.applymap(color_vencimiento, subset=['Vencimiento']),
        column_config={"Usuario": st.column_config.Column(disabled=True), "Servicio": st.column_config.Column(disabled=True), "Vencimiento": st.column_config.Column(disabled=True)},
        use_container_width=True, hide_index=True, key="editor_vfinal"
    )

    if st.button("💾 Guardar Cambios"):
        with get_engine().connect() as conn:
            for _, row in df_editado.iterrows():
                conn.execute(sqlalchemy.text('UPDATE clientes SET "WhatsApp"=:w, "Observaciones"=:o WHERE "Usuario"=:u'),
                             {"w": str(row["WhatsApp"]), "o": str(row["Observaciones"]), "u": row["Usuario"]})
            conn.commit()
        st.rerun()

    st.divider()
    # --- BLOQUE RESTAURADO: ELIMINAR USUARIO ---
    st.subheader("🗑️ Eliminar Usuario")
    u_del = st.selectbox("Selecciona para borrar:", ["---"] + list(df_cli['Usuario'].unique()), key="del_box")
    if st.button("❌ Confirmar Eliminación"):
        if u_del != "---":
            with get_engine().connect() as conn:
                conn.execute(sqlalchemy.text('DELETE FROM clientes WHERE "Usuario"=:u'), {"u": u_del})
                conn.commit()
            st.success(f"Usuario {u_del} eliminado")
            st.rerun()

# --- PESTAÑA 2: VENTAS (3 COLUMNAS COMPLETAS) ---
with t2:
    c1, c2, c3 = st.columns(3)
    engine = get_engine()
    with c1:
        st.subheader("🔄 Renovación")
        u_ren = st.selectbox("Cliente:", ["---"] + list(df_cli['Usuario'].unique()), key="ren_box")
        with st.form("f_ren"):
            pr, ct, vl = st.selectbox("Prod:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"]), st.number_input("Meses:", 1, 12, 1), st.number_input("Precio ($):", 0.0)
            if st.form_submit_button("💰 Renovar"):
                if u_ren != "---":
                    fv = (datetime.now() + timedelta(days=ct*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('UPDATE clientes SET "Vencimiento"=:v, "Servicio"=:s WHERE "Usuario"=:u'), {"v":fv, "s":pr, "u":u_ren})
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'), {"f":datetime.now().strftime("%Y-%m-%d"), "t":"Ingreso", "d":f"Renov {ct}m: {u_ren}", "m":float(vl)})
                        conn.commit()
                    st.rerun()
    with c2:
        st.subheader("➕ Nuevo Registro")
        with st.form("f_nue"):
            nu, np, nw = st.text_input("Usuario"), st.selectbox("Panel", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"]), st.text_input("WhatsApp")
            ct_n, ni = st.number_input("Meses:", 1, 12, 1), st.number_input("Precio ($)", 0.0)
            if st.form_submit_button("💾 Crear"):
                if nu:
                    fv_n = (datetime.now() + timedelta(days=ct_n*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO clientes ("Usuario", "Servicio", "Vencimiento", "WhatsApp", "Observaciones") VALUES (:u, :s, :v, :w, :o)'), {"u":nu, "s":np, "v":fv_n, "w":nw, "o":""})
                        if ni > 0: conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'), {"f":datetime.now().strftime("%Y-%m-%d"), "t":"Ingreso", "d":f"Nuevo {ct_n}m: {nu}", "m":float(ni)})
                        conn.commit()
                    st.rerun()
    with c3:
        st.subheader("💳 Egresos / Créditos")
        with st.form("f_egr"):
            de, me = st.text_input("Detalle (Ej: Créditos M327)"), st.number_input("Costo ($)", 0.0)
            if st.form_submit_button("📦 Registrar Compra"):
                if de and me > 0:
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'), {"f":datetime.now().strftime("%Y-%m-%d"), "t":"Egreso", "d":de, "m":float(me)})
                        conn.commit()
                    st.rerun()

# --- PESTAÑA 3: REPORTES ---
with t3:
    st.subheader("📊 Reporte Financiero")
    df_fin['Monto'] = pd.to_numeric(df_fin['Monto'], errors='coerce').fillna(0.0)
    ing, egr = df_fin[df_fin['Tipo']=="Ingreso"]['Monto'].sum(), df_fin[df_fin['Tipo']=="Egreso"]['Monto'].sum()
    st.metric("Utilidad Neta", f"${ing - egr:,.2f}", delta=f"Gastos: ${egr}")
    st.dataframe(df_fin.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
    st.download_button("📥 Descargar Reporte CSV", df_fin.to_csv(index=False).encode('utf-8'), f'reporte_{datetime.now().strftime("%Y-%m-%d")}.csv', 'text/csv')
