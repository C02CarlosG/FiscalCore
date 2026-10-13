"""CSV de muestra de la lista 69-B (cp1252, con preámbulo), compartido por las pruebas de EFOS."""
import csv
import io

from backend import efos


def fila(no, rfc, nombre, situacion, presunto="01/06/2018", definitivo="", desvirtuado="", sentencia=""):
    """Una fila de 20 columnas; las fechas SAT y DOF de cada etapa son la misma."""
    return [str(no), rfc, nombre, situacion,
            "500-05-2018-1 de fecha 01 de junio de 2018" if presunto else "", presunto,
            "500-05-2018-1 de fecha 01 de junio de 2018" if presunto else "", presunto,
            "of-desv" if desvirtuado else "", desvirtuado, "of-desv-dof" if desvirtuado else "", desvirtuado,
            "of-def" if definitivo else "", definitivo, "of-def-dof" if definitivo else "", definitivo,
            "of-sent" if sentencia else "", sentencia, "of-sent-dof" if sentencia else "", sentencia]


def csv_muestra(filas, actualizada="31 de diciembre de 2025", preambulo=True, encabezado=None) -> bytes:
    salida = io.StringIO()
    w = csv.writer(salida, lineterminator="\r\n")
    if preambulo:
        w.writerow([f"Información actualizada al {actualizada}; los listados a que se hace mención son públicos."])
        w.writerow(["Listado completo de contribuyentes (Artículo 69-B del CFF)"] + [""] * 19)
    w.writerow(list(encabezado if encabezado is not None else efos.COLUMNAS))
    for f in filas:
        w.writerow(f)
    return salida.getvalue().encode("cp1252")


def validas(n, desde=1):
    """``n`` filas válidas con RFC distintos (ABC + 6 dígitos + 3 caracteres)."""
    return [fila(desde + i, f"ABC{(desde + i):06d}AB1", f"CONTRIBUYENTE {desde + i}", "Definitivo", definitivo="01/08/2018")
            for i in range(n)]
