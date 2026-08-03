"""
Fase 1 - San Vicente Informa
Convierte el export XML de Blogger (feed.atom) en una base de conocimiento
JSON liviana, quedandose SOLO con las entradas de tipo POST (se descartan
los COMMENT).

Uso:
    python3 build_knowledge_base.py feed.atom knowledge_base.json
"""

import sys
import json
import re
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

# Namespaces usados por el XML de Blogger. Sin esto, ElementTree no
# encuentra las etiquetas porque vienen "prefijadas" internamente.
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "blogger": "http://schemas.google.com/blogger/2018",
}


def limpiar_html(html_content: str) -> str:
    """Convierte el HTML del post en texto plano legible para la IA."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    texto = soup.get_text(separator=" ")
    # Colapsa espacios/saltos de linea multiples en uno solo
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def construir_url(entry, dominio: str) -> str:
    """
    En este export, <link rel="alternate"> viene vacio.
    La ruta real esta en <blogger:filename>, ej: /2026/06/mi-post.html
    Hay que pegarla al dominio del blog para tener la URL completa.
    """
    filename = entry.findtext("blogger:filename", default="", namespaces=NS)
    if not filename:
        return ""
    if not filename.startswith("/"):
        filename = "/" + filename
    return dominio.rstrip("/") + filename


def procesar_feed(ruta_entrada: str, ruta_salida: str, dominio: str):
    tree = ET.parse(ruta_entrada)
    root = tree.getroot()

    posts = []
    total_entradas = 0
    descartadas_comentarios = 0

    for entry in root.findall("atom:entry", NS):
        total_entradas += 1

        tipo = entry.findtext("blogger:type", default="", namespaces=NS)
        estado = entry.findtext("blogger:status", default="", namespaces=NS)

        # Nos quedamos SOLO con posts publicados (no comentarios, no borradores)
        if tipo != "POST":
            descartadas_comentarios += 1
            continue
        if estado != "LIVE":
            continue

        post_id = entry.findtext("atom:id", default="", namespaces=NS)
        titulo = entry.findtext("atom:title", default="", namespaces=NS)
        publicado = entry.findtext("atom:published", default="", namespaces=NS)
        actualizado = entry.findtext("atom:updated", default="", namespaces=NS)

        contenido_el = entry.find("atom:content", NS)
        contenido_html = contenido_el.text if contenido_el is not None else ""
        contenido_texto = limpiar_html(contenido_html)

        # Las etiquetas vienen como multiples <category term="..."/>
        etiquetas = [
            cat.get("term", "")
            for cat in entry.findall("atom:category", NS)
            if cat.get("term")
        ]

        # Descartamos borradores vacios (sin titulo NI contenido) que Blogger
        # a veces guarda automaticamente y nunca llegaron a publicarse.
        if not titulo.strip() and not contenido_texto.strip():
            continue

        posts.append({
            "id": post_id,
            "titulo": titulo,
            "url": construir_url(entry, dominio),
            "publicado": publicado,
            "actualizado": actualizado,
            "etiquetas": etiquetas,
            "contenido": contenido_texto,
            "cantidad_palabras": len(contenido_texto.split()),
        })

    # Ordenamos por fecha de publicacion, mas nuevo primero
    posts.sort(key=lambda p: p["publicado"], reverse=True)

    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"Entradas totales en el XML: {total_entradas}")
    print(f"Descartadas (comentarios/otros): {descartadas_comentarios}")
    print(f"Posts guardados en la base de conocimiento: {len(posts)}")
    print(f"Archivo generado: {ruta_salida}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 build_knowledge_base.py <entrada.atom> <salida.json> <dominio>")
        print("Ej:  python3 build_knowledge_base.py feed.atom knowledge_base.json https://www.sanvicenteinforma.com")
        sys.exit(1)
    procesar_feed(sys.argv[1], sys.argv[2], sys.argv[3])
