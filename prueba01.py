import re
import base64
from pathlib import Path

import streamlit as st
import pydeck as pdk
import pandas as pd
import numpy as np
import requests

from cargar_kmz import cargar_lineas_y_subestaciones_kmz, COLORES_POR_VOLTAJE

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
# 0.1 MODO OSCURO — interruptor arriba a la derecha
# =========================================================
_col_vacio, _col_vista, _col_switch = st.columns([6, 2, 1])
with _col_vista:
    vista_mapa = st.radio(
        "Vista del mapa", options=["Calle", "Satélite"], horizontal=True,
        label_visibility="collapsed", key="vista_mapa",
    )
with _col_switch:
    modo_oscuro = st.toggle("🌙 Oscuro", value=False, key="modo_oscuro")

ESTILOS_MAPBOX = {
    "Calle": "mapbox://styles/mapbox/streets-v12",
    "Satélite": "mapbox://styles/mapbox/satellite-streets-v12",
}

# Tokens de color que cambian según el modo. Los colores de marca
# (AZUL_CONELSUR, VERDE_CONELSUR) se mantienen fijos — se usan también
# en el mapa — pero el resto de la interfaz (fondos, texto, tarjetas)
# se adapta para mantener buen contraste en modo oscuro.
if modo_oscuro:
    COLOR_FONDO_PAGINA = "#0E1117"
    COLOR_FONDO_TARJETA = "#1B1E24"
    COLOR_TEXTO = "#D8DBE0"
    COLOR_TEXTO_SECUNDARIO = "#9AA0A8"
    COLOR_BORDE = "#2E333B"
    COLOR_TITULO = "#9DB4F5"
    COLOR_TAB_BORDE = "#2A3550"
    COLOR_UBICACION_BG = "#11291B"
    COLOR_UBICACION_TEXTO_TITULO = VERDE_CONELSUR
    COLOR_BADGE_BG = "#12341F"
    COLOR_BADGE_TEXTO = VERDE_CONELSUR
    COLOR_SOMBRA = "rgba(0, 0, 0, 0.45)"
else:
    COLOR_FONDO_PAGINA = GRIS_CLARO
    COLOR_FONDO_TARJETA = "#FFFFFF"
    COLOR_TEXTO = GRIS_TEXTO
    COLOR_TEXTO_SECUNDARIO = "#555555"
    COLOR_BORDE = GRIS_BORDE
    COLOR_TITULO = AZUL_CONELSUR
    COLOR_TAB_BORDE = AZUL_CONELSUR_CLARO
    COLOR_UBICACION_BG = VERDE_CONELSUR_CLARO
    COLOR_UBICACION_TEXTO_TITULO = VERDE_CONELSUR_OSCURO
    COLOR_BADGE_BG = VERDE_CONELSUR_CLARO
    COLOR_BADGE_TEXTO = VERDE_CONELSUR_OSCURO
    COLOR_SOMBRA = "rgba(11, 48, 136, 0.08)"

# =========================================================
# 1. ESTILOS DE MARCA (CSS) — el tema base (colores, fuente)
#    se fija en .streamlit/config.toml para los widgets nativos;
#    aquí se profundiza con tipografía corporativa (Google Fonts),
#    un panel lateral tipo tarjeta, tarjetas de indicadores (KPI),
#    color consistente en pestañas, botones, inputs y alertas,
#    y los tokens de color de arriba para alternar modo claro/oscuro.
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
            background-color: {COLOR_FONDO_PAGINA};
        }}
        html, body, [class*="st-"], .stApp, p, div, span, li, label {{
            color: {COLOR_TEXTO};
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
            background-color: {COLOR_FONDO_TARJETA};
            padding: 18px 28px;
            display: flex;
            align-items: center;
            gap: 22px;
            margin-bottom: 20px;
            border-radius: 0 0 12px 12px;
            box-shadow: 0 3px 14px {COLOR_SOMBRA};
        }}
        .conelsur-header img {{ height: 46px; }}
        .conelsur-header .titulo-wrap {{ display: flex; flex-direction: column; gap: 2px; }}
        .conelsur-header h1 {{
            color: {COLOR_TITULO};
            font-size: 24px;
            margin: 0;
            letter-spacing: -0.2px;
        }}
        .conelsur-header p {{
            color: {COLOR_TEXTO_SECUNDARIO};
            margin: 0;
            font-size: 13.5px;
            font-family: 'Inter', sans-serif;
        }}
        .conelsur-badge {{
            margin-left: auto;
            background-color: {COLOR_BADGE_BG};
            color: {COLOR_BADGE_TEXTO};
            font-size: 12px;
            font-weight: 600;
            padding: 5px 12px;
            border-radius: 20px;
            white-space: nowrap;
        }}

        h1, h2, h3 {{ color: {COLOR_TITULO}; }}

        /* ---- Panel lateral tipo tarjeta ---- */
        [data-testid="column"]:first-of-type {{
            background-color: {COLOR_FONDO_TARJETA};
            border-radius: 14px;
            padding: 20px 22px 26px 22px;
            box-shadow: 0 2px 12px {COLOR_SOMBRA};
            border: 1px solid {COLOR_BORDE};
        }}

        /* ---- Tarjetas de indicadores (KPI) ---- */
        .kpi-fila {{ display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }}
        .kpi-card {{
            flex: 1;
            min-width: 140px;
            background-color: {COLOR_FONDO_TARJETA};
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 2px 10px {COLOR_SOMBRA};
            border-top: 3px solid {VERDE_CONELSUR};
        }}
        .kpi-card .kpi-valor {{
            font-family: 'Poppins', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: {COLOR_TITULO};
            line-height: 1.1;
        }}
        .kpi-card .kpi-etiqueta {{
            font-size: 12.5px;
            color: {COLOR_TEXTO};
            margin-top: 4px;
        }}

        /* ---- Contenedor del mapa ---- */
        .mapa-card {{
            position: relative;
            background-color: {COLOR_FONDO_TARJETA};
            border-radius: 14px;
            padding: 10px;
            box-shadow: 0 2px 12px {COLOR_SOMBRA};
            border: 1px solid {COLOR_BORDE};
            margin-bottom: 14px;
        }}

        /* ---- Leyenda flotante, fija en la esquina del mapa (compacta) ---- */
        .leyenda-flotante {{
            position: absolute;
            bottom: 22px;
            right: 22px;
            z-index: 50;
            background-color: rgba(255, 255, 255, 0.93);
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 2px 14px rgba(0, 0, 0, 0.25);
            width: max-content;
            max-width: 260px;
            pointer-events: none;
        }}
        .leyenda-flotante .leyenda-item {{
            display: flex;
            align-items: center;
            gap: 4px;
            margin-right: 0;
            margin-bottom: 1px;
            font-size: 10px;
            line-height: 1.3;
            white-space: nowrap;
            color: #1A1A1A;
        }}
        .leyenda-flotante .leyenda-titulo {{
            color: {AZUL_CONELSUR};
            font-size: 10px;
            margin-bottom: 3px;
        }}
        .leyenda-flotante .leyenda-linea-swatch {{
            width: 16px;
            border-top-width: 2px;
        }}
        .leyenda-flotante .leyenda-punto-swatch {{
            width: 8px;
            height: 8px;
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
            border-bottom: 2px solid {COLOR_TAB_BORDE};
        }}
        .stTabs [data-baseweb="tab"] {{
            color: {COLOR_TITULO};
            font-weight: 500;
            padding: 8px 14px;
        }}
        .stTabs [aria-selected="true"] {{
            color: {VERDE_CONELSUR} !important;
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

        /* ---- Inputs nativos: fondo, texto y borde adaptados al modo ----
           Anclado a data-testid (estable entre versiones de Streamlit) y a
           *todos* los descendientes, con !important, para ganarle al tema
           base fijado en config.toml. */
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] div[data-baseweb="input"],
        div[data-testid="stTextInput"] div[data-baseweb="input"],
        div[data-testid="stTextArea"] div[data-baseweb="textarea"] {{
            background-color: {COLOR_FONDO_TARJETA} !important;
            border-color: {COLOR_BORDE} !important;
        }}
        div[data-testid="stSelectbox"] *,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea {{
            background-color: transparent !important;
            color: {COLOR_TEXTO} !important;
            -webkit-text-fill-color: {COLOR_TEXTO} !important;
        }}
        div[data-testid="stTextArea"] textarea {{
            background-color: {COLOR_FONDO_TARJETA} !important;
        }}
        div[data-testid="stSelectbox"] svg {{
            fill: {COLOR_TEXTO} !important;
        }}
        div[data-baseweb="input"]:focus-within,
        div[data-baseweb="select"]:focus-within,
        div[data-baseweb="textarea"]:focus-within {{
            border-color: {AZUL_CONELSUR} !important;
            box-shadow: 0 0 0 1px {AZUL_CONELSUR} !important;
        }}
        ul[data-baseweb="menu"], div[data-baseweb="popover"] ul {{
            background-color: {COLOR_FONDO_TARJETA} !important;
        }}
        ul[data-baseweb="menu"] li, ul[data-baseweb="menu"] li * {{
            color: {COLOR_TEXTO} !important;
        }}
        ul[data-baseweb="menu"] li:hover {{
            background-color: {COLOR_BORDE} !important;
        }}

        /* ---- Alertas con acento de marca ---- */
        div[data-testid="stAlertContainer"] {{
            border-left: 6px solid {VERDE_CONELSUR};
            border-radius: 8px;
        }}

        /* ---- Tarjeta de ubicación estimada ---- */
        .ubicacion-card {{
            background-color: {COLOR_UBICACION_BG};
            border: 1px solid {VERDE_CONELSUR};
            border-radius: 10px;
            padding: 14px 16px;
            margin: 10px 0 16px 0;
        }}
        .ubicacion-card .titulo {{
            color: {COLOR_UBICACION_TEXTO_TITULO};
            font-weight: 600;
            font-size: 14.5px;
            margin-bottom: 4px;
        }}
        .ubicacion-card .detalle {{
            color: {COLOR_TEXTO};
            font-size: 13.5px;
            line-height: 1.5;
        }}

        /* ---- Expanders y subheaders ---- */
        details > summary {{
            color: {COLOR_TITULO};
            font-weight: 600;
        }}

        /* ---- Leyenda de restricciones ---- */
        .leyenda-card {{
            background-color: {COLOR_FONDO_TARJETA};
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 2px 10px {COLOR_SOMBRA};
            border: 1px solid {COLOR_BORDE};
        }}
        .leyenda-titulo {{
            font-size: 12.5px;
            font-weight: 600;
            color: {COLOR_TITULO};
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
            color: {COLOR_TEXTO};
            font-family: 'Inter', sans-serif;
        }}
        .leyenda-swatch {{
            width: 13px;
            height: 13px;
            border-radius: 4px;
            display: inline-block;
        }}
        .leyenda-linea-swatch {{
            width: 24px;
            height: 0;
            border-top-width: 3px;
            border-top-style: solid;
            display: inline-block;
        }}
        .leyenda-punto-swatch {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}

        /* ---- Pie de página de marca ---- */
        .conelsur-footer {{
            margin-top: 26px;
            padding: 12px 0;
            text-align: center;
            font-size: 12px;
            color: {COLOR_TEXTO_SECUNDARIO};
            border-top: 1px solid {COLOR_BORDE};
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

logo_b64 = cargar_logo_base64("conelsur_logo_transparente.png")
logo_mime = "image/png"
if not logo_b64:
    # Compatibilidad hacia atrás por si el repo aún no tiene la versión transparente
    logo_b64 = cargar_logo_base64("conelsur_logo.jpg")
    logo_mime = "image/jpeg"

if logo_b64:
    st.markdown(
        f"""
        <div class="conelsur-header">
            <img src="data:{logo_mime};base64,{logo_b64}" alt="Conelsur">
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


def hex_a_rgb(color_hex, alpha=255):
    """Convierte '#RRGGBB' a [r, g, b, alpha] para las capas de PyDeck."""
    color_hex = color_hex.lstrip("#")
    r, g, b = (int(color_hex[i:i + 2], 16) for i in (0, 2, 4))
    return [r, g, b, alpha]


# El TextLayer de deck.gl solo genera glifos para los caracteres de esta lista
# (por defecto, un set ASCII básico) — sin tildes/eñe aquí, nombres como
# "Huánuco" o "Ñaña" se ven con letras faltantes ("Missing character").
JUEGO_CARACTERES_TEXTO = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789 .,:;()/_-·–—'\"°%ÁÉÍÓÚÑáéíóúñÜü"
)


URL_EMERGENCIAS_BOMBEROS = (
    "https://docs.google.com/spreadsheets/d/"
    "1n_YelAX4D_mFQbXLduWTpjFLfzYOElzSYM8FiiWBhto/export?format=csv"
)


@st.cache_data(ttl=90, show_spinner="Consultando emergencias de Bomberos Perú...")
def cargar_emergencias_bomberos():
    """Hoja de Google Sheets con el registro de emergencias de Bomberos Perú
    (actualizada automáticamente por un tercero), sin necesidad de pegar HTML
    a mano. Se cachea 90 s para no golpear la hoja en cada interacción."""
    df_em = pd.read_csv(URL_EMERGENCIAS_BOMBEROS)
    df_em = df_em.rename(
        columns={
            "Nro Parte": "parte",
            "Fecha Hora": "fecha_hora",
            "Dirección / Distrito": "direccion",
            "Tipo": "tipo",
            "Estado": "estado",
            "Máquina": "maquinas",
            "Coordenada": "coordenada",
        }
    )

    def _extraer_lat_lon(valor):
        try:
            lat_str, lon_str = str(valor).split(",")
            lat, lon = float(lat_str), float(lon_str)
        except (ValueError, AttributeError):
            return pd.Series([None, None])
        if lat == 0 and lon == 0:
            return pd.Series([None, None])
        return pd.Series([lat, lon])

    df_em[["lat", "lon"]] = df_em["coordenada"].apply(_extraer_lat_lon)
    df_em["maquinas"] = df_em["maquinas"].fillna("").astype(str)
    df_em["direccion"] = df_em["direccion"].fillna("").astype(str)
    return df_em[["parte", "fecha_hora", "direccion", "tipo", "estado", "maquinas", "lat", "lon"]]


# Open-Meteo: API meteorológica gratuita, sin clave ni registro. No da la
# ubicación exacta de cada rayo (eso solo lo tiene Blitzortung, y solo para
# participantes de su red) — pero el código de clima (weather_code) sí avisa
# si hay tormenta eléctrica en curso en el punto consultado, que es la mejor
# aproximación gratuita disponible a "riesgo de descarga atmosférica".
DESCRIPCION_CLIMA = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna ligera", 53: "Llovizna moderada", 55: "Llovizna intensa",
    56: "Llovizna helada ligera", 57: "Llovizna helada intensa",
    61: "Lluvia ligera", 63: "Lluvia moderada", 65: "Lluvia intensa",
    66: "Lluvia helada ligera", 67: "Lluvia helada intensa",
    71: "Nevada ligera", 73: "Nevada moderada", 75: "Nevada intensa", 77: "Granos de nieve",
    80: "Chubascos ligeros", 81: "Chubascos moderados", 82: "Chubascos violentos",
    85: "Chubascos de nieve ligeros", 86: "Chubascos de nieve intensos",
    95: "Tormenta eléctrica", 96: "Tormenta con granizo ligero", 99: "Tormenta con granizo fuerte",
}
CODIGOS_TORMENTA = {95, 96, 99}


@st.cache_data(ttl=600, show_spinner="Consultando clima en el punto de falla...")
def cargar_clima(lat, lon):
    """Clima actual + acumulado de lluvia de las últimas 24 h, para el punto dado."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "precipitation,weather_code,wind_speed_10m",
            "hourly": "precipitation,weather_code",
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "America/Lima",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=600, show_spinner="Consultando clima a lo largo de la línea...")
def cargar_clima_en_puntos(lats, lons):
    """Clima actual en varios puntos a la vez — Open-Meteo acepta listas de
    coordenadas separadas por coma en una sola llamada, y devuelve una lista
    de resultados (uno por punto) en vez de un solo objeto."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ",".join(f"{v:.5f}" for v in lats),
            "longitude": ",".join(f"{v:.5f}" for v in lons),
            "current": "precipitation,weather_code",
            "timezone": "America/Lima",
        },
        timeout=15,
    )
    resp.raise_for_status()
    datos = resp.json()
    return datos if isinstance(datos, list) else [datos]


# Subestaciones de origen/destino por código de línea (tomado de la hoja
# "INFORMACIÓN LLTT" del Excel de torres de Conelsur). Se usa para nombrar
# los extremos de cada línea; la coordenada se aproxima con la primera y
# última torre registrada de esa línea en consolidado_total.xlsx.
SUBESTACIONES_POR_LINEA = {
    2001: ("HUINCO", "CARAPONGO"),
    2002: ("HUINCO", "CARAPONGO"),
    2701: ("CARAPONGO", "SANTA ROSA"),
    2702: ("CARAPONGO", "SANTA ROSA"),
    2007: ("MATUCANA", "CALLAHUANCA"),
    2008: ("CALLAHUANCA", "CARAPONGO"),
    2009: ("CALLAHUANCA", "CARAPONGO"),
    2708: ("CARAPONGO", "CAJAMARQUILLA"),
    2709: ("CARAPONGO", "CAJAMARQUILLA"),
    2014: ("CAJAMARQUILLA", "CHAVARRÍA"),
    2015: ("CAJAMARQUILLA", "CHAVARRÍA"),
    2256: ("YANANGO", "PACHACHACA"),
    2257: ("CHIMAY", "YANANGO"),
    2716: ("CALLAHUANCA REP", "CALLAHUANCA CNS"),
    2260: ("CAJAMARCA NORTE", "TRUJILLO NORTE"),
    2263: ("CAJAMARCA NORTE", "CERRO CORONA"),
    1047: ("ARES", "TALTA"),
    1040: ("TALTA", "CALLALLI"),
    6011: ("MOYOPAMPA", "PORTILLO"),
    6020: ("MOYOPAMPA", "PORTILLO"),
    6436: ("PORTILLO", "GLORIA"),
    6437: ("PORTILLO", "GLORIA"),
    6031: ("CALLAHUANCA", "HUACHIPA"),
    6040: ("CALLAHUANCA", "HUAMPANÍ"),
    6055: ("MOYOPAMPA", "SALAMANCA"),
    6060: ("MOYOPAMPA", "SALAMANCA"),
    6068: ("SALAMANCA", "BALNEARIOS"),
    6111: ("CALLAHUANCA", "MOYOPAMPA"),
    6434: ("SANTA ROSA ANTIGUA", "GLORIA"),
    6435: ("SANTA ROSA ANTIGUA", "GLORIA"),
    6544: ("HUAMPANÍ", "ÑAÑA"),
    6577: ("ÑAÑA", "PORTILLO"),
    6578: ("PORTILLO", "SANTA CLARA"),
}


def construir_subestaciones(datos_lineas):
    """Respaldo cuando se carga desde Excel (sin KMZ): ubica cada subestación
    en la coordenada de la primera/última torre de alguna línea que la tenga
    como extremo. Sin polígono ni voltaje confirmado, a diferencia del KMZ."""
    subestaciones = {}
    for nombre_linea, grupo in datos_lineas.items():
        codigo = codigo_de_nombre_linea(nombre_linea)
        extremos = SUBESTACIONES_POR_LINEA.get(codigo)
        if not extremos or grupo.empty:
            continue
        nombre_origen, nombre_destino = extremos
        primera, ultima = grupo.iloc[0], grupo.iloc[-1]
        if nombre_origen not in subestaciones:
            subestaciones[nombre_origen] = {
                "lat": primera["Latitud"], "lon": primera["Longitud"],
                "voltaje_kv": None, "poligono": None,
            }
        if nombre_destino not in subestaciones:
            subestaciones[nombre_destino] = {
                "lat": ultima["Latitud"], "lon": ultima["Longitud"],
                "voltaje_kv": None, "poligono": None,
            }
    return subestaciones


# =========================================================
# 4. CARGAR DATOS — KMZ reales si están disponibles (carpeta kmz/),
#    con el Excel consolidado_total.xlsx como respaldo mientras se
#    termina de subir el set completo de archivos KMZ al repositorio.
# =========================================================
filas_descartadas = 0
info_lineas = {}  # nombre_linea -> {"voltaje_kv": int|None, "tipo": "Aérea"|"Subterránea"|None}

if Path("kmz").is_dir() and any(Path("kmz").glob("*.kmz")):
    df, subestaciones, info_lineas = cargar_lineas_y_subestaciones_kmz("kmz")
    fuente_datos = "kmz"
else:
    df = pd.read_excel("consolidado_total.xlsx")
    df.columns = df.columns.str.strip()
    df["Latitud"] = pd.to_numeric(df["Latitud"], errors="coerce")
    df["Longitud"] = pd.to_numeric(df["Longitud"], errors="coerce")
    df["Torre"] = df["Torre"].astype(str).str.strip()

    # Una sola torre con coordenada vacía o mal escrita rompe el trazado en PyDeck
    # (genera los "abanicos" triangulares gigantes), así que se descartan aquí,
    # en el origen, antes de construir líneas, distancias o capas del mapa.
    filas_antes = len(df)
    df = df.dropna(subset=["Latitud", "Longitud"]).reset_index(drop=True)
    filas_descartadas = filas_antes - len(df)
    fuente_datos = "excel"

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

# Si se cargó desde el Excel (sin KMZ), las subestaciones se siguen
# aproximando con el diccionario de origen/destino, como antes.
if fuente_datos == "excel":
    subestaciones = construir_subestaciones(datos_lineas)

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

    if filas_descartadas > 0:
        st.warning(
            f"⚠️ {filas_descartadas} torre(s) con coordenadas inválidas o vacías fueron "
            "excluidas de consolidado_total.xlsx (causaban errores de dibujo en el mapa)."
        )

    linea_seleccionada = st.selectbox("Seleccione la Línea:", list(datos_lineas.keys()))
    df_linea = datos_lineas[linea_seleccionada]

    _info_sel = info_lineas.get(linea_seleccionada, {})
    if _info_sel.get("voltaje_kv"):
        st.caption(f"⚡ {_info_sel['voltaje_kv']} kV · {_info_sel.get('tipo') or '—'}")

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
        mostrar_restricciones = st.checkbox("Mostrar restricciones en el mapa", value=False)
    else:
        mostrar_restricciones = False
        st.warning("No se encontró restricciones_conelsur.csv en el repositorio.")

    mostrar_subestaciones = st.checkbox("Mostrar subestaciones (patio real)", value=False)

    mostrar_incendios = st.checkbox("🔥 Mostrar incendios activos (Bomberos Perú)", value=False)
    df_incendios_cercanos = pd.DataFrame()
    df_incendios = pd.DataFrame()
    if mostrar_incendios:
        try:
            df_bomberos = cargar_emergencias_bomberos()
            df_incendios = df_bomberos[df_bomberos["tipo"].str.contains("INCENDIO", case=False, na=False)].copy()
            n_atencion = (df_incendios["estado"].str.upper() == "ATENDIENDO").sum()
            n_cerrado = (df_incendios["estado"].str.upper() == "CERRADO").sum()
            st.caption(
                f"🔴 {n_atencion} en atención · 🟠 {n_cerrado} cerrado(s) "
                "(incluye todo el Perú, actualizado cada ~90 s)."
            )

            con_coords = df_incendios[
                (df_incendios["estado"].str.upper() == "ATENDIENDO")
            ].dropna(subset=["lat", "lon"])
            cercanos = []
            for _, r in con_coords.iterrows():
                dist_m, torre = punto_mas_cercano_en_linea(df_linea, r["lat"], r["lon"])
                if dist_m < 500:
                    cercanos.append((r, dist_m, torre))
                    df_incendios_cercanos = pd.concat(
                        [df_incendios_cercanos, pd.DataFrame([r])], ignore_index=True
                    )
            if cercanos:
                st.error(f"⚠️ {len(cercanos)} incendio(s) EN ATENCIÓN a menos de 500 m de **{linea_seleccionada}**")

                muy_cercanos = [c for c in cercanos if c[1] < 100]
                if muy_cercanos:
                    st.error(
                        f"🚨 ¡ALERTA CRÍTICA! {len(muy_cercanos)} incendio(s) a **menos de 100 m** "
                        "de la línea — riesgo inmediato, requiere atención prioritaria."
                    )

                for r, dist_m, torre in cercanos:
                    if dist_m < 100:
                        st.write(
                            f"🚨 **{r['direccion']}** — a solo **{dist_m:.0f} m** "
                            f"de la torre {torre['Torre']} · {r['fecha_hora']}"
                        )
                    else:
                        st.write(
                            f"**{r['direccion']}**  \n"
                            f"A {dist_m:.0f} m de la torre {torre['Torre']} · {r['fecha_hora']}"
                        )
        except Exception as e:
            st.warning(f"No se pudo consultar la hoja de emergencias de Bomberos: {e}")

    # ---------------------------------------------------
    # Clima a lo largo de la línea: lluvia y riesgo de tormenta eléctrica.
    # El checkbox va aquí (justo debajo de incendios); el detalle puntual en
    # el punto de falla se muestra más abajo, una vez calculada esa posición.
    # ---------------------------------------------------
    mostrar_clima = st.checkbox("🌩️ Mostrar clima (lluvia / riesgo de rayo)", value=False)
    datos_calor_clima = []
    if mostrar_clima:
        try:
            paso = max(1, len(df_linea) // 12)  # ~12 puntos repartidos a lo largo de la línea
            puntos_muestra = df_linea.iloc[::paso]
            resultados_clima = cargar_clima_en_puntos(
                puntos_muestra["Latitud"].tolist(), puntos_muestra["Longitud"].tolist()
            )
            for (_, fila_torre), resultado in zip(puntos_muestra.iterrows(), resultados_clima):
                actual = resultado.get("current", {})
                codigo = actual.get("weather_code")
                lluvia = actual.get("precipitation") or 0
                peso = 1.0 if codigo in CODIGOS_TORMENTA else (0.35 if lluvia > 0 else 0.04)
                datos_calor_clima.append(
                    {"position": [fila_torre["Longitud"], fila_torre["Latitud"]], "weight": peso}
                )
        except Exception as e:
            st.warning(f"No se pudo consultar el clima a lo largo de la línea: {e}")

    # ---------------------------------------------------
    # Ubicación de la falla
    # ---------------------------------------------------
    lat_falla, lon_falla = punto_en_distancia(df_linea, distancia_falla_m)

    if len(df_linea) < 2:
        st.error(
            f"⚠️ '{linea_seleccionada}' solo tiene {len(df_linea)} punto(s) válido(s) — "
            "revisa ese KMZ, no se puede calcular una falla sobre un solo punto."
        )
        st.stop()

    df_antes = df_linea[df_linea["Distancia_m"] <= distancia_falla_m]
    df_despues = df_linea[df_linea["Distancia_m"] > distancia_falla_m]
    if df_despues.empty:
        t_anterior = df_antes.iloc[-2] if len(df_antes) >= 2 else df_linea.iloc[-2]
        t_posterior = df_antes.iloc[-1] if not df_antes.empty else df_linea.iloc[-1]
    else:
        t_anterior = df_antes.iloc[-1] if not df_antes.empty else df_linea.iloc[0]
        t_posterior = df_despues.iloc[0]

    if t_anterior["Torre"] == t_posterior["Torre"]:
        ubicacion_detalle = f"Falla exacta en torre: <b>{t_anterior['Torre']}</b>"
    else:
        ubicacion_detalle = f"Entre torres <b>{t_anterior['Torre']}</b> y <b>{t_posterior['Torre']}</b>"

    st.markdown(
        f'<div class="ubicacion-card">'
        f'<div class="titulo">📍 Ubicación estimada</div>'
        f'<div class="detalle">Coordenadas: {lat_falla:.5f}, {lon_falla:.5f}<br>{ubicacion_detalle}</div>'
        f'</div>',
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

    # ---------------------------------------------------
    # Clima en el punto de falla: detalle puntual (el checkbox ya se
    # declaró arriba, justo debajo de incendios)
    # ---------------------------------------------------
    if mostrar_clima:
        try:
            clima = cargar_clima(lat_falla, lon_falla)
            actual = clima["current"]
            codigo = actual["weather_code"]
            descripcion = DESCRIPCION_CLIMA.get(codigo, f"Código {codigo}")
            lluvia_actual = actual.get("precipitation", 0) or 0

            lluvia_24h = None
            if "hourly" in clima and clima["hourly"].get("precipitation"):
                lluvia_24h = sum(v for v in clima["hourly"]["precipitation"][:24] if v is not None)

            if codigo in CODIGOS_TORMENTA:
                st.error(f"⚡ Riesgo de descarga atmosférica en el punto de falla — {descripcion}")
            elif lluvia_actual > 0:
                st.warning(f"🌧️ Lluvia en el punto de falla ({lluvia_actual:.1f} mm/h) — {descripcion}")
            else:
                st.info(f"☀️ Sin lluvia en el punto de falla — {descripcion}")

            if lluvia_24h is not None:
                st.caption(f"Acumulado de lluvia en las últimas 24 h: {lluvia_24h:.1f} mm")
        except Exception as e:
            st.warning(f"No se pudo consultar el clima: {e}")

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

    COLOR_LINEA_SIN_VOLTAJE = "#AEB8D1"  # cuando no se pudo determinar el kV
    capas_pydeck = []

    def _info_voltaje_linea(nombre_linea):
        datos = info_lineas.get(nombre_linea, {})
        kv, tipo = datos.get("voltaje_kv"), datos.get("tipo")
        if kv and tipo:
            return f" — {kv} kV · {tipo}"
        if kv:
            return f" — {kv} kV"
        return ""

    def _color_por_voltaje(nombre_linea):
        kv = info_lineas.get(nombre_linea, {}).get("voltaje_kv")
        return COLORES_POR_VOLTAJE.get(kv, COLOR_LINEA_SIN_VOLTAJE)

    def _tramos_linea(coords_lonlat, nombre_linea):
        """Un solo trazo continuo para aéreas; varios tramos cortos alternados
        (efecto punteado) para subterráneas — PathLayer no soporta dash nativo."""
        es_subterranea = info_lineas.get(nombre_linea, {}).get("tipo") == "Subterránea"
        if not es_subterranea or len(coords_lonlat) < 2:
            return [coords_lonlat]
        return [coords_lonlat[i:i + 2] for i in range(0, len(coords_lonlat) - 1, 2)]

    # ---------------------------------------------------
    # Todas las demás líneas, coloreadas por nivel de tensión
    # ---------------------------------------------------
    datos_otras_lineas = [
        {
            "path": tramo,
            "nombre": f"Línea: {nombre_linea}",
            "info": _info_voltaje_linea(nombre_linea),
            "color": hex_a_rgb(_color_por_voltaje(nombre_linea), 190),
        }
        for nombre_linea, grupo_linea in datos_lineas.items()
        if nombre_linea != linea_seleccionada
        for tramo in _tramos_linea(grupo_linea[["Longitud", "Latitud"]].values.tolist(), nombre_linea)
    ]
    capas_pydeck.append(
        pdk.Layer(
            "PathLayer",
            data=datos_otras_lineas,
            get_path="path",
            get_color="color",
            get_width=2,
            width_units=pdk.types.String("pixels"),
            joint_rounded=True,
            cap_rounded=True,
            pickable=True,
        )
    )

    # ---------------------------------------------------
    # Línea seleccionada, resaltada en azul de marca (siempre distinguible
    # del resto, sin importar su voltaje) y más gruesa
    # ---------------------------------------------------
    dato_linea_sel = [
        {
            "path": tramo,
            "nombre": f"Línea: {linea_seleccionada}",
            "info": _info_voltaje_linea(linea_seleccionada),
        }
        for tramo in _tramos_linea(df_linea[["Longitud", "Latitud"]].values.tolist(), linea_seleccionada)
    ]
    capas_pydeck.append(
        pdk.Layer(
            "PathLayer",
            data=dato_linea_sel,
            get_path="path",
            get_color=hex_a_rgb(AZUL_CONELSUR),
            get_width=4,
            width_units=pdk.types.String("pixels"),
            joint_rounded=True,
            cap_rounded=True,
            pickable=True,
        )
    )

    # Torres de la línea seleccionada únicamente — las demás líneas se
    # quedan solo con el trazo, para no saturar el mapa con ~2,500 puntos.
    datos_torres_sel = [
        {
            "position": [fila["Longitud"], fila["Latitud"]],
            "nombre": f"Torre {fila['Torre']}",
            "info": f" — {linea_seleccionada} · Km {fila['Distancia_m'] / 1000:.2f}",
        }
        for _, fila in df_linea.iterrows()
    ]
    capas_pydeck.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=datos_torres_sel,
            get_position="position",
            get_fill_color=hex_a_rgb(AZUL_CONELSUR),
            get_line_color=[255, 255, 255, 255],
            line_width_min_pixels=1,
            stroked=True,
            get_radius=3.5,
            radius_units=pdk.types.String("pixels"),
            radius_min_pixels=2,
            radius_max_pixels=4.5,
            pickable=True,
        )
    )

    # ---------------------------------------------------
    # Restricciones (zonas pobladas, cruces, etc.)
    # ---------------------------------------------------
    if mostrar_restricciones and not df_rest_linea.empty:
        datos_rest_tramo, datos_rest_punto = [], []
        for _, r in df_rest_linea.iterrows():
            color_rgb = hex_a_rgb(COLORES_TIPO.get(r["Tipo"], "#808080"), 200)
            info = (
                f" — {r['Zona_Geografica']}"
                f" · {r['Texto_Original']}"
                f" · D. horizontal: {r['Distancia_Horizontal_m']:.0f} m · Fuente: {r['Fuente']}"
            )
            if r["Acumulado_Inicio_m"] == r["Acumulado_Fin_m"]:
                datos_rest_punto.append(
                    {
                        "position": [r["lon_ini"], r["lat_ini"]],
                        "color": color_rgb,
                        "nombre": r["Tipo"],
                        "info": info,
                    }
                )
            else:
                datos_rest_tramo.append(
                    {
                        "path": [[r["lon_ini"], r["lat_ini"]], [r["lon_fin"], r["lat_fin"]]],
                        "color": color_rgb,
                        "nombre": r["Tipo"],
                        "info": info,
                    }
                )
        if datos_rest_tramo:
            capas_pydeck.append(
                pdk.Layer(
                    "PathLayer",
                    data=datos_rest_tramo,
                    get_path="path",
                    get_color="color",
                    get_width=4,
                    width_units=pdk.types.String("pixels"),
                    joint_rounded=True,
                    cap_rounded=True,
                    pickable=True,
                )
            )
        if datos_rest_punto:
            capas_pydeck.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=datos_rest_punto,
                    get_position="position",
                    get_fill_color="color",
                    get_radius=120,
                    radius_min_pixels=5,
                    pickable=True,
                )
            )

    # ---------------------------------------------------
    # Subestaciones: su polígono real (patio) + nombre siempre visible.
    # Ya no se dibuja un cuadrado sintético — el KMZ trae el contorno real.
    # ---------------------------------------------------
    if mostrar_subestaciones and subestaciones:
        datos_etiquetas_se, datos_poligonos_se = [], []
        for nombre_se, info_se in subestaciones.items():
            lat_se, lon_se = info_se.get("lat"), info_se.get("lon")
            if pd.isna(lat_se) or pd.isna(lon_se):
                continue
            kv = info_se.get("voltaje_kv")
            nombre_mostrado = f"{nombre_se} · {kv} kV" if kv else nombre_se
            datos_etiquetas_se.append({"position": [lon_se, lat_se], "nombre": nombre_mostrado, "info": ""})

            poligono = info_se.get("poligono")
            if poligono:
                datos_poligonos_se.append(
                    {
                        "poligono": [[lon, lat] for lat, lon in poligono],
                        "nombre": nombre_mostrado,
                        "info": "",
                    }
                )

        if datos_poligonos_se:
            capas_pydeck.append(
                pdk.Layer(
                    "PolygonLayer",
                    data=datos_poligonos_se,
                    get_polygon="poligono",
                    get_fill_color=[17, 17, 17, 110],
                    get_line_color=[17, 17, 17, 255],
                    line_width_min_pixels=1.5,
                    stroked=True,
                    filled=True,
                    pickable=True,
                )
            )
        capas_pydeck.append(
            pdk.Layer(
                "TextLayer",
                data=datos_etiquetas_se,
                character_set=pdk.types.String(JUEGO_CARACTERES_TEXTO),
                get_position="position",
                get_text="nombre",
                get_size=900,
                size_units=pdk.types.String("meters"),
                size_min_pixels=0,
                size_max_pixels=13,
                get_color=[255, 255, 255, 255],
                outline_width=4,
                outline_color=[0, 0, 0, 220],
                font_settings={"sdf": True},
                get_pixel_offset=[10, 0],
                get_alignment_baseline="'center'",
                get_text_anchor="'start'",
                font_family=pdk.types.String("Inter, Arial, sans-serif"),
            )
        )

    # ---------------------------------------------------
    # Mapa de calor: riesgo de tormenta eléctrica / lluvia a lo largo de la
    # línea (muestreado en ~12 puntos vía Open-Meteo; ver panel de control).
    # ---------------------------------------------------
    if mostrar_clima and datos_calor_clima:
        capas_pydeck.append(
            pdk.Layer(
                "HeatmapLayer",
                data=datos_calor_clima,
                get_position="position",
                get_weight="weight",
                radius_pixels=70,
                intensity=1.5,
                threshold=0.03,
                color_range=[
                    [237, 231, 246, 0],
                    [203, 178, 227, 130],
                    [158, 119, 199, 170],
                    [122, 68, 172, 210],
                    [74, 20, 134, 255],
                ],
                pickable=False,
            )
        )

    # ---------------------------------------------------
    # Incendios activos (Bomberos Perú)
    # ---------------------------------------------------
    if mostrar_incendios and not df_incendios.empty:
        COLOR_INCENDIO_ATENCION = [214, 40, 40, 255]   # rojo
        COLOR_INCENDIO_CERRADO = [255, 152, 0, 255]    # naranja
        datos_incendios = [
            {
                "position": [r["lon"], r["lat"]],
                "nombre": f"🔥 {r['tipo']}",
                "info": f" — {r['estado']} · {r['direccion']} · {r['fecha_hora']} · Máquinas: {r['maquinas'] or '—'}",
                "color": COLOR_INCENDIO_ATENCION if r["estado"].upper() == "ATENDIENDO" else COLOR_INCENDIO_CERRADO,
            }
            for _, r in df_incendios.dropna(subset=["lat", "lon"]).iterrows()
        ]
        if datos_incendios:
            capas_pydeck.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=[d for d in datos_incendios if d["color"] == COLOR_INCENDIO_ATENCION],
                    get_position="position",
                    get_fill_color=[255, 87, 34, 70],
                    get_radius=350,
                    radius_min_pixels=14,
                    pickable=False,
                )
            )
            capas_pydeck.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=datos_incendios,
                    get_position="position",
                    get_fill_color="color",
                    get_line_color=[255, 255, 255, 255],
                    line_width_min_pixels=1.5,
                    stroked=True,
                    get_radius=120,
                    radius_min_pixels=6,
                    pickable=True,
                )
            )

    # ---------------------------------------------------
    # Marcador de la falla estimada
    # ---------------------------------------------------
    dato_falla = [
        {
            "position": [lon_falla, lat_falla],
            "nombre": f"Falla estimada — Km {distancia_falla_km:.2f}",
            "info": "",
        }
    ]
    capas_pydeck.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=dato_falla,
            get_position="position",
            get_fill_color=hex_a_rgb(VERDE_CONELSUR),
            get_line_color=[255, 255, 255, 255],
            line_width_min_pixels=2,
            stroked=True,
            get_radius=180,
            radius_min_pixels=8,
            pickable=True,
        )
    )
    capas_pydeck.append(
        pdk.Layer(
            "TextLayer",
            data=dato_falla,
            character_set=pdk.types.String(JUEGO_CARACTERES_TEXTO),
            get_position="position",
            get_text="nombre",
            get_size=13,
            get_color=hex_a_rgb(VERDE_CONELSUR_OSCURO),
            outline_width=3,
            outline_color=[255, 255, 255, 230],
            font_settings={"sdf": True},
            get_pixel_offset=[0, -18],
            font_family=pdk.types.String("Poppins, Arial, sans-serif"),
        )
    )

    # ---------------------------------------------------
    # Vista: se encuadra la línea SELECCIONADA (no todo el país), así que al
    # cambiar de línea en el desplegable el mapa se acerca automáticamente a
    # ella. De paso, esto también ayuda en modo Satélite: una sola línea cubre
    # mucho menos área que el país entero, por lo que pide muchas menos
    # teselas satelitales de golpe (evita los 429 de Mapbox).
    # ---------------------------------------------------
    puntos_vista_linea = df_linea[["Longitud", "Latitud"]].dropna().values.tolist()
    vista_inicial = pdk.data_utils.compute_view(puntos_vista_linea) if puntos_vista_linea else pdk.ViewState(
        latitude=lat_falla, longitude=lon_falla, zoom=12
    )
    vista_inicial.pitch = 0
    vista_inicial.max_zoom = 20  # el límite real de Mapbox satelital ronda ahí; 22 no aporta más detalle

    # Desde Streamlit 1.64, [mapbox] en config.toml ya no funciona — el token
    # se pasa directamente a PyDeck. Se lee de los "Secrets" de Streamlit
    # Cloud (Settings > Secrets, formato [mapbox] token = "pk...."), nunca
    # hardcodeado en el repo.
    try:
        token_mapbox = st.secrets["mapbox"]["token"]
    except Exception:
        token_mapbox = None
        st.warning(
            "⚠️ Falta configurar el token de Mapbox en Settings → Secrets de "
            "Streamlit Cloud — el mapa satelital no cargará sin eso."
        )

    mapa_deck = pdk.Deck(
        layers=capas_pydeck,
        initial_view_state=vista_inicial,
        map_provider="mapbox",
        map_style=ESTILOS_MAPBOX[vista_mapa],
        api_keys={"mapbox": token_mapbox} if token_mapbox else None,
        tooltip={
            "html": "<b>{nombre}</b>{info}",
            "style": {
                "backgroundColor": AZUL_CONELSUR,
                "color": "white",
                "fontFamily": "Inter, Arial, sans-serif",
                "fontSize": "12.5px",
            },
        },
    )

    # ---------------------------------------------------
    # Leyenda flotante fija en la esquina del mapa — dinámica: las líneas de
    # voltaje siempre se muestran (siempre están en el mapa), pero incendios
    # y clima solo aparecen si su checkbox respectivo está activo.
    # ---------------------------------------------------
    seccion_leyenda_incendios = ""
    if mostrar_incendios:
        seccion_leyenda_incendios = (
            '<span class="leyenda-item"><span class="leyenda-punto-swatch" style="background-color:#D62828;"></span>Incendio en Atención</span>'
            '<span class="leyenda-item"><span class="leyenda-punto-swatch" style="background-color:#FF9800;"></span>Incendio Cerrado</span>'
        )

    seccion_leyenda_clima = ""
    if mostrar_clima:
        seccion_leyenda_clima = (
            '<span class="leyenda-item"><span class="leyenda-punto-swatch" style="background-color:#4A1486;"></span>Riesgo de tormenta eléctrica</span>'
            '<span class="leyenda-item"><span class="leyenda-punto-swatch" style="background-color:#9E77C7;"></span>Lluvia</span>'
        )

    # Todo en una sola línea, sin sangría: Streamlit/Markdown interpreta 4+
    # espacios de sangría al inicio de línea como un bloque de código, lo que
    # hacía que parte del HTML se mostrara como texto literal en vez de
    # renderizarse.
    leyenda_html = (
        '<div class="leyenda-flotante">'
        '<div class="leyenda-titulo">Leyenda</div>'
        f'<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:{COLORES_POR_VOLTAJE[220]};"></span>Activo de Transmisión de 220KV</span>'
        f'<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:{COLORES_POR_VOLTAJE[138]};"></span>Activo de Transmisión de 138KV</span>'
        f'<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:{COLORES_POR_VOLTAJE[69]};"></span>Activo de Transmisión de 69KV</span>'
        f'<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:{COLORES_POR_VOLTAJE[60]};"></span>Activo de Transmisión de 60KV / 50KV</span>'
        '<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:#111111; border-top-style:solid;"></span>Línea Aérea</span>'
        '<span class="leyenda-item"><span class="leyenda-linea-swatch" style="border-color:#111111; border-top-style:dashed;"></span>Línea Subterránea</span>'
        f'{seccion_leyenda_incendios}'
        f'{seccion_leyenda_clima}'
        '</div>'
    )

    st.markdown('<div class="mapa-card">', unsafe_allow_html=True)
    st.pydeck_chart(mapa_deck, use_container_width=True, height=580)
    st.markdown(leyenda_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if mostrar_restricciones and not df_rest_linea.empty:
        tipos_presentes = sorted(df_rest_linea["Tipo"].unique())
        leyenda_items = "".join(
            f'<span class="leyenda-item"><span class="leyenda-swatch" '
            f'style="background-color:{COLORES_TIPO.get(t, "#808080")}"></span>{t}</span>'
            for t in tipos_presentes
        )
        st.markdown(
            f'<div class="leyenda-card">'
            f'<div class="leyenda-titulo">Leyenda de restricciones</div>'
            f'{leyenda_items}'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown(
    '<div class="conelsur-footer">CONELSUR — Centro de Control de Operaciones de Transmisión · '
    'Sistema de Localización de Fallas SEIN</div>',
    unsafe_allow_html=True,
)
