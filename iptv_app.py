import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Configuración de página
st.set_page_config(page_title="Administración IPTV Pro", layout="wide")

# --- CARGA DE DATOS LOCALES ---
def load_data():
    if os.path.exists('database.csv'):
        df_c = pd.read_csv('database.csv')
    else:
        df_c = pd.DataFrame(columns=['Usuario','Servicio','Vencimiento','WhatsApp','Observaciones'])
    
    if os.path.exists('finanzas.csv'):
        df_f = pd.read_csv('finanzas.csv')
    else:
        df_f = pd.DataFrame(columns=['Fecha','Tipo','Detalle','Monto'])
        
    return df_c.fillna(""), df_f.fillna("")

df_cli, df_fin = load_data()

st.title("🖥️ Administración IPTV Pro")

t1, t2, t3 = st.tabs(["📋 Lista de Clientes", "🛒 Ventas y Créditos", "📊 Reporte Financiero"])

# --- PESTAÑA 1: CLIENTES (CON COLORES Y ELIMINACIÓN) ---
with t1:
    st.subheader("📝 Gestión de Clientes")
    busqueda = st.text_input("🔍 Buscar cliente:", "")
    
    df_mostrar = df_cli.copy()
    if busqueda:
        df_mostrar = df_cli[df_cli['Usuario'].str.contains(busqueda, case=False, na=False)]

    def color_vencimiento(val):
        try:
            fecha_v = datetime.strptime(f"{val}-{datetime.now().year}", "%d-%b-%Y")
            dias = (fecha_v - datetime.now()).days
            if dias <= 2: return 'background-color: #ff4b4b; color: white'
            elif dias <= 5: return 'background-color: #ffeb3b; color: black'
            return ''
        except: return ''

    # Editor de datos
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

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("💾 Guardar Cambios"):
            try:
                if busqueda: df_cli.update(df_editado)
                else: df_cli = df_editado
                df_cli.to_csv('database.csv', index=False)
                st.success("¡Guardado!")
                st.rerun()
            except: st.error("Cierra el Excel")

    st.divider()
    
    # SECCIÓN RESTAURADA: ELIMINAR USUARIO
    st.subheader("🗑️ Eliminar Usuario")
    u_del = st.selectbox("Selecciona para borrar:", ["---"] + list(df_cli['Usuario'].unique()))
    if st.button("❌ Confirmar Eliminación"):
        if u_del != "---":
            new_df = df_cli[df_cli['Usuario'] != u_del]
            new_df.to_csv('database.csv', index=False)
            st.success(f"Usuario {u_del} eliminado")
            st.rerun()

# --- PESTAÑA 2: VENTAS (RENOVACIÓN CON CRÉDITOS) ---
with t2:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("🔄 Renovación")
        u_s = st.selectbox("Elegir cliente:", ["---"] + list(df_cli['Usuario'].unique()))
        with st.form("f_renov"):
            pr = st.selectbox("Producto:", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            cant_c = st.number_input("Meses (Créditos):", min_value=1, value=1)
            vl = st.number_input("Precio ($):", min_value=0.0)
            if st.form_submit_button("💰 Registrar Venta"):
                if u_s != "---":
                    idx = df_cli[df_cli['Usuario'] == u_s].index[0]
                    fv = (datetime.now() + timedelta(days=cant_c*30)).strftime('%d-%b').lower()
                    df_cli.at[idx, 'Vencimiento'], df_cli.at[idx, 'Servicio'] = fv, pr
                    df_cli.to_csv('database.csv', index=False)
                    # Finanzas
                    ni = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d"), "Tipo": "Ingreso", "Detalle": f"Renov {cant_c}m {pr}: {u_s}", "Monto": vl}])
                    pd.concat([df_fin, ni], ignore_index=True).to_csv('finanzas.csv', index=False)
                    st.rerun()

    with c2:
        st.subheader("➕ Nuevo Registro")
        with st.form("f_nuevo"):
            nu = st.text_input("Usuario")
            np = st.selectbox("Panel", ["M327", "LEDTV", "SMARTBOX", "ALFA TV"])
            nw = st.text_input("WhatsApp")
            ni = st.number_input("Precio ($) ", min_value=0.0)
            if st.form_submit_button("💾 Crear"):
                if nu:
                    fv = (datetime.now() + timedelta(days=30)).strftime('%d-%b').lower()
                    nr = pd.DataFrame([{"Usuario": nu, "Servicio": np, "Vencimiento": fv, "WhatsApp": nw, "Observaciones": ""}])
                    pd.concat([df_cli, nr], ignore_index=True).to_csv('database.csv', index=False)
                    st.rerun()

    with c3:
        st.subheader("💳 Egresos / Créditos")
        with st.form("f_egr"):
            det_e = st.text_input("Detalle (Ej: 50 Créditos M327)")
            mnt_e = st.number_input("Costo pagado ($) ", min_value=0.0)
            if st.form_submit_button("📦 Registrar Compra"):
                if det_e and mnt_e > 0:
                    ne = pd.DataFrame([{"Fecha": datetime.now().strftime("%Y-%m-%d"), "Tipo": "Egreso", "Detalle": det_e, "Monto": mnt_e}])
                    pd.concat([df_fin, ne], ignore_index=True).to_csv('finanzas.csv', index=False)
                    st.rerun()

# --- PESTAÑA 3: REPORTES ---
with t3:
    st.subheader("📊 Reporte Financiero")
    df_fin['Monto'] = pd.to_numeric(df_fin['Monto'], errors='coerce')
    ing, egr = df_fin[df_fin['Tipo']=="Ingreso"]['Monto'].sum(), df_fin[df_fin['Tipo']=="Egreso"]['Monto'].sum()
    st.metric("Utilidad Neta", f"${ing - egr:,.2f}", delta=f"Gastos: ${egr}")
    st.dataframe(df_fin.sort_values("Fecha", ascending=False), use_container_width=True, hide_index=True)