"""PDF sintéticos para pruebas: válidos, mínimos y sin datos reales del SAT.

Nunca se commitean constancias u opiniones reales; las pruebas arman el PDF en
memoria con el texto que necesitan.
"""
from __future__ import annotations


def _escapar(linea: str) -> str:
    return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_con_texto(lineas: list[str], paginas: int = 1) -> bytes:
    """PDF con las líneas dadas en la primera página y ``paginas - 1`` páginas vacías."""
    contenidos = []
    y = 750
    partes = []
    for linea in lineas:
        partes.append(f"BT /F1 10 Tf 50 {y} Td ({_escapar(linea)}) Tj ET")
        y -= 14
    contenidos.append("\n".join(partes).encode("latin-1"))
    contenidos += [b""] * (paginas - 1)

    # Objetos: 1 catálogo, 2 páginas, 3 fuente, luego (página, contenido) por cada hoja.
    ids_pagina = [4 + 2 * i for i in range(paginas)]
    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in ids_pagina)}] /Count {paginas} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, contenido in enumerate(contenidos):
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {ids_pagina[i] + 1} 0 R >>".encode()
        )
        objetos.append(
            f"<< /Length {len(contenido)} >>\nstream\n".encode() + contenido + b"\nendstream"
        )

    body = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, obj in enumerate(objetos, start=1):
        offsets.append(len(body))
        body += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(body)
    total = len(objetos) + 1
    xref = f"xref\n0 {total}\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"
    trailer = f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    body += xref.encode() + trailer.encode()
    return bytes(body)


RFC_PRUEBA = "ACM010101AA1"


def constancia_sintetica(rfc: str = RFC_PRUEBA) -> bytes:
    return pdf_con_texto([
        "CÉDULA DE IDENTIFICACIÓN FISCAL",
        "CONSTANCIA DE SITUACIÓN FISCAL",
        f"RFC: {rfc}",
        "idCIF: 12345678901",
        "Lugar y Fecha de Emisión",
        "OAXACA DE JUAREZ , OAXACA A 03 DE OCTUBRE DE 2026",
        "Denominación/Razón Social: ACME COMERCIALIZADORA SA DE CV",
        "Estatus en el padrón: ACTIVO",
        "Código Postal: 68000",
        "Régimen General de Ley Personas Morales",
    ])


def opinion_sintetica(rfc: str = RFC_PRUEBA, sentido: str = "POSITIVO") -> bytes:
    return pdf_con_texto([
        "Opinión del cumplimiento de obligaciones fiscales",
        "Folio 26NA1234567",
        f"Clave de R.F.C.: {rfc}",
        "Nombre, denominación o razón social: ACME COMERCIALIZADORA SA DE CV",
        "Revisión practicada el día 03 de octubre de 2026, a las 10:15 horas",
        f"se emite opinión en sentido {sentido}",
    ])
