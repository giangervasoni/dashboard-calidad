import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ==============================================================================
# 1. DICCIONARIO MAESTRO DE ESPECIFICACIONES (MATRIZ DE CALIDAD ACTUALIZADA)
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
st.set_page_config(page_title="Dashboard de Calidad Multiproducto", layout="wide")
st.title("📊 Plataforma de Control Granulométrico y Benchmark de Proveedores")

# ==============================================================================
# 3. BARRA LATERAL (SUBIDA DE ARCHIVOS Y FILTROS)
# ==============================================================================
st.sidebar.header("1. Carga de Datos")
prod_seleccionado = st.sidebar.selectbox("Seleccionar Producto:", list(SPECS.keys()))
archivo_subido = st.sidebar.file_uploader("Subir reporte LIMS (.csv)", type=["csv"])

st.sidebar.markdown("---")
st.sidebar.header("2. Navegación por Módulos")
modulo_activo = st.sidebar.radio("Ir a:", [
    "🔍 Análisis por Malla y Outliers", 
    "🏆 Scorecard de Proveedores", 
    "🎛️ Simulador de Especificaciones (R&D)"
])

# ==============================================================================
# 4. FUNCIÓN INTELIGENTE DE PARSEO DE DATOS
# ==============================================================================
@st.cache_data
def procesar_datos(file):
    df_raw = pd.read_csv(file, sep=";", decimal=",")
    if len(df_raw.columns) < 2:
        file.seek(0)
        df_raw = pd.read_csv(file, sep=",")
    
    # Formato Ancho vs Largo
    if any("Malla_710" in str(c) or "Malla_250" in str(c) or "Malla_425" in str(c) for c in df_raw.columns):
        cols_retener = ["Proveedor"] + [c for c in df_raw.columns if "Malla" in c or "Fondo" in c]
        df_raw = df_raw[cols_retener]
        df_long = df_raw.melt(id_vars=["Proveedor"], var_name="Malla", value_name="Valor")
        df_long['Malla'] = df_long['Malla'].str.replace("_", " ") + " µm"
        df_long['Malla'] = df_long['Malla'].str.replace("Fondo µm", "Fondo")
    else:
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
    
    df_long = df_long[df_long['Malla'] != "Otra"].dropna(subset=['Valor']).copy()
    df_long['Valor'] = df_long['Valor'].apply(lambda x: 0.0 if float(x) < 0 else float(x))
    
    return df_long[['Proveedor', 'Malla', 'Valor']]

# Evaluación de cumplimiento según especificación
def evaluar_cumplimiento(row, producto):
    malla = row['Malla']
    valor = row['Valor']
    if producto in SPECS and malla in SPECS[producto]:
        lim = SPECS[producto][malla]
        min_val = lim.get("min", 0.0)
        max_val = lim.get("max", 100.0)
        return min_val <= valor <= max_val
    return True

# ==============================================================================
# 5. EJECUCIÓN PRINCIPAL DE MÓDULOS
# ==============================================================================
if archivo_subido is not None:
    try:
        df = procesar_datos(archivo_subido)
        df['Cumple_Spec'] = df.apply(evaluar_cumplimiento, producto=prod_seleccionado, axis=1)
        
        # --- MÓDULO 1: ANÁLISIS DE MALLAS Y OUTLIERS ---
        if modulo_activo == "🔍 Análisis por Malla y Outliers":
            st.header(f"Análisis Individual por Malla - {prod_seleccionado}")
            
            lista_proveedores = ["Todos"] + list(df['Proveedor'].unique())
            prov_sel = st.sidebar.selectbox("Seleccionar Proveedor:", lista_proveedores)
            
            lista_mallas = list(df['Malla'].unique())
            malla_sel = st.sidebar.selectbox("Seleccionar Fracción (Malla):", lista_mallas)
            
            df_filt = df[df['Malla'] == malla_sel].copy()
            if prov_sel != "Todos":
                df_filt = df_filt[df_filt['Proveedor'] == prov_sel]
                
            if not df_filt.empty:
                # Detección IQR
                Q1 = df_filt['Valor'].quantile(0.25)
                Q3 = df_filt['Valor'].quantile(0.75)
                IQR = Q3 - Q1
                df_filt['Es_Outlier'] = (df_filt['Valor'] < (Q1 - 1.5 * IQR)) | (df_filt['Valor'] > (Q3 + 1.5 * IQR))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📦 Dispersión de Lotes (Boxplot)")
                    fig_box = px.box(df_filt, y="Valor", points="all", color_discrete_sequence=["#2980B9"])
                    st.plotly_chart(fig_box, use_container_width=True)
                with col2:
                    st.subheader("🔔 Campana del Proceso (Histograma)")
                    df_limpio = df_filt[~df_filt['Es_Outlier']]
                    fig_hist = px.histogram(df_limpio, x="Valor", nbins=15, color_discrete_sequence=["#27AE60"])
                    
                    if prod_seleccionado in SPECS and malla_sel in SPECS[prod_seleccionado]:
                        lim = SPECS[prod_seleccionado][malla_sel]
                        if "min" in lim:
                            fig_hist.add_vline(x=lim["min"], line_dash="dash", line_color="#C0392B", annotation_text="Min Spec")
                        if "max" in lim:
                            fig_hist.add_vline(x=lim["max"], line_dash="dash", line_color="#C0392B", annotation_text="Max Spec")
                    st.plotly_chart(fig_hist, use_container_width=True)

        # --- MÓDULO 2: SCORECARD Y BENCHMARK DE PROVEEDORES ---
        elif modulo_activo == "🏆 Scorecard de Proveedores (Vendor Rating)":
            st.header(f"Evaluación y Ranking de Proveedores - {prod_seleccionado}")
            st.markdown("Índice de Calidad Granulométrica (ICG) calculado a partir del cumplimiento, variabilidad y tasa de atipicidades.")
            
            # Cálculo de outliers por malla para todo el dataset
            def marcar_outlier(df_sub):
                Q1 = df_sub['Valor'].quantile(0.25)
                Q3 = df_sub['Valor'].quantile(0.75)
                IQR = Q3 - Q1
                df_sub['Es_Outlier'] = (df_sub['Valor'] < (Q1 - 1.5 * IQR)) | (df_sub['Valor'] > (Q3 + 1.5 * IQR))
                return df_sub

            df_out = df.groupby('Malla', group_keys=False).apply(marcar_outlier)
            
            # Agregación por Proveedor
            scorecard = df_out.groupby('Proveedor').agg(
                Total_Ensayos=('Valor', 'count'),
                Cumplimiento_Pct=('Cumple_Spec', lambda x: round(x.mean() * 100, 1)),
                Tasa_Outliers_Pct=('Es_Outlier', lambda x: round(x.mean() * 100, 1)),
                Variabilidad_Promedio=('Valor', lambda x: round(x.std(), 2))
            ).reset_index()
            
            # Cálculo del ICG (Fórmula Ponderada: 60% Cumplimiento + 20% Estabilidad + 20% Ausencia de Outliers)
            max_var = scorecard['Variabilidad_Promedio'].max() if scorecard['Variabilidad_Promedio'].max() > 0 else 1
            scorecard['Factor_Estabilidad'] = (1 - (scorecard['Variabilidad_Promedio'] / max_var)) * 100
            
            scorecard['ICG'] = (
                (scorecard['Cumplimiento_Pct'] * 0.60) + 
                (scorecard['Factor_Estabilidad'] * 0.20) + 
                ((100 - scorecard['Tasa_Outliers_Pct']) * 0.20)
            ).round(1)
            
            scorecard = scorecard.sort_values(by='ICG', ascending=False)
            
            # KPI Cards
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            col_kpi1.metric("🏆 Mejor Proveedor", scorecard.iloc[0]['Proveedor'], f"ICG: {scorecard.iloc[0]['ICG']}/100")
            col_kpi2.metric("🎯 Cumplimiento Promedio Global", f"{scorecard['Cumplimiento_Pct'].mean():.1f}%")
            col_kpi3.metric("⚠️ Tasa Promedio de Outliers", f"{scorecard['Tasa_Outliers_Pct'].mean():.1f}%")
            
            st.markdown("---")
            st.subheader("Tabla Comparativa de Desempeño (Vendor Rating)")
            
            st.dataframe(
                scorecard[['Proveedor', 'ICG', 'Cumplimiento_Pct', 'Tasa_Outliers_Pct', 'Variabilidad_Promedio', 'Total_Ensayos']].rename(columns={
                    'Cumplimiento_Pct': '% Cumplimiento',
                    'Tasa_Outliers_Pct': '% Outliers',
                    'Variabilidad_Promedio': 'Desv. Est. Promedio (SD)'
                }),
                use_container_width=True
            )
            
            fig_icg = px.bar(scorecard, x='Proveedor', y='ICG', color='ICG', 
                             color_continuous_scale='Greens', title="Ranking ICG por Proveedor")
            st.plotly_chart(fig_icg, use_container_width=True)

        # --- MÓDULO 3: SIMULADOR DE ESPECIFICACIONES (R&D) ---
        elif modulo_activo == "🎛️ Simulador de Especificaciones (R&D)":
            st.header("Simulador de Impacto de Ficha Técnica (R&D)")
            st.markdown("Ajustá los límites teóricos para medir de forma inmediata el impacto sobre la tasa de aprobación de lotes históricos.")
            
            malla_sim = st.selectbox("Seleccionar Malla a Simular:", list(df['Malla'].unique()))
            df_sim = df[df['Malla'] == malla_sim].copy()
            
            lim_actual = SPECS.get(prod_seleccionado, {}).get(malla_sim, {})
            def_min = float(lim_actual.get("min", df_sim['Valor'].min()))
            def_max = float(lim_actual.get("max", df_sim['Valor'].max()))
            
            val_min_data = float(df_sim['Valor'].min())
            val_max_data = float(df_sim['Valor'].max())
            
            st.subheader(f"Configurar Nuevos Límites Propuestos para {malla_sim}")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                nuevo_min = st.slider("Nuevo Límite MÍNIMO (%)", min_value=0.0, max_value=val_max_data, value=def_min, step=0.5)
            with col_s2:
                nuevo_max = st.slider("Nuevo Límite MÁXIMO (%)", min_value=nuevo_min, max_value=val_max_data + 10.0, value=def_max, step=0.5)
                
            df_sim['Cumple_Actual'] = df_sim.apply(evaluar_cumplimiento, producto=prod_seleccionado, axis=1)
            df_sim['Cumple_Nuevo'] = (df_sim['Valor'] >= nuevo_min) & (df_sim['Valor'] <= nuevo_max)
            
            pct_actual = (df_sim['Cumple_Actual'].sum() / len(df_sim)) * 100
            pct_nuevo = (df_sim['Cumple_Nuevo'].sum() / len(df_sim)) * 100
            delta = pct_nuevo - pct_actual
            
            st.markdown("---")
            st.subheader("Impacto Estimado en Aprobación de Lotes")
            c1, c2, c3 = st.columns(3)
            c1.metric("% Cumplimiento Actual (Ficha Vigente)", f"{pct_actual:.1f}%")
            c2.metric("% Cumplimiento Propuesto (Nueva Ficha)", f"{pct_nuevo:.1f}%", f"{delta:+.1f}% vs Actual")
            c3.metric("Lotes Recuperados / Impactados", f"{df_sim['Cumple_Nuevo'].sum()} de {len(df_sim)} lotes")
            
            fig_sim = px.histogram(df_sim, x="Valor", nbins=20, title=f"Distribución de {malla_sim} vs Límites", color_discrete_sequence=["#27AE60"])
            
            if "min" in lim_actual:
                fig_sim.add_vline(x=lim_actual["min"], line_dash="dash", line_color="#C0392B", annotation_text="Min Actual")
            if "max" in lim_actual:
                fig_sim.add_vline(x=lim_actual["max"], line_dash="dash", line_color="#C0392B", annotation_text="Max Actual")
                
            fig_sim.add_vline(x=nuevo_min, line_dash="solid", line_color="#2980B9", annotation_text="NUEVO Min", line_width=3)
            fig_sim.add_vline(x=nuevo_max, line_dash="solid", line_color="#2980B9", annotation_text="NUEVO Max", line_width=3)
            
            st.plotly_chart(fig_sim, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Ocurrió un error al procesar el archivo. Detalle: {e}")
else:
    st.info("👆 Por favor, selecciona un producto y sube tu archivo CSV en la barra lateral izquierda para comenzar.")
