"""
Fase 3 - San Vicente Informa
Precalcula un indice de busqueda a partir de knowledge_base.json.
Corre offline (en GitHub Actions, junto al script de la Fase 2), NO en
cada pregunta de un lector - asi el Worker de Cloudflare solo necesita
consultar este indice, que es rapido, en vez de recorrer todo el texto
de las 9.789 notas en cada pedido (cosa que no entra en el limite
gratuito de 10ms de Cloudflare Workers).

Uso:
    python3 build_search_index.py knowledge_base.json search_index.json
"""

import sys
import json
import re
import math
from collections import defaultdict

# Igual que en los scripts anteriores: palabras sin valor de busqueda.
PALABRAS_VACIAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "en", "y", "o", "que", "cual", "cuando", "como", "donde", "por",
    "para", "con", "sin", "es", "son", "fue", "fueron", "ser", "sobre",
    "se", "su", "sus", "a", "al", "lo", "le", "les", "me", "mi", "tu",
    "yo", "hay", "hubo", "esta", "estas", "esto", "eso", "ese", "esa",
    "estan", "asi", "aca", "alli", "ahi", "vos", "usted", "ustedes",
    "nosotros", "ellos", "ellas", "tambien", "porque", "pero", "mas",
    "muy", "hola", "buenas", "buenos", "dias", "tardes", "noches",
    "gracias",
}

# NOTA: antes tenia un filtro que sacaba del indice las palabras que
# aparecian en mas del 15% de las notas (para evitar que "concejo" opaque
# a "Holland", por ejemplo). Se saco: el peso IDF de abajo ya resuelve eso
# matematicamente (le da menos peso, no lo borra), y borrar la palabra del
# todo tenia un efecto secundario grave - palabras muy comunes PERO
# igual de importantes (como el nombre de una localidad: "Dos de Mayo")
# quedaban totalmente invisibles para la busqueda en vez de solo pesar menos.


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para que 'económico' y 'economico' matcheen."""
    texto = texto.lower()
    reemplazos = str.maketrans("áéíóúüñ", "aeiouun")
    return texto.translate(reemplazos)


def tokenizar(texto: str) -> list:
    """Parte el texto en palabras, sacando puntuacion, y descarta
    palabras vacias y muy cortas (menos de 3 letras)."""
    texto = normalizar(texto)
    palabras = re.findall(r"[a-z0-9]+", texto)
    return [p for p in palabras if len(p) > 2 and p not in PALABRAS_VACIAS]


def construir_indice(ruta_entrada: str, ruta_salida: str):
    with open(ruta_entrada, "r", encoding="utf-8") as f:
        notas = json.load(f)

    total_notas = len(notas)

    # postings_titulo / postings_contenido: palabra -> set de indices de nota
    # (usamos el indice dentro de la lista, no el id largo, para que el
    # archivo final pese menos)
    postings_titulo = defaultdict(set)
    postings_contenido = defaultdict(set)
    frecuencia_documento = defaultdict(int)  # en cuantas notas aparece cada palabra

    for i, nota in enumerate(notas):
        palabras_titulo = set(tokenizar(nota["titulo"]))
        palabras_contenido = set(tokenizar(nota["contenido"]))

        for palabra in palabras_titulo:
            postings_titulo[palabra].add(i)
        for palabra in palabras_contenido:
            postings_contenido[palabra].add(i)

        # Para el conteo de "en cuantas notas aparece", contamos una vez
        # por nota aunque la palabra este en titulo y contenido a la vez.
        for palabra in palabras_titulo | palabras_contenido:
            frecuencia_documento[palabra] += 1

    # Ya no filtramos por frecuencia de documento: el peso IDF de abajo
    # se encarga de bajarle la importancia a las palabras muy comunes
    # sin borrarlas del todo del indice.
    vocabulario_util = set(frecuencia_documento.keys())

    # IDF (Inverse Document Frequency): cuanto mas rara la palabra, mas
    # peso tiene. Formula estandar de motores de busqueda.
    idf = {
        palabra: round(math.log(total_notas / (1 + frecuencia_documento[palabra])), 4)
        for palabra in vocabulario_util
    }

    indice = {
        "total_notas": total_notas,
        "idf": idf,
        "postings_titulo": {
            palabra: sorted(ids) for palabra, ids in postings_titulo.items()
            if palabra in vocabulario_util
        },
        "postings_contenido": {
            palabra: sorted(ids) for palabra, ids in postings_contenido.items()
            if palabra in vocabulario_util
        },
    }

    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Notas procesadas: {total_notas}")
    print(f"Palabras unicas totales: {len(frecuencia_documento)}")
    print(f"Palabras utiles en el indice (no demasiado comunes): {len(vocabulario_util)}")
    print(f"Archivo generado: {ruta_salida}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 build_search_index.py <knowledge_base.json> <search_index.json>")
        sys.exit(1)
    construir_indice(sys.argv[1], sys.argv[2])
