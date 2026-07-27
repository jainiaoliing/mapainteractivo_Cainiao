import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Configuración de página ancha
st.set_page_config(layout="wide", page_title="Red SVC - Dashboard Interactivo")

# CONFIGURACIÓN DE RUTAS DE GITHUB
USUARIO_GITHUB = "cainiao"
REPOSITORIO = "mapainteractivocainiao"
ARCHIVO_EXCEL = "DIRECCIONES.xlsx"
URL_EXCEL_GITHUB = f"https://raw.githubusercontent.com/{USUARIO_GITHUB}/{REPOSITORIO}/main/{ARCHIVO_EXCEL}"

# Función auxiliar para validar y limpiar valores vacíos
def limpiar_texto(valor, default=""):
    if pd.isna(valor) or valor is None:
        return default
    val_str = str(valor).strip()
    if val_str.lower() in ["nan", "none", "null", ""]:
        return default
    return val_str

# 1. Función para cargar datos con caché controlada
@st.cache_data(ttl=60)
def cargar_datos():
    try:
        df = pd.read_excel(URL_EXCEL_GITHUB)
    except Exception:
        df = pd.read_excel(ARCHIVO_EXCEL)

    # Conversión de coordenadas a números
    df["LAT"] = pd.to_numeric(df["LAT"], errors='coerce')
    df["LON"] = pd.to_numeric(df["LON"], errors='coerce')

    # CORRECCIÓN DE COLUMNA DE REGIÓN
    columna_region_real = None
    for opcion in ["Region", "Región", "REGION", "región", "region"]:
        if opcion in df.columns:
            columna_region_real = opcion
            break
    if columna_region_real and columna_region_real != "Region":
        df["Region"] = df[columna_region_real]
    elif columna_region_real is None:
        df["Region"] = "Centro"

    # IDENTIFICACIÓN Y NORMALIZACIÓN DE LA COLUMNA 'HUB'
    columna_hub_real = None
    for opcion in ["Hub", "HUB", "hub"]:
        if opcion in df.columns:
            columna_hub_real = opcion
            break
    if columna_hub_real and columna_hub_real != "Hub":
        df["Hub"] = df[columna_hub_real]
    elif columna_hub_real is None:
        df["Hub"] = None

    # IDENTIFICACIÓN Y NORMALIZACIÓN DE LA COLUMNA 'TIPO'
    columna_tipo_real = None
    for opcion in ["Tipo", "TIPO", "tipo", "Tipo de Instalacion", "Tipo de Instalación", "TIPO DE INSTALACION"]:
        if opcion in df.columns:
            columna_tipo_real = opcion
            break
    if columna_tipo_real:
        df["Tipo"] = df[columna_tipo_real]
    else:
        df["Tipo"] = None

    # Lógica inteligente para inferir "Bodega" si el campo viene vacío en el Excel
    def inferir_tipo(row):
        tipo_val = limpiar_texto(row.get("Tipo"))
        if tipo_val:
            return tipo_val
        dsp_val = limpiar_texto(row.get("DSP NAME")).lower()
        modelo_val = limpiar_texto(row.get("Modelo")).lower()
        if "bodega" in dsp_val or "bodega" in modelo_val or "hub" in dsp_val:
            return "Bodega"
        return "Proveedor"

    df["Tipo"] = df.apply(inferir_tipo, axis=1)
    df["Region"] = df["Region"].fillna("Sin Región")
    if "Hub" in df.columns:
        df["Hub"] = df["Hub"].fillna("Sin Asignar")
    
    return df.dropna(subset=["LAT", "LON"])

# Carga inicial directa
df_original = cargar_datos()

# =========================================================================
# MENÚ LATERAL: BÚSQUEDA Y FILTROS
# =========================================================================
st.sidebar.header("BÚSQUEDA Y FILTROS")

if st.sidebar.button("🔄 Actualizar Datos desde GitHub"):
    st.cache_data.clear()
    st.rerun()

busqueda = st.sidebar.text_input("🔍 Buscar por DSP o Representante...", "")

# Filtros dinámicos basados en el Excel
opciones_tipo = ["Todos"] + sorted(df_original["Tipo"].dropna().unique().tolist())
filtro_tipo = st.sidebar.selectbox("Tipo de Instalación", opciones_tipo)

opciones_modelo = ["Todos"] + sorted(df_original["Modelo"].dropna().unique().tolist()) if "Modelo" in df_original.columns else ["Todos"]
filtro_modelo = st.sidebar.selectbox("Modelo", opciones_modelo)

opciones_region = ["Todas"] + sorted(df_original["Region"].dropna().unique().tolist()) if "Region" in df_original.columns else ["Todas"]
filtro_region = st.sidebar.selectbox("Región", opciones_region)

# NUEVO FILTRO: Selección de HUB para ver qué proveedores operan desde allí
opciones_hub = ["Todos"] + sorted(df_original["Hub"].dropna().unique().tolist()) if "Hub" in df_original.columns else ["Todos"]
filtro_hub = st.sidebar.selectbox("Filtrar por HUB (Proveedores asociados)", opciones_hub)

# =========================================================================
# LÓGICA DE FILTRADO
# =========================================================================
df_filtrado = df_original.copy()

if busqueda:
    dsp_mask = df_filtrado["DSP NAME"].astype(str).str.contains(busqueda, case=False, na=False) if "DSP NAME" in df_filtrado.columns else False
    rep_mask = df_filtrado["Representante Legal"].astype(str).str.contains(busqueda, case=False, na=False) if "Representante Legal" in df_filtrado.columns else False
    df_filtrado = df_filtrado[dsp_mask | rep_mask]

if filtro_tipo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Tipo"] == filtro_tipo]

if "Modelo" in df_filtrado.columns and filtro_modelo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Modelo"] == filtro_modelo]

if "Region" in df_filtrado.columns and filtro_region != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Region"] == filtro_region]

# Aplicar el nuevo filtro de HUB asignado al proveedor
if "Hub" in df_filtrado.columns and filtro_hub != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Hub"] == filtro_hub]

# =========================================================================
# INTERFAZ PRINCIPAL: MÉTRICAS
# =========================================================================
st.title("🚚 Directorio Interactivo HUB y Estaciones DSP")

m1, m2, m3, m4 = st.columns(4)
total = len(df_filtrado)
bodegas_mask = df_filtrado["Tipo"].astype(str).str.contains("Bodega", case=False, na=False)
n_bodegas = len(df_filtrado[bodegas_mask])
n_proveedores = total - n_bodegas
n_regiones = df_filtrado["Region"].nunique() if "Region" in df_filtrado.columns else 0

m1.metric("Total Nodos", total)
m2.metric("Bodegas (Rojo)", n_bodegas)
m3.metric("Proveedores (Azul)", n_proveedores)
m4.metric("Regiones Activas", n_regiones)

st.markdown("---")

# =========================================================================
# TABLA INTERACTIVA Y MAPA
# =========================================================================
col_mapa, col_info = st.columns(2)

with col_info:
    st.subheader("Lista de Nodos / Proveedores")
    st.write("Selecciona una fila para ubicarla en el mapa:")
    
    # Se añade la columna 'Hub' a la tabla para mejorar el control visual
    columnas_tabla = [col for col in ["DSP NAME", "Hub", "PIC Capacity", "Tipo", "Modelo", "Region"] if col in df_filtrado.columns]
    
    event = st.dataframe(
        df_filtrado[columnas_tabla],
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch"
    )

    seleccion_idx = event.selection.get("rows", [])
    punto_seleccionado = None
    if len(seleccion_idx) > 0:
        punto_seleccionado = df_filtrado.iloc[seleccion_idx]
        dsp_nombre = limpiar_texto(punto_seleccionado['DSP NAME'].values[0], default="Nodo seleccionado")
        st.info(f"📍 Enfocando: {dsp_nombre}")

with col_mapa:
    if not df_filtrado.empty:
        if punto_seleccionado is not None:
            lat_ini = float(punto_seleccionado["LAT"].values[0])
            lon_ini = float(punto_screenshot = punto_seleccionado["LON"].values[0]) # Corrección de tipografía interna
            lon_ini = float(punto_seleccionado["LON"].values[0])
            zoom_ini = 14
        else:
            lat_ini = df_filtrado["LAT"].mean()
            lon_ini = df_filtrado["LON"].mean()
            zoom_ini = 5

        mapa = folium.Map(location=[lat_ini, lon_ini], zoom_start=zoom_ini, tiles="Cartodb Positron")
        marker_cluster = MarkerCluster().add_to(mapa)

        for idx, fila in df_filtrado.iterrows():
            dsp = limpiar_texto(fila.get("DSP NAME"), "SIN NOMBRE").upper()
            hub = limpiar_texto(fila.get("Hub")) # Vinculado a la nueva columna normalizada
            pic = limpiar_texto(fila.get("PIC Capacity"))
            mod = limpiar_texto(fila.get("Modelo"))
            reg = limpiar_texto(fila.get("Region"))
            rep = limpiar_texto(fila.get("Representante Legal"))
            tipo_raw = limpiar_texto(fila.get("Tipo")).lower()
            lat_val = fila.get("LAT")
            lon_val = fila.get("LON")

            is_bodega = "bodega" in tipo_raw
            color_ico = "red" if is_bodega else "blue"
            icon_name = "home" if is_bodega else "truck"

            # CONSTRUCCIÓN DINÁMICA DEL POPUP
            html_detalles = []
            if rep:
                html_detalles.append(f"<b>Representante:</b> {rep.upper()}")
            if hub and hub != "SIN ASIGNAR":
                html_detalles.append(f"<b>Hub Origen:</b> {hub.upper()}")
            if mod:
                html_detalles.append(f"<b>Modelo:</b> {mod.upper()}")
            if reg:
                html_detalles.append(f"<b>Región:</b> {reg.upper()}")
            if pic:
                html_detalles.append(f"<b>PIC Capacity:</b> {pic.upper()}")

            detalles_str = "<br>".join(html_detalles) if html_detalles else "<i>Sin detalles adicionales</i>"

            # CONSTRUCCIÓN DEL BLOQUE DE COORDENADAS
            html_coords = f"""
            <div style="font-size: 10px; color: #666666; margin-top: 8px; border-top: 1px dashed #eee; padding-top: 4px;">
                📍 Coords: {lat_val:.5f}, {lon_val:.5f}
            </div>
            """ if pd.notna(lat_val) and pd.notna(lon_val) else ""

            html = f"""
            <div style="font-family: Arial; min-width: 180px; font-size: 13px; line-height: 1.4;">
                <h4 style="color: #1e40af; margin:0 0 6px 0;">{dsp}</h4>
