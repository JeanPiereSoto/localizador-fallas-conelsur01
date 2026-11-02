"""
Carga de líneas de transmisión y subestaciones directamente desde archivos
KMZ, reemplazando consolidado_total.xlsx y el diccionario SUBESTACIONES_POR_LINEA
que antes se mantenía a mano.

Convención de nombres de archivo (confirmada con el listado real de Conelsur):

  - SUBESTACIÓN:  "<kV>KV_SE <nombre>.kmz"   ej. "220KV_SE Cajamarca Norte.kmz"
                  Adentro: un Placemark de tipo <Polygon> (el patio de la
                  subestación). Se usa el polígono completo para dibujarla en
                  el mapa, y su centroide como posición de la etiqueta.

  - LÍNEA:        "<kV>KV_L-<código[-código2]>_<Origen> - <Destino>[_A|_S].kmz"
                  ej. "220KV_L-2007_SE Matucana - SE Callahuanca_A.kmz"
                      "138KV_L-1101_SE Paramonga Nueva - SE Paramonga Existente.kmz"
                  El sufijo _A/_S (Aérea/Subterránea) es OPCIONAL — muchos
                  archivos no lo traen. Adentro: Placemarks de tipo <Point> —
                  las torres (T01, T02, ...) y, normalmente, las subestaciones
                  de los extremos con nombre "SE <nombre>". Las líneas
                  subterráneas suelen NO tener puntos de torre individuales —
                  en ese caso se usan los vértices de la <LineString> del
                  trazado como respaldo.

  Nota: algunos archivos combinan dos circuitos con nombre de subestación
  "ZZZ" como placeholder (ej. "138KV_L-1040-1047_SE ZZZ_A.kmz") cuando ya
  existen los archivos individuales de cada circuito por separado — se
  cargan igual (no se excluyen), ya que no se pidió deduplicarlos.

Todos los .kmz (líneas y subestaciones) pueden convivir en una sola carpeta
del repositorio, p. ej. kmz/ — el nombre del archivo basta para clasificarlos.
"""

import math
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import streamlit as st

NS_KML = "{http://www.opengis.net/kml/2.2}"

# Color por nivel de tensión para la leyenda y el trazado del mapa.
COLORES_POR_VOLTAJE = {
    220: "#E53935",   # rojo
    138: "#2E7D32",   # verde
    69: "#F57C00",    # naranja
    60: "#1565C0",    # azul
    50: "#1565C0",    # azul (comparte estilo con 60 kV)
}

# "<kV>KV_L-<código(s)>_<resto>[_A|_S]" — el sufijo _A/_S es opcional.
# El segmento de código no admite "_" (para no comerse un "_SE" pegado por
# error de tipeo en el nombre), pero sí "-" entre códigos (ej. "2001-2002").
PATRON_ARCHIVO_LINEA = re.compile(
    r"^(\d+)\s*kv_l-([a-z0-9().]+(?:-[a-z0-9().]+)*)_(.+?)(?:_([as]))?$",
    re.IGNORECASE,
)
# "<kV>KV_SE_<nombre>" o "<kV>KV_SE <nombre>"
PATRON_ARCHIVO_SUBESTACION = re.compile(r"^(\d+)\s*kv[_ ]+se[_ ]*(.*)$", re.IGNORECASE)


def _leer_kml_de_kmz(ruta_kmz: Path) -> ET.Element:
    """Un KMZ es un .zip que contiene un doc.kml (u otro .kml) adentro. Algunos
    exportadores generan XML con un prefijo de espacio de nombres mal declarado
    ("unbound prefix"); si el parseo normal falla, se reintenta quitando todos
    los prefijos de espacio de nombres del texto crudo (xmlns:xxx y xxx:tag)."""
    with zipfile.ZipFile(ruta_kmz, "r") as z:
        nombres_kml = [n for n in z.namelist() if n.lower().endswith(".kml")]
        if not nombres_kml:
            raise ValueError(f"{ruta_kmz.name} no contiene ningún archivo .kml")
        nombre_elegido = next((n for n in nombres_kml if n.lower() == "doc.kml"), nombres_kml[0])
        contenido = z.read(nombre_elegido)

    try:
        return ET.fromstring(contenido)
    except ET.ParseError:
        texto = contenido.decode("utf-8", errors="replace")
        texto = re.sub(r'\s+xmlns:\w+="[^"]*"', "", texto)
        texto = re.sub(r"(</?)\w+:", r"\1", texto)
        texto = re.sub(r'(\s)\w+:(\w+=")', r"\1\2", texto)
        return ET.fromstring(texto.encode("utf-8"))


def _coords_texto_a_latlon(texto_coords: str):
    """'<coordinates>' en KML viene como "lon,lat,alt" — puede haber varias."""
    puntos = []
    for grupo in texto_coords.strip().split():
        partes = grupo.split(",")
        if len(partes) >= 2:
            lon, lat = float(partes[0]), float(partes[1])
            puntos.append((lat, lon))
    return puntos


def _es_archivo_subestacion(nombre_archivo: str) -> bool:
    """'220KV_SE_...' (sin '_L-' después del kV) -> subestación."""
    return bool(PATRON_ARCHIVO_SUBESTACION.match(nombre_archivo)) and "_l-" not in nombre_archivo.lower()


def _info_desde_nombre_linea(nombre_sin_ext: str):
    """Extrae (voltaje_kv, tipo) del nombre del archivo de una línea.
    tipo es 'Aérea', 'Subterránea' o None si el archivo no trae el sufijo."""
    m = PATRON_ARCHIVO_LINEA.match(nombre_sin_ext)
    if not m:
        return None, None
    voltaje_kv = int(m.group(1))
    sufijo = m.group(4)
    tipo = {"a": "Aérea", "s": "Subterránea"}.get(sufijo.lower()) if sufijo else None
    return voltaje_kv, tipo


def _nombre_mostrado_linea(nombre_sin_ext: str) -> str:
    """'138KV_L-1047_SE Talta - SE Ares_A' -> 'L-1047 SE Talta - SE Ares'
    (quita el prefijo de voltaje y el sufijo _A/_S; se muestra aparte).
    Si el nombre no sigue el patrón esperado, se deja tal cual."""
    m = PATRON_ARCHIVO_LINEA.match(nombre_sin_ext)
    if not m:
        return nombre_sin_ext
    codigo, resto = m.group(2), m.group(3)
    return f"L-{codigo} {resto.strip()}"


def _parsear_subestacion(ruta_kmz: Path):
    """Devuelve (nombre, lat_centroide, lon_centroide, voltaje_kv, poligono)
    a partir del polígono del patio y del nombre del archivo. 'poligono' es
    una lista [(lat, lon), ...] del contorno, o None si no se encontró."""
    nombre_sin_ext = ruta_kmz.stem
    m = PATRON_ARCHIVO_SUBESTACION.match(nombre_sin_ext)
    voltaje_kv = int(m.group(1)) if m else None
    nombre_se = re.sub(r"_+", " ", m.group(2)).strip() if m else nombre_sin_ext
    nombre_se = f"SE {nombre_se}" if not nombre_se.upper().startswith("SE") else nombre_se

    raiz = _leer_kml_de_kmz(ruta_kmz)

    anillo = raiz.find(f".//{NS_KML}Polygon/{NS_KML}outerBoundaryIs/{NS_KML}LinearRing/{NS_KML}coordinates")
    if anillo is not None and anillo.text:
        puntos = _coords_texto_a_latlon(anillo.text)
        if puntos:
            lat_c = sum(p[0] for p in puntos) / len(puntos)
            lon_c = sum(p[1] for p in puntos) / len(puntos)
            return nombre_se, lat_c, lon_c, voltaje_kv, puntos

    # Respaldo: si no hay polígono, probar con un Point directo (sin contorno)
    punto = raiz.find(f".//{NS_KML}Point/{NS_KML}coordinates")
    if punto is not None and punto.text:
        lat, lon = _coords_texto_a_latlon(punto.text)[0]
        return nombre_se, lat, lon, voltaje_kv, None

    return None


def _distancia_aprox_m(a, b):
    """Distancia en metros entre dos (lat, lon) — aproximación plana local,
    suficiente para tramos cortos (unir tramos, proyectar torres)."""
    lat_media = math.radians((a[0] + b[0]) / 2)
    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(lat_media)
    return math.hypot(dx, dy)


def _unir_tramos(segmentos, tolerancia_m=5.0):
    """Muchos KMZ dibujan el trazado como decenas de <LineString> de 2 puntos
    (torre a torre), en cualquier orden y sentido. Se unen por sus extremos
    coincidentes (con una tolerancia de pocos metros) para obtener trazados
    continuos. Devuelve una lista de cadenas [(lat, lon), ...]."""
    pendientes = [list(s) for s in segmentos if len(s) >= 2]
    cadenas = []
    while pendientes:
        cadena = pendientes.pop(0)
        hubo_union = True
        while hubo_union:
            hubo_union = False
            for i, seg in enumerate(pendientes):
                if _distancia_aprox_m(cadena[-1], seg[0]) <= tolerancia_m:
                    cadena = cadena + seg[1:]
                elif _distancia_aprox_m(cadena[-1], seg[-1]) <= tolerancia_m:
                    cadena = cadena + seg[::-1][1:]
                elif _distancia_aprox_m(cadena[0], seg[-1]) <= tolerancia_m:
                    cadena = seg[:-1] + cadena
                elif _distancia_aprox_m(cadena[0], seg[0]) <= tolerancia_m:
                    cadena = seg[::-1][:-1] + cadena
                else:
                    continue
                pendientes.pop(i)
                hubo_union = True
                break
        cadenas.append(cadena)
    return cadenas


def _longitud_m(cadena):
    return sum(_distancia_aprox_m(cadena[i], cadena[i + 1]) for i in range(len(cadena) - 1))


def _ruta_principal(cadenas):
    """Encadena todos los trazados en una sola ruta ordenada (para medir la
    progresiva de cada torre): parte del más largo y le va pegando, por el
    extremo más cercano, el trazado restante más próximo."""
    if not cadenas:
        return []
    restantes = sorted(cadenas, key=_longitud_m, reverse=True)
    ruta = list(restantes.pop(0))
    while restantes:
        mejor = None
        for i, c in enumerate(restantes):
            opciones = (
                (_distancia_aprox_m(ruta[-1], c[0]), i, "fin", c),
                (_distancia_aprox_m(ruta[-1], c[-1]), i, "fin", c[::-1]),
                (_distancia_aprox_m(ruta[0], c[-1]), i, "inicio", c),
                (_distancia_aprox_m(ruta[0], c[0]), i, "inicio", c[::-1]),
            )
            for op in opciones:
                if mejor is None or op[0] < mejor[0]:
                    mejor = op
        _, i, extremo, c = mejor
        restantes.pop(i)
        ruta = ruta + list(c) if extremo == "fin" else list(c) + ruta
    return ruta


def _progresiva_en_ruta(ruta, punto):
    """Distancia (m) a lo largo de la ruta hasta la proyección del punto sobre
    el tramo más cercano. Así el orden de las torres sale del recorrido real
    dibujado en el KMZ, no del número escrito en su nombre."""
    mejor_dist, mejor_prog = None, 0.0
    acumulado = 0.0
    k_lon = 111_320 * math.cos(math.radians(punto[0]))
    px, py = punto[1] * k_lon, punto[0] * 111_320
    for i in range(len(ruta) - 1):
        ax, ay = ruta[i][1] * k_lon, ruta[i][0] * 111_320
        bx, by = ruta[i + 1][1] * k_lon, ruta[i + 1][0] * 111_320
        dx, dy = bx - ax, by - ay
        largo2 = dx * dx + dy * dy
        t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
        d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        largo = math.sqrt(largo2)
        if mejor_dist is None or d < mejor_dist:
            mejor_dist, mejor_prog = d, acumulado + t * largo
        acumulado += largo
    return mejor_prog


def _numero_de_torre(nombre):
    m = re.search(r"\d+", nombre)
    return int(m.group()) if m else None


def _parsear_linea(ruta_kmz: Path):
    """Devuelve (nombre_linea, torres, subestaciones_inline, voltaje_kv, tipo, trazados).
    torres: [(nombre, lat, lon), ...]  (excluye las que empiezan con 'SE ')
            ordenadas según su posición a lo largo del trazado real.
    subestaciones_inline: [(nombre, lat, lon), ...]
    trazados: [[(lat, lon), ...], ...] — el recorrido real de la línea tal
              como viene en las <LineString> del KMZ (lo que se dibuja)."""
    nombre_linea = _nombre_mostrado_linea(ruta_kmz.stem)
    voltaje_kv, tipo = _info_desde_nombre_linea(ruta_kmz.stem)
    raiz = _leer_kml_de_kmz(ruta_kmz)

    torres, subestaciones_inline, segmentos = [], [], []
    contador_sin_nombre = 0

    for placemark in raiz.iter(f"{NS_KML}Placemark"):
        nombre_el = placemark.find(f"{NS_KML}name")
        nombre = nombre_el.text.strip() if nombre_el is not None and nombre_el.text else None

        # Todas las <LineString> del Placemark (también dentro de <MultiGeometry>)
        for coords_el in placemark.findall(f".//{NS_KML}LineString/{NS_KML}coordinates"):
            if coords_el.text:
                puntos = _coords_texto_a_latlon(coords_el.text)
                if len(puntos) >= 2:
                    segmentos.append(puntos)

        punto = placemark.find(f".//{NS_KML}Point/{NS_KML}coordinates")
        if punto is not None and punto.text:
            puntos = _coords_texto_a_latlon(punto.text)
            if not puntos:
                continue
            lat, lon = puntos[0]
            if not nombre:
                contador_sin_nombre += 1
                nombre = f"T{contador_sin_nombre:02d}"
            if nombre.upper().startswith("SE "):
                subestaciones_inline.append((nombre, lat, lon))
            else:
                torres.append((nombre, lat, lon))

    trazados = _unir_tramos(segmentos)
    ruta = _ruta_principal(trazados)

    if not torres and ruta:
        # Cables subterráneos y tramos cortos: no suele haber Point por
        # torre, solo el trazado. Se usan sus vértices (ya en orden).
        torres = [(f"T{i + 1:02d}", lat, lon) for i, (lat, lon) in enumerate(ruta)]
    elif len(torres) < 2 and len(ruta) >= 2:
        # Una sola torre marcada pero con trazado: se usan los vértices del
        # trazado, conservando el nombre de la torre en el vértice que le
        # corresponde (si está a menos de 15 m).
        nuevas = []
        for i, (lat, lon) in enumerate(ruta):
            nombre = f"V{i + 1:02d}"
            for nombre_t, lat_t, lon_t in torres:
                if _distancia_aprox_m((lat, lon), (lat_t, lon_t)) <= 15:
                    nombre = nombre_t
            nuevas.append((nombre, lat, lon))
        torres = nuevas
    elif len(torres) >= 2 and len(ruta) >= 2:
        # El orden de los Placemark en el KMZ no es el del recorrido, y el
        # número del nombre tampoco sirve (TA-12, PMB-76, TCC7N1, numeración
        # descendente, prefijos mezclados...). Se ordena por la posición de
        # cada torre a lo largo del trazado real.
        torres.sort(key=lambda t: _progresiva_en_ruta(ruta, (t[1], t[2])))
        # Sentido: se mantiene la convención de empezar por la torre de menor
        # número si la numeración va mayoritariamente al revés.
        numeros = [_numero_de_torre(t[0]) for t in torres]
        pares = [(a, b) for a, b in zip(numeros, numeros[1:]) if a is not None and b is not None]
        if sum(b < a for a, b in pares) > sum(b > a for a, b in pares):
            torres.reverse()
    else:
        # Sin trazado para guiarse: último recurso, el número de la torre.
        torres.sort(key=lambda t: (
            _numero_de_torre(t[0]) if _numero_de_torre(t[0]) is not None else 10**9, t[0]
        ))

    return nombre_linea, torres, subestaciones_inline, voltaje_kv, tipo, trazados


@st.cache_data(ttl=3600, show_spinner="Leyendo archivos KMZ (líneas y subestaciones)...")
def cargar_lineas_y_subestaciones_kmz(carpeta: str = "kmz"):
    """Reemplazo de pd.read_excel('consolidado_total.xlsx') + SUBESTACIONES_POR_LINEA.

    Devuelve:
      df_torres: DataFrame con columnas Linea, Torre, Latitud, Longitud
      subestaciones: dict {nombre: {"lat", "lon", "voltaje_kv", "poligono"}}
                      poligono es [(lat, lon), ...] del contorno real, o None
      info_lineas: dict {nombre_linea: {"voltaje_kv": int|None, "tipo": str|None}}
      trazados_lineas: dict {nombre_linea: [[(lat, lon), ...], ...]} — el
                       recorrido real de cada línea según sus <LineString>
    """
    carpeta_path = Path(carpeta)
    archivos_kmz = sorted(carpeta_path.glob("*.kmz"))
    if not archivos_kmz:
        raise FileNotFoundError(
            f"No se encontraron archivos .kmz en '{carpeta}/'. "
            "Sube ahí los KMZ de líneas y subestaciones."
        )

    registros_torres = []
    subestaciones = {}
    info_lineas = {}
    trazados_lineas = {}
    archivos_con_error = []

    # 1) Primero las subestaciones "oficiales" (con polígono y voltaje confirmado)
    for ruta in archivos_kmz:
        if not _es_archivo_subestacion(ruta.name):
            continue
        try:
            resultado = _parsear_subestacion(ruta)
            if resultado:
                nombre_se, lat, lon, voltaje_kv, poligono = resultado
                subestaciones[nombre_se] = {
                    "lat": lat, "lon": lon, "voltaje_kv": voltaje_kv, "poligono": poligono,
                }
            else:
                archivos_con_error.append(f"{ruta.name} (sin polígono ni punto reconocible)")
        except Exception as e:
            archivos_con_error.append(f"{ruta.name} ({e})")

    # 2) Luego las líneas: torres + subestaciones de extremo (solo si no vinieron
    #    ya de un archivo dedicado, para no perder el voltaje/polígono confirmado)
    for ruta in archivos_kmz:
        if _es_archivo_subestacion(ruta.name):
            continue
        if "zzz" in ruta.name.lower():
            # Archivo combinado de varios circuitos con nombre de subestación
            # "ZZZ" como placeholder — redundante con los archivos individuales
            # de cada circuito (que sí tienen nombre y trazado real), y en la
            # práctica suele venir con muy pocos puntos (solo los extremos),
            # lo que dibuja una línea recta artificial en vez del trazado real.
            continue
        try:
            nombre_linea, torres, subestaciones_inline, voltaje_kv, tipo, trazados = _parsear_linea(ruta)
            # La versión aérea (_A) y la subterránea (_S) de un mismo circuito
            # dan el mismo nombre; sin distinguirlas, sus puntos se mezclaban
            # en un solo grupo y se dibujaban saltos rectos entre ambas.
            if tipo == "Subterránea":
                nombre_linea = f"{nombre_linea} (Subterránea)"
            if not torres:
                archivos_con_error.append(f"{ruta.name} (sin torres ni trazado reconocible)")
                continue
            for nombre_torre, lat, lon in torres:
                registros_torres.append(
                    {"Linea": nombre_linea, "Torre": nombre_torre, "Latitud": lat, "Longitud": lon}
                )
            for nombre_se, lat, lon in subestaciones_inline:
                if nombre_se not in subestaciones:
                    subestaciones[nombre_se] = {
                        "lat": lat, "lon": lon, "voltaje_kv": None, "poligono": None,
                    }
            info_lineas[nombre_linea] = {"voltaje_kv": voltaje_kv, "tipo": tipo}
            trazados_lineas[nombre_linea] = trazados
        except Exception as e:
            archivos_con_error.append(f"{ruta.name} ({e})")

    if archivos_con_error:
        st.warning("No se pudieron leer estos archivos KMZ:\n\n- " + "\n- ".join(archivos_con_error))

    df_torres = pd.DataFrame(registros_torres)
    df_torres["Latitud"] = pd.to_numeric(df_torres["Latitud"], errors="coerce")
    df_torres["Longitud"] = pd.to_numeric(df_torres["Longitud"], errors="coerce")
    df_torres["Torre"] = df_torres["Torre"].astype(str).str.strip()
    df_torres = df_torres.dropna(subset=["Latitud", "Longitud"]).reset_index(drop=True)

    return df_torres, subestaciones, info_lineas, trazados_lineas
