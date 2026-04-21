FROM python:3.12-slim

# Evitar que o Python gere ficheiros bytecode (.pyc) e força o output a não ter buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

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
