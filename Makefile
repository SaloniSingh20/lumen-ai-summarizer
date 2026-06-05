.PHONY: help install dev docker demo test clean

help:
	@echo "AI Video Summarizer — Make targets"
	@echo ""
	@echo "  install    Install Python + Node dependencies"
	@echo "  dev        Start backend + frontend in dev mode (requires Redis)"
	@echo "  docker     Build and start all services via Docker Compose"
	@echo "  demo       Run end-to-end demo on the sample video"
	@echo "  test       Run unit tests"
	@echo "  clean      Remove uploads, keyframes, and DB"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev:
	@echo "Starting Redis (must be running separately or via Docker)"
	@echo "Starting backend API..."
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "Starting Celery worker..."
	cd backend && celery -A worker.tasks.celery_app worker --loglevel=info -c 2 &
	@echo "Starting frontend..."
	cd frontend && npm run dev

docker:
	cp -n .env.example .env || true
	docker-compose up --build

demo:
	@echo "Running end-to-end demo..."
	python scripts/demo.py

test:
	cd backend && python -m pytest tests/ -v

clean:
	rm -rf backend/uploads backend/keyframes backend/data
	@echo "Cleaned up uploads, keyframes, and DB."
