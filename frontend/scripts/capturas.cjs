// Capturas de todas las pantallas de FiscalCore para compararlas contra la
// plataforma de referencia al cierre de cada fase (ver
// docs/superpowers/specs/2026-10-01-paridad-y-mejoras-roadmap.md).
//
// Requiere el stack local arriba (./dev.sh). Uso, desde frontend/:
//   FC_EMAIL=... FC_PASSWORD=... node scripts/capturas.cjs
// Opcionales: FC_PERIODO (YYYY-MM, por defecto el mes actual), FC_URL
// (por defecto http://localhost:3000) y FC_OUT (por defecto ./capturas,
// ignorado por git).
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

const URL_BASE = process.env.FC_URL ?? "http://localhost:3000";
const PERIODO = process.env.FC_PERIODO ?? new Date().toISOString().slice(0, 7);
const OUT = path.resolve(process.env.FC_OUT ?? "capturas");
const PAGINAS = [
  "dashboard",
  "cfdi",
  "cfdi/emitidos",
  "cfdi/recibidos",
  "cfdi/nomina",
  "ingesta",
  "conciliacion",
  "cedula-iva",
];

(async () => {
  const { FC_EMAIL, FC_PASSWORD } = process.env;
  if (!FC_EMAIL || !FC_PASSWORD) {
    console.error("Faltan FC_EMAIL y FC_PASSWORD.");
    process.exit(1);
  }
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });
  try {
    await page.goto(`${URL_BASE}/login`);
    await page.locator("#email").fill(FC_EMAIL);
    await page.locator("#password").fill(FC_PASSWORD);
    await page.locator("button[type=submit]").click();
    await page.waitForFunction(() => localStorage.getItem("fiscalcore.session") !== null, null, {
      timeout: 15_000,
    });
    const empresas = await page.evaluate(
      () => JSON.parse(localStorage.getItem("fiscalcore.session")).empresas,
    );
    if (!empresas.length) throw new Error("El usuario no tiene empresas vinculadas.");
    const empresaId = empresas[0].empresa_id;

    await page.goto(`${URL_BASE}/empresas`);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: path.join(OUT, "01-empresas.png"), fullPage: true });

    let n = 2;
    for (const pagina of PAGINAS) {
      await page.goto(`${URL_BASE}/empresas/${empresaId}/${pagina}`);
      await page.waitForLoadState("networkidle");
      const periodo = page.locator("input[type=month]").first();
      if (await periodo.count()) {
        await periodo.fill(PERIODO);
        await page.waitForLoadState("networkidle");
      }
      const archivo = `${String(n++).padStart(2, "0")}-${pagina.replace("/", "-")}.png`;
      await page.screenshot({ path: path.join(OUT, archivo), fullPage: true });
      console.log(archivo);
    }
    console.log(`Capturas de ${PERIODO} en ${OUT}`);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
