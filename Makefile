.PHONY: setup setup-back setup-front run-back run-front dev clean

# Comandos Globais
# Executa a instalação de ambos (backend e frontend)
setup: setup-back setup-front

# Executa o frontend e o backend em simultâneo
dev:
	@echo "A iniciar o Frontend e o Backend em paralelo..."
	@make -j2 run-back run-front

# ======= BACKEND =======
setup-back:
	@echo "A construir os contentores Docker do Backend (API, DB, Redis)..."
	docker compose build

run-back:
	@echo "A inciar os serviços em Docker (FastAPI, Postgres, Redis)..."
	docker compose up -d

# ======= FRONTEND =======
# NOTA: Como a pasta frontend apenas tem o README por agora, a makefile verifica se existe um package.json antes de executar npm.
setup-front:
	@echo "A configurar o Frontend..."
	@if [ -f frontend/package.json ]; then cd frontend && npm install; else echo "[Aviso] Nenhum package.json encontrado no Frontend. Ignorado."; fi

run-front:
	@echo "A iniciar a aplicação Web (Frontend)..."
	@if [ -f frontend/package.json ]; then cd frontend && npm run dev; else echo "[Aviso] Frontend vazio! Por favor inicializa um projeto frontend (ex: Vite/NextJS) na pasta frontend."; fi

# ======= UTILITÁRIOS =======
# Limpa as pastas geradas (ex: venv, node_modules) e desliga contentores
clean:
	@echo "A limpar ficheiros temporários e contentores..."
	docker compose down -v
	rm -rf backend/venv
	rm -rf frontend/node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} +
