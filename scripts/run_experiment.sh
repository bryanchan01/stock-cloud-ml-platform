#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_experiment.sh --limit 10 --model logistic_regression
  bash scripts/run_experiment.sh --limit 50 --model random_forest
  bash scripts/run_experiment.sh --limit 100 --model logistic_regression
EOF
}

LIMIT=""
MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$LIMIT" || -z "$MODEL" ]]; then
  echo "Both --limit and --model are required." >&2
  usage >&2
  exit 2
fi

if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -le 0 ]]; then
  echo "--limit must be a positive integer." >&2
  exit 2
fi

case "$MODEL" in
  logistic_regression|random_forest|baseline)
    ;;
  *)
    echo "--model must be one of: logistic_regression, random_forest, baseline" >&2
    exit 2
    ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP="$(date +"%Y-%m-%d_%H%M%S")"
SAFE_MODEL="$(printf '%s' "$MODEL" | tr -c 'A-Za-z0-9._-' '_')"
RUN_ID="${TIMESTAMP}_limit_${LIMIT}_${SAFE_MODEL}"
EXPERIMENT_DIR="experiments/${RUN_ID}"
LOG_FILE="${EXPERIMENT_DIR}/run.log"
METADATA_FILE="${EXPERIMENT_DIR}/metadata.txt"
STAGE_TIMES_FILE="${EXPERIMENT_DIR}/stage_times.csv"
TOTAL_STARTED_AT=""
TOTAL_RECORDED=0

mkdir -p "$EXPERIMENT_DIR"
touch "$LOG_FILE"
printf 'run_id,ticker_limit,model,stage,runtime_seconds,timestamp,git_commit,hostname\n' > "$STAGE_TIMES_FILE"

copy_artifacts() {
  set +e
  mkdir -p "${EXPERIMENT_DIR}/data" "${EXPERIMENT_DIR}/config" "${EXPERIMENT_DIR}/models"

  if [[ -d data/results ]]; then
    rm -rf "${EXPERIMENT_DIR}/data/results"
    cp -a data/results "${EXPERIMENT_DIR}/data/"
  fi

  if [[ -d data/predictions ]]; then
    rm -rf "${EXPERIMENT_DIR}/data/predictions"
    cp -a data/predictions "${EXPERIMENT_DIR}/data/"
  fi

  if [[ -d "models/${MODEL}" ]]; then
    rm -rf "${EXPERIMENT_DIR}/models/${MODEL}"
    cp -a "models/${MODEL}" "${EXPERIMENT_DIR}/models/"
  fi

  if [[ -f config/config.yaml ]]; then
    cp config/config.yaml "${EXPERIMENT_DIR}/config/config.yaml"
  fi
}

finalize() {
  local exit_code=$?
  if [[ -n "${TOTAL_STARTED_AT}" && "${TOTAL_RECORDED}" -eq 0 ]]; then
    append_stage_time "total_pipeline" "$TOTAL_STARTED_AT" "$(date +%s)"
    TOTAL_RECORDED=1
  fi
  {
    echo
    echo "completed_at=$(date -Is)"
    echo "exit_code=${exit_code}"
  } >> "$METADATA_FILE"
  copy_artifacts
  echo
  echo "Experiment folder: ${EXPERIMENT_DIR}"
  echo "Run log: ${LOG_FILE}"
  echo "Exit code: ${exit_code}"
}
trap finalize EXIT

exec > >(tee -a "$LOG_FILE") 2>&1

GIT_COMMIT="unavailable"
if command -v git >/dev/null 2>&1; then
  GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || printf 'unavailable')"
fi

PYTHON_VERSION="$(python --version 2>&1 || true)"
JAVA_VERSION="$(java -version 2>&1 | head -n 1 || true)"
OS_INFO="$(uname -a 2>/dev/null || true)"
if [[ -f /etc/os-release ]]; then
  OS_PRETTY="$(grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"' || true)"
  OS_INFO="${OS_PRETTY}; ${OS_INFO}"
fi

cat > "$METADATA_FILE" <<EOF
timestamp=${TIMESTAMP}
hostname=$(hostname 2>/dev/null || printf 'unavailable')
git_commit=${GIT_COMMIT}
ticker_limit=${LIMIT}
model=${MODEL}
python_version=${PYTHON_VERSION}
java_version=${JAVA_VERSION}
os_information=${OS_INFO}

commands_executed:
- make download TICKER_LIMIT=${LIMIT}
- make features
- make train MODEL=${MODEL}
- make backtest MODEL=${MODEL}
- make benchmark
EOF

run_cmd() {
  echo
  echo ">>> $*"
  "$@"
}

append_stage_time() {
  local stage="$1"
  local started_at="$2"
  local finished_at="$3"
  local runtime_seconds=$((finished_at - started_at))
  printf '%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$RUN_ID" \
    "$LIMIT" \
    "$MODEL" \
    "$stage" \
    "$runtime_seconds" \
    "$(date -Is)" \
    "$GIT_COMMIT" \
    "$(hostname 2>/dev/null || printf 'unavailable')" \
    >> "$STAGE_TIMES_FILE"
}

run_stage() {
  local stage="$1"
  shift
  local started_at
  local finished_at
  local exit_code
  started_at="$(date +%s)"
  echo
  echo "=== Stage: ${stage} started at $(date -Is) ==="
  set +e
  run_cmd "$@"
  exit_code=$?
  set -e
  finished_at="$(date +%s)"
  append_stage_time "$stage" "$started_at" "$finished_at"
  echo "=== Stage: ${stage} finished in $((finished_at - started_at)) seconds with exit_code=${exit_code} ==="
  return "$exit_code"
}

clean_dir_contents() {
  local dir="$1"
  mkdir -p "$dir"
  find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
}

echo "Starting experiment: limit=${LIMIT}, model=${MODEL}"
echo "Experiment folder: ${EXPERIMENT_DIR}"

echo
echo "Cleaning generated files..."
clean_dir_contents data/raw
clean_dir_contents data/processed
clean_dir_contents data/predictions
clean_dir_contents data/results
rm -rf "models/${MODEL}"
mkdir -p data/raw data/processed data/predictions data/results/plots models

TOTAL_STARTED_AT="$(date +%s)"
run_stage download make download "TICKER_LIMIT=${LIMIT}"
run_stage feature_engineering make features
run_stage train make train "MODEL=${MODEL}"
run_stage backtest make backtest "MODEL=${MODEL}"
run_stage benchmark make benchmark
append_stage_time "total_pipeline" "$TOTAL_STARTED_AT" "$(date +%s)"
TOTAL_RECORDED=1

echo
echo "Experiment completed successfully."
