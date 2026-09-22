#!/usr/bin/env bash
set -euo pipefail

echo "== Demonstração da API =="
uv run llm-lab-demo

echo
echo "== Avaliação sintética =="
uv run llm-lab-eval

echo
echo "== Métricas (amostra) =="
curl --fail --silent http://127.0.0.1:8000/metrics | grep '^llm_lab_' | head -n 20

