#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
[ -f artifacts/models.joblib ] || python -m app.training
uvicorn app.main:app --reload --port 8000 &
cd ../frontend
npm install --no-audit --no-fund
npm run dev
