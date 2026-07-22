import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Configuración de página ancha
st.set_page_config(layout="wide", page_title="Red SVC - Dashboard Interactivo")

# CONFIGURACIÓN DE RUTAS DE GITHUB
USUARIO_GITHUB = "cainiao"  # Basado en tu URL de la captura de pantalla
REPOSITORIO = "mapainteractivocainiao"
ARCHIVO_EXCEL = "DIRECCIONES.xlsx"

URL_EXCEL_GITHUB = f"https://githubusercontent.com{USUARIO_GITHUB}/{REPOSITORIO}/main/{ARCHIVO_EXCEL}"

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
    
   # 🟢 CORRECCIÓN DE REGIÓN: Buscar variaciones comunes de nombre con/sin acento o mayúsculas
    columna_region_real = None
    for opcion in ["Region", "Región", "REGION", "región", "region"]:
        if opcion in df.columns:
            columna_region_real = opcion
            break
            
    # Si la encuentra con acento o mayúsculas, la renombra a 'Region' de manera interna
    if columna_region_real and columna_region_real != "Region":
        df["Region"] = df[columna_region_real]
    elif json_region_real is None:
        # Si de plano no existe la columna en el Excel, crea una por defecto para que no truene
        df["Region"] = "Centro"
    
    # Forzar la existencia de la columna Tipo
    if "Tipo" not in df.columns:
        if "TIPO" in df.columns:
            df["Tipo"] = df["TIPO"]
        else:
            df["Tipo"] = "Proveedor"
            
    df["Tipo"] = df["Tipo"].fillna("Proveedor")
    df["Region"] = df["Region"].fillna("Sin Región")
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

# 🟢 NUEVO FILTRO LATERAL: Región (Columna agregada)
opciones_region = ["Todas"] + sorted(df_original["region"].dropna().unique().tolist()) if "Region" in df_original.columns else ["Todas"]
filtro_region = st.sidebar.selectbox("Región", opciones_region)

# =========================================================================
# LÓGICA DE FILTRADO
# =========================================================================
df_filtrado = df_original.copy()

if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado["DSP NAME"].str.contains(busqueda, case=False, na=False) | 
        df_filtrado["Representante Legal"].str.contains(busqueda, case=False, na=False)
    ]

if filtro_tipo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Tipo"] == filtro_tipo]

if "Modelo" in df_filtrado.columns and filtro_modelo != "Todos":
    df_filtrado = df_filtrado[df_filtrado["Modelo"] == filtro_modelo]

# 🟢 APLICAR FILTRO DE REGIÓN
if "Region" in df_filtrado.columns and filtro_region != "Todas":
    df_filtrado = df_filtrado[df_filtrado["region"] == filtro_region]

# =========================================================================
# INTERFAZ PRINCIPAL: MÉTRICAS (SECCIÓN MODIFICADA)
# =========================================================================
st.title("🚚 Panel de Control Red SVC")

# Configurar 4 columnas para incluir la Región
m1, m2, m3, m4 = st.columns(4)
total = len(df_filtrado)

# Conteo basado en la columna 'Tipo' de manera segura
bodegas_mask = df_filtrado["Tipo"].astype(str).str.contains("Bodega", case=False, na=False)
n_bodegas = len(df_filtrado[bodegas_mask])
n_proveedores = total - n_bodegas

# Conteo dinámico de regiones activas según los filtros
n_regiones = df_filtrado["region"].nunique() if "Region" in df_filtrado.columns else 0

# Desplegar las métricas superiores
m1.metric("Total Nodos", total)
m2.metric("Bodegas (Rojo)", n_bodegas)
m3.metric("Proveedores (Azul)", n_proveedores)
m4.metric("Regiones Activas", n_regiones)  # 🟢 Nueva métrica visual instalada

st.markdown("---")

# =========================================================================
# TABLA INTERACTIVA Y MAPA
# =========================================================================
col_mapa, col_info = st.columns(2)

with col_info:
    st.subheader("Lista de Proveedores")
    st.write("Selecciona una fila para ubicarla en el mapa:")
    
    columnas_tabla = ["DSP NAME"]
    if "PIC Capacity" in df_filtrado.columns:
        columnas_tabla.append("PIC Capacity")
    if "Tipo" in df_filtrado.columns:
        columnas_tabla.append("Tipo")
    if "Modelo" in df_filtrado.columns:
        columnas_tabla.append("Modelo")
    if "Region" in df_filtrado.columns:
        columnas_tabla.append("Region")  # Mostrar región en la tabla derecha
    
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
        st.info(f"📍 Enfocando: {punto_seleccionado['DSP NAME'].values[0]}")

with col_mapa:
    if not df_filtrado.empty:
        # Centrar el mapa de forma dinámica según la selección de la tabla
        if punto_seleccionado is not None:
            # 🟢 SOLUCIÓN AL ERROR ANTERIOR: Extraemos el valor indexado de forma correcta
            lat_ini = float(punto_seleccionado["LAT"].values[0])
            lon_ini = float(punto_seleccionado["LON"].values[0])
            zoom_ini = 14
        else:
            lat_ini = df_filtrado["LAT"].mean()
            lon_ini = df_filtrado["LON"].mean()
            zoom_ini = 5

        mapa = folium.Map(location=[lat_ini, lon_ini], zoom_start=zoom_ini, tiles="Cartodb Positron")
        marker_cluster = MarkerCluster().add_to(mapa)

        for idx, fila in df_filtrado.iterrows():
            dsp = fila["DSP NAME"]
            rep = fila["Representante Legal"]
            pic = fila.get("PIC Capacity", "N/A")
            mod = fila.get("Modelo", "N/A")
            reg = fila.get("Region", "N/A")
            tipo_raw = str(fila.get("Tipo", "")).lower()

            is_bodega = "bodega" in tipo_raw
            color_ico = "red" if is_bodega else "blue"
            icon_name = "home" if is_bodega else "truck"

            # Contenido HTML con la nueva variable de región integrada al Popup
            html = f"""
            <div style="font-family: Arial; min-width: 180px;">
                <h4 style="color: #1e40af; margin:0;">{dsp}</h4>
                <hr style="margin:5px 0;">
                <b>Representante:</b> {rep}<br>
                <b>PIC Capacity:</b> {pic}<br>
                <b>Modelo:</b> {mod}<br>
                <b>Región:</b> {reg}
            </div>
            """
            
            # Destacar en verde si está seleccionado en la tabla
            if punto_seleccionado is not None and idx == punto_seleccionado.index[0]:
                folium.Marker(
                    location=[fila["LAT"], fila["LON"]],
                    popup=folium.Popup(html, max_width=300, show=True),
                    icon=folium.Icon(color="green", icon="star", prefix='fa')
                ).add_to(mapa)
            else:
                folium.Marker(
                    location=[fila["LAT"], fila["LON"]],
                    popup=folium.Popup(html, max_width=300),
                    icon=folium.Icon(color=color_ico, icon=icon_name, prefix='fa')
                ).add_to(marker_cluster)

        st_folium(mapa, width="stretch", height=600)
    else:
        st.warning("No hay datos para mostrar con los filtros actuales.")
