#!/usr/bin/env bash
# CareReady AI — Phase 1 local run
cd "$(dirname "$0")"
pip install -r backend/requirements.txt
cd backend
FRONTEND_DIR=../frontend uvicorn app.main:app --reload --port 8000
