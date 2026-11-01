import streamlit as st
import json
import os
import time
import datetime
from google import genai
from google.genai import types
from fpdf import FPDF
import qrcode

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Facturación IA (Prototipo TFI)", page_icon="🧾", layout="centered")

# --- REQUISITO CÁTEDRA: CONFIGURACIÓN IA ---
with st.sidebar:
    st.header("⚙️ Configuración del Modelo IA")
    st.info("Parámetros del proceso TO-BE simulado")
    st.write("**Rol:** Asistente de facturación comercial.")
    st.write("**Contexto:** Extracción automática de datos de Órdenes de Compra (PDF) para agilizar la facturación.")
    st.write("**Reglas de negocio:** Identificar CUIT válido, Razón Social, e ítems con cantidades y precios netos unitarios.")
    st.write("**Formato de salida:** JSON estricto estructurado.")
    st.write("**Restricciones:** No inventar datos, omitir impuestos en el precio unitario, derivar al usuario si falta el CUIT (Excepción).")

# --- CARGA DE API KEY GEMINI ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("Error al cargar la clave de Gemini. Revisá los Secrets en Streamlit.")
    st.stop()

# --- FUNCIONES DE NÚCLEO ---
def extraer_datos_oc(bytes_pdf: bytes) -> dict:
    prompt = """
    Analiza esta Orden de Compra y extrae los datos para facturación comercial en Argentina.
    Devuelve estrictamente un objeto JSON con esta estructura exacta:
    {
      "cuit_cliente": "solo digitos numericos sin guiones",
      "razon_social": "nombre de la empresa o cliente",
      "numero_oc": "identificador de OC",
      "items": [
        {
          "descripcion": "detalle del producto o servicio",
          "cantidad": float o int,
          "precio_unitario": float con precio neto unitario (sin $ ni separadores de miles),
          "alicuota_iva": float (21.0, 10.5 o 0.0)
        }
      ]
    }
    """
    
    modelos_disponibles = ["gemini-3.1-pro-preview", "gemini-3.5-flash", "gemini-2.5-flash"]
    ultimo_error = None
    
    for modelo in modelos_disponibles:
        for intento in range(1, 3):
            try:
                respuesta = gemini_client.models.generate_content(
                    model=modelo,
                    contents=[types.Part.from_bytes(data=bytes_pdf, mime_type="application/pdf"), prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                )
                if respuesta.text:
                    return json.loads(respuesta.text)
            except Exception as e:
                ultimo_error = e
                time.sleep(1)

    raise Exception(f"Servidores ocupados. Detalle: {ultimo_error}")

def emitir_factura_arca() -> dict:
    time.sleep(2) 
    return {
        "cae": "73245678901234",
        "vto_cae": (datetime.date.today() + datetime.timedelta(days=10)).strftime("%d/%m/%Y"),
        "nro_factura": 125
    }

def generar_pdf_factura(datos_fac: dict, items: list, archivo_salida="factura_emitida.pdf"):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "FACTURA (SIMULACION TFI)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    letra = "A" if datos_fac["tipo_cbte"] == 1 else "B"
    pdf.cell(0, 6, f"TIPO: {letra} - COD. {str(datos_fac['tipo_cbte']).zfill(2)}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, f"Punto de Venta: {str(datos_fac['punto_vta']).zfill(4)}", border="L,T")
    pdf.cell(95, 6, f"Comp. Nro: {str(datos_fac['nro_factura']).zfill(8)}", border="R,T", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, f"CUIT Emisor: {datos_fac['cuit_emisor']}", border="L,B")
    pdf.cell(95, 6, f"Fecha de Emision: {datos_fac['fecha_emision'].strftime('%d/%m/%Y')}", border="R,B", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    
    if datos_fac.get('concepto') in [2, 3]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"Periodo Facturado: Desde {datos_fac['fecha_desde'].strftime('%d/%m/%Y')} Hasta {datos_fac['fecha_hasta'].strftime('%d/%m/%Y')} | Vto. Pago: {datos_fac['vto_pago'].strftime('%d/%m/%Y')}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "DATOS DEL RECEPTOR Y CONDICIONES", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(105, 5, f"Razon Social: {datos_fac['razon_social']}", new_x="RIGHT")
    pdf.cell(85, 5, f"CUIT: {datos_fac['cuit_cliente']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(105, 5, f"Condicion de Venta: {datos_fac['condicion_venta']}", new_x="RIGHT")
    pdf.cell(85, 5, f"Condicion IVA: {datos_fac['condicion_iva_str']}", new_x="LMARGIN", new_y="NEXT")
    
    texto_docs = f"Orden de Compra: {datos_fac.get('numero_oc', 'N/A')}"
    if datos_fac.get('numero_remito'):
        fecha_r = datos_fac['fecha_remito'].strftime('%d/%m/%Y') if datos_fac.get('fecha_remito') else 'N/A'
        texto_docs += f" | Remito Nro: {datos_fac['numero_remito']} (Fecha: {fecha_r})"
    pdf.cell(0, 5, texto_docs, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(95, 7, "Descripcion", border=1)
    pdf.cell(25, 7, "Cantidad", border=1, align="C")
    pdf.cell(35, 7, "P. Unitario", border=1, align="R")
    pdf.cell(35, 7, "Subtotal", border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    for it in items:
        sub = it["cantidad"] * it["precio_unitario"]
        pdf.cell(95, 6, str(it["descripcion"])[:45], border=1)
        pdf.cell(25, 6, str(it["cantidad"]), border=1, align="C")
        pdf.cell(35, 6, f"$ {it['precio_unitario']:,.2f}", border=1, align="R")
        pdf.cell(35, 6, f"$ {sub:,.2f}", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(140, 6, "Importe Neto Gravado:", align="R")
    pdf.cell(50, 6, f"$ {datos_fac['imp_neto']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(140, 6, "IVA (21%):", align="R")
    pdf.cell(50, 6, f"$ {datos_fac['imp_iva']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(140, 7, "TOTAL:", align="R")
    pdf.cell(50, 7, f"$ {datos_fac['imp_total']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    qr_data = f"https://www.arca.gob.ar/fe/qr/?p={datos_fac['cuit_emisor']}&cae={datos_fac['cae']}"
    qr_img = qrcode.make(qr_data)
    qr_img.save("qr_temp.png")
    pdf.image("qr_temp.png", x=10, y=pdf.get_y(), w=26)
    pdf.set_xy(40, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, f"CAE Nro: {datos_fac['cae']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(40)
    pdf.cell(0, 6, f"Vto. CAE: {datos_fac['vto_cae']}", new_x="LMARGIN", new_y="NEXT")

    pdf.output(archivo_salida)
    if os.path.exists("qr_temp.png"):
        os.remove("qr_temp.png")
    return archivo_salida

# --- INTERFAZ STREAMLIT ---
st.title("🧾 Simulador de Comprobantes ARCA")

st.subheader("1. Subir Orden de Compra")
archivo = st.file_uploader("Cargá un PDF de Orden de Compra", type=["pdf"])

if archivo is not None:
    if st.button("🔍 Extraer Datos con IA", use_container_width=True):
        with st.spinner("Procesando con IA..."):
            try:
                st.session_state["datos_oc"] = extraer_datos_oc(archivo.getvalue())
                st.success("¡Datos extraídos!")
            except Exception as ex:
                st.error(str(ex))

if "datos_oc" not in st.session_state:
    st.info("👈 Cargá un PDF arriba para habilitar el formulario administrativo.")
else:
    st.divider()
    st.subheader("2. Panel de Control ARCA")
    datos = st.session_state["datos_oc"]
    
    st.markdown("#### Datos de Emisión")
    c1, c2, c3 = st.columns(3)
    with c1:
        fecha_emision = st.date_input("Fecha Comprobante", value=datetime.date.today())
    with c2:
        tipo_cbte = st.selectbox("Tipo", options=[1, 6], format_func=lambda x: "Factura A" if x == 1 else "Factura B")
    with c3:
        punto_vta = st.number_input("Punto Venta", value=1, min_value=1)
        
    concepto = st.selectbox("Concepto a facturar", options=[1, 2, 3], format_func=lambda x: {1: "1 - Productos", 2: "2 - Servicios", 3: "3 - Productos y Servicios"}[x])
    
    fecha_desde = fecha_hasta = vto_pago = None
    if concepto in [2, 3]:
        st.warning("⚠️ ARCA requiere los períodos obligatorios para la facturación de Servicios.")
        cs1, cs2, cs3 = st.columns(3)
        with cs1:
            fecha_desde = st.date_input("Período Desde")
        with cs2:
            fecha_hasta = st.date_input("Período Hasta")
        with cs3:
            vto_pago = st.date_input("Vto. para el Pago")

    st.markdown("#### Datos del Receptor")
    c4, c5 = st.columns(2)
    with c4:
        cuit_cliente = st.text_input("CUIT", value=datos.get("cuit_cliente", ""))
        dic_iva = {1: "IVA Resp. Inscripto", 6: "Monotributo", 5: "Consumidor Final", 4: "Exento"}
        condicion_iva = st.selectbox("Condición frente al IVA", options=[1, 6, 5, 4], format_func=lambda x: dic_iva[x])
    with c5:
        razon_social = st.text_input("Razón Social", value=datos.get("razon_social", ""))
        condicion_venta = st.selectbox("Condición de Venta", options=["Cuenta Corriente", "Contado", "Tarjeta de Débito", "Tarjeta de Crédito", "Cheque"])

    st.markdown("#### Documentos Asociados")
    c6, c7 = st.columns(2)
    with c6:
        numero_oc = st.text_input("N° Orden de Compra", value=datos.get("numero_oc", ""))
        numero_remito = st.text_input("N° Remito Vinculado", value="")
    with c7:
        fecha_remito = st.date_input("Fecha Remito", disabled=(numero_remito == ""))
        cuit_emisor = st.number_input("CUIT Emisor (Tu empresa)", value=20141240103)

    st.divider()
    items = datos.get("items", [])
    neto = 0.0
    iva = 0.0
    for item in items:
        sub = item["cantidad"] * item["precio_unitario"]
        neto += sub
        iva += sub * (item.get("alicuota_iva", 21.0) / 100.0)

    total = neto + iva
    st.subheader(f"Total: ${total:,.2f}")
    st.caption(f"Importe Neto Gravado: ${neto:,.2f} | IVA: ${iva:,.2f}")

    if st.button("⚡ Confirmar y Generar PDF Oficial", type="primary", use_container_width=True):
        with st.spinner("Conectando con simulador ARCA..."):
            try:
                res_arca = emitir_factura_arca()
                
                datos_pdf = {
                    "tipo_cbte": tipo_cbte,
                    "punto_vta": punto_vta,
                    "fecha_emision": fecha_emision,
                    "concepto": concepto,
                    "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta,
                    "vto_pago": vto_pago,
                    "cuit_emisor": cuit_emisor,
                    "cuit_cliente": cuit_cliente,
                    "razon_social": razon_social,
                    "condicion_iva_str": dic_iva[condicion_iva],
                    "condicion_venta": condicion_venta,
                    "numero_oc": numero_oc,
                    "numero_remito": numero_remito,
                    "fecha_remito": fecha_remito if numero_remito else None,
                    "imp_neto": neto,
                    "imp_iva": iva,
                    "imp_total": total,
                    "cae": res_arca['cae'],
                    "vto_cae": res_arca['vto_cae'],
                    "nro_factura": res_arca['nro_factura']
                }
                
                ruta = generar_pdf_factura(datos_pdf, items)
                st.success(f"¡Autorizado! CAE simulado: {res_arca['cae']}")
                
                with open(ruta, "rb") as f_pdf:
                    st.download_button(
                        label="📥 Descargar Factura (PDF)",
                        data=f_pdf,
                        file_name=f"Factura_{str(punto_vta).zfill(4)}-{str(res_arca['nro_factura']).zfill(8)}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error generando PDF: {e}")