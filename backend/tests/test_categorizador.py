from backend.categorizador import normalizar_concepto, sugerir_categoria_id


def test_normalizar_quita_acentos_numeros_y_mayusculas():
    assert normalizar_concepto("Pagó Nómina 12345 S.A.") == "PAGO NOMINA SA"


def test_normalizar_colapsa_espacios():
    assert normalizar_concepto("  SPEI   ENVIADO  ") == "SPEI ENVIADO"


def _regla(palabra, cat, origen="regla", tipo_match="concepto", peso=1, tipo="ambos"):
    return {"palabra_clave": palabra, "categoria_id": cat, "origen": origen,
            "tipo_match": tipo_match, "peso": peso, "tipo": tipo}


def test_regla_base_por_palabra_clave_en_concepto():
    reglas = [_regla("NOMINA", "cat-nomina")]
    assert sugerir_categoria_id("PAGO NOMINA QUINCENAL", None, "retiro", reglas) == "cat-nomina"


def test_sin_match_devuelve_none():
    reglas = [_regla("NOMINA", "cat-nomina")]
    assert sugerir_categoria_id("DEPOSITO EN EFECTIVO", None, "deposito", reglas) is None


def test_filtra_por_tipo_de_movimiento():
    reglas = [_regla("TRANSFER", "cat-egreso", tipo="retiro")]
    # mismo concepto pero movimiento es depósito -> la regla de retiro no aplica
    assert sugerir_categoria_id("TRANSFER RECIBIDA", None, "deposito", reglas) is None
    assert sugerir_categoria_id("TRANSFER ENVIADA", None, "retiro", reglas) == "cat-egreso"


def test_historial_rfc_tiene_prioridad_sobre_regla_base():
    reglas = [
        _regla("NOMINA", "cat-nomina"),
        _regla("AAA010101AAA", "cat-proveedor", origen="historial", tipo_match="rfc", peso=5),
    ]
    res = sugerir_categoria_id("PAGO NOMINA", "AAA010101AAA", "retiro", reglas)
    assert res == "cat-proveedor"


def test_mayor_peso_gana_dentro_de_misma_prioridad():
    reglas = [
        _regla("PAGO", "cat-a", origen="historial", tipo_match="concepto", peso=1),
        _regla("PAGO SERVICIO", "cat-b", origen="historial", tipo_match="concepto", peso=9),
    ]
    assert sugerir_categoria_id("PAGO SERVICIO LUZ", None, "retiro", reglas) == "cat-b"
