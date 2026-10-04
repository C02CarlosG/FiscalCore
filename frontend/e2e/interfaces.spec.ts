import { expect, test } from "@playwright/test";

const empresaId = "empresa-demo";
const empresa = {
  id: empresaId,
  rfc: "AAA010101AAA",
  razon_social: "Empresa de prueba",
  regimen_fiscal: "601",
  cp_fiscal: "06000",
  curp: null,
  obligaciones: [],
  representante_legal: null,
  rfc_representante: null,
  activo: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
const columna = (clave: string, etiqueta: string, tipo_dato: string, ordenable = false) => ({
  clave, etiqueta, tipo_dato, grupo: "encabezado", visible_por_defecto: true, ordenable, filtrable: ordenable, opciones: [],
});
const columnasCfdi = {
  encabezado: [
    columna("fecha_emision", "Fecha de expedición", "fecha", true),
    columna("folio", "Folio", "texto", true),
    columna("contraparte", "Nombre", "texto", true),
    columna("total", "Total", "moneda", true),
    columna("estado", "Estado", "catalogo"),
  ],
  concepto: [
    { ...columna("descripcion", "Descripción", "texto", true), grupo: "concepto" },
    { ...columna("importe", "Importe", "moneda", true), grupo: "concepto" },
  ],
};
const detalleCfdi = (uuid: string) => ({
  encabezado: {
    uuid, version: "4.0", tipo_comprobante: "I", serie: "A", folio: "001", fecha_emision: "2026-09-01T10:00:00",
    fecha_timbrado: "2026-09-01T10:01:00", no_certificado: "30001000000500003416", lugar_expedicion: "68000",
    moneda: "MXN", tipo_cambio: 1, subtotal: 1000, descuento: 0, iva_trasladado: 250, iva_retenido: 0,
    isr_retenido: 0, total: 1250, saldo: 0, metodo_pago: "PUE", metodo_pago_desc: "PUE - Pago en una sola exhibición",
    forma_pago: "03", forma_pago_desc: "03 - Transferencia electrónica de fondos", uso_cfdi: "G03",
    uso_cfdi_desc: "G03 - Gastos en general", estado: "vigente",
  },
  emisor: { rfc: "AAA010101AAA", nombre: "Empresa de prueba", regimen: "601", regimen_desc: "601 - General de Ley Personas Morales" },
  receptor: { rfc: "BBB010101BBB", nombre: "Proveedor ficticio uno", regimen: "601", regimen_desc: "601 - General de Ley Personas Morales", domicilio_fiscal: "68000" },
  impuestos: [],
  conceptos: [
    { linea: 1, clave_prod_serv: "84111506", cantidad: 1, unidad: "Servicio", descripcion: "Servicio de consultoría ficticio", valor_unitario: 1000, importe: 1000, descuento: 0, iva_traslado_importe: 250 },
  ],
  total_conceptos: 1,
  pagos: [],
  relacionados: [],
  tiene_xml: true,
});
const filasCfdi = [
  { uuid: "cfdi-demo-001", fecha_emision: "2026-09-01T10:00:00", folio: "001", contraparte: "Proveedor ficticio uno", total: 1250, estado: "vigente" },
  { uuid: "cfdi-demo-002", fecha_emision: "2026-09-02T11:30:00", folio: "002", contraparte: "Proveedor ficticio dos", total: 2500, estado: "vigente" },
];
const bloqueCfdi = (conteo: number, total: number) => ({
  conteo, retencion_iva: 0, retencion_ieps: 0, retencion_isr: 0, traslado_iva: 600, traslado_ieps: 0,
  traslado_isr: 0, total_retenciones: 0, subtotal: total - 600, descuento: 0, neto: total - 600, total,
});
const resumenCfdi = {
  conteos: { I: 2, E: 0, T: 0, N: 1, P: 0 },
  totales: { periodo: bloqueCfdi(2, 3750), acumulado: bloqueCfdi(9, 21000) },
  advertencias: [],
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "fiscalcore.session",
      JSON.stringify({
        accessToken: "playwright-test-token",
        userId: "user-demo",
        email: "pruebas@example.test",
        nombre: "Usuario de prueba",
        empresas: [],
      }),
    );
  });

  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};

    if (path.endsWith("/auth/me")) {
      body = { id: "user-demo" };
    } else if (path.endsWith("/cfdi/upload")) {
      body = {
        mensaje: "1 CFDI procesado correctamente",
        registros_procesados: 1,
        errores: [],
        periodo: "2026-09",
      };
    } else if (path.endsWith("/banco/upload")) {
      body = {
        mensaje: "1 movimiento procesado correctamente",
        registros_procesados: 1,
        errores: [],
        periodo: "2026-09",
      };
    } else if (path === "/api/v1/empresas") {
      body = [empresa];
    } else if (path.includes("/dashboard/")) {
      body = {
        empresa,
        score_actual: null,
        riesgos_abiertos: [{
          id: "riesgo-demo",
          codigo: "R-001",
          nombre: "Revisión de prueba",
          severidad: "alto",
          monto_afectado: 2500,
          descripcion: "Registro fiscal sintético para pruebas visuales.",
          cfdi_id: null,
          movimiento_id: null,
          estado: "abierto",
          periodo: "2026-09",
          created_at: "2026-09-02T00:00:00Z",
        }],
        resumen_riesgos: {
          critico: 0,
          alto: 1,
          medio: 0,
          bajo: 0,
          monto_total_en_riesgo: 2500,
        },
        tendencia_score: [{ periodo: "2026-09", score: 88 }],
        indicadores: { pct_conciliacion: 50 },
      };
    } else if (path.includes("/conciliaciones/accionables")) {
      body = {
        total: 1,
        pares: [{
          id: "par-demo",
          tipo_match: "parcial",
          monto_movimiento: 2500,
          monto_cfdi: 2450,
          diferencia: 50,
          porcentaje_match: 98,
          periodo: "2026-09",
          movimiento_id: "mov-demo",
          mov_fecha: "2026-09-02",
          concepto: "Transferencia de prueba",
          mov_monto: 2500,
          mov_tipo: "abono",
          rfc_detectado: "BBB010101BBB",
        }],
      };
    } else if (path.includes("/conciliaciones")) {
      body = {
        total: 2,
        exacto: 1,
        parcial: 1,
        sin_cfdi: 0,
        sin_movimiento: 0,
        pct_conciliado: 50,
      };
    } else if (path.includes("/cedula-iva/")) {
      body = {
        empresa_id: empresaId,
        periodo: "2026-09",
        trasladado: {
          pue: { base: 0, iva: 0 },
          ppd: { cobrado: 0, iva: 0 },
          notas_credito: { base: 0, iva: 0 },
          total: 0,
        },
        acreditable: {
          pue: { base: 0, iva: 0 },
          ppd: { pagado: 0, iva: 0 },
          notas_credito: { base: 0, iva: 0 },
          excluido_efectivo: { iva: 0 },
          bruto: 0,
          factor_prorrateo: 1,
          ajustado: 0,
        },
        iva_retenido: 0,
        resultado: { iva_por_pagar: 0, saldo_a_cargo: 0, saldo_a_favor: 0 },
        comparativo_sat: { diot_iva_pagado: 0, diferencia: 0 },
      };
    } else if (/\/cfdis\/[^/]+\/xml$/.test(path)) {
      await route.fulfill({
        status: 200,
        contentType: "application/xml",
        headers: { "Content-Disposition": 'attachment; filename="cfdi-demo-001.xml"' },
        body: "<cfdi:Comprobante/>",
      });
      return;
    } else if (/\/cfdis\/cfdi-demo-\d+$/.test(path)) {
      body = detalleCfdi(path.split("/").pop()!);
    } else if (path.endsWith("/cfdis/columnas")) {
      body = columnasCfdi;
    } else if (path.endsWith("/cfdis/resumen")) {
      body = resumenCfdi;
    } else if (path.endsWith("/cfdis")) {
      // El servidor ordena: el mock respeta `orden` y `dir` para probar que viajan.
      const consulta = new URL(route.request().url()).searchParams;
      const filas = [...filasCfdi];
      if (consulta.get("orden") === "total") {
        filas.sort((a, b) => a.total - b.total);
        if (consulta.get("dir") === "desc") filas.reverse();
      }
      body = { items: filas, total: filas.length, pagina: 1, por_pagina: 30 };
    } else if (path.endsWith("/periodos")) {
      body = { periodos: ["2026-09", "2026-08"] };
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
});

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status === "passed") {
    const name = testInfo.title.replace(/[^a-z0-9-]/gi, "-").toLowerCase();
    await page.screenshot({ path: `/tmp/fiscalcore-current-${name}.png`, fullPage: true });
  }
});

test("login muestra un error accesible cuando faltan credenciales", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("Correo y contraseña son obligatorios")).toBeVisible();
});

test("la raíz dirige al listado de empresas con sesión", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/");
  await expect.poll(() => page.evaluate(() => localStorage.getItem("fiscalcore.session"))).not.toBeNull();
  await expect.poll(() => pageErrors).toEqual([]);
  await expect(page).toHaveURL(/\/empresas$/);
  await expect(page.getByRole("heading", { name: "Empresas" })).toBeVisible();
});

test("empresas abre el formulario de alta", async ({ page }) => {
  await page.goto("/empresas");
  await expect(page.getByText("Empresa de prueba")).toBeVisible();
  await page.getByRole("button", { name: "Nueva empresa" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Agregar empresa" })).toBeVisible();
});

test("empresas muestra su estado vacío cuando no hay registros", async ({ page }) => {
  await page.route("**/api/v1/empresas", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.goto("/empresas");
  await expect(page.getByText("Aún no hay empresas registradas.")).toBeVisible();
});

test("dashboard carga dentro del shell de empresa", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("Score fiscal del periodo")).toBeVisible();
});

test("dashboard muestra skeleton mientras consulta", async ({ page }) => {
  await page.route("**/api/v1/dashboard/**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fallback();
  });
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await expect(page.getByRole("status", { name: "Cargando dashboard" })).toBeVisible();
  await expect(page.getByText("Revisión de prueba")).toBeVisible();
});

test("dashboard presenta error contextual y permite reintentar", async ({ page }) => {
  await page.route("**/api/v1/dashboard/**", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Fallo de prueba" }),
    });
  });
  await page.goto(`/empresas/${empresaId}/dashboard`);
  const dashboardError = page.getByRole("alert").filter({ hasText: "No se pudo cargar el dashboard." });
  await expect(dashboardError).toBeVisible();
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(dashboardError).toBeVisible();
});

test("cédula de IVA calcula con el periodo global", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cedula-iva`);
  await expect(page.getByRole("combobox", { name: "Periodo" })).toBeVisible();
  await expect(page.getByText("IVA por pagar")).toBeVisible();
});

test("el periodo elegido se conserva al cambiar de pantalla", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await page.getByRole("combobox", { name: "Periodo" }).click();
  await page.getByRole("option", { name: "2026 - Agosto" }).click();
  await expect(page).toHaveURL(/periodo=2026-08/);

  await page.getByRole("link", { name: "Cédula de IVA" }).click();

  await expect(page).toHaveURL(/cedula-iva\?periodo=2026-08/);
  await expect(page.getByRole("combobox", { name: "Periodo" })).toContainText("2026 - Agosto");
});

test("CFDI emitidos muestra el listado del periodo con sus totales", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos`);
  await expect(page.getByRole("heading", { name: "CFDI emitidos" })).toBeVisible();
  await expect(page).toHaveURL(/periodo=\d{4}-\d{2}/);
  await expect(page.getByRole("tab", { name: /Ingreso/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("cell", { name: "Proveedor ficticio uno" })).toBeVisible();
  await expect(page.getByRole("row", { name: /^Periodo/ })).toContainText("$3,750.00");
  await expect(page.getByText("01/09/2026")).toBeVisible();
});

test("una fila despliega sus conceptos sin salir del listado", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await page.getByRole("button", { name: "Ver conceptos" }).first().click();

  await expect(page.getByText("Servicio de consultoría ficticio")).toBeVisible();
  await expect(page.getByText("1 concepto", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/cfdi\/emitidos\?periodo=2026-09$/);

  await page.getByRole("button", { name: "Ocultar conceptos" }).click();
  await expect(page.getByText("Servicio de consultoría ficticio")).toHaveCount(0);
});

test("el visor muestra el CFDI y descarga su XML", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await page.getByRole("button", { name: "Abrir visor del CFDI" }).first().click();

  const visor = page.getByRole("dialog");
  await expect(visor.getByRole("heading", { name: /Ingreso A-001/ })).toBeVisible();
  await expect(visor.getByText("30001000000500003416")).toBeVisible();
  await expect(visor.getByText("01/09/2026 10:00")).toBeVisible();
  await expect(visor.getByRole("table", { name: "Totales" })).toContainText("$1,250.00");

  const descarga = page.waitForEvent("download");
  await visor.getByRole("button", { name: "Descargar XML" }).click();
  expect((await descarga).suggestedFilename()).toBe("cfdi-demo-001.xml");

  await visor.getByRole("button", { name: "Cerrar" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("al imprimir solo queda el visor del CFDI", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await page.getByRole("button", { name: "Abrir visor del CFDI" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.emulateMedia({ media: "print" });

  await expect(page.getByRole("dialog").getByText("30001000000500003416")).toBeVisible();
  await expect(page.getByRole("heading", { name: "CFDI emitidos" })).toBeHidden();
  await expect(page.getByRole("dialog").getByRole("button", { name: "Imprimir" })).toBeHidden();
});

test("CFDI recibidos usa la misma pantalla con su propio título", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/recibidos?periodo=2026-09`);
  await expect(page.getByRole("heading", { name: "CFDI recibidos" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Proveedor ficticio dos" })).toBeVisible();
});

test("el listado ordena en el servidor y el orden sobrevive a recargar", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  const primera = page.getByRole("cell", { name: /^Proveedor ficticio/ }).first();

  await page.getByRole("button", { name: "Total" }).click();
  await expect(page).toHaveURL(/orden=total/);
  await expect(primera).toHaveText("Proveedor ficticio uno");

  await page.getByRole("button", { name: "Total" }).click();
  await expect(page).toHaveURL(/dir=desc/);
  await expect(primera).toHaveText("Proveedor ficticio dos");

  await page.reload();
  await expect(page).toHaveURL(/orden=total.*dir=desc|dir=desc.*orden=total/);
  await expect(primera).toHaveText("Proveedor ficticio dos");
  // La tabla de totales también tiene un encabezado "Total": se acota al listado (la segunda tabla).
  await expect(page.getByRole("table").nth(1).getByRole("columnheader", { name: "Total", exact: true }))
    .toHaveAttribute("aria-sort", "descending");
});

test("Nómina es una pestaña del listado, no una pantalla aparte", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);

  await page.getByRole("tab", { name: /Nómina/ }).click();

  await expect(page).toHaveURL(/tipo=N/);
  await expect(page.getByRole("tab", { name: /Nómina/ })).toHaveAttribute("aria-selected", "true");
});

test("las rutas viejas del Visor SAT y de Nómina llevan al listado", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi`);
  await expect(page).toHaveURL(/\/cfdi\/emitidos/);

  await page.goto(`/empresas/${empresaId}/cfdi/nomina`);
  await expect(page).toHaveURL(/\/cfdi\/emitidos.*tipo=N/);
});

test("el menú CFDIs ofrece solo Emitidos y Recibidos", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await page.getByRole("button", { name: "CFDIs" }).click();
  await expect(page.getByRole("link", { name: "Emitidos" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Recibidos" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Visor SAT" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Nómina/ })).toHaveCount(0);
});

test("conciliación presenta resumen y partidas accionables", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/conciliacion`);
  await expect(page.getByRole("heading", { name: "Cruces banco-CFDI" })).toBeVisible();
  await expect(page.getByText("Conciliado")).toBeVisible();
});

test("ingesta presenta los formularios CFDI y banco", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/ingesta`);
  await expect(page.getByRole("heading", { name: "Ingesta" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Subir CFDI" })).toBeVisible();
  await expect(page.getByRole("button", { name: /subir estado de cuenta/i })).toBeVisible();
});

test("ingesta procesa un archivo XML de prueba", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/ingesta`);
  await page.getByLabel("Periodo (YYYY-MM)").first().fill("2026-09");
  await page.getByLabel("Archivos XML").setInputFiles({
    name: "cfdi-demo.xml",
    mimeType: "text/xml",
    buffer: Buffer.from("<Comprobante />"),
  });
  await page.getByRole("button", { name: "Subir CFDI" }).click();
  await expect(page.getByText("1 CFDI procesado correctamente")).toBeVisible();
  // Regresión: limpiar el formulario tras el éxito tronaba y se mostraba "No se pudo subir".
  await expect(page.getByText("No se pudo subir")).toHaveCount(0);
});

test("selector de banco revela campo libre para la opción Otro", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/ingesta`);
  await page.getByRole("combobox", { name: "Banco" }).click();
  await page.getByRole("option", { name: "Otro" }).click();
  await expect(page.getByLabel("Nombre del banco")).toBeVisible();
});

test("el upload bancario muestra el resultado de una carga de prueba", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/ingesta`);
  await page.getByLabel("Periodo (YYYY-MM)").nth(1).fill("2026-09");
  await page.getByRole("combobox", { name: "Banco" }).click();
  await page.getByRole("option", { name: "BBVA" }).click();
  await page.getByLabel("Estado de cuenta (.xlsx o .csv)").setInputFiles({
    name: "estado-demo.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("fecha,concepto,monto\\n2026-09-01,Prueba,100"),
  });
  await page.getByRole("button", { name: /subir estado de cuenta/i }).click();
  await expect(page.getByText("1 movimiento procesado correctamente")).toBeVisible();
  await expect(page.getByText("No se pudo subir")).toHaveCount(0);
});

test("el tema oscuro se aplica y persiste en la sesión local", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await page.getByRole("button", { name: "Modo claro" }).click();
  await expect.poll(() => page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("fiscalcore-theme"))).toBe("dark");
});

test("la tabla conserva el ancho de página en móvil", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await expect(page.getByRole("cell", { name: "Proveedor ficticio uno" })).toBeVisible();
  const widths = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
});

test("la navegación móvil abre el menú y conserva sus rutas", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/empresas/${empresaId}/dashboard`);
  await page.getByRole("button", { name: "Abrir menú" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("link", { name: "Empresas" })).toBeVisible();
  await page.getByRole("link", { name: "Ingesta" }).click();
  await expect(page).toHaveURL(new RegExp(`/empresas/${empresaId}/ingesta$`));
});