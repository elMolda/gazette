from __future__ import annotations

import argparse
import html
import math
import os
import random
import smtplib
import sys
import unicodedata
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ebooklib import epub
from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATES_DIR = BASE_DIR / "templates"
DEFAULT_CSS_PATH = BASE_DIR / "styles" / "edicion_kindle.css"
NOMBRE_PLANTILLA = "capitulo_epub.xhtml.j2"

# Fuentes sin paywall agrupadas por idioma y catalogadas por tema y ritmo
FUENTES: Dict[str, List[Dict[str, object]]] = {
    "en": [
        # Internacional / actualidad diaria
        {"nombre": "BBC World", "rss": "https://feeds.bbci.co.uk/news/world/rss.xml", "tema": "internacional", "ritmo": "diario"},
        {"nombre": "The Guardian World", "rss": "https://www.theguardian.com/world/rss", "tema": "internacional", "ritmo": "diario"},
        {"nombre": "Al Jazeera English", "rss": "https://www.aljazeera.com/xml/rss/all.xml", "tema": "internacional", "ritmo": "diario"},

        # Ciencia
        {"nombre": "NASA Breaking News", "rss": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "tema": "ciencia", "ritmo": "diario"},
        {"nombre": "Nautilus", "rss": "https://nautil.us/feed/", "tema": "ciencia", "ritmo": "ensayo"},

        # Tecnología
        {"nombre": "Lobsters", "rss": "https://lobste.rs/rss", "tema": "tecnologia", "ritmo": "diario"},
        {"nombre": "Slashdot", "rss": "https://rss.slashdot.org/Slashdot/slashdotMain", "tema": "tecnologia", "ritmo": "diario"},
        {"nombre": "Netflix TechBlog", "rss": "https://netflixtechblog.com/feed", "tema": "tecnologia", "ritmo": "ensayo"},
        {"nombre": "Kottke", "rss": "https://feeds.kottke.org/main", "tema": "tecnologia", "ritmo": "diario"},

        # Cultura, filosofía y ensayo largo
        {"nombre": "Aeon", "rss": "https://aeon.co/feed.rss", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Psyche", "rss": "https://psyche.co/feed.rss", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "The Public Domain Review", "rss": "https://publicdomainreview.org/rss.xml", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Longreads", "rss": "https://longreads.com/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Works in Progress", "rss": "https://worksinprogress.co/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Astral Codex Ten", "rss": "https://www.astralcodexten.com/feed", "tema": "cultura_filosofia", "ritmo": "ensayo"},
    ],
    "es": [
        # Internacional / actualidad diaria
        {"nombre": "BBC Mundo", "rss": "https://feeds.bbci.co.uk/mundo/rss.xml", "tema": "internacional", "ritmo": "diario"},
        {"nombre": "DW Español", "rss": "https://rss.dw.com/rdf/rss-es-all", "tema": "internacional", "ritmo": "diario"},

        # Política y economía
        {"nombre": "Politikon", "rss": "https://politikon.es/feed/", "tema": "politica_economia", "ritmo": "ensayo"},
        {"nombre": "Nueva Sociedad", "rss": "https://nuso.org/rss/", "tema": "politica_economia", "ritmo": "ensayo"},
        {"nombre": "Razón Pública", "rss": "https://razonpublica.com/feed/", "tema": "politica_economia", "ritmo": "ensayo"},
        {"nombre": "ElDiario.es", "rss": "https://www.eldiario.es/rss/", "tema": "politica_economia", "ritmo": "diario"},
        {"nombre": "CTXT", "rss": "https://ctxt.es/es/?tpl=20", "tema": "politica_economia", "ritmo": "ensayo"},
        {"nombre": "La Silla Vacía", "rss": "https://www.lasillavacia.com/rss/", "tema": "politica_economia", "ritmo": "diario"},

        # Ciencia
        {"nombre": "Cuaderno de Cultura Científica", "rss": "https://culturacientifica.com/feed/", "tema": "ciencia", "ritmo": "ensayo"},
        {"nombre": "The Conversation", "rss": "https://theconversation.com/es/articles.atom", "tema": "ciencia", "ritmo": "diario"},

        # Cultura, filosofía y ensayo largo
        {"nombre": "Jot Down", "rss": "https://www.jotdown.es/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Letras Libres", "rss": "https://letraslibres.com/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Ethic", "rss": "https://ethic.es/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Gatopardo", "rss": "https://gatopardo.com/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
        {"nombre": "Revista Anfibia", "rss": "https://www.revistaanfibia.com/feed/", "tema": "cultura_filosofia", "ritmo": "ensayo"},
    ],
}

TEXTOS_POR_IDIOMA: Dict[str, Dict[str, str]] = {
    "en": {
        "indice": "Index",
        "fuente": "Original source",
        "min_unidad": "min",
        "min_total": "min total",
        "palabras": "words",
    },
    "es": {
        "indice": "Índice",
        "fuente": "Fuente original",
        "min_unidad": "min",
        "min_total": "min total",
        "palabras": "palabras",
    },
}

VELOCIDAD_LECTURA_PPM = 220

# Periódico (noticias de actualidad diaria)
MIN_MINUTOS_PERIODICO = 1
MAX_MINUTOS_PERIODICO = 12
OBJETIVO_ARTICULOS_PERIODICO = 5

# Revista (ensayos y lecturas de fondo)
MIN_MINUTOS_REVISTA = 4
MAX_MINUTOS_REVISTA = 25
OBJETIVO_ARTICULOS_REVISTA = 3

# Valores retrocompatibles por defecto
MIN_MINUTOS_LECTURA = MIN_MINUTOS_REVISTA
MAX_MINUTOS_LECTURA = MAX_MINUTOS_REVISTA
OBJETIVO_ARTICULOS = OBJETIVO_ARTICULOS_REVISTA


def calcular_minutos_lectura(texto_plano: str) -> int:
    palabras = len(texto_plano.split())
    return max(1, math.ceil(palabras / VELOCIDAD_LECTURA_PPM))


def limpiar_html_para_kindle(html_crudo: str) -> str:
    """
    Mantiene estructura semántica básica sin imágenes, iframes, scripts ni estilos inline[cite: 2].
    """
    soup = BeautifulSoup(html_crudo, "html.parser")

    for tag in soup(["img", "figure", "picture", "svg", "iframe", "script", "style", "aside"]):
        tag.decompose()

    for tag in soup.find_all(True):
        tag.attrs = {}

    return str(soup)


def normalizar_texto(texto: str) -> str:
    texto_norm = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto_norm if not unicodedata.combining(c)).lower().strip()


def coincide_fuente(nombre_fuente: str, filtro: str) -> bool:
    return normalizar_texto(filtro) in normalizar_texto(nombre_fuente)


def identificar_fuente_e_idioma(url: str, idioma_por_defecto: str = "es") -> tuple[str, str]:
    """
    Identifica el nombre de la fuente y su idioma a partir del dominio de la URL.
    Si pertenece a los feeds conocidos en FUENTES, toma su nombre y lengua oficial.
    """
    netloc = urlparse(url).netloc.lower()
    netloc_clean = netloc.replace("www.", "")

    for lang, lista_fuentes in FUENTES.items():
        for f in lista_fuentes:
            f_netloc = urlparse(f["rss"]).netloc.lower().replace("www.", "")
            if f_netloc in netloc_clean or netloc_clean in f_netloc:
                return f["nombre"], lang

    dominio = netloc_clean.split(".")[0].capitalize()
    return dominio, idioma_por_defecto


def extraer_titulo_de_html(html_crudo: str, url: str) -> str:
    """Extrae el mejor título posible de un documento HTML."""
    try:
        meta = trafilatura.extract_metadata(html_crudo)
        if meta and meta.title:
            return html.unescape(meta.title).strip()
    except Exception:
        pass

    soup = BeautifulSoup(html_crudo, "html.parser")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return html.unescape(og_title["content"]).strip()

    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    if twitter_title and twitter_title.get("content"):
        return html.unescape(twitter_title["content"]).strip()

    if soup.title and soup.title.string:
        return html.unescape(soup.title.string).strip()

    h1 = soup.find("h1")
    if h1:
        return html.unescape(h1.get_text(" ", strip=True)).strip()

    path_slug = Path(urlparse(url).path).name
    return path_slug.replace("-", " ").capitalize() or "Sin título"


def extraer_articulo_desde_url(url: str, idioma_por_defecto: str = "es") -> Optional[Dict]:
    """
    Descarga y extrae el contenido de un artículo a partir de su URL directa,
    omitiendo restricciones de longitud y tiempo de lectura.
    """
    fuente_nombre, lang_detectado = identificar_fuente_e_idioma(url, idioma_por_defecto)
    print(f"Descargando artículo: {url} ({fuente_nombre})...")
    descargado = trafilatura.fetch_url(url)
    if not descargado:
        print(f"  [!] No se pudo descargar la URL: {url}")
        return None

    titulo = extraer_titulo_de_html(descargado, url)

    cuerpo_html = trafilatura.extract(
        descargado,
        output_format="html",
        include_images=False,
        include_tables=False,
        include_links=False,
        favor_precision=True,
    )

    if not cuerpo_html:
        cuerpo_html = trafilatura.extract(
            descargado,
            output_format="html",
            include_images=False,
            include_tables=False,
            include_links=False,
            favor_recall=True,
        )

    if not cuerpo_html:
        print(f"  [!] No se pudo extraer el contenido del artículo: {url}")
        return None

    cuerpo_limpio = limpiar_html_para_kindle(cuerpo_html)
    texto_plano = BeautifulSoup(cuerpo_limpio, "html.parser").get_text(" ", strip=True)
    palabras = len(texto_plano.split())
    minutos = calcular_minutos_lectura(texto_plano)

    # Se omiten las restricciones de longitud y tiempo de lectura según lo solicitado
    print(f"  [OK] '{titulo}' ({minutos} min, {palabras} palabras) - {fuente_nombre}")
    return {
        "idioma": lang_detectado,
        "fuente": fuente_nombre,
        "titulo": titulo,
        "url": url,
        "minutos": minutos,
        "palabras": palabras,
        "cuerpo_html": cuerpo_limpio,
    }


def extraer_articulos_desde_archivo(
    ruta_archivo: Path, idioma_por_defecto: str = "es"
) -> List[Dict]:
    """
    Lee URLs de un archivo de texto plano (una por línea) y extrae sus artículos.
    """
    if not ruta_archivo.exists():
        raise FileNotFoundError(f"No existe el archivo de URLs: {ruta_archivo}")

    lineas = ruta_archivo.read_text(encoding="utf-8").splitlines()
    urls = [linea.strip() for linea in lineas if linea.strip() and not linea.strip().startswith("#")]

    if not urls:
        raise RuntimeError(f"El archivo '{ruta_archivo}' no contiene ninguna URL válida.")

    print(f"Procesando {len(urls)} URLs desde '{ruta_archivo}'...")
    articulos: List[Dict] = []
    for u in urls:
        art = extraer_articulo_desde_url(u, idioma_por_defecto=idioma_por_defecto)
        if art:
            articulos.append(art)

    return articulos


def extraer_articulos_fuente(
    fuente: Dict[str, object],
    idioma: str,
    max_articulos: int = 1,
    orden: str = "random",
    urls_excluidas: Optional[set[str]] = None,
    min_minutos: int = MIN_MINUTOS_LECTURA,
    max_minutos: int = MAX_MINUTOS_LECTURA,
) -> List[Dict]:
    """
    Consulta el RSS de una fuente y devuelve hasta max_articulos válidos
    cuyo texto íntegro tenga entre min_minutos y max_minutos de lectura.
    Si orden == 'random', baraja las entradas recientes.
    Si orden == 'reciente', respeta el orden de llegada del feed (lo último publicado primero).
    """
    print(f"Consultando {fuente['nombre']}...")
    feed = feedparser.parse(fuente["rss"])
    if not feed.entries:
        print(f"  [!] Sin entradas en {fuente['nombre']}")
        return []

    candidatos = list(feed.entries[:20])
    if orden == "random":
        random.shuffle(candidatos)

    excluidas = urls_excluidas if urls_excluidas is not None else set()
    articulos_encontrados: List[Dict] = []

    for entrada in candidatos:
        if len(articulos_encontrados) >= max_articulos:
            break

        url = entrada.get("link")
        titulo = html.unescape(entrada.get("title", "Sin título")).strip()
        if not url or url in excluidas:
            continue

        descargado = trafilatura.fetch_url(url)
        if not descargado:
            continue

        cuerpo_html = trafilatura.extract(
            descargado,
            output_format="html",
            include_images=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
        )

        if not cuerpo_html:
            continue

        cuerpo_limpio = limpiar_html_para_kindle(cuerpo_html)
        texto_plano = BeautifulSoup(cuerpo_limpio, "html.parser").get_text(" ", strip=True)
        palabras = len(texto_plano.split())
        minutos = calcular_minutos_lectura(texto_plano)

        if min_minutos <= minutos <= max_minutos:
            print(f"  [OK] '{titulo}' ({minutos} min, {palabras} palabras)")
            articulos_encontrados.append(
                {
                    "idioma": idioma,
                    "fuente": fuente["nombre"],
                    "titulo": titulo,
                    "url": url,
                    "minutos": minutos,
                    "palabras": palabras,
                    "cuerpo_html": cuerpo_limpio,
                }
            )
            excluidas.add(url)

    if not articulos_encontrados:
        print(
            f"  [-] Ningún candidato cumplió el rango de "
            f"{min_minutos}-{max_minutos} min en {fuente['nombre']}"
        )
    return articulos_encontrados


def extraer_articulo_valido(
    fuente: Dict[str, object],
    idioma: str,
    orden: str = "random",
    min_minutos: int = MIN_MINUTOS_LECTURA,
    max_minutos: int = MAX_MINUTOS_LECTURA,
) -> Optional[Dict]:
    """
    Función de compatibilidad: extrae el primer artículo válido de una fuente.
    """
    arts = extraer_articulos_fuente(
        fuente,
        idioma,
        max_articulos=1,
        orden=orden,
        min_minutos=min_minutos,
        max_minutos=max_minutos,
    )
    return arts[0] if arts else None


def seleccionar_articulos(
    idioma_arg: str,
    objetivo: int = OBJETIVO_ARTICULOS,
    filtro_fuente: Optional[str] = None,
    filtro_ritmo: Optional[str] = None,
    filtro_tema: Optional[str] = None,
    orden: str = "random",
    min_minutos: int = MIN_MINUTOS_REVISTA,
    max_minutos: int = MAX_MINUTOS_REVISTA,
) -> List[Dict]:
    """
    Selecciona hasta `objetivo` artículos desde las fuentes del idioma elegido ('en', 'es' o 'mix').
    Permite filtrar por nombre de fuente, ritmo ('diario'/'ensayo') y tema, y definir el orden.
    """
    if idioma_arg == "mix":
        pool: List[tuple[str, Dict[str, object]]] = [
            ("en", f) for f in FUENTES["en"]
        ] + [
            ("es", f) for f in FUENTES["es"]
        ]
    elif idioma_arg in FUENTES:
        pool = [(idioma_arg, f) for f in FUENTES[idioma_arg]]
    else:
        raise ValueError(f"Idioma no soportado: {idioma_arg}")

    if filtro_ritmo:
        pool = [(lang, f) for lang, f in pool if f.get("ritmo") == filtro_ritmo]

    if filtro_tema:
        pool = [(lang, f) for lang, f in pool if f.get("tema") == filtro_tema]

    if filtro_fuente:
        pool = [
            (lang, f) for lang, f in pool if coincide_fuente(str(f["nombre"]), filtro_fuente)
        ]

    if not pool:
        detalles = []
        if filtro_fuente:
            detalles.append(f"fuente '{filtro_fuente}'")
        if filtro_ritmo:
            detalles.append(f"ritmo '{filtro_ritmo}'")
        if filtro_tema:
            detalles.append(f"tema '{filtro_tema}'")
        filtros_str = ", ".join(detalles) if detalles else "los filtros solicitados"
        raise RuntimeError(
            f"No se encontró ninguna fuente que coincida con {filtros_str} en el idioma '{idioma_arg}'."
        )

    fuentes_candidatas = list(pool)
    if orden == "random":
        random.shuffle(fuentes_candidatas)

    seleccionados: List[Dict] = []
    urls_vistas: set[str] = set()

    # Si sólo hay una fuente coincidente, extraemos directamente los requeridos de ella
    if len(fuentes_candidatas) == 1:
        lang, fuente = fuentes_candidatas[0]
        return extraer_articulos_fuente(
            fuente,
            lang,
            max_articulos=objetivo,
            orden=orden,
            urls_excluidas=urls_vistas,
            min_minutos=min_minutos,
            max_minutos=max_minutos,
        )

    # Si hay varias fuentes, distribuimos: primero un artículo por fuente
    for lang, fuente in fuentes_candidatas:
        if len(seleccionados) >= objetivo:
            break
        arts = extraer_articulos_fuente(
            fuente,
            lang,
            max_articulos=1,
            orden=orden,
            urls_excluidas=urls_vistas,
            min_minutos=min_minutos,
            max_minutos=max_minutos,
        )
        if arts:
            seleccionados.extend(arts)

    # Si no se completó el cupo de artículos, extraemos adicionales de las fuentes disponibles
    if len(seleccionados) < objetivo:
        for lang, fuente in fuentes_candidatas:
            faltantes = objetivo - len(seleccionados)
            if faltantes <= 0:
                break
            arts = extraer_articulos_fuente(
                fuente,
                lang,
                max_articulos=faltantes,
                orden=orden,
                urls_excluidas=urls_vistas,
                min_minutos=min_minutos,
                max_minutos=max_minutos,
            )
            if arts:
                seleccionados.extend(arts)

    return seleccionados


def generar_epub(
    articulos: List[Dict],
    idioma_edicion: str,
    directorio_plantillas: Path,
    ruta_css: Path,
    archivo_salida: Path,
    nombre_plantilla: str = NOMBRE_PLANTILLA,
    tipo_edicion: str = "revista",
) -> Path:
    if not directorio_plantillas.exists():
        raise FileNotFoundError(f"No existe el directorio de plantillas: {directorio_plantillas}")
    if not ruta_css.exists():
        raise FileNotFoundError(f"No existe el archivo CSS: {ruta_css}")

    env = Environment(
        loader=FileSystemLoader(str(directorio_plantillas)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    plantilla = env.get_template(nombre_plantilla)

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    idioma_meta = "en" if idioma_edicion == "en" else "es"
    if tipo_edicion == "periodico":
        titulo_edicion = f"The elmolda gazette · {fecha_hoy}"
    else:
        titulo_edicion = f"The elmolda gazette magazine · {fecha_hoy}"
    minutos_totales = sum(a["minutos"] for a in articulos)

    book = epub.EpubBook()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    book.set_identifier(f"urn:uuid:edicion-kindle-{stamp}")
    book.set_title(titulo_edicion)
    book.set_language(idioma_meta)
    book.add_author("The elmolda gazette")

    css_item = epub.EpubItem(
        uid="style_edicion_kindle",
        file_name="Styles/edicion_kindle.css",
        media_type="text/css",
        content=ruta_css.read_bytes(),
    )
    book.add_item(css_item)

    capitulos: List[epub.EpubHtml] = []

    for idx, art in enumerate(articulos, start=1):
        lang_cap = art.get("idioma", idioma_meta)
        textos = TEXTOS_POR_IDIOMA.get(lang_cap, TEXTOS_POR_IDIOMA[idioma_meta])

        xhtml = plantilla.render(
            idioma=lang_cap,
            titulo_edicion=titulo_edicion,
            minutos_totales=minutos_totales,
            textos=textos,
            titulo=art["titulo"],
            fuente=art["fuente"],
            minutos=art["minutos"],
            palabras=art["palabras"],
            url=art.get("url"),
            cuerpo_html=art["cuerpo_html"],
        )

        cap = epub.EpubHtml(
            title=f"{art['titulo']} ({art['minutos']} {textos['min_unidad']})",
            file_name=f"Text/articulo_{idx:02d}.xhtml",
            lang=lang_cap,
        )
        cap.set_content(xhtml.encode("utf-8"))
        cap.add_item(css_item)
        book.add_item(cap)
        capitulos.append(cap)

    book.toc = tuple(capitulos)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *capitulos]

    archivo_salida.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(archivo_salida), book, {})
    return archivo_salida


def enviar_epub_a_kindle(ruta_epub: Path, asunto: Optional[str] = None) -> None:
    """Envía el archivo .epub por correo SMTP a la dirección @kindle.com."""
    if not ruta_epub.exists():
        raise FileNotFoundError(f"No existe el archivo EPUB: {ruta_epub}")

    requeridas = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "KINDLE_EMAIL"]
    faltantes = [var for var in requeridas if not os.getenv(var)]
    if faltantes:
        raise RuntimeError(f"Faltan variables de entorno SMTP: {', '.join(faltantes)}")

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    kindle_email = os.environ["KINDLE_EMAIL"]

    msg = EmailMessage()
    msg["Subject"] = asunto or f"Edicion Kindle {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = smtp_user
    msg["To"] = kindle_email
    msg.set_content("Edición automática en formato EPUB para Kindle.")

    msg.add_attachment(
        ruta_epub.read_bytes(),
        maintype="application",
        subtype="epub+zip",
        filename=ruta_epub.name,
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Selecciona artículos por idioma, tipo (periódico/revista), fuente y duración, genera un EPUB con Jinja2 y opcionalmente lo envía a Kindle."
    )
    parser.add_argument(
        "idioma",
        nargs="?",
        choices=["en", "es", "mix"],
        default=None,
        help="Idioma de las fuentes a consultar ('en', 'es' o 'mix'). Por defecto: 'es'.",
    )
    parser.add_argument(
        "-t",
        "--tipo",
        "--ritmo",
        dest="tipo",
        type=str.lower,
        choices=["periodico", "diario", "revista", "ensayo"],
        default=None,
        help="Tipo de publicación: 'periodico'/'diario' (noticias de actualidad) o 'revista'/'ensayo' (ensayos largos). Por defecto: 'revista'.",
    )
    parser.add_argument(
        "--periodico",
        "--diario",
        dest="flag_periodico",
        action="store_true",
        help="Atajo para generar un periódico (--tipo periodico).",
    )
    parser.add_argument(
        "--revista",
        "--ensayo",
        dest="flag_revista",
        action="store_true",
        help="Atajo para generar una revista de ensayos (--tipo revista).",
    )
    parser.add_argument(
        "--tema",
        "--seccion",
        type=str.lower,
        default=None,
        help="Filtra fuentes por tema ('internacional', 'ciencia', 'tecnologia', 'politica_economia', 'cultura_filosofia').",
    )
    parser.add_argument(
        "-f",
        "--fuente",
        type=str,
        default=None,
        help="Filtra por nombre de fuente (coincidencia parcial o exacta, insensible a mayúsculas/minúsculas).",
    )
    parser.add_argument(
        "-u",
        "--urls-file",
        "--urls",
        "--archivo-urls",
        dest="urls_file",
        type=Path,
        default=None,
        help="Ruta a un archivo .txt con URLs de artículos (una por línea). Se omiten las restricciones de tiempo de lectura.",
    )
    parser.add_argument(
        "--orden",
        "-o_orden",
        "-O",
        type=str.lower,
        choices=["random", "reciente", "cronologico"],
        default="random",
        help="Orden de selección: 'random' (aleatorio) o 'reciente'/'cronologico' (según orden RSS, lo último publicado primero). Por defecto: 'random'.",
    )
    parser.add_argument(
        "-n",
        "--cantidad",
        type=int,
        default=None,
        help="Cantidad de artículos a incluir en la edición (por defecto: 5 para periódico, 3 para revista).",
    )
    parser.add_argument(
        "--min-minutos",
        type=int,
        default=None,
        help="Tiempo mínimo de lectura por artículo en minutos.",
    )
    parser.add_argument(
        "--max-minutos",
        type=int,
        default=None,
        help="Tiempo máximo de lectura por artículo en minutos.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Ruta de salida del archivo .epub (por defecto: ./output/<tipo>_<idioma>_YYYY-MM-DD.epub).",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=DEFAULT_TEMPLATES_DIR,
        help="Directorio que contiene la plantilla Jinja2 (por defecto: ./templates).",
    )
    parser.add_argument(
        "--template",
        type=str,
        default=NOMBRE_PLANTILLA,
        help=f"Nombre del archivo de plantilla (por defecto: {NOMBRE_PLANTILLA}).",
    )
    parser.add_argument(
        "--css",
        type=Path,
        default=DEFAULT_CSS_PATH,
        help="Ruta del archivo CSS externo (por defecto: ./styles/edicion_kindle.css).",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Envía el EPUB generado por correo a KINDLE_EMAIL.",
    )
    parser.add_argument(
        "--send-only",
        type=Path,
        default=None,
        help="Envía un .epub ya existente sin consultar feeds ni regenerar.",
    )
    args = parser.parse_args()

    if args.cantidad is not None and args.cantidad <= 0:
        parser.error("--cantidad / -n debe ser un número entero mayor a 0.")

    orden = "reciente" if args.orden == "cronologico" else args.orden

    # Determinar tipo de publicación (periódico vs revista)
    if args.flag_periodico:
        tipo = "periodico"
    elif args.flag_revista:
        tipo = "revista"
    elif args.tipo:
        tipo = "periodico" if args.tipo in ["periodico", "diario"] else "revista"
    else:
        tipo = None

    # Si no se pasó tipo explícito pero se pasó una fuente, deducir el tipo a partir de esa fuente
    if tipo is None and args.fuente:
        fuentes_todas = FUENTES["en"] + FUENTES["es"]
        coincidentes = [f for f in fuentes_todas if coincide_fuente(str(f["nombre"]), args.fuente)]
        if coincidentes:
            tipo = "periodico" if coincidentes[0].get("ritmo") == "diario" else "revista"

    # Por defecto, mantiene el comportamiento original (revista / ensayo)
    if tipo is None:
        tipo = "revista"

    ritmo_filtro = "diario" if tipo == "periodico" else "ensayo"
    objetivo_cantidad = (
        args.cantidad
        if args.cantidad is not None
        else (OBJETIVO_ARTICULOS_PERIODICO if tipo == "periodico" else OBJETIVO_ARTICULOS_REVISTA)
    )
    min_minutos = (
        args.min_minutos
        if args.min_minutos is not None
        else (MIN_MINUTOS_PERIODICO if tipo == "periodico" else MIN_MINUTOS_REVISTA)
    )
    max_minutos = (
        args.max_minutos
        if args.max_minutos is not None
        else (MAX_MINUTOS_PERIODICO if tipo == "periodico" else MAX_MINUTOS_REVISTA)
    )

    try:
        if args.send_only:
            enviar_epub_a_kindle(args.send_only)
            print(f"Enviado a Kindle: {args.send_only}")
            return 0

        if args.urls_file:
            idioma_base = args.idioma or "es"
            seleccionados = extraer_articulos_desde_archivo(
                args.urls_file, idioma_por_defecto=idioma_base
            )
            if not seleccionados:
                raise RuntimeError(
                    f"No se pudo extraer ningún artículo válido desde '{args.urls_file}'."
                )

            if args.idioma is None:
                idiomas_arts = {a.get("idioma", "es") for a in seleccionados}
                if len(idiomas_arts) == 1:
                    idioma = idiomas_arts.pop()
                else:
                    idioma = "mix"
            else:
                idioma = args.idioma
        else:
            idioma = args.idioma
            if args.fuente and idioma is None:
                matches_en = [f for f in FUENTES["en"] if coincide_fuente(str(f["nombre"]), args.fuente)]
                matches_es = [f for f in FUENTES["es"] if coincide_fuente(str(f["nombre"]), args.fuente)]
                if matches_en and not matches_es:
                    idioma = "en"
                elif matches_es and not matches_en:
                    idioma = "es"
                elif matches_en and matches_es:
                    idioma = "mix"
                else:
                    raise RuntimeError(f"No se encontró ninguna fuente que coincida con '{args.fuente}'.")
            elif idioma is None:
                idioma = "es"

            seleccionados = seleccionar_articulos(
                idioma_arg=idioma,
                objetivo=objetivo_cantidad,
                filtro_fuente=args.fuente,
                filtro_ritmo=ritmo_filtro,
                filtro_tema=args.tema,
                orden=orden,
                min_minutos=min_minutos,
                max_minutos=max_minutos,
            )
            if not seleccionados:
                raise RuntimeError("No se pudo extraer ningún artículo válido en esta ejecución.")

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        prefijo_salida = (
            "the_elmolda_gazette" if tipo == "periodico" else "the_elmolda_gazette_magazine"
        )
        salida = args.output or (Path("output") / f"{prefijo_salida}_{idioma}_{fecha_hoy}.epub")

        epub_generado = generar_epub(
            articulos=seleccionados,
            idioma_edicion=idioma,
            directorio_plantillas=args.templates_dir,
            ruta_css=args.css,
            archivo_salida=salida,
            nombre_plantilla=args.template,
            tipo_edicion=tipo,
        )

        minutos_totales = sum(a["minutos"] for a in seleccionados)
        desc_tipo = (
            "The elmolda gazette" if tipo == "periodico" else "The elmolda gazette magazine"
        )
        print(
            f"\nListo ({desc_tipo}): {len(seleccionados)} artículos ({minutos_totales} min) "
            f"en '{epub_generado.resolve()}'."
        )

        if args.send:
            asunto_correo = (
                f"The elmolda gazette · {fecha_hoy}"
                if tipo == "periodico"
                else f"The elmolda gazette magazine · {fecha_hoy}"
            )
            enviar_epub_a_kindle(epub_generado, asunto=asunto_correo)
            print(f"Enviado por correo a: {os.getenv('KINDLE_EMAIL')}")

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
