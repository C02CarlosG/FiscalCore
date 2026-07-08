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

ENV PORT=8080
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn backend.main_api:app --host 0.0.0.0 --port ${PORT:-8080}"]
