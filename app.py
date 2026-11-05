import streamlit as st
import pandas as pd
import time
import random
import os
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
import qrcode
import tempfile

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS GRAFITECNIA
# ==========================================
st.set_page_config(
    page_title="Grafitecnia - Sistema ARCA", 
    layout="wide", 
    initial_sidebar_state="collapsed" # Fuerza la ocultación de la barra lateral
)

st.markdown("""
    <style>
    /* Forzar fondo blanco y limpieza visual */
    .stApp { background-color: #FFFFFF; }
    
    /* Ocultar barra lateral y elementos por defecto de Streamlit */
    [data-testid="collapsedControl"] { display: none; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Botones primarios con el naranja institucional */
    .stButton>button {
        background-color: #F26522 !important;
        color: white !important;
        border: none !important;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #d95316 !important;
    }
    h1, h2, h3 { color: #333333; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INICIALIZACIÓN DE BASE DE DATOS SIMULADA (STATE)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

if "db_facturas" not in st.session_state:
    st.session_state.db_facturas = pd.DataFrame({
        "Fecha": ["2026-11-01", "2026-11-02", "2026-11-03"],
        "Tipo": ["Factura A", "Factura A", "Factura B"],
        "N_Comprobante": ["0001-00000001", "0001-00000002", "0001-00000003"],
        "CUIT": ["30712345678", "33555555559", "20123456789"],
        "Cliente": ["Acme Corp", "Industrias TFI", "Consumidor Final"],
        "N_OC": ["OC-1001", "OC-1002", "OC-1003"],
        "Neto_Gravado": [100000, 50000, 10000],
        "IVA": [21000, 10500, 2100],
        "Total": [121000, 60500, 12100],
        "Estado": ["Aprobada", "Aprobada", "Aprobada"],
        "CAE": ["73158941234567", "73158941234568", "73158941234569"]
    })

if "db_ocs" not in st.session_state:
    st.session_state.db_ocs = {"OC-1001", "OC-1002", "OC-1003"}

if "paso_operativo" not in st.session_state:
    st.session_state.paso_operativo = "carga"

if "factura_actual" not in st.session_state:
    st.session_state.factura_actual = None

# ==========================================
# FUNCIONES AUXILIARES (PDF Y QR)
# ==========================================
def generar_qr(cuit, cae):
    qr = qrcode.QRCode(version=1, box_size=4, border=4)
    datos_qr = f"https://www.afip.gob.ar/fe/qr/?cuit={cuit}&cae={cae}"
    qr.add_data(datos_qr)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp_img.name)
    return temp_img.name

def generar_pdf_factura(datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(242, 101, 34)
    pdf.cell(0, 10, "GRAFITECNIA - FACTURA ELECTRONICA", ln=True, align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Comprobante: {datos['N_Comprobante']}  |  Fecha: {datos['Fecha']}", ln=True, align='C')
    pdf.line(10, 30, 200, 30)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(100, 8, f"Cliente: {datos['Cliente']}", ln=False)
    pdf.cell(90, 8, f"CUIT: {datos['CUIT']}", ln=True)
    pdf.cell(100, 8, f"Orden de Compra: {datos['N_OC']}", ln=False)
    pdf.cell(90, 8, f"Remito: {datos['Remito']}", ln=True)
    pdf.line(10, 50, 200, 50)
    pdf.ln(10)
    pdf.set_font("Arial", '', 11)
    pdf.cell(140, 8, "Concepto", 1)
    pdf.cell(50, 8, "Importe", 1, ln=True, align='C')
    pdf.cell(140, 8, "Neto Gravado", 1)
    pdf.cell(50, 8, f"$ {datos['Neto_Gravado']:,.2f}", 1, ln=True, align='R')
    pdf.cell(140, 8, "IVA", 1)
    pdf.cell(50, 8, f"$ {datos['IVA']:,.2f}", 1, ln=True, align='R')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(140, 10, "TOTAL", 1)
    pdf.cell(50, 10, f"$ {datos['Total']:,.2f}", 1, ln=True, align='R')
    pdf.ln(20)
    qr_path = generar_qr(datos['CUIT'], datos['CAE'])
    pdf.image(qr_path, x=10, w=30)
    pdf.set_xy(45, pdf.get_y() - 20)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, f"CAE: {datos['CAE']}", ln=True)
    pdf.set_x(45)
    pdf.cell(0, 8, "Vencimiento CAE: " + (pd.to_datetime(datos['Fecha']) + pd.Timedelta(days=10)).strftime("%Y-%m-%d"), ln=True)
    return pdf.output(dest='S')

# ==========================================
# RENDERIZADO DEL LOGO CORPORATIVO (BLOQUE SEGURO)
# ==========================================
col_logo, col_vacia = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=200)
    else:
        st.markdown("<h2 style='color: #F26522;'>GRAFITECNIA</h2>", unsafe_allow_html=True)
st.divider()

# ==========================================
# SISTEMA DE LOGIN Y RUTEO SIN BARRA LATERAL
# ==========================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align: center;'>Portal de Facturacion ARCA</h3>", unsafe_allow_html=True)
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contrasena", type="password")
            submit = st.form_submit_button("Ingresar al Sistema")
            
            if submit:
                if usuario == "admin" and password == "admin":
                    st.session_state.logged_in = True
                    st.session_state.role = "Administracion"
                    st.rerun()
                elif usuario == "director" and password == "director":
                    st.session_state.logged_in = True
                    st.session_state.role = "Direccion"
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas. Verifique usuario y contrasena.")
    st.stop()

# ==========================================
# NAVEGACIÓN SUPERIOR (TABS) SEGÚN ROL
# ==========================================
col_titulo, col_boton = st.columns([4, 1])
with col_titulo:
    st.write(f"Sesion iniciada como: **{st.session_state.role}**")
with col_boton:
    if st.button("Cerrar Sesion"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

if st.session_state.role == "Administracion":
    tabs = st.tabs(["Consola Operativa", "Dashboard Directivo", "Reporte Contable"])
else:
    tabs = st.tabs(["Dashboard Directivo", "Reporte Contable"])
    
# Ajuste de índices de tabs según el rol
tab_operativa = tabs[0] if st.session_state.role == "Administracion" else None
tab_dashboard = tabs[1] if st.session_state.role == "Administracion" else tabs[0]
tab_reporte = tabs[2] if st.session_state.role == "Administracion" else tabs[1]

# ==========================================
# CONSOLA OPERATIVA (HU 1, 2, 3, 4, 5)
# ==========================================
if tab_operativa:
    with tab_operativa:
        st.header("Consola Operativa - Emision de Comprobantes")
        
        if st.session_state.paso_operativo == "carga":
            st.write("Arrastre la Orden de Compra en formato PDF para extraer los datos mediante Inteligencia Artificial.")
            archivo = st.file_uploader("Cargar Orden de Compra", type=["pdf"])
            
            if archivo is not None:
                if st.button("Procesar documento"):
                    with st.spinner("Procesando documento con Inteligencia Artificial..."):
                        time.sleep(3)
                        st.session_state.factura_actual = {
                            "CUIT": "30111222334",
                            "Cliente": "Cliente Simulado S.A.",
                            "N_OC": f"OC-{random.randint(2000, 9999)}",
                            "Concepto": "Carteleria corporea acrilico e instalacion",
                            "Cantidad": 1,
                            "Precio_Unitario": 150000.0,
                            "Remito": "0000"
                        }
                        st.session_state.paso_operativo = "revision"
                        st.rerun()

        elif st.session_state.paso_operativo == "revision":
            st.subheader("Revision de Reglas de Negocio y Datos Extraidos")
            datos = st.session_state.factura_actual
            
            with st.form("form_revision"):
                col1, col2 = st.columns(2)
                with col1:
                    cuit = st.text_input("CUIT Receptor", value=datos["CUIT"], max_chars=11)
                    cliente = st.text_input("Razon Social", value=datos["Cliente"])
                    n_oc = st.text_input("Nro Orden de Compra", value=datos["N_OC"])
                    remito = st.text_input("Nro Remito Fisico", value=datos["Remito"])
                with col2:
                    concepto = st.text_input("Descripcion", value=datos["Concepto"])
                    cantidad = st.number_input("Cantidad", value=datos["Cantidad"], step=1, min_value=1)
                    precio_u = st.number_input("Precio Unitario", value=datos["Precio_Unitario"], step=100.0)
                    alicuota_iva = st.selectbox("Alicuota IVA", ["21%", "10.5%"])
                
                subtotal = cantidad * precio_u
                iva_calc = subtotal * (0.21 if alicuota_iva == "21%" else 0.105)
                total = subtotal + iva_calc
                
                st.info(f"Proyeccion Impositiva: Neto: ${subtotal:,.2f} | IVA: ${iva_calc:,.2f} | TOTAL: ${total:,.2f}")
                
                submit_factura = st.form_submit_button("Confirmar y Emitir CAE (ARCA)")
                
                if submit_factura:
                    if len(cuit) != 11 or not cuit.isdigit():
                        st.error("Error de Regla ARCA: El CUIT debe contener exactamente 11 digitos numericos.")
                    elif n_oc in st.session_state.db_ocs:
                        st.error("Error de Duplicidad: Esta Orden de Compra ya fue facturada anteriormente.")
                    else:
                        st.session_state.factura_actual.update({
                            "CUIT": cuit, "Cliente": cliente, "N_OC": n_oc, "Remito": remito,
                            "Neto_Gravado": subtotal, "IVA": iva_calc, "Total": total
                        })
                        st.session_state.paso_operativo = "emision"
                        st.rerun()
                        
            if st.button("Cancelar operacion"):
                st.session_state.paso_operativo = "carga"
                st.rerun()

        elif st.session_state.paso_operativo == "emision":
            st.subheader("Comunicacion con ARCA")
            
            with st.spinner("Conectando con Web Service de ARCA y solicitando CAE..."):
                time.sleep(2.5)
                datos = st.session_state.factura_actual
                datos["Fecha"] = datetime.now().strftime("%Y-%m-%d")
                datos["N_Comprobante"] = f"0001-{random.randint(1000000, 9999999)}"
                datos["CAE"] = str(random.randint(70000000000000, 79999999999999))
                datos["Tipo"] = "Factura A"
                datos["Estado"] = "Aprobada"
                
                nueva_fila = pd.DataFrame([datos])
                st.session_state.db_facturas = pd.concat([st.session_state.db_facturas, nueva_fila], ignore_index=True)
                st.session_state.db_ocs.add(datos["N_OC"])
                
                st.success("Comprobante emitido con exito.")
                st.write(f"**Nro Comprobante:** {datos['N_Comprobante']}")
                st.write(f"**Nro CAE:** {datos['CAE']}")
                
                pdf_bytes = generar_pdf_factura(datos)
                
                st.download_button(
                    label="Descargar Factura PDF Legal",
                    data=pdf_bytes,
                    file_name=f"Factura_{datos['N_Comprobante']}.pdf",
                    mime="application/pdf"
                )
                
            if st.button("Volver al Inicio"):
                st.session_state.paso_operativo = "carga"
                st.rerun()

# ==========================================
# DASHBOARD DIRECTIVO (HU 6)
# ==========================================
with tab_dashboard:
    st.header("Dashboard Directivo")
    df = st.session_state.db_facturas
    
    if df.empty:
        st.warning("No hay comprobantes emitidos en el sistema.")
    else:
        col1, col2, col3 = st.columns(3)
        total_mes = df['Total'].sum()
        cant_facturas = len(df)
        aprobadas = len(df[df['Estado'] == 'Aprobada'])
        
        col1.metric("Total Facturado (Mes)", f"${total_mes:,.2f}")
        col2.metric("Comprobantes Emitidos", cant_facturas)
        col3.metric("Facturas Aprobadas", aprobadas)
        
        st.divider()
        st.subheader("Volumen de Facturacion por Cliente")
        chart_data = df.groupby('Cliente')['Total'].sum().reset_index()
        st.bar_chart(chart_data.set_index('Cliente'))
        
        st.subheader("Historial Operativo")
        cliente_filtro = st.selectbox("Filtrar por Cliente", ["Todos"] + list(df['Cliente'].unique()))
        df_mostrar = df if cliente_filtro == "Todos" else df[df['Cliente'] == cliente_filtro]
        st.dataframe(df_mostrar[['Fecha', 'N_Comprobante', 'Cliente', 'N_OC', 'Total', 'Estado']], use_container_width=True)

# ==========================================
# REPORTE PARA ESTUDIO CONTABLE (HU 7)
# ==========================================
with tab_reporte:
    st.header("Exportacion para Estudio Contable")
    
    col1, col2 = st.columns(2)
    with col1:
        mes_seleccionado = st.selectbox("Seleccione Mes", ["Noviembre", "Diciembre"])
    with col2:
        anio_seleccionado = st.selectbox("Seleccione Ano", ["2026", "2027"])
        
    df = st.session_state.db_facturas
    st.write("Vista Previa del Libro IVA Ventas:")
    cols_contables = ['Fecha', 'Tipo', 'N_Comprobante', 'CUIT', 'Cliente', 'Neto_Gravado', 'IVA', 'Total', 'CAE']
    
    if df.empty:
        st.warning("No hay datos para el periodo seleccionado.")
    else:
        st.dataframe(df[cols_contables], use_container_width=True)
        csv = df[cols_contables].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Exportar Reporte de Ventas CSV",
            data=csv,
            file_name=f"Subdiario_Ventas_{mes_seleccionado}_{anio_seleccionado}.csv",
            mime="text/csv",
        )