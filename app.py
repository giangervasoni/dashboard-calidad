import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ==============================================================================
# 1. DICCIONARIO MAESTRO DE ESPECIFICACIONES (MATRIZ DE CALIDAD)
# ==============================================================================
SPECS = {
    "Trozos de Maíz": {
        "Malla 5660 µm": {"max": 10.0},
        "Malla 4750 µm": {"min": 30.0, "max": 50.0},
        "Malla 4000 µm": {"min": 40.0, "max": 60.0},
        "Malla 3350 µm": {"max": 10.0},
        "Fondo": {"max": 1.5}
    },
    "Harina de Maíz": {
        "Malla 710 µm": {"max": 0.5},
        "Malla 355 µm": {"max": 7.5},
        "Malla 250 µm": {"min": 25.0, "max": 40.0},
        "Malla 180 µm": {"max": 40.0},
        "Fondo": {"max": 50.0}
    },
    "Harina de Trigo 000 (Extrusión)": {
        "Malla 250 µm": {"max": 4.0},
        "Malla 180 µm": {"max": 13.0},
        "Malla 150 µm": {"max": 16.0},
        "Fondo": {"min": 74.0}
    },
    "Harina de Arroz": {
        "Malla 710 µm": {"max": 0.5},
        "Malla 500 µm": {"max": 0.5},
        "Malla 425 µm": {"max": 8.0},
        "Malla 355 µm": {"max": 30.0},
        "Malla 300 µm": {"max": 20.0},
        "Malla 250 µm": {"min": 10.0, "max": 15.0},
        "Malla 180 µm": {"min": 10.0, "max": 15.0},
        "Fondo": {"max": 30.0}
    },
    "Harina de Avena": {
        "Malla 425 µm": {"max": 20.0},
        "Malla 355 µm": {"min": 10.0, "max": 25.0},
        "Malla 250 µm": {"min": 20.0, "max": 40.0},
        "Malla 180 µm": {"max": 40.0},
        "Fondo": {"max": 30.0}
    }
}

# ==============================================================================
# 2. CONFIGURACIÓN DE LA PÁGINA
# ==============================================================================
st.set_page_config(page_title="Dashboard de Calidad", layout="wide")
st.title("📊 Dashboard de Control Granulométrico")
st.markdown("Visualización interactiva, detección de outliers y cruce con especificaciones de planta.")

# ==============================================================================
# 3. BARRA LATERAL (SUBIDA DE ARCHIVOS Y FILTROS)
# ==============================================================================
st.sidebar.header("1. Carga de Datos")
prod_seleccionado = st.sidebar.selectbox("Seleccionar Producto:", list(SPECS.keys()))
archivo_subido = st.sidebar.file_uploader("Subir reporte LIMS (.csv)", type=["csv"])

st.sidebar.markdown("---")
st.sidebar.header("2. Filtros de Análisis")

# ==============================================================================
# 4. FUNCIÓN INTELIGENTE DE PARSEO DE DATOS
# ==============================================================================
@st.cache_data
def procesar_datos(file):
    # Intento de lectura con separadores comunes en exportaciones locales
    df_raw = pd.read_csv(file, sep=";", decimal=",")
    if len(df_raw.columns) < 2:
        file.seek(0)
        df_raw = pd.read_csv(file, sep=",")
    
    # Detección de formato: ¿Es formato ancho (columnas por malla) o largo (LIMS)?
    if any("Malla_710" in str(c) or "Malla_250" in str(c) for c in df_raw.columns):
        # Formato Ancho (Ej: Archivo original Harina de Maíz)
        cols_retener = ["Proveedor"] + [c for c in df_raw.columns if "Malla" in c or "Fondo" in c]
        df_raw = df_raw[cols_retener]
        df_long = df_raw.melt(id_vars=["Proveedor"], var_name="Malla", value_name="Valor")
        df_long['Malla'] = df_long['Malla'].str.replace("_", " ") + " µm"
        df_long['Malla'] = df_long['Malla'].str.replace("Fondo µm", "Fondo")
    else:
        # Formato Largo (Ej: Reportes LIMS de Trigo, Arroz, Trozos)
        prov_col = [c for c in df_raw.columns if "entidad" in c.lower() or "proveedor" in c.lower()][0]
        ensayo_col = [c for c in df_raw.columns if "ensayo" in c.lower() or "análisis" in c.lower() or "analisis" in c.lower()][0]
        val_col = [c for c in df_raw.columns if "valor" in c.lower()][0]
        
        df_long = df_raw[[prov_col, ensayo_col, val_col]].copy()
        df_long.columns = ["Proveedor", "Tipo_Analisis", "Valor"]
        
        def extraer_nombre_malla(texto):
            texto = str(texto)
            if "Fondo" in texto: return "Fondo"
            match = re.search(r'Malla\s*\d+', texto)
            if match: return match.group(0) + " µm"
            return "Otra"
            
        df_long['Malla'] = df_long['Tipo_Analisis'].apply(extraer_nombre_malla)
    
    # Limpieza final de valores negativos o vacíos
    df_long = df_long[df_long['Malla'] != "Otra"].dropna(subset=['Valor']).copy()
    df_long['Valor'] = df_long['Valor'].apply(lambda x: 0.0 if float(x) < 0 else float(x))
    
    return df_long[['Proveedor', 'Malla', 'Valor']]

# ==============================================================================
# 5. EJECUCIÓN PRINCIPAL
# ==============================================================================
if archivo_subido is not None:
    try:
        df = procesar_datos(archivo_subido)
        
        # Filtros dinámicos basados en el archivo subido
        lista_proveedores = ["Todos"] + list(df['Proveedor'].unique())
        prov_seleccionado = st.sidebar.selectbox("Seleccionar Proveedor:", lista_proveedores)
        
        lista_mallas = list(df['Malla'].unique())
        malla_seleccionada = st.sidebar.selectbox("Seleccionar Fracción (Malla):", lista_mallas)
        
        # Filtrado de base de datos
        df_filtrado = df[df['Malla'] == malla_seleccionada].copy()
        if prov_seleccionado != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Proveedor'] == prov_seleccionado]
            
        if not df_filtrado.empty:
            # Cálculo de Outliers (IQR)
            Q1 = df_filtrado['Valor'].quantile(0.25)
            Q3 = df_filtrado['Valor'].quantile(0.75)
            IQR = Q3 - Q1
            limite_inf = Q1 - 1.5 * IQR
            limite_sup = Q3 + 1.5 * IQR
            df_filtrado['Es_Outlier'] = (df_filtrado['Valor'] < limite_inf) | (df_filtrado['Valor'] > limite_sup)
            
            # --- RENDERIZADO VISUAL ---
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📦 Dispersión de Lotes (Boxplot)")
                st.write("Identificación de lotes fuera de los desvíos estándar del proceso (1.5 IQR).")
                fig_box = px.box(df_filtrado, y="Valor", points="all", color_discrete_sequence=["#2980B9"])
                st.plotly_chart(fig_box, use_container_width=True)
                
            with col2:
                st.subheader("🔔 Campana del Proceso (Histograma)")
                st.write("Distribución de los datos limpios y límites de la matriz de calidad.")
                df_limpio = df_filtrado[~df_filtrado['Es_Outlier']]
                fig_hist = px.histogram(df_limpio, x="Valor", nbins=15, color_discrete_sequence=["#27AE60"])
                
                # --- AGREGADO DE LÍNEAS DE ESPECIFICACIÓN (PUNTEADAS) ---
                if prod_seleccionado in SPECS and malla_seleccionada in SPECS[prod_seleccionado]:
                    limites = SPECS[prod_seleccionado][malla_seleccionada]
                    if "min" in limites:
                        fig_hist.add_vline(x=limites["min"], line_dash="dash", line_color="#C0392B", 
                                           annotation_text="Mínimo", annotation_position="top left", line_width=2.5)
                    if "max" in limites:
                        fig_hist.add_vline(x=limites["max"], line_dash="dash", line_color="#C0392B", 
                                           annotation_text="Máximo", annotation_position="top right", line_width=2.5)
                
                st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.warning("⚠️ No hay datos para la combinación seleccionada.")
            
    except Exception as e:
        st.error(f"❌ Ocurrió un error al procesar el archivo. Asegurate de que sea un reporte del LIMS válido. Detalle: {e}")
else:
    st.info("👆 Por favor, selecciona un producto y sube tu archivo CSV en la barra lateral izquierda para comenzar el análisis.")
