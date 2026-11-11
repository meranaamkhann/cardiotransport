#!/usr/bin/env bash
set -e
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root/backend"
[ -f artifacts/models.joblib ] || python -m app.training --skip-paper
python -m app.seed
uvicorn app.main:app --reload --port 8000 &
api=$!
trap 'kill $api' EXIT
cd "$root/frontend"
npm install --no-audit --no-fund
npm run dev
