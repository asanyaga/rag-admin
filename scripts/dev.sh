#!/bin/bash

echo "==================================="
echo "RAG Admin - Starting Dev Servers"
echo "==================================="
echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

trap 'kill 0' EXIT

cd backend && uv run uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev &

wait
