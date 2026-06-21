#!/usr/bin/env python3
"""
Siembra (o promueve) un usuario administrador en FiscalCore.

A diferencia del seed automático de backend/db.py — que solo crea un admin
cuando la tabla 'usuarios' está vacía — este script funciona bajo demanda:
crea el admin si no existe, o promueve a 'admin' un usuario ya registrado.

El rol 'admin' es la fuente de verdad (migración 020_admin_rol.sql); el login
lo propaga al JWT y el frontend muestra el menú de Administración con él.

Uso:
    # Crear un admin nuevo (aunque la base ya tenga usuarios):
    .venv/bin/python scripts/seed_admin.py \\
        --email nuevo@admin.com --password secreto --nombre "Carlos Admin"

    # Promover a admin un usuario ya existente (no pide contraseña):
    .venv/bin/python scripts/seed_admin.py --email ya@existe.com --promote

Sin argumentos pide email/nombre/contraseña de forma interactiva. DATABASE_URL
se toma del entorno (o de un .env en la raíz); si no existe, usa el default local.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import bcrypt as _bcrypt

_LOCAL_DEFAULT = "postgresql://postgres:postgres@127.0.0.1:5432/fiscalcore"


def _database_url() -> str:
    raiz = Path(__file__).resolve().parent.parent
    if load_dotenv is not None:
        load_dotenv(raiz / ".env")
    return os.getenv("DATABASE_URL", _LOCAL_DEFAULT)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crea o promueve un usuario admin en FiscalCore")
    p.add_argument("--email", help="Correo del administrador")
    p.add_argument("--password", help="Contraseña en texto plano (se hashea con bcrypt)")
    p.add_argument("--nombre", help="Nombre para mostrar")
    p.add_argument(
        "--promote",
        action="store_true",
        help="Solo promover a admin un usuario ya existente (no crea ni pide contraseña)",
    )
    return p.parse_args()


def _pedir(valor: str | None, etiqueta: str, *, secreto: bool = False) -> str:
    if valor:
        return valor
    valor = getpass.getpass(f"{etiqueta}: ") if secreto else input(f"{etiqueta}: ").strip()
    if not valor:
        sys.exit(f"Error: {etiqueta} es obligatorio")
    return valor


def main() -> None:
    args = _parse_args()
    email = _pedir(args.email, "Email").lower()

    conn = psycopg2.connect(_database_url())
    conn.autocommit = True
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, rol FROM usuarios WHERE email = %s", (email,))
            existente = cur.fetchone()

            if existente:
                if existente["rol"] == "admin":
                    print(f"El usuario '{email}' ya es admin (id={existente['id']}). Sin cambios.")
                    return
                cur.execute(
                    "UPDATE usuarios SET rol = 'admin' WHERE id = %s",
                    (existente["id"],),
                )
                print(f"Usuario '{email}' promovido a admin (id={existente['id']}).")
                return

            if args.promote:
                sys.exit(
                    f"Error: --promote requiere un usuario existente, pero '{email}' no existe. "
                    "Omite --promote (y pasa --password) para crearlo."
                )

            nombre = _pedir(args.nombre, "Nombre")
            password = _pedir(args.password, "Contraseña", secreto=True)
            password_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO usuarios (email, password_hash, nombre, rol) "
                "VALUES (%s, %s, %s, 'admin') RETURNING id",
                (email, password_hash, nombre),
            )
            nuevo_id = cur.fetchone()["id"]
            print(f"Admin '{email}' creado (id={nuevo_id}).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
