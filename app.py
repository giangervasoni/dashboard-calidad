import streamlit as st
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Dashboard Calidad", layout="wide")
st.title("📊 Dashboard de Calidad: Trozos de Maíz")
st.markdown("Aplicación interactiva para el control estadístico de granulometría.")

# 2. CARGA Y LIMPIEZA DE DATOS (En caché para que sea rápido)
@st.cache_data
def load_data():
    # Asumimos que el CSV está subido al mismo repositorio
    df_raw = pd.read_csv("Granulometría - Trozos de maíz.csv", sep=";", decimal=",")
    df_raw = df_raw.iloc[:, 0:4]
    df_raw.columns = ["Tipo_Analisis", "Num_Analisis", "Proveedor", "Valor"]
    
    df = df_raw.dropna(subset=['Valor']).copy()
    df['Valor'] = df['Valor'].apply(lambda x: 0 if x < 0 else x)
    
    def clasificar_malla(texto):
        if "5660" in str(texto): return "Malla 5660 µm"
        if "4750" in str(texto): return "Malla 4750 µm"
        if "4000" in str(texto): return "Malla 4000 µm"
        if "3350" in str(texto): return "Malla 3350 µm"
        if "Fondo" in str(texto): return "Fondo"
        return "Otra"
        
    df['Malla'] = df['Tipo_Analisis'].apply(clasificar_malla)
    return df[df['Malla'] != "Otra"]

# Manejo de error simple por si falta el CSV en el repo
try:
    df = load_data()
except FileNotFoundError:
    st.error("⚠️ No se encontró el archivo CSV en el repositorio. Por favor, subilo.")
    st.stop()

# 3. BARRA LATERAL (FILTROS)
st.sidebar.header("Filtros de Análisis")
lista_proveedores = ["Todos"] + list(df['Proveedor'].unique())
prov_seleccionado = st.sidebar.selectbox("Seleccionar Proveedor:", lista_proveedores)

lista_mallas = list(df['Malla'].unique())
malla_seleccionada = st.sidebar.selectbox("Seleccionar Fracción:", lista_mallas)

# 4. LÓGICA DE FILTRADO Y CÁLCULO DE OUTLIERS
df_filtrado = df[df['Malla'] == malla_seleccionada].copy()
if prov_seleccionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Proveedor'] == prov_seleccionado]

if not df_filtrado.empty:
    Q1 = df_filtrado['Valor'].quantile(0.25)
    Q3 = df_filtrado['Valor'].quantile(0.75)
    IQR = Q3 - Q1
    limite_inf = Q1 - 1.5 * IQR
    limite_sup = Q3 + 1.5 * IQR

    df_filtrado['Es_Outlier'] = (df_filtrado['Valor'] < limite_inf) | (df_filtrado['Valor'] > limite_sup)

    # 5. RENDERIZADO DE GRÁFICOS
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dispersión de Lotes (Boxplot)")
        st.write("Los puntos separados de la caja representan los outliers (1.5 IQR).")
        # Plotly permite pasar el mouse por encima y ver el valor exacto del lote
        fig_box = px.box(df_filtrado, y="Valor", points="all", color_discrete_sequence=["#2980B9"])
        st.plotly_chart(fig_box, use_container_width=True)

    with col2:
        st.subheader("Campana del Proceso (Histograma)")
        st.write("Visualización con los datos limpios (sin outliers).")
        df_limpio = df_filtrado[~df_filtrado['Es_Outlier']]
        fig_hist = px.histogram(df_limpio, x="Valor", nbins=10, color_discrete_sequence=["#27AE60"])
        st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.warning("No hay datos para la combinación seleccionada.")
