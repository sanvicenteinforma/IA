"""
Fase 2 - San Vicente Informa
Lee el feed publico de Blogger, detecta notas nuevas que todavia no estan
en knowledge_base.json, y las agrega. Pensado para correr automaticamente
via GitHub Actions (cron).

Uso:
    python3 update_knowledge_base.py knowledge_base.json <url_del_feed>
"""

import sys
import json
import re
import urllib.request
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

NS = {"atom": "http://www.w3.org/2005/Atom"}


def limpiar_html(html_content: str) -> str:
    """Igual que en Fase 1: convierte el HTML del post en texto plano."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    texto = soup.get_text(separator=" ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def descargar_feed(url_feed: str) -> bytes:
    """
    Descarga el feed. Le pedimos hasta 150 resultados por si el robot
    no corrio en un tiempo y se acumularon mas de las 25 que trae por
    defecto (asi no se pierde ninguna nota).
    """
    url_completa = f"{url_feed}?max-results=150"
    request = urllib.request.Request(
        url_completa,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SanVicenteInformaBot/1.0)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def extraer_url(entry) -> str:
    """En el feed publico (a diferencia del export privado), el link
    rel='alternate' SI viene completo."""
    for link in entry.findall("atom:link", NS):
        if link.get("rel") == "alternate":
            return link.get("href", "")
    return ""


def parsear_entries(xml_bytes: bytes) -> list:
    root = ET.fromstring(xml_bytes)
    entries = []
    for entry in root.findall("atom:entry", NS):
        post_id = entry.findtext("atom:id", default="", namespaces=NS)
        titulo = entry.findtext("atom:title", default="", namespaces=NS)
        publicado = entry.findtext("atom:published", default="", namespaces=NS)
        actualizado = entry.findtext("atom:updated", default="", namespaces=NS)

        contenido_el = entry.find("atom:content", NS)
        contenido_html = contenido_el.text if contenido_el is not None else ""
        contenido_texto = limpiar_html(contenido_html)

        etiquetas = [
            cat.get("term", "")
            for cat in entry.findall("atom:category", NS)
            if cat.get("term")
        ]

        entries.append({
            "id": post_id,
            "titulo": titulo,
            "url": extraer_url(entry),
            "publicado": publicado,
            "actualizado": actualizado,
            "etiquetas": etiquetas,
            "contenido": contenido_texto,
            "cantidad_palabras": len(contenido_texto.split()),
        })
    return entries


def actualizar(ruta_json: str, url_feed: str):
    with open(ruta_json, "r", encoding="utf-8") as f:
        base_actual = json.load(f)

    ids_existentes = {p["id"] for p in base_actual}

    xml_bytes = descargar_feed(url_feed)
    entries_del_feed = parsear_entries(xml_bytes)

    nuevas = [e for e in entries_del_feed if e["id"] not in ids_existentes]

    if not nuevas:
        print("Sin novedades: no hay notas nuevas en el feed.")
        return False  # False = no hubo cambios

    base_actualizada = nuevas + base_actual  # las nuevas van primero
    base_actualizada.sort(key=lambda p: p["publicado"], reverse=True)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(base_actualizada, f, ensure_ascii=False, indent=2)

    print(f"Se agregaron {len(nuevas)} nota(s) nueva(s):")
    for n in nuevas:
        print(f"  - {n['titulo']}")

    return True  # True = hubo cambios (util para el workflow)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 update_knowledge_base.py <knowledge_base.json> <url_feed>")
        sys.exit(1)
    hubo_cambios = actualizar(sys.argv[1], sys.argv[2])
    # Le avisamos a GitHub Actions si hubo cambios, escribiendo en un
    # archivo especial que el workflow va a leer (lo vemos en el Paso 2.4)
    import os
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"hubo_cambios={'true' if hubo_cambios else 'false'}\n")
