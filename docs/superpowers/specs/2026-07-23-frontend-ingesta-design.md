# Ingesta de CFDI y estado de cuenta bancario — Fase 2a del frontend

## Contexto

Fase 1 del frontend (`feat/frontend-nextjs`, ver
`docs/superpowers/specs/2026-07-10-reescritura-frontend-design.md`) cubrió login, alta de
empresas, dashboard y cédula de IVA. Las páginas restantes del frontend anterior quedaron
fuera de esa fase.

Esta spec cubre el primer sub-proyecto de la "Fase 2" (ingesta / conciliación / movimientos),
identificado como prerequisito de los otros dos: sin CFDI ni movimientos bancarios cargados no
hay nada que conciliar ni categorizar.

Rama de trabajo: `feat/frontend-ingesta`, creada desde la punta de `feat/frontend-nextjs`.

## Alcance

Una página nueva, mapeada a los dos endpoints de ingesta ya existentes en
`backend/routers/ingesta.py`:

| Endpoint | Función |
|---|---|
| `POST /api/v1/empresas/{empresa_id}/cfdi/upload` | Sube uno o más XML de CFDI para un periodo |
| `POST /api/v1/empresas/{empresa_id}/banco/upload` | Sube un estado de cuenta (`.xlsx`/`.csv`) de un banco para un periodo |

**Explícitamente fuera de esta fase:** conciliación (`/conciliaciones`, `/cierre/{periodo}`),
movimientos y categorización (`/movimientos`, `/categorias`) — son los otros dos sub-proyectos
de la Fase 2, con spec propia posterior. Constancia de situación fiscal, SAT/FIEL, CFDI
emitidos/recibidos, reportes adicionales, riesgos, admin, perfil — fuera de alcance de la Fase 2
completa (ver spec de fase 1).

## Estructura de la página

Página única `/empresas/[empresaId]/ingesta`, bajo el layout protegido `(app)/`, con dos
formularios independientes:

- **Subir CFDI**: input de archivos múltiple (`accept=".xml"`) + selector de periodo
  (`YYYY-MM`, mismo patrón que ya usa `/dashboard`).
- **Subir estado de cuenta**: input de archivo único (`accept=".xlsx,.csv"`) + selector de
  banco + selector de periodo.

Los dos formularios comparten el layout de la página pero no comparten estado: un fallo en uno
no oscurece el resultado del otro. Cada uno mantiene su propio estado de resultado/error.

### Selector de banco

El campo `banco` del backend es un string libre (`bbva`, `santander`, etc., sin enum validado
en la API). El formulario usa un `Select` de shadcn/ui con bancos mexicanos comunes (BBVA,
Santander, Banamex, Banorte, HSBC, Scotiabank) más una opción "Otro" que habilita un `Input`
de texto libre. Esto evita inconsistencias de escritura entre cargas del mismo banco, sin
bloquear bancos no listados.

### Navegación

`EmpresaList.tsx` (Fase 1) gana un link "Ingesta" por fila, apuntando a
`/empresas/${empresa.id}/ingesta` — mismo patrón que tendría un link a cédula de IVA.

### Comportamiento tras subir

Tras una subida exitosa (2xx, con o sin errores parciales), la página se queda en `/ingesta`:
muestra el resumen (`mensaje`, `registros_procesados`, lista de `errores`) y limpia el
formulario correspondiente para permitir otra carga (útil para subir varios periodos o bancos
seguidos). No hay redirección automática.

## Componentes

- `components/ingesta/CfdiUploadForm.tsx` — arma `FormData` con `archivos[]` + `periodo`,
  llama `useSubirCfdi`.
- `components/ingesta/BancoUploadForm.tsx` — arma `FormData` con `archivo` + `banco` +
  `periodo`, llama `useSubirBanco`. Maneja el estado local del select "Otro".
- `components/ingesta/IngestaResultado.tsx` — componente compartido: renderiza `mensaje`,
  `registros_procesados` y la lista de `errores` (strings ya formateados por el backend,
  p. ej. `"archivo.xml: descripción del error"`).
- `hooks/useIngesta.ts` — `useSubirCfdi(empresaId)` y `useSubirBanco(empresaId)`, mutaciones
  de TanStack Query. No invalidan queries existentes en esta fase (no hay página de
  conciliación/movimientos con cache dependiente todavía).

## Tipos nuevos (`types/api.ts`)

```ts
export interface IngestaResponse {
  mensaje: string;
  registros_procesados: number;
  errores: string[];
  periodo: string;
}
```

## Cambio necesario en `lib/api-client.ts`

Hoy `apiFetch` siempre inyecta `Content-Type: application/json`. Para subir archivos el body
debe ser `FormData`, y el browser necesita fijar su propio `Content-Type` (con boundary). Se
ajusta `apiFetch` para omitir el header `Content-Type` cuando `options.body instanceof
FormData`. El resto del wrapper (header `Authorization`, manejo de 401/422, `ApiError`) no
cambia.

## Manejo de errores

- Error de red o 4xx/5xx en la subida (ej. archivo rechazado por extensión/tamaño, backend
  responde 400) → `ApiError` capturado, se muestra con el `ErrorState` ya existente de Fase 1.
- Éxito (2xx) con `errores` no vacío (procesamiento parcial, ej. algunos CFDI con error de
  parseo) → no es una excepción; se muestra en `IngestaResultado` como advertencias junto al
  conteo de procesados.
- 401 → cubierto globalmente por `QueryProvider`/`AuthGuard` (Fase 1), sin cambios.

## Testing

Vitest + React Testing Library, mismo patrón TDD que Fase 1:

- `CfdiUploadForm.test.tsx`: periodo requerido antes de habilitar el envío, arma el `FormData`
  esperado (campo `periodo` + archivos), muestra `errores` parciales sin tratarlos como fallo.
- `BancoUploadForm.test.tsx`: lo mismo + lógica del select "Otro" (habilita/deshabilita el
  input libre, el valor final enviado es el del input cuando se elige "Otro").
- Ajuste a `api-client.test.ts`: nuevo caso que verifica que `apiFetch` no agrega
  `Content-Type` cuando el body es `FormData`, y que sí lo agrega cuando es un objeto (caso
  existente).
- Sin E2E en esta fase (misma decisión que Fase 1).

## Fuera de alcance / decisiones pendientes

- Ninguna decisión de plataforma de deploy nueva (hereda la de Fase 1: deploy-agnóstico).
- Límite de tamaño/cantidad de archivos por carga: se hereda el que ya aplica `validar_upload`
  en el backend; el frontend no agrega un límite adicional en esta fase.
- Historial de cargas anteriores (qué se subió, cuándo) no se muestra en esta página — no hay
  endpoint de backend para listarlo todavía.
