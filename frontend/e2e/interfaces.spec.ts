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
const cfdiRows = [
  {
    uuid: "cfdi-demo-002",
    tipo_comprobante: "Ingreso",
    serie_folio: "SER-002",
    fecha: "2026-09-02",
    rfc_emisor: "BBB010101BBB",
    nombre_emisor: "Proveedor ficticio dos",
    rfc_receptor: empresa.rfc,
    nombre_receptor: empresa.razon_social,
    total: 2500,
    iva: 400,
    estado: "vigente",
    direccion: "recibido" as const,
  },
  {
    uuid: "cfdi-demo-001",
    tipo_comprobante: "Ingreso",
    serie_folio: "SER-001",
    fecha: "2026-09-01",
    rfc_emisor: "CCC010101CCC",
    nombre_emisor: "Proveedor ficticio uno",
    rfc_receptor: empresa.rfc,
    nombre_receptor: empresa.razon_social,
    total: 1250,
    iva: 200,
    estado: "vigente",
    direccion: "recibido" as const,
  },
];

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
    } else if (path.endsWith("/cfdis/columnas")) {
      body = {
        encabezado: [
          { clave: "fecha_emision", etiqueta: "Fecha expedición", tipo_dato: "fecha", visible_por_defecto: true, ordenable: true },
          { clave: "serie", etiqueta: "Serie", tipo_dato: "texto", visible_por_defecto: true, ordenable: true },
          { clave: "contraparte", etiqueta: "Nombre", tipo_dato: "texto", visible_por_defecto: true, ordenable: true },
          { clave: "total", etiqueta: "Total", tipo_dato: "moneda", visible_por_defecto: true, ordenable: true },
          { clave: "estado", etiqueta: "Estado", tipo_dato: "catalogo", visible_por_defecto: true, ordenable: false },
        ],
        concepto: [],
      };
    } else if (path.endsWith("/cfdis/resumen")) {
      const sinDatos = { conteo: 0, retencion_iva: null, retencion_ieps: null, retencion_isr: null, traslado_iva: null,
        traslado_ieps: null, traslado_isr: null, total_retenciones: null, subtotal: null, descuento: null, neto: null, total: null };
      body = {
        conteos: { I: 2, E: 0, T: 0, N: 0, P: 0 },
        totales: { periodo: { ...sinDatos, conteo: 2, subtotal: 3250, total: 3750 }, acumulado: sinDatos },
        advertencias: [],
      };
    } else if (path.endsWith("/cfdis")) {
      body = {
        items: cfdiRows.map((r) => ({
          uuid: r.uuid, fecha_emision: `${r.fecha}T10:00:00`, serie: r.serie_folio, contraparte: r.nombre_emisor,
          total: r.total, estado: r.estado,
        })),
        total: cfdiRows.length, pagina: 1, por_pagina: 30,
      };
    } else if (path.endsWith("/periodos")) {
      body = { periodos: ["2026-09"] };
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
    } else if (path.includes("/emitidos")) {
      body = {
        periodo: "2026-09",
        empresa_rfc: empresa.rfc,
        resumen: {
          subtotal: 0,
          iva_trasladado: 0,
          total_facturado: 3750,
          vigentes: 2,
          canceladas: 0,
          total_cfdi_periodo: 0,
          ingreso_neto_periodo: 0,
          num_ingresos: 0,
          num_egresos: 0,
        },
        ingresos: {
          ventas_servicios: [{
            uuid: "emitido-demo",
            serie_folio: "FAC-001",
            fecha: "2026-09-01",
            rfc_receptor: "BBB010101BBB",
            nombre_receptor: "Cliente ficticio",
            subtotal: 1000,
            descuento: 0,
            total: 1160,
            iva: 160,
            metodo_pago: "PUE",
            forma_pago: "03",
            uso_cfdi: "G03",
            moneda: "MXN",
            estado: "vigente",
            estado_pago: "pagado",
            es_anticipo: false,
            es_factura_con_anticipo: false,
          }],
          anticipos: [],
          facturas_con_anticipo: [],
        },
        egresos: { notas_credito: [], aplicaciones_anticipo: [] },
      };
    } else if (path.includes("/recibidos")) {
      body = {
        periodo: "2026-09",
        resumen: {
          subtotal: 0,
          iva_acreditable: 0,
          total: 3750,
          num_compras: 0,
          num_egresos: 0,
          vigentes: 2,
          canceladas: 0,
        },
        compras: [{
          uuid: "recibido-demo",
          serie_folio: "COMP-001",
          fecha: "2026-09-02",
          rfc_emisor: "BBB010101BBB",
          nombre_emisor: "Proveedor ficticio",
          subtotal: 1000,
          total: 1160,
          iva: 160,
          estado: "vigente",
        }],
        egresos: [],
      };
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

test("cédula de IVA consulta el periodo elegido", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cedula-iva?periodo=2026-09`);
  await expect(page.getByText("IVA por pagar")).toBeVisible();
});

test("CFDI emitidos lista el periodo de la URL con totales y pestañas", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await expect(page.getByRole("heading", { name: "Emitidos" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Ingreso\s*2/ })).toBeVisible();
  await expect(page.getByText("Acumulado")).toBeVisible();
  await expect(page.getByText("SER-001")).toBeVisible();
  await expect(page.getByText("01/09/2026")).toBeVisible();
});

test("CFDI recibidos sin periodo en la URL usa el mes actual y lo escribe en la URL", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/recibidos`);
  await expect(page).toHaveURL(/periodo=\d{4}-\d{2}/);
  await expect(page.getByRole("heading", { name: "Recibidos" })).toBeVisible();
});

test("el estado del listado vive en la URL y el periodo viaja por el menú", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await page.getByRole("tab", { name: /Egreso/ }).click();
  await expect(page).toHaveURL(/tipo=E/);
  await page.getByRole("button", { name: "Cancelados" }).click();
  await expect(page).toHaveURL(/estado=cancelado/);
  await page.getByRole("link", { name: /Cédula de IVA/ }).click();
  await expect(page).toHaveURL(/cedula-iva\?periodo=2026-09/);
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
});

test("selector de banco revela campo libre para la opción Otro", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/ingesta`);
  await page.getByRole("combobox", { name: "Banco" }).click();
  await page.getByRole("option", { name: "Otro" }).click();
  await expect(page.getByLabel("Nombre del banco")).toBeVisible();
});

test("la tabla de CFDI ordena y busca en el servidor vía la URL", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos?periodo=2026-09`);
  await expect(page.getByText("SER-002")).toBeVisible();
  await page.getByRole("button", { name: "Total" }).click();
  await expect(page).toHaveURL(/orden=total/);
  await page.getByRole("button", { name: "Total" }).click();
  await expect(page).toHaveURL(/dir=desc/);
  await page.getByRole("searchbox", { name: "Buscar CFDI" }).fill("BBB010101BBB");
  await expect(page).toHaveURL(/q=BBB010101BBB/);
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
  await expect(page.getByText("SER-001")).toBeVisible();
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