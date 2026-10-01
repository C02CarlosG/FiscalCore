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
    } else if (path.includes("/cfdi/nomina")) {
      body = {
        periodo: "2026-09",
        empresa_rfc: empresa.rfc,
        resumen: { total_nomina: 2500, num_recibos: 1, vigentes: 1, canceladas: 0 },
        recibos: [{
          uuid: "nomina-demo",
          serie_folio: "NOM-001",
          fecha: "2026-09-15",
          rfc_receptor: "DDD010101DDD",
          nombre_receptor: "Persona ficticia",
          subtotal: 2300,
          total: 2500,
          estado: "vigente",
        }],
      };
    } else if (path.includes("/cfdi/visor")) {
      body = {
        periodo: "2026-09",
        empresa_rfc: empresa.rfc,
        resumen: {
          total_cfdi: 2,
          emitidos: 0,
          recibidos: 2,
          vigentes: 2,
          canceladas: 0,
          monto_total: 3750,
        },
        cfdi: cfdiRows,
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
  await expect(page.getByText("Score fiscal actual")).toBeVisible();
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
  await page.goto(`/empresas/${empresaId}/cedula-iva`);
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("IVA por pagar")).toBeVisible();
});

test("visor SAT consulta CFDI por periodo", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi`);
  await expect(page.getByRole("heading", { name: "Visor SAT" })).toBeVisible();
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("Total CFDI")).toBeVisible();
});

test("CFDI emitidos consulta el periodo elegido", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/emitidos`);
  await expect(page.getByRole("heading", { name: "CFDI Emitidos" })).toBeVisible();
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("Total facturado")).toBeVisible();
});

test("CFDI recibidos consulta el periodo elegido", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/recibidos`);
  await expect(page.getByRole("heading", { name: "CFDI Recibidos" })).toBeVisible();
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("IVA acreditable", { exact: true })).toBeVisible();
});

test("CFDI nómina consulta el periodo elegido", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi/nomina`);
  await expect(page.getByRole("heading", { name: "CFDI Nómina" })).toBeVisible();
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("Total nómina")).toBeVisible();
  await expect(page.getByText("NOM-001")).toBeVisible();
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

test("la tabla del Visor SAT busca y ordena filas CFDI", async ({ page }) => {
  await page.goto(`/empresas/${empresaId}/cfdi`);
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
  await expect(page.getByText("SER-002")).toBeVisible();
  await page.getByRole("button", { name: "Total" }).click();
  await expect(page.getByRole("row").nth(1)).toContainText("SER-001");
  await page.getByRole("button", { name: "Total" }).click();
  await expect(page.getByRole("row").nth(1)).toContainText("SER-002");
  await page.getByRole("textbox", { name: "Buscar por folio, RFC o nombre..." }).fill("BBB010101BBB");
  await expect(page.getByRole("row")).toHaveCount(2);
  await expect(page.getByText("SER-002")).toBeVisible();
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
  await page.goto(`/empresas/${empresaId}/cfdi`);
  await page.getByLabel("Periodo (YYYY-MM)").fill("2026-09");
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