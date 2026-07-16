# Migración del entorno de desarrollo: WSL → Windows nativo

Guía para dejar de trabajar en FiscalCore desde WSL y continuar 100% en Windows
nativo (PowerShell/cmd, Python de Windows, sin distro Linux). Generada el
2026-07-16 tras auditar el repo real (`git status`, `git stash list`,
`git branch -vv`, dependencias, scripts `dev.*`).

## 0. Antes de tocar nada: resolver lo que NO está en GitHub

Esto es lo único que se perdería si simplemente clonas el repo en Windows sin
revisarlo primero, porque vive solo en este disco WSL:

- **`git stash@{0}`** en `main` — WIP del 2026-06-21 "feat: rediseño UI/UX
  completo — fuentes, accesibilidad y componentes unificados". Toca casi
  todo `backend/` y archivos del frontend legacy (`src/*.jsx` → `_legacy/`).
  Es anterior a la limpieza del frontend que ya está en el historial de
  `main`, así que probablemente esté superado — pero no lo descarté por ti.
  Ya lo exporté a un `.patch` como respaldo (ver abajo). **Decide:** ¿lo
  aplicas y revisas, o lo descartamos (`git stash drop`)?
- **`feat/modulo-cedula-iva`** tiene 1 commit sin pushear
  (`31869d7 docs: spec de diseño — reescritura de frontend`). Súbelo con
  `git push origin feat/modulo-cedula-iva` antes de migrar o quedará
  atrapado en esta máquina.
- Verifiqué que **no hay más ramas con commits sin pushear** ni otros
  stashes.

Respaldo del stash: `/home/carlo/stash-wip-2026-06-21.patch` (432 KB).
Cópialo también a Windows si quieres conservarlo para revisión posterior.

## 1. Lo que NO necesitas migrar manualmente

- **Todo el código e historial**: vive en GitHub
  (`git@github.com:C02CarlosG/FiscalCore.git`). Un `git clone` en Windows
  trae todo, incluidas las 5 ramas con PRs abiertos (#3, #4, #5, #7, #8).
- **Las ~25 carpetas ocultas** de otras herramientas de IA
  (`.goose/`, `.kiro/`, `.windsurf/`, etc.) que ves en este directorio
  **no están trackeadas en git** — no se van a clonar, no hay que
  limpiarlas ni migrarlas.
- **El código del backend no tiene dependencias de Unix**: no hay rutas
  hardcodeadas (`/tmp`, `/bin`, etc.), no hay `subprocess`/`os.system`, y
  el manejo de archivos (`backend/routers/empresas.py`,
  `backend/fiel_store.py`) usa `pathlib.Path`, que es multiplataforma. El
  backend corre igual en Windows nativo.

## 2. Software a instalar en Windows

| Herramienta | Notas |
|---|---|
| **Git for Windows** | Incluye Git Bash y el credential manager. |
| **Python 3.11** (python.org, no Microsoft Store) | Marca "Add python.exe to PATH" y "py launcher" en el instalador — `dev.bat` ya usa `py -3.11`. |
| **Docker Desktop** (recomendado) | Para `docker compose up -d db` (Postgres). Usa WSL2 como backend internamente, pero eso **no cuenta como "desarrollar desde WSL"** — tú sigues trabajando 100% desde Windows/PowerShell; WSL2 queda como motor invisible de Docker. Alternativa: instalar PostgreSQL 15 nativo para Windows si quieres cero dependencia de WSL2. |
| **VS Code** (o tu editor) | Sin la extensión "Remote - WSL"; ábrelo directo sobre la carpeta de Windows. |
| **GitHub CLI (`gh`)** | Si usas `gh pr create` / `gh pr list` como en esta sesión. `gh auth login` de nuevo en Windows. |

## 3. Clonar y configurar

```powershell
git clone git@github.com:C02CarlosG/FiscalCore.git
cd FiscalCore
```

El remoto usa **SSH** (`git@github.com:...`). Necesitas una key SSH nueva en
Windows (o reusar la de WSL copiándola a `%USERPROFILE%\.ssh\`) y agregarla
en GitHub → Settings → SSH keys. Alternativa más simple: cambiar el remoto a
HTTPS y autenticar con el credential manager de Git for Windows:

```powershell
git remote set-url origin https://github.com/C02CarlosG/FiscalCore.git
```

Configura identidad y line endings (el repo ya tiene `core.autocrlf`
sin forzar; en Windows es buena práctica dejar que Git normalice):

```powershell
git config user.name "C02CarlosG"
git config user.email "carlos.ghernandez22@gmail.com"
git config core.autocrlf true
```

## 4. Entorno Python

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Todas las dependencias de `requirements.txt` (`psycopg2-binary`, `bcrypt`,
`python-jose[cryptography]`, `pdfplumber`, `satcfdi`, etc.) tienen wheels
precompilados para Windows — no deberías necesitar compilador ni Build
Tools de Visual Studio.

O simplemente corre `dev.bat` (ver sección 6) — ya lo actualicé para que
cree el venv e instale dependencias automáticamente la primera vez, igual
que hace `dev.sh` en WSL.

## 5. Variables de entorno

No existe `.env` en el repo (correctamente, está en `.gitignore`). Crea tu
propio `.env` en la raíz basado en `.env.example`, con estas variables que
el backend efectivamente lee:

- `DATABASE_URL`
- `JWT_SECRET`
- `FIEL_ENCRYPTION_KEY`
- `SEED_ADMIN_EMAIL`
- `SEED_ADMIN_PASSWORD`
- `ALLOWED_ORIGINS`
- `RAILWAY_ENVIRONMENT` (solo aplica en despliegue Railway, no en local)

**Estos valores son secretos** (contraseñas, llaves) — no te los copio ni
los leo desde aquí. Transfiérelos tú mismo desde tu `.env`/`.env.local`
actual en WSL a Windows por un canal seguro (no por git, no por chat):
USB cifrado, gestor de contraseñas, o `scp`/`rsync` si tienes ambas
máquinas en la misma red.

Lo mismo aplica a **`uploads/`** (constancias de situación fiscal) y a
cualquier **archivo FIEL** (`.cer`/`.key`) que tengas localmente para
pruebas: ambos están gitignored, así que no viajan con `git clone`. Cópialos
manualmente si los necesitas para seguir probando en Windows.

## 6. Base de datos

```powershell
docker compose up -d db
```

Esto levanta Postgres 15 en `localhost:5432` (usuario/clave `postgres`,
db `fiscalcore`) con un volumen Docker nuevo — vacío la primera vez. El
backend aplica las migraciones de `database/migrations/` automáticamente al
arrancar (`backend/db.py: init_db()`), no hace falta correr nada manual.

Si quieres los **datos** que ya tienes en el Postgres de WSL (no solo el
schema): hazles un dump antes de abandonar esa máquina —
`docker exec fiscalcore_db pg_dump -U postgres fiscalcore > respaldo.sql` —
y restáuralo en el contenedor de Windows con
`docker exec -i fiscalcore_db psql -U postgres fiscalcore < respaldo.sql`.
Si Docker Desktop en Windows apunta al **mismo** motor/volúmenes que usabas
desde WSL (integración WSL2 sin reinstalar Docker Desktop), ni siquiera
necesitas el dump — los datos ya están ahí.

## 7. Levantar el backend

```powershell
dev.bat
```

o directo:

```powershell
.venv\Scripts\python -m uvicorn backend.main_api:app --reload --port 8000
```

Backend en `http://localhost:8000/docs`.

## 8. Tests

```powershell
.venv\Scripts\python -m pytest -m "not db"   # rápido, sin Postgres
.venv\Scripts\python -m pytest -m db         # requiere docker compose up -d db
.venv\Scripts\python -m pytest               # suite completa
```

## 9. Checklist final

- [ ] Decidir qué hacer con el stash WIP (`git stash drop` o revisar el patch)
- [ ] `git push origin feat/modulo-cedula-iva`
- [ ] Instalar Git for Windows, Python 3.11, Docker Desktop, VS Code, `gh`
- [ ] Clonar el repo (SSH key nueva o remoto en HTTPS)
- [ ] `py -3.11 -m venv .venv` + instalar dependencias (o dejar que `dev.bat` lo haga solo)
- [ ] Crear `.env` con las 6 variables listadas, copiadas de forma segura desde WSL
- [ ] Copiar manualmente `uploads/` y archivos FIEL de prueba si los necesitas
- [ ] `docker compose up -d db` (+ restaurar dump si quieres los datos existentes)
- [ ] `dev.bat` y confirmar `http://localhost:8000/docs`
- [ ] `pytest -m "not db"` en verde
- [ ] `gh auth login` si vas a seguir creando PRs desde la terminal
