#!/bin/bash
set -e

# 도커 named volume(node_modules)가 비어 있거나 오래된 경우를 대비해 동기화
pnpm install --frozen-lockfile
pnpm run build && pnpm run start

wait