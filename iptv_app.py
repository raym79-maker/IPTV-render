import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlalchemy

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Administración IPTV Pro", layout="wide")

# --- 2. CONFIGURACIÓN DE BASE DE DATOS ---
def get_engine():
    # Railway inyecta automáticamente la variable DATABASE_URL
    url = os.getenv("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return sqlalchemy.create_engine(url)

def inicializar_tablas():
    engine = get_engine()
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
    
    # CORRECCIÓN DE ERROR DE TIPO DE DATOS EN OBSERVACIONES
    if 'Observaciones' in df_c.columns:
        df_c['Observaciones'] = df_c['Observaciones'].astype(str).replace(['None', 'nan', 'nan ', '<NA>'], '')
    
    return df_c, df_f

# Cargamos los datos globales
df_cli, df_fin = load_data()

# Limpiamos DF para visualización (quitando ID interno)
df_cli_view = df_cli.drop(columns=['id']) if 'id' in df_cli.columns else df_cli
df_fin_view = df_fin.drop(columns=['id']) if 'id' in df_fin.columns else df_fin

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Créditos", "📊 Reporte Financiero"])

# --- PESTAÑA 1: GESTIÓN DE CLIENTES ---
with t1:
    st.subheader("📝 Gestión de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente por nombre:", "")
    
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

    # Editor de datos para notas y whatsapp
    df_editado = st.data_editor(
        df_mostrar.style.applymap(color_vencimiento, subset=['Vencimiento']),
        column_config={
            "WhatsApp": st.column_config.TextColumn("WhatsApp"),
            "Observaciones": st.column_config.TextColumn("Observaciones"),
            "Usuario": st.column_config.Column(disabled=True),
            "Servicio": st.column_config.Column(disabled=True),
            "Vencimiento": st.column_config.Column(disabled=True)
        },
        use_container_width=True, hide_index=True, key="editor_final"
    )

    if st.button("💾 Guardar Cambios en Notas/WhatsApp"):
        engine = get_engine()
        with engine.connect() as conn:
            for _, row in df_editado.iterrows():
                conn.execute(
                    sqlalchemy.text('UPDATE clientes SET "WhatsApp" = :w, "Observaciones" = :o WHERE "Usuario" = :u'),
                    {"w": str(row["WhatsApp"]), "o": str(row["Observaciones"]), "u": row["Usuario"]}
                )
            conn.commit()
        st.success("¡Base de Datos Actualizada!")
        st.rerun()

    st.divider()
    
    st.subheader("🗑️ Eliminar Usuario")
    u_del = st.selectbox("Selecciona un usuario para dar de baja:", ["---"] + list(df_cli['Usuario'].unique()))
    if st.button("❌ Confirmar Eliminación"):
        if u_del != "---":
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text('DELETE FROM clientes WHERE "Usuario" = :u'), {"u": u_del})
                conn.commit()
            st.success(f"Usuario {u_del} eliminado correctamente")
            st.rerun()

# --- PESTAÑA 2: VENTAS Y GESTIÓN DE CRÉDITOS ---
with t2:
    # Las 3 columnas originales que mencionaste
    c1, c2, c3 = st.columns(3)
    engine = get_engine()
    
    with c1:
        st.subheader("🔄 Renovación")
        u_renov = st.selectbox("Elegir cliente para renovar:", ["---"] + list(df_cli['Usuario'].unique()), key="sb_renov")
        with st.form("f_renov"):
            pr = st.selectbox("Producto:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            cant_c = st.number_input("Meses a renovar:", min_value=1, value=1)
            vl = st.number_input("Precio cobrado ($):", min_value=0.0)
            if st.form_submit_button("💰 Registrar Renovación"):
                if u_renov != "---":
                    fv = (datetime.now() + timedelta(days=cant_c*30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(
                            sqlalchemy.text('UPDATE clientes SET "Vencimiento" = :v, "Servicio" = :s WHERE "Usuario" = :u'),
                            {"v": fv, "s": pr, "u": u_renov}
                        )
                        conn.execute(
                            sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                            {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Renov {cant_c}m {pr}: {u_renov}", "m": vl}
                        )
                        conn.commit()
                    st.rerun()

    with c2:
        st.subheader("➕ Nuevo Registro")
        with st.form("f_nuevo"):
            nu = st.text_input("Nombre de Usuario")
            np = st.selectbox("Elegir Panel", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            nw = st.text_input("Número de WhatsApp")
            ni_val = st.number_input("Precio de venta ($)", min_value=0.0)
            if st.form_submit_button("💾 Crear Usuario"):
                if nu:
                    fv = (datetime.now() + timedelta(days=30)).strftime('%d-%b').lower()
                    with engine.connect() as conn:
                        conn.execute(
                            sqlalchemy.text('INSERT INTO clientes ("Usuario", "Servicio", "Vencimiento", "WhatsApp", "Observaciones") VALUES (:u, :s, :v, :w, :o)'),
                            {"u": nu, "s": np, "v": fv, "w": nw, "o": ""}
                        )
                        if ni_val > 0:
                            conn.execute(
                                sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                                {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Ingreso", "d": f"Nuevo: {nu}", "m": ni_val}
                            )
                        conn.commit()
                    st.rerun()

    with c3:
        st.subheader("💳 Egresos / Créditos")
        with st.form("f_egr"):
            det_e = st.text_input("Detalle del gasto (Ej: Compra de créditos)")
            mnt_e = st.number_input("Costo total pagado ($)", min_value=0.0)
            if st.form_submit_button("📦 Registrar Gasto"):
                if det_e and mnt_e > 0:
                    with engine.connect() as conn:
                        conn.execute(
                            sqlalchemy.text('INSERT INTO finanzas ("Fecha", "Tipo", "Detalle", "Monto") VALUES (:f, :t, :d, :m)'),
                            {"f": datetime.now().strftime("%Y-%m-%d"), "t": "Egreso", "d": det_e, "m": mnt_e}
                        )
                        conn.commit()
                    st.rerun()

# --- PESTAÑA 3: REPORTES FINANCIEROS Y EXPORTACIÓN ---
with t3:
    st.subheader("📊 Resumen de Utilidades")
    
    # 1. Cálculos de dinero
    df_fin_view['Monto'] = pd.to_numeric(df_fin_view['Monto'], errors='coerce')
    ing = df_fin_view[df_fin_view['Tipo']=="Ingreso"]['Monto'].sum()
    egr = df_fin_view[df_fin_view['Tipo']=="Egreso"]['Monto'].sum()
    
    # 2. Mostrar métricas
    st.metric("Utilidad Actual", f"${ing - egr:,.2f}", delta=f"Gastos totales: ${egr}")
    
    # 3. Mostrar tabla si hay datos
    if not df_fin_view.empty:
        st.dataframe(df_fin_view.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay movimientos financieros registrados.")

    # 4. BOTÓN DE EXPORTAR (FUERA DEL IF PARA QUE SIEMPRE SE VEA)
    st.divider()
    st.write("📂 **Exportar Contabilidad**")
    
    # Preparamos el archivo aunque esté vacío
    csv_data = df_fin_view.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="📥 Descargar historial financiero para Excel",
        data=csv_data,
        file_name=f'reporte_iptv_{datetime.now().strftime("%Y-%m-%d")}.csv',
        mime='text/csv',
        key="btn_descarga_final"
    )
