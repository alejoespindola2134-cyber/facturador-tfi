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
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# --- FUNCIONES DE NÚCLEO ---
def extraer_datos_oc(bytes_pdf: bytes) -> dict:
    """Extrae datos de la OC usando Gemini."""
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
    
    modelos_disponibles = [
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash",
        "gemini-2.5-flash"
    ]
    
    ultimo_error = None
    for modelo in modelos_disponibles:
        for intento in range(1, 3):
            try:
                respuesta = gemini_client.models.generate_content(
                    model=modelo,
                    contents=[
                        types.Part.from_bytes(data=bytes_pdf, mime_type="application/pdf"),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                if respuesta.text:
                    return json.loads(respuesta.text)
            except Exception as e:
                ultimo_error = e
                time.sleep(1)

    raise Exception(f"Servidores de IA ocupados. Por favor volvé a intentar. Detalle: {ultimo_error}")

def emitir_factura_arca() -> dict:
    """SIMULACIÓN: Emite la factura sin conectarse a servidores reales de AFIP/ARCA."""
    time.sleep(2.5) 
    fecha_hoy = datetime.date.today().strftime("%Y%m%d")
    return {
        "cae": "73245678901234",
        "vto_cae": (datetime.date.today() + datetime.timedelta(days=10)).strftime("%Y%m%d"),
        "nro_factura": 125,
        "fecha_cae": fecha_hoy
    }

def generar_pdf_factura(datos_fac: dict, items: list, archivo_salida="factura_emitida.pdf"):
    """Genera la factura oficial en PDF con los nuevos campos de ARCA."""
    pdf = FPDF()
    pdf.add_page()

    # Encabezado Tipo Factura
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "FACTURA (SIMULACION TFI)", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    letra = "A" if datos_fac["tipo_cbte"] == 1 else "B"
    pdf.cell(0, 6, f"TIPO: {letra} - COD. {str(datos_fac['tipo_cbte']).zfill(2)}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3