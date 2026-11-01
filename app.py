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
st.set_page_config(page_title="Facturación IA (Prototipo TFI)", page_icon="🧾", layout="wide")

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
    
    # Encabezado
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "FACTURA (SIMULACION TFI)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    letra = "A" if datos_fac["tipo_cbte"] == 1 else "B"
    pdf.cell(0, 6, f"TIPO: {letra} - COD. {str(datos_fac['tipo_cbte']).zfill(2)}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Datos Emisor
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, f"Punto de Venta: {str(datos_fac['punto_vta']).zfill(4)}", border="L,T")
    pdf.cell(95, 6, f"Comp. Nro: {str(datos_fac['nro_factura']).zfill(8)}", border="R,T", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 6, f"CUIT Emisor: {datos_fac['cuit_emisor']}", border="L,B")
    pdf.cell(95, 6, f"Fecha de Emision: {datos_fac['fecha_emision'].strftime('%d/%m/%Y')}", border="R,B", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    
    # Si es servicio, imprime el Período
    if datos_fac.get('concepto') in [2, 3]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"Periodo Facturado: Desde {datos_fac['fecha_desde'].strftime('%d/%m/%Y')} Hasta {datos_fac['fecha_hasta'].strftime('%d/%m/%Y')} | Vto. Pago: {datos_fac['vto_pago'].strftime('%d/%m/%Y')}", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Datos Receptor
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "DATOS DEL RECEPTOR Y CONDICIONES", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(105, 5, f"Razon Social: {datos_fac['razon_social']}", new_x="RIGHT")
    pdf.cell(85, 5, f"CUIT: {datos_fac['cuit_cliente']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(105, 5, f"Condicion de Venta: {datos_fac['condicion_venta']}", new_x="RIGHT")
    pdf.cell(85, 5, f"Condicion IVA: {datos_fac['condicion_iva_str']}", new_x="LMARGIN", new_y="NEXT")
    
    # Docs Asociados
    texto_docs = f"Orden de Compra: {datos_fac.get('numero_oc', 'N/A')}"
    if datos_fac.get('numero_remito'):
        fecha_