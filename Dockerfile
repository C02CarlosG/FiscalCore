# ── Etapa 1: Build del frontend ──────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY index.html vite.config.js tailwind.config.js postcss.config.js ./
COPY src/ ./src/
RUN npm run build

# ── Etapa 2: Imagen de producción ────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Dependencias del sistema para psycopg2 y pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código backend
COPY backend/ ./backend/
COPY database/ ./database/

# Frontend compilado
COPY --from=frontend-build /app/dist ./dist

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "backend.main_api:app", "--host", "0.0.0.0", "--port", "8080"]
