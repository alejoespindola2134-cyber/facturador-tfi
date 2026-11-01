import datetime
import json
import os
import time

import qrcode
import streamlit as st
from fpdf import FPDF
from google import genai
from google.genai import types


# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Facturación IA (Prototipo TFI)", page_icon="🧾", layout="wide")

# --- CONFIGURACIÓN DEL PROCESO ---
with st.sidebar:
    st.header("⚙️ Configuración del Modelo IA")
    st.info("Parámetros del proceso TO-BE simulado")
    st.write("**Rol:** Asistente de facturación comercial.")
    st.write("**Contexto:** Extracción automática de datos de Órdenes de Compra (PDF) para agilizar la facturación.")
    st.write("**Reglas de negocio:** Identificar CUIT válido, Razón Social e ítems con cantidades y precios netos unitarios.")
    st.write("**Formato de salida:** JSON estricto estructurado.")
    st.write("**Restricciones:** No inventar datos, omitir impuestos en el precio unitario y derivar al usuario si falta el CUIT.")


def obtener_cliente_gemini():
    """Inicializa Gemini solo cuando se necesita, para permitir abrir la app sin configurar Secrets."""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Configurá GEMINI_API_KEY en Secrets de Streamlit o como variable de entorno.")
    return genai.Client(api_key=api_key)


def extraer_datos_oc(bytes_pdf: bytes) -> dict:
    """Extrae datos de la orden de compra usando Gemini."""
    prompt = """
    Analiza esta Orden de Compra y extrae los datos para facturación comercial en Argentina.
    No inventes datos. Si el CUIT no aparece, usa una cadena vacía.
    Devuelve estrictamente un objeto JSON con esta estructura:
    {
      "cuit_cliente": "solo dígitos numéricos sin guiones",
      "razon_social": "nombre de la empresa o cliente",
      "numero_oc": "identificador de OC",
      "items": [
        {
          "descripcion": "detalle del producto o servicio",
          "cantidad": 1,
          "precio_unitario": 0.0,
          "alicuota_iva": 21.0
        }
      ]
    }
    El precio unitario debe ser neto, sin impuestos, símbolos ni separadores de miles.
    """
    modelos_disponibles = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]
    cliente = obtener_cliente_gemini()
    ultimo_error = None

    for modelo in modelos_disponibles:
        for intento in range(2):
            try:
                respuesta = cliente.models.generate_content(
                    model=modelo,
                    contents=[types.Part.from_bytes(data=bytes_pdf, mime_type="application/pdf"), prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
                )
                if respuesta.text:
                    datos = json.loads(respuesta.text)
                    if not isinstance(datos, dict) or not isinstance(datos.get("items"), list):
                        raise ValueError("La respuesta de IA no contiene el formato esperado.")
                    return datos
                raise ValueError("El modelo no devolvió contenido.")
            except Exception as error:
                ultimo_error = error
                if intento == 0:
                    time.sleep(1)
    raise RuntimeError(f"No se pudieron extraer los datos. Detalle: {ultimo_error}")


def cuit_valido(cuit: str) -> bool:
    """Valida formato y dígito verificador de un CUIT argentino."""
    digitos = "".join(caracter for caracter in str(cuit) if caracter.isdigit())
    if len(digitos) != 11:
        return False
    multiplicadores = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    suma = sum(int(digitos[i]) * multiplicadores[i] for i in range(10))
    verificador = 11 - (suma % 11)
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 9
    return verificador == int(digitos[-1])


def emitir_factura_arca(cuit_emisor: int, tipo_cbte: int, punto_vta: int, cuit_cliente: int,
                        condicion_iva: int, concepto: int, imp_neto: float, imp_iva: float,
                        imp_total: float) -> dict:
    """Simula la emisión; no se conecta a servidores reales de AFIP/ARCA."""
    time.sleep(1)
    hoy = datetime.date.today()
    return {
        "cae": "SIMULADO",
        "vto_cae": (hoy + datetime.timedelta(days=10)).strftime("%Y%m%d"),
        "nro_factura": 125,
        "fecha": hoy.strftime("%Y%m%d"),
        "punto_vta": punto_vta,
        "tipo_cbte": tipo_cbte,
    }


def generar_pdf_factura(datos_fac: dict, items: list, archivo_salida="factura_emitida.pdf") -> bytes:
    """Genera una factura de demostración en PDF con CAE simulado y QR."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, "FACTURA - SIMULACION", ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, f"Comprobante: {datos_fac.get('punto_vta', 1):04d}-{datos_fac.get('nro_factura', 0):08d}", ln=True)
    pdf.cell(0, 7, f"Fecha: {datos_fac.get('fecha', '')}", ln=True)
    pdf.cell(0, 7, f"Cliente: {datos_fac.get('razon_social', '')}", ln=True)
    pdf.cell(0, 7, f"CUIT: {datos_fac.get('cuit_cliente', '')}    OC: {datos_fac.get('numero_oc', '')}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 8, "Descripcion", border=1)
    pdf.cell(25, 8, "Cantidad", border=1, align="R")
    pdf.cell(35, 8, "Precio unitario", border=1, align="R")
    pdf.cell(35, 8, "Subtotal", border=1, align="R", ln=True)
    pdf.set_font("Arial", "", 9)
    for item in items:
        descripcion = str(item.get("descripcion", ""))[:48]
        cantidad = float(item.get("cantidad", 0))
        precio = float(item.get("precio_unitario", 0))
        subtotal = cantidad * precio
        pdf.cell(90, 8, descripcion, border=1)
        pdf.cell(25, 8, f"{cantidad:g}", border=1, align="R")
        pdf.cell(35, 8, f"${precio:,.2f}", border=1, align="R")
        pdf.cell(35, 8, f"${subtotal:,.2f}", border=1, align="R", ln=True)
    pdf.ln(4)
    pdf.cell(0, 7, f"Neto: ${datos_fac['imp_neto']:,.2f}    IVA: ${datos_fac['imp_iva']:,.2f}    Total: ${datos_fac['imp_total']:,.2f}", ln=True)
    pdf.cell(0, 7, f"CAE: {datos_fac.get('cae', '')}    Vencimiento CAE: {datos_fac.get('vto_cae', '')}", ln=True)

    # QR de demostración: no representa un comprobante oficial de ARCA.
    qr_data = json.dumps({"simulado": True, "cae": datos_fac.get("cae"), "factura": datos_fac.get("nro_factura")})
    qr = qrcode.make(qr_data)
    qr_path = "_qr_temporal.png"
    qr.save(qr_path)
    pdf.image(qr_path, x=160, y=pdf.get_y() + 3, w=30, h=30)
    try:
        os.remove(qr_path)
    except OSError:
        pass
    salida = pdf.output(dest="S")
    return salida.encode("latin-1") if isinstance(salida, str) else bytes(salida)


# --- INTERFAZ ---
st.title("🧾 Facturación asistida por IA")
st.caption("Prototipo académico: la emisión y el CAE son simulados; no genera comprobantes fiscales válidos.")
archivo = st.file_uploader("Cargá una Orden de Compra en PDF", type=["pdf"])

if archivo and st.button("Analizar Orden de Compra", type="primary"):
    try:
        with st.spinner("Analizando documento..."):
            st.session_state["datos_oc"] = extraer_datos_oc(archivo.getvalue())
    except Exception as error:
        st.error(str(error))

datos_oc = st.session_state.get("datos_oc")
if datos_oc:
    st.subheader("Datos extraídos (revisalos antes de continuar)")
    cuit = st.text_input("CUIT del cliente", value=str(datos_oc.get("cuit_cliente", "")))
    razon_social = st.text_input("Razón social", value=str(datos_oc.get("razon_social", "")))
    numero_oc = st.text_input("Número de OC", value=str(datos_oc.get("numero_oc", "")))
    items = st.data_editor(datos_oc.get("items", []), num_rows="dynamic", use_container_width=True,
                           column_config={
                               "cantidad": st.column_config.NumberColumn(min_value=0.0, step=1.0),
                               "precio_unitario": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                               "alicuota_iva": st.column_config.NumberColumn(min_value=0.0, max_value=100.0),
                           })

    if cuit and not cuit_valido(cuit):
        st.warning("El CUIT ingresado no tiene un formato o dígito verificador válido.")
    elif not cuit:
        st.warning("Falta el CUIT: no se puede continuar con la simulación de emisión.")

    if st.button("Simular emisión de factura"):
        if not cuit_valido(cuit):
            st.error("Ingresá un CUIT válido para continuar.")
        elif not items:
            st.error("Agregá al menos un ítem para emitir la factura.")
        else:
            try:
                imp_neto = sum(float(item.get("cantidad", 0)) * float(item.get("precio_unitario", 0)) for item in items)
                imp_iva = sum(float(item.get("cantidad", 0)) * float(item.get("precio_unitario", 0)) * float(item.get("alicuota_iva", 0)) / 100 for item in items)
                factura = emitir_factura_arca(0, 1, 1, int(cuit), 0, 1, imp_neto, imp_iva, imp_neto + imp_iva)
                factura.update({"cuit_cliente": cuit, "razon_social": razon_social, "numero_oc": numero_oc,
                                "imp_neto": imp_neto, "imp_iva": imp_iva, "imp_total": imp_neto + imp_iva})
                pdf_bytes = generar_pdf_factura(factura, items)
                st.success("Simulación completada. Este comprobante no es fiscal.")
                st.download_button("Descargar factura de demostración (PDF)", data=pdf_bytes,
                                   file_name="factura_simulada.pdf", mime="application/pdf")
            except (TypeError, ValueError, KeyError) as error:
                st.error(f"Revisá los datos de los ítems: {error}")