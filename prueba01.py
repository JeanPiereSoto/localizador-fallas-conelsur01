import re
import io
import base64
from pathlib import Path

import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import requests

# =========================================================
# 0. COLORES DE MARCA CONELSUR
# =========================================================
AZUL_CONELSUR = "#0B3088"
AZUL_CONELSUR_OSCURO = "#082564"
AZUL_CONELSUR_CLARO = "#E9EEFA"
VERDE_CONELSUR = "#00A651"
VERDE_CONELSUR_OSCURO = "#00803D"
VERDE_CONELSUR_CLARO = "#E3F7EC"
GRIS_CLARO = "#F5F7FA"
GRIS_TEXTO = "#4A4F57"
GRIS_BORDE = "#E3E6EC"

COLORES_TIPO = {
    "Poblado": "#FF8C00",
    "Carretera": "#696969",
    "Rio": "#1E90FF",
    "Cultivo": "#6B8E23",
    "Pastizal": "#9ACD32",
    "Eriazo": "#A0522D",
    "Bosque": "#2E7D32",
    "Mineria": "#222222",
    "Parque": "#228B22",
    "Telecom": "#8A2BE2",
    "Otro": "#808080",
}

st.set_page_config(
    layout="wide",
    page_title="Sistema de Localización de Fallas - SEIN",
    page_icon="⚡",
)

# =========================================================
# 1. ESTILOS DE MARCA (CSS) — el tema base (colores, fuente)
#    se fija en .streamlit/config.toml para los widgets nativos;
#    aquí se profundiza con tipografía corporativa (Google Fonts),
#    un panel lateral tipo tarjeta, tarjetas de indicadores (KPI),
#    y color consistente en pestañas, botones, inputs y alertas.
# =========================================================
st.markdown(
    f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

    <style>
        html, body, [class*="st-"], .stApp, p, div, span, li, label, input, textarea, select {{
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
        }}
        h1, h2, h3, h4, h5, h6,
        .conelsur-header h1,
        div[data-testid="stMetricValue"] {{
            font-family: 'Poppins', 'Segoe UI', Arial, sans-serif;
            font-weight: 600;
        }}

        .stApp {{
            background-color: {GRIS_CLARO};
        }}

        /* ---- Barra superior con degradado de marca ---- */
        .conelsur-gradiente {{
            height: 6px;
            width: 100%;
            background: linear-gradient(90deg, {AZUL_CONELSUR} 0%, {AZUL_CONELSUR} 55%, {VERDE_CONELSUR} 100%);
            border-radius: 0 0 4px 4px;
            margin-bottom: 0;
        }}

        /* ---- Encabezado ---- */
        .conelsur-header {{
            background-color: #FFFFFF;
            padding: 18px 28px;
            display: flex;
            align-items: center;
            gap: 22px;
            margin-bottom: 20px;
            border-radius: 0 0 12px 12px;
            box-shadow: 0 3px 14px rgba(11, 48, 136, 0.10);
        }}
        .conelsur-header img {{ height: 46px; }}
        .conelsur-header .titulo-wrap {{ display: flex; flex-direction: column; gap: 2px; }}
        .conelsur-header h1 {{
            color: {AZUL_CONELSUR};
            font-size: 24px;
            margin: 0;
            letter-spacing: -0.2px;
        }}
        .conelsur-header p {{
            color: {GRIS_TEXTO};
            margin: 0;
            font-size: 13.5px;
            font-family: 'Inter', sans-serif;
        }}
        .conelsur-badge {{
            margin-left: auto;
            background-color: {VERDE_CONELSUR_CLARO};
            color: {VERDE_CONELSUR_OSCURO};
            font-size: 12px;
            font-weight: 600;
            padding: 5px 12px;
            border-radius: 20px;
            white-space: nowrap;
        }}

        h2, h3 {{ color: {AZUL_CONELSUR}; }}

        /* ---- Panel lateral tipo tarjeta ---- */
        [data-testid="column"]:first-of-type {{
            background-color: #FFFFFF;
            border-radius: 14px;
            padding: 20px 22px 26px 22px;
            box-shadow: 0 2px 12px rgba(11, 48, 136, 0.08);
            border: 1px solid {GRIS_BORDE};
        }}

        /* ---- Tarjetas de indicadores (KPI) ---- */
        .kpi-fila {{ display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }}
        .kpi-card {{
            flex: 1;
            min-width: 140px;
            background-color: #FFFFFF;
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 2px 10px rgba(11, 48, 136, 0.07);
            border-top: 3px solid {VERDE_CONELSUR};
        }}
        .kpi-card .kpi-valor {{
            font-family: 'Poppins', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: {AZUL_CONELSUR};
            line-height: 1.1;
        }}
        .kpi-card .kpi-etiqueta {{
            font-size: 12.5px;
            color: {GRIS_TEXTO};
            margin-top: 4px;
        }}

        /* ---- Contenedor del mapa ---- */
        .mapa-card {{
            background-color: #FFFFFF;
            border-radius: 14px;
            padding: 10px;
            box-shadow: 0 2px 12px rgba(11, 48, 136, 0.08);
            border: 1px solid {GRIS_BORDE};
            margin-bottom: 14px;
        }}

        /* ---- Botones ---- */
        .stButton > button, .stDownloadButton > button {{
            background-color: {AZUL_CONELSUR};
            color: white;
            border-radius: 7px;
            border: none;
            font-weight: 500;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            background-color: {VERDE_CONELSUR};
            color: white;
        }}

        /* ---- Pestañas (st.tabs) ---- */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 2px solid {AZUL_CONELSUR_CLARO};
        }}
        .stTabs [data-baseweb="tab"] {{
            color: {AZUL_CONELSUR};
            font-weight: 500;
            padding: 8px 14px;
        }}
        .stTabs [aria-selected="true"] {{
            color: {VERDE_CONELSUR_OSCURO} !important;
            border-bottom: 3px solid {VERDE_CONELSUR} !important;
            font-weight: 600;
        }}

        /* ---- Checkboxes y sliders con acento de marca ---- */
        input[type="checkbox"] {{ accent-color: {VERDE_CONELSUR}; }}
        div[data-baseweb="slider"] div[role="slider"] {{
            background-color: {VERDE_CONELSUR} !important;
            border-color: {VERDE_CONELSUR} !important;
        }}
        div[data-baseweb="slider"] > div > div {{
            background: {VERDE_CONELSUR} !important;
        }}

        /* ---- Inputs: borde azul al enfocar ---- */
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="select"]:focus-within,
        div[data-baseweb="textarea"]:focus-within {{
            border-color: {AZUL_CONELSUR} !important;
            box-shadow: 0 0 0 1px {AZUL_CONELSUR} !important;
        }}

        /* ---- Alertas con acento de marca ---- */
        div[data-testid="stAlertContainer"] {{
            border-left: 6px solid {VERDE_CONELSUR};
            border-radius: 8px;
        }}

        /* ---- Tarjeta de ubicación estimada ---- */
        .ubicacion-card {{
            background-color: {VERDE_CONELSUR_CLARO};
            border: 1px solid {VERDE_CONELSUR};
            border-radius: 10px;
            padding: 14px 16px;
            margin: 10px 0 16px 0;
        }}
        .ubicacion-card .titulo {{
            color: {VERDE_CONELSUR_OSCURO};
            font-weight: 600;
            font-size: 14.5px;
            margin-bottom: 4px;
        }}
        .ubicacion-card .detalle {{
            color: {GRIS_TEXTO};
            font-size: 13.5px;
            line-height: 1.5;
        }}

        /* ---- Expanders y subheaders ---- */
        details > summary {{
            color: {AZUL_CONELSUR};
            font-weight: 600;
        }}

        /* ---- Leyenda de restricciones ---- */
        .leyenda-card {{
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 2px 10px rgba(11, 48, 136, 0.06);
            border: 1px solid {GRIS_BORDE};
        }}
        .leyenda-titulo {{
            font-size: 12.5px;
            font-weight: 600;
            color: {AZUL_CONELSUR};
            text-transform: uppercase;
            letter-spacing: 0.4px;
            margin-bottom: 8px;
        }}
        .leyenda-item {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-right: 16px;
            margin-bottom: 4px;
            font-size: 13px;
            color: {GRIS_TEXTO};
            font-family: 'Inter', sans-serif;
        }}
        .leyenda-swatch {{
            width: 13px;
            height: 13px;
            border-radius: 4px;
            display: inline-block;
        }}

        /* ---- Pie de página de marca ---- */
        .conelsur-footer {{
            margin-top: 26px;
            padding: 12px 0;
            text-align: center;
            font-size: 12px;
            color: #9AA0A8;
            border-top: 1px solid {GRIS_BORDE};
            font-family: 'Inter', sans-serif;
        }}
    </style>
    <div class="conelsur-gradiente"></div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 2. ENCABEZADO CON LOGO
# =========================================================
def cargar_logo_base64(ruta: str) -> str:
    try:
        return base64.b64encode(Path(ruta).read_bytes()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = cargar_logo_base64("conelsur_logo.jpg")

if logo_b64:
    st.markdown(
        f"""
        <div class="conelsur-header">
            <img src="data:image/jpeg;base64,{logo_b64}" alt="Conelsur">
            <div class="titulo-wrap">
                <h1>Centro de Control: Localizador de Fallas Georreferenciado</h1>
                <p>Herramienta analítica para la optimización de tiempos de respuesta post-falla</p>
            </div>
            <span class="conelsur-badge">● SEIN en línea</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title("⚡ Centro de Control: Localizador de Fallas Georreferenciado")
    st.markdown("Herramienta analítica para la optimización de tiempos de respuesta post-falla.")
    st.divider()

# =========================================================
# 3. FUNCIONES AUXILIARES
# =========================================================
def distancia_m(lat1, lon1, lat2, lon2):
    R = 6371000
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def punto_en_distancia(df_linea, dist_m):
    """Interpola lat/lon a lo largo de una línea dada una distancia acumulada en metros."""
    df_antes = df_linea[df_linea["Distancia_m"] <= dist_m]
    df_despues = df_linea[df_linea["Distancia_m"] > dist_m]

    if df_antes.empty:
        fila = df_linea.iloc[0]
        return fila["Latitud"], fila["Longitud"]
    if df_despues.empty:
        fila = df_linea.iloc[-1]
        return fila["Latitud"], fila["Longitud"]

    t_ant = df_antes.iloc[-1]
    t_pos = df_despues.iloc[0]

    if t_pos["Distancia_m"] != t_ant["Distancia_m"]:
        peso = (dist_m - t_ant["Distancia_m"]) / (t_pos["Distancia_m"] - t_ant["Distancia_m"])
    else:
        peso = 0

    lat = t_ant["Latitud"] + peso * (t_pos["Latitud"] - t_ant["Latitud"])
    lon = t_ant["Longitud"] + peso * (t_pos["Longitud"] - t_ant["Longitud"])
    return lat, lon


def punto_mas_cercano_en_linea(df_linea, lat, lon):
    """Devuelve (distancia_m, fila) de la torre más cercana de la línea a un punto dado."""
    distancias = distancia_m(df_linea["Latitud"].values, df_linea["Longitud"].values, lat, lon)
    idx = distancias.argmin()
    return distancias[idx], df_linea.iloc[idx]


def codigo_de_nombre_linea(nombre_linea):
    m = re.search(r"L-(\d+)", nombre_linea)
    return int(m.group(1)) if m else None


def codigos_en_texto(texto):
    return set(int(n) for n in re.findall(r"\d+", str(texto)))


# =========================================================
# 4. CARGAR DATOS
# =========================================================
df = pd.read_excel("consolidado_total.xlsx")
df.columns = df.columns.str.strip()
df["Latitud"] = pd.to_numeric(df["Latitud"], errors="coerce")
df["Longitud"] = pd.to_numeric(df["Longitud"], errors="coerce")
df["Torre"] = df["Torre"].astype(str).str.strip()

datos_lineas = {}
for linea, grupo in df.groupby("Linea"):
    grupo = grupo.reset_index(drop=True)
    grupo["Distancia_m"] = 0.0
    for i in range(1, len(grupo)):
        d = distancia_m(
            grupo.loc[i - 1, "Latitud"], grupo.loc[i - 1, "Longitud"],
            grupo.loc[i, "Latitud"], grupo.loc[i, "Longitud"],
        )
        grupo.loc[i, "Distancia_m"] = grupo.loc[i - 1, "Distancia_m"] + d
    datos_lineas[linea] = grupo

# Restricciones (zonas pobladas, cruces de carretera/río, etc.)
try:
    df_rest = pd.read_csv("restricciones_conelsur.csv", encoding="utf-8-sig")
    df_rest["Tipo"] = df_rest["Tipo"].astype(str).str.strip()
    restricciones_disponibles = True
except FileNotFoundError:
    df_rest = pd.DataFrame()
    restricciones_disponibles = False

# =========================================================
# 5. INTERFAZ — CONTROLES
# =========================================================
col_control, col_mapa = st.columns([1, 3])

with col_control:
    st.header("📋 Datos del Evento")

    linea_seleccionada = st.selectbox("Seleccione la Línea:", list(datos_lineas.keys()))
    df_linea = datos_lineas[linea_seleccionada]

    distancia_max_km = df_linea["Distancia_m"].max() / 1000

    distancia_falla_km = st.number_input(
        f"Distancia de falla (0 a {distancia_max_km:.2f} km):",
        min_value=0.0,
        max_value=float(distancia_max_km),
        value=distancia_max_km / 2,
        step=0.1,
    )
    distancia_falla_m = distancia_falla_km * 1000

    if restricciones_disponibles:
        mostrar_restricciones = st.checkbox("Mostrar restricciones en el mapa", value=True)
    else:
        mostrar_restricciones = False
        st.warning("No se encontró restricciones_conelsur.csv en el repositorio.")

    # ---------------------------------------------------
    # Ubicación de la falla
    # ---------------------------------------------------
    lat_falla, lon_falla = punto_en_distancia(df_linea, distancia_falla_m)

    df_antes = df_linea[df_linea["Distancia_m"] <= distancia_falla_m]
    df_despues = df_linea[df_linea["Distancia_m"] > distancia_falla_m]
    if df_despues.empty:
        t_anterior, t_posterior = df_antes.iloc[-2], df_antes.iloc[-1]
    else:
        t_anterior = df_antes.iloc[-1] if not df_antes.empty else df_linea.iloc[0]
        t_posterior = df_despues.iloc[0]

    if t_anterior["Torre"] == t_posterior["Torre"]:
        ubicacion_detalle = f"Falla exacta en torre: <b>{t_anterior['Torre']}</b>"
    else:
        ubicacion_detalle = f"Entre torres <b>{t_anterior['Torre']}</b> y <b>{t_posterior['Torre']}</b>"

    st.markdown(
        f"""
        <div class="ubicacion-card">
            <div class="titulo">📍 Ubicación estimada</div>
            <div class="detalle">
                Coordenadas: {lat_falla:.5f}, {lon_falla:.5f}<br>
                {ubicacion_detalle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------
    # Restricciones de la línea seleccionada
    # ---------------------------------------------------
    df_rest_linea = pd.DataFrame()
    if restricciones_disponibles:
        codigo_linea_actual = codigo_de_nombre_linea(linea_seleccionada)
        mask = df_rest["Codigo_Linea"].apply(lambda s: codigo_linea_actual in codigos_en_texto(s))
        df_rest_linea = df_rest[mask].copy()

        if not df_rest_linea.empty:
            puntos_ini = df_rest_linea["Acumulado_Inicio_m"].apply(lambda d: punto_en_distancia(df_linea, d))
            puntos_fin = df_rest_linea["Acumulado_Fin_m"].apply(lambda d: punto_en_distancia(df_linea, d))
            df_rest_linea["lat_ini"] = puntos_ini.apply(lambda p: p[0])
            df_rest_linea["lon_ini"] = puntos_ini.apply(lambda p: p[1])
            df_rest_linea["lat_fin"] = puntos_fin.apply(lambda p: p[0])
            df_rest_linea["lon_fin"] = puntos_fin.apply(lambda p: p[1])

        # --- Chequeo automático: ¿el punto de falla cae en una restricción? ---
        st.subheader("🔎 Verificación en el punto de falla")
        margen_m = 25  # tolerancia de interpolación
        en_rango = df_rest_linea[
            (df_rest_linea["Acumulado_Inicio_m"] - margen_m <= distancia_falla_m)
            & (df_rest_linea["Acumulado_Fin_m"] + margen_m >= distancia_falla_m)
        ]

        if en_rango.empty:
            st.info("No se registran restricciones conocidas en este punto.")
        else:
            for _, r in en_rango.iterrows():
                detalle = (
                    f"**{r['Tipo']}** — {r['Zona_Geografica']}  \n"
                    f"{r['Texto_Original']}  \n"
                    f"Distancia horizontal al eje: {r['Distancia_Horizontal_m']:.0f} m · Fuente: {r['Fuente']}"
                )
                if r["Tipo"] == "Poblado" and r["Distancia_Horizontal_m"] < 100:
                    st.error(f"⚠️ Zona poblada cercana\n\n{detalle}")
                elif r["Fuente"] == "Cruce":
                    st.warning(f"🚧 Cruce con {r['Tipo'].lower()}\n\n{detalle}")
                else:
                    st.warning(detalle)

# =========================================================
# 6. MAPA
# =========================================================
with col_mapa:
    # ---------------------------------------------------
    # Tarjetas de indicadores (KPI) de la línea seleccionada
    # ---------------------------------------------------
    n_torres = len(df_linea)
    longitud_km = df_linea["Distancia_m"].max() / 1000
    n_restricciones = len(df_rest_linea) if not df_rest_linea.empty else 0

    st.markdown(
        f"""
        <div class="kpi-fila">
            <div class="kpi-card">
                <div class="kpi-valor">{n_torres}</div>
                <div class="kpi-etiqueta">Torres en la línea</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-valor">{longitud_km:.1f} km</div>
                <div class="kpi-etiqueta">Longitud total</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-valor">{n_restricciones}</div>
                <div class="kpi-etiqueta">Restricciones registradas</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-valor">{distancia_falla_km:.2f} km</div>
                <div class="kpi-etiqueta">Distancia de falla</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m = folium.Map(location=[lat_falla, lon_falla], zoom_start=11)

    coord_linea = list(zip(df_linea["Latitud"], df_linea["Longitud"]))
    folium.PolyLine(coord_linea, color=AZUL_CONELSUR, weight=4).add_to(m)

    for _, fila in df_linea.iterrows():
        popup_torre = (
            f'<div style="font-family:Inter,Arial,sans-serif;">'
            f'<b style="color:{AZUL_CONELSUR};">{fila["Torre"]}</b><br>'
            f'Km {fila["Distancia_m"]/1000:.2f}</div>'
        )
        folium.CircleMarker(
            location=[fila["Latitud"], fila["Longitud"]],
            radius=4,
            color=AZUL_CONELSUR,
            fill=True,
            fill_color="white",
            fill_opacity=1,
            popup=popup_torre,
        ).add_to(m)

    if mostrar_restricciones and not df_rest_linea.empty:
        capa_restricciones = folium.FeatureGroup(name="Restricciones")
        for _, r in df_rest_linea.iterrows():
            color = COLORES_TIPO.get(r["Tipo"], "#808080")
            popup_html = (
                f'<div style="font-family:Inter,Arial,sans-serif; font-size:13px;">'
                f'<b style="color:{color};">{r["Tipo"]}</b> ({r["Fuente"]})<br>'
                f'{r["Zona_Geografica"]}<br>'
                f'{r["Texto_Original"]}<br>'
                f'D. horizontal: {r["Distancia_Horizontal_m"]:.0f} m</div>'
            )
            if r["Acumulado_Inicio_m"] == r["Acumulado_Fin_m"]:
                folium.CircleMarker(
                    location=[r["lat_ini"], r["lon_ini"]],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=popup_html,
                ).add_to(capa_restricciones)
            else:
                folium.PolyLine(
                    [[r["lat_ini"], r["lon_ini"]], [r["lat_fin"], r["lon_fin"]]],
                    color=color,
                    weight=6,
                    opacity=0.65,
                    popup=popup_html,
                ).add_to(capa_restricciones)
        capa_restricciones.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)

    popup_falla = (
        f'<div style="font-family:Inter,Arial,sans-serif;">'
        f'<b style="color:{VERDE_CONELSUR_OSCURO};">⚡ Falla estimada</b><br>'
        f'Km {distancia_falla_km:.2f}</div>'
    )
    folium.Marker(
        location=[lat_falla, lon_falla],
        popup=popup_falla,
        icon=folium.Icon(color="green", icon="bolt", prefix="fa"),
    ).add_to(m)

    st.markdown('<div class="mapa-card">', unsafe_allow_html=True)
    st_folium(m, width="100%", height=580)
    st.markdown("</div>", unsafe_allow_html=True)

    if mostrar_restricciones and not df_rest_linea.empty:
        tipos_presentes = sorted(df_rest_linea["Tipo"].unique())
        leyenda_items = "".join(
            f'<span class="leyenda-item"><span class="leyenda-swatch" '
            f'style="background-color:{COLORES_TIPO.get(t, "#808080")}"></span>{t}</span>'
            for t in tipos_presentes
        )
        st.markdown(
            f"""
            <div class="leyenda-card">
                <div class="leyenda-titulo">Leyenda de restricciones</div>
                {leyenda_items}
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    '<div class="conelsur-footer">CONELSUR — Centro de Control de Operaciones de Transmisión · '
    'Sistema de Localización de Fallas SEIN</div>',
    unsafe_allow_html=True,
)
