#!/bin/bash
set -e

if [ -f /.dockerenv ]; then
    echo "Running in Docker"
    # 도커 볼륨 재사용 시 .venv 상태가 달라질 수 있어 실행 전에 동기화
    uv sync --frozen --group dev
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000 --reload &
    uv run python watcher.py
else
    echo "Running locally with uv"
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000 --reload &
    uv run python watcher.py
fi
wait
