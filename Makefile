.PHONY: setup setup-back setup-front run-back run-front dev clean

# Comandos Globais
setup: setup-back setup-front

dev:
	@echo "A iniciar o Frontend e o Backend em paralelo..."
	@make -j2 run-back run-front

# ======= BACKEND =======
setup-back:
	@echo "A construir os contentores Docker do Backend (API, DB, Redis)..."
	docker compose build

run-back:
	@echo "A iniciar os servicos em Docker (FastAPI, Postgres, Redis)..."
	docker compose up -d

# ======= FRONTEND =======
setup-front:
	@echo "A configurar o Frontend..."
	@if exist frontend\package.json (cd frontend && npm install) else (echo [Aviso] Nenhum package.json encontrado no Frontend. Ignorado.)

run-front:
	@echo "A iniciar a aplicacao Web (Frontend)..."
	@if exist frontend\package.json (cd frontend && npm run dev) else (echo [Aviso] Frontend vazio! Inicializa um projeto frontend na pasta frontend.)

# ======= UTILITARIOS =======
clean:
	@echo "A limpar ficheiros temporarios e contentores..."
	docker compose down -v
	if exist backend\venv rmdir /s /q backend\venv
	if exist frontend\node_modules rmdir /s /q frontend\node_modules
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"