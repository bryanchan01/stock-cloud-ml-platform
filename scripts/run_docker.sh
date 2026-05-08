#!/usr/bin/env bash
set -euo pipefail

docker compose build
docker compose run --rm stock-ml make smoke

