import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np

# =========================================================
# 1. CONFIGURACIÓN
# =========================================================
st.set_page_config(layout="wide", page_title="Sistema de Localización de Fallas - SEIN")

st.title("⚡ Centro de Control: Localizador de Fallas Georreferenciado")
st.markdown("Herramienta analítica para la optimización de tiempos de respuesta post-falla.")
st.divider()

# =========================================================
# 2. CARGAR EXCEL REAL
# =========================================================
ruta_excel = r"C:\Users\practica.jeanpiere\Downloads\KMZ LINEAS CNS\consolidado_total.xlsx"

df = pd.read_excel(ruta_excel)

# limpiar columnas
df.columns = df.columns.str.strip()

# asegurar tipos
df["Latitud"] = pd.to_numeric(df["Latitud"], errors="coerce")
df["Longitud"] = pd.to_numeric(df["Longitud"], errors="coerce")
df["Torre"] = df["Torre"].astype(str).str.strip()

# =========================================================
# 3. FUNCIÓN DISTANCIA (REAL)
# =========================================================
def distancia(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# =========================================================
# 4. CREAR DICCIONARIO DE LÍNEAS + DISTANCIA REAL
# =========================================================
datos_lineas = {}

for linea, grupo in df.groupby("Linea"):
    grupo = grupo.reset_index(drop=True)

    # calcular distancia acumulada
    grupo["Distancia_km"] = 0.0
    for i in range(1, len(grupo)):
        d = distancia(
            grupo.loc[i-1, "Latitud"], grupo.loc[i-1, "Longitud"],
            grupo.loc[i, "Latitud"], grupo.loc[i, "Longitud"]
        )
        grupo.loc[i, "Distancia_km"] = grupo.loc[i-1, "Distancia_km"] + d

    datos_lineas[linea] = grupo

# =========================================================
# 5. INTERFAZ
# =========================================================
col_control, col_mapa = st.columns([1, 3])

with col_control:
    st.header("📋 Datos del Evento")

    linea_seleccionada = st.selectbox("Seleccione la Línea:", list(datos_lineas.keys()))
    df_linea = datos_lineas[linea_seleccionada]

    distancia_max = df_linea["Distancia_km"].max()

    distancia_falla = st.number_input(
        f"Distancia de falla (0 a {distancia_max:.2f} km):",
        min_value=0.0,
        max_value=float(distancia_max),
        value=distancia_max / 2,
        step=0.1
    )

    # =========================================================
    # 6. CÁLCULO DE FALLA
    # =========================================================
    df_antes = df_linea[df_linea["Distancia_km"] <= distancia_falla]
    df_despues = df_linea[df_linea["Distancia_km"] > distancia_falla]

    if df_despues.empty:
        t_anterior = df_antes.iloc[-2]
        t_posterior = df_antes.iloc[-1]
    else:
        t_anterior = df_antes.iloc[-1]
        t_posterior = df_despues.iloc[0]

    if t_posterior["Distancia_km"] != t_anterior["Distancia_km"]:
        peso = (distancia_falla - t_anterior["Distancia_km"]) / (
            t_posterior["Distancia_km"] - t_anterior["Distancia_km"]
        )
    else:
        peso = 0

    lat_falla = t_anterior["Latitud"] + peso * (t_posterior["Latitud"] - t_anterior["Latitud"])
    lon_falla = t_anterior["Longitud"] + peso * (t_posterior["Longitud"] - t_anterior["Longitud"])

    st.success("📍 Ubicación estimada")
    st.write(f"Coordenadas: {lat_falla:.5f}, {lon_falla:.5f}")

    if t_anterior["Torre"] == t_posterior["Torre"]:
        st.write(f"Falla exacta en torre: {t_anterior['Torre']}")
    else:
        st.write(f"Entre: {t_anterior['Torre']} y {t_posterior['Torre']}")

# =========================================================
# 7. MAPA
# =========================================================
with col_mapa:
    m = folium.Map(location=[lat_falla, lon_falla], zoom_start=11)

    # línea
    coord_linea = list(zip(df_linea["Latitud"], df_linea["Longitud"]))
    folium.PolyLine(coord_linea, color="blue", weight=4).add_to(m)

    # torres
    for _, fila in df_linea.iterrows():
        folium.CircleMarker(
            location=[fila["Latitud"], fila["Longitud"]],
            radius=4,
            color="black",
            fill=True,
            fill_color="white",
            popup=f"{fila['Torre']} (Km {fila['Distancia_km']:.2f})"
        ).add_to(m)

    # falla
    folium.Marker(
        location=[lat_falla, lon_falla],
        popup=f"Falla Km {distancia_falla:.2f}",
        icon=folium.Icon(color="red", icon="bolt", prefix="fa")
    ).add_to(m)

    st_folium(m, width="100%", height=600)
