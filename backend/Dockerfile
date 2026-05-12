FROM python:3.12-slim

# Evitar que o Python gere ficheiros bytecode (.pyc) e força o output a não ter buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de sistema:
#   ffmpeg        → MoviePy/vídeo (Epic 6.4)
#   WeasyPrint    → libpango, libcairo, libgdk-pixbuf (Epic 6.1 + 6.3)
#   fonts         → fontes para WeasyPrint PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      libffi-dev \
      shared-mime-info \
      fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de artefactos (volume mapeado em produção)
RUN mkdir -p /app/media/artefactos

# Copiar os requerimentos e instalar
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar a aplicação
COPY . .

# Expor a porta 8000 para acesso externo
EXPOSE 8000

# Comando para arrancar a app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
