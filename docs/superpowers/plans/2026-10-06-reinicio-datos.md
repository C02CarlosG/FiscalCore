# Plan — Reiniciar datos de una empresa

Spec: `docs/superpowers/specs/2026-10-06-reinicio-datos-design.md`.

1. Spec con la lista exacta de tablas y pedido D → A, B, C en el plan maestro.
2. Migración 067 y su prueba (idempotente, token único, alcance «todo»).
3. E2E primero: contador 403; previsualizar (conteos, frase, solo hash del token);
   confirmaciones inválidas sin borrar; borrado exacto, conservación, otra empresa
   intacta, sincronización pausada, auditoría; dos confirmaciones simultáneas; 409 con
   más de 50,000 CFDI.
4. `reinicio_empresa.py` (tablas, token, transacción con FOR UPDATE NOWAIT) y
   `routers/reinicio.py` (permisos de U1, frase, contraseña, límite 5/min).
5. OpenAPI (dos rutas y la etiqueta «Reinicio»).
6. Frontend: `components/reinicio/ReiniciarDatos` (vista previa, frase, contraseña),
   página `/empresas/{id}/reiniciar` y entrada en el menú; vitest.
7. Suites completas, PR «D·Reinicio» y aviso a la coordinación.
