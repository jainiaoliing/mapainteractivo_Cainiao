import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Configuración de página ancha
st.set_page_config(layout="wide", page_title="Red SVC - Dashboard Interactivo")

# CONFIGURACIÓN DE RUTAS (Modificar tras crear tu cuenta de GitHub)
USUARIO_GITHUB = "TU_USUARIO_AQUI"  # <--- Cambiaremos esto en el Paso 3
REPOSITORIO = "mapa-red-svc"
ARCHIVO_EXCEL = "DIRECCIONES.xlsx"

# Enlace directo al archivo crudo en los servidores de GitHub
URL_EXCEL_GITHUB = f"https://githubusercontent.com{USUARIO_GITHUB}/{REPOSITORIO}/main/{ARCHIVO_EXCEL}"

# 1. Función para cargar datos desde internet (Con un tiempo de vida corto en caché)
@st.cache_data(ttl=60) # ttl=60 hace que el mapa revise si hay un Excel nuevo en GitHub cada 60 segundos
def cargar_datos():
    try:
        # Intenta leer directamente desde el repositorio público de GitHub
        df = pd.read_excel(URL_EXCEL_GITHUB)
    except Exception:
        # Si no hay internet o aún no se sube, lee el archivo local de respaldo
        df = pd.read_excel(ARCHIVO_EXCEL)
    
    # Conversión de coordenadas a números
    df["LAT"] = pd.to_numeric(df["LAT"], errors='coerce')
    df["LON"] = pd.to_numeric(df["LON"], errors='coerce')
    
    # Forzar existencia de la columna Tipo
    if "Tipo" not in df.columns:
        if "TIPO" in df.columns:
            df["Tipo"] = df["TIPO"]
        else:
            df["Tipo"] = "Proveedor"
            
    df["Tipo"] = df["Tipo"].fillna("Proveedor")
    return df.dropna(subset=["LAT", "LON"])

# Carga inicial
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

# =========================================================================
# INTERFAZ PRINCIPAL: MÉTRICAS
# =========================================================================
st.title("🚚 Panel de Control Red SVC")

m1, m2, m3 = st.columns(3)
total = len(df_filtrado)

bodegas_mask = df_filtrado["Tipo"].astype(str).str.contains("Bodega", case=False, na=False)
n_bodegas = len(df_filtrado[bodegas_mask])
n_proveedores = total - n_bodegas

m1.metric("Total Nodos", total)
m2.metric("Bodegas (Rojo)", n_bodegas)
m3.metric("Proveedores (Azul)", n_proveedores)

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
        st.info(f"📍 Enfocando: {punto_seleccionado['DSP NAME'].values}")

with col_mapa:
    if not df_filtrado.empty:
        if punto_seleccionado is not None:
            lat_ini = float(punto_seleccionado["LAT"].values)
            lon_ini = float(punto_seleccionado["LON"].values)
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
            tipo_raw = str(fila.get("Tipo", "")).lower()

            is_bodega = "bodega" in tipo_raw
            color_ico = "red" if is_bodega else "blue"
            icon_name = "home" if is_bodega else "truck"

            html = f"""
            <div style="font-family: Arial; min-width: 180px;">
                <h4 style="color: #1e40af; margin:0;">{dsp}</h4>
                <hr style="margin:5px 0;">
                <b>Representante:</b> {rep}<br>
                <b>PIC Capacity:</b> {pic}<br>
                <b>Modelo:</b> {mod}
            </div>
            """
            
            if punto_seleccionado is not None and idx == punto_seleccionado.index:
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
