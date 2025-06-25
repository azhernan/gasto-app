import streamlit as st
import pdfplumber
import pandas as pd
import re
from datetime import datetime
import os

# Clasificación básica por proveedor
clasificacion = {
    "metrogas": ("Fijo", "Gas"),
    "edenor": ("Fijo", "Electricidad"),
    "personal": ("Fijo", "Internet"),
    "flow": ("Fijo", "Internet"),
    "carrefour": ("Variable", "Supermercado"),
    "día": ("Variable", "Supermercado"),
    "mcdonald": ("Variable", "Comida rápida"),
    "burger": ("Variable", "Comida rápida"),
    "visa": ("Variable", "Tarjeta de crédito"),
    "amex": ("Variable", "Tarjeta de crédito"),
}

def clasificar_gasto(proveedor):
    proveedor_lower = proveedor.lower()
    for clave, (tipo, categoria) in clasificacion.items():
        if clave in proveedor_lower:
            return tipo, categoria
    return "Variable", "Otro"

def extraer_fecha(texto):
    match = re.search(r"Fecha de pago\s+.*?(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})", texto)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y %H:%M:%S").date()
        except:
            return "Fecha inválida"
    return "No encontrada"

def procesar_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except:
        return None, f"No se pudo procesar: {file}"

    proveedor = re.search(r"Pagaste a\s+([^\n]+)", text)
    monto = re.search(r"Total pagado\s*\$?\s*([0-9\.,]+)", text)
    fecha = extraer_fecha(text)

    if not proveedor or not monto or fecha in ["No encontrada", "Fecha inválida"]:
        return None, f"No se pudo extraer información de: {file}"

    proveedor = proveedor.group(1).strip()
    monto = monto.group(1).replace('.', '').replace(',', '.')
    tipo, categoria = clasificar_gasto(proveedor)

    return {
        "Fecha": fecha,
        "Proveedor": proveedor,
        "Monto": float(monto),
        "Tipo de gasto": tipo,
        "Categoría": categoria
    }, None

# ---------------- INTERFAZ STREAMLIT ----------------
st.title("📄 Clasificador de Comprobantes de Gasto")
st.write("Subí comprobantes PDF y clasificá tus gastos automáticamente.")

uploaded_files = st.file_uploader("Seleccioná uno o varios comprobantes PDF", type="pdf", accept_multiple_files=True)

csv_filename = "gastos.csv"
if os.path.exists(csv_filename):
    df_existente = pd.read_csv(csv_filename)
else:
    df_existente = pd.DataFrame(columns=["Fecha", "Proveedor", "Monto", "Tipo de gasto", "Categoría"])

registros_nuevos = []
errores = []
duplicados = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        with open(f"comprobantes/{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())

        resultado, error = procesar_pdf(f"comprobantes/{uploaded_file.name}")
        if error:
            errores.append(error)
            continue

        # Verificar duplicados
        existe = (
            (df_existente["Fecha"] == str(resultado["Fecha"])) &
            (df_existente["Proveedor"] == resultado["Proveedor"]) &
            (df_existente["Monto"] == resultado["Monto"])
        ).any()

        if existe:
            duplicados.append(f"Duplicado no agregado: {resultado['Proveedor']} - {resultado['Monto']} - {resultado['Fecha']}")
        else:
            registros_nuevos.append(resultado)

# Mostrar errores si los hubo
for e in errores:
    st.error(e)

# Permitir carga manual si hubo errores
if errores:
    st.markdown("### 📋 Ingresá manualmente un gasto")
    with st.form("form_manual"):
        fecha_manual = st.date_input("Fecha")
        proveedor_manual = st.text_input("Proveedor")
        monto_manual = st.number_input("Monto", step=0.01)
        tipo_manual = st.selectbox("Tipo de gasto", ["Fijo", "Variable"])
        categoria_manual = st.text_input("Categoría")

        submit = st.form_submit_button("Agregar manualmente")

        if submit and proveedor_manual and monto_manual and categoria_manual:
            registros_nuevos.append({
                "Fecha": fecha_manual,
                "Proveedor": proveedor_manual,
                "Monto": monto_manual,
                "Tipo de gasto": tipo_manual,
                "Categoría": categoria_manual
            })
            st.success("Registro manual agregado.")

# Agregar nuevos registros al CSV
if registros_nuevos:
    df_nuevos = pd.DataFrame(registros_nuevos)
    df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    df_final["Fecha"] = df_final["Fecha"].astype(str)
    df_final.to_csv(csv_filename, index=False)
    st.success(f"{len(df_nuevos)} nuevo(s) gasto(s) agregado(s). Total: {len(df_final)}")
    st.dataframe(df_final)
    csv_download = df_final.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Descargar CSV acumulado", data=csv_download, file_name="gastos.csv", mime="text/csv")

# Mostrar duplicados si hubo
for d in duplicados:
    st.warning(d)

