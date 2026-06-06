#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==[1/3] refresh specs (static + Kimovil live if reachable) =="
uv run python -m src.kimovil
echo "==[2/3] refresh listings (Kimovil/Reddit/eBay) =="
uv run python -m src.fetch
echo "==[3/3] generate static report =="
uv run python -m src.generate_report
echo "done. docs/index.html updated."
