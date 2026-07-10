# Reescritura de frontend — Fase 1 (núcleo mínimo)

## Contexto

El frontend original (React + Vite, JS plano) fue eliminado el 2026-07-04 (`3b56009`,
`be13baa`) por estar en desuso; el repo quedó backend-only (FastAPI, deploy en Railway).
Esta spec cubre la primera fase de su reescritura, arrancada en paralelo al trabajo
pendiente de backend (ISR provisional, COGS/deducciones — ver memoria de roadmap).

No hay decisión de plataforma de deploy todavía (Vercel vs Railway); el diseño es
deploy-agnóstico a propósito.

## Alcance (fase 1)

Cuatro páginas, mapeadas 1:1 a endpoints ya existentes en `backend/routers/`:

| Página | Endpoint(s) | Notas |
|---|---|---|
| `/login` | `POST /api/v1/auth/login` | Guarda `access_token` + `empresas`; redirige a `/empresas`. |
| `/empresas` | `GET /api/v1/empresas`, `POST /api/v1/mis-empresas` | Lista + alta manual (RFC, razón social, régimen). |
| `/dashboard` | `GET /api/v1/dashboard/{empresa_id}?periodo=` | Selector de empresa + periodo (`YYYY-MM`). |
| `/empresas/[id]/cedula-iva` | `GET /api/v1/empresas/{empresa_id}/cedula-iva/{periodo}` | Selector de periodo; tabla trasladado/acreditable/prorrateo/resultado. |

**Explícitamente fuera de esta fase:**
- Parseo de constancia de situación fiscal (`POST /api/v1/constancia/parsear`) para
  precargar datos al dar de alta una empresa.
- Resto de las 12 páginas del frontend anterior (banco/conciliación, CFDI, reportes,
  riesgos, admin, perfil, descargas, workspace) — quedan para fases siguientes; varias
  ni tienen módulo de backend completo todavía (ISR, COGS).

## Stack

- **Next.js (App Router) + TypeScript.** Se usa solo como router/bundler — sin SSR de
  datos de negocio, porque el token de sesión vive en `localStorage` (inaccesible desde
  servidor/middleware). Todas las páginas de negocio son Client Components.
- **shadcn/ui + Tailwind** en vez de los componentes UI hechos a mano que tenía el
  frontend anterior (`src/components/ui/*`).
- **TanStack Query** para fetch/cache/invalidación contra la API de FastAPI.
- **Vitest + React Testing Library** para unit tests.

## Arquitectura de carpetas

```
frontend/
  app/
    layout.tsx                  # layout raíz, QueryClientProvider
    login/page.tsx              # pública
    (app)/layout.tsx            # AuthGuard envuelve todo lo protegido
    (app)/dashboard/page.tsx
    (app)/empresas/page.tsx
    (app)/empresas/[empresaId]/cedula-iva/page.tsx
  components/
    ui/                          # shadcn/ui generado
    auth/AuthGuard.tsx
    empresas/EmpresaForm.tsx, EmpresaList.tsx
    cedula-iva/CedulaIvaTable.tsx
  lib/
    api-client.ts                # fetch wrapper + Authorization header
    auth.ts                      # get/set/clear token en localStorage
    query-client.ts
  hooks/
    useAuth.ts, useEmpresas.ts, useDashboard.ts, useCedulaIva.ts
  types/
    api.ts                       # interfaces TS que espejan las respuestas del backend
```

## Auth

- `POST /api/v1/auth/login` responde `{access_token, user_id, email, nombre, empresas: [...]}`.
  Todo se guarda en `localStorage` bajo una sola clave (`fiscalcore.session`).
- `AuthContext` rehidrata la sesión leyendo esa clave al montar la app.
- `AuthGuard` (client component, envuelve `(app)/layout.tsx`): sin token → redirige a
  `/login`. Con token, además llama `GET /api/v1/auth/me` una vez al montar para
  confirmar que sigue vigente; si responde 401, limpia la sesión y redirige.
- Token en `localStorage` (no cookie httpOnly) fue decisión explícita: frontend y
  backend pueden terminar en dominios distintos (Vercel + Railway) y no se quiere tocar
  CORS/cookies del backend para soportarlo. Riesgo aceptado: XSS podría robar el token.

## Flujo de datos

- `lib/api-client.ts`: wrapper delgado sobre `fetch`. Toma `NEXT_PUBLIC_API_URL` del
  entorno y agrega `Authorization: Bearer <token>` leyendo `lib/auth.ts`.
- Un hook de TanStack Query por recurso: `useEmpresas()`, `useDashboard(empresaId, periodo)`,
  `useCedulaIva(empresaId, periodo)`. Query keys como `['dashboard', empresaId, periodo]`.
- La mutación de alta de empresa (`POST /mis-empresas`) invalida `['empresas']` al
  completarse.

## Manejo de errores

- `api-client.ts` normaliza cualquier respuesta no-2xx en `ApiError { status, message }`.
  FastAPI regresa `{"detail": ...}`; los 422 de Pydantic vienen como lista de
  `{loc, msg}` y se mapean a errores por campo en los formularios.
- 401 global → limpia sesión + redirige a `/login` (mismo mecanismo que `AuthGuard`).
- Errores de red/5xx → estado de error compartido por página (`<ErrorState message />`),
  sin reintentos silenciosos.

## Testing

- Vitest + React Testing Library. Cobertura prioritaria de esta fase:
  - `AuthGuard`: redirige a `/login` cuando no hay token.
  - `api-client`: agrega el header `Authorization` correctamente; lanza `ApiError` en
    respuestas no-2xx.
  - Validación de `EmpresaForm` (campos requeridos, formato de RFC).
- Sin E2E en esta fase (decisión explícita del usuario).

## Fuera de alcance / decisiones pendientes

- Plataforma de deploy (Vercel vs Railway) — no bloquea el desarrollo porque el diseño
  es deploy-agnóstico (variable de entorno para la URL base de la API).
- Constancia de situación fiscal (parseo de PDF) en el alta de empresa.
- Páginas restantes del frontend anterior (banco/conciliación, CFDI, reportes, riesgos,
  admin, perfil, descargas, workspace).
