.PHONY: up down test train bench seed lint
up:        ; docker compose up --build
down:      ; docker compose down
test:      ; cd backend && python -m pytest -q
train:     ; cd backend && python -m app.ml.train
bench:     ; cd backend && python -m sim.benchmark --days 20
seed:      ; cd backend && python -m scripts.seed_db
dev-api:   ; cd backend && uvicorn app.main:app --reload
dev-web:   ; cd frontend && npm run dev
