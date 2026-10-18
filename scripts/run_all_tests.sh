#!/usr/bin/env bash
# Runs every automated suite and regenerates all reports from the fresh results.
#
#   ./scripts/run_all_tests.sh            # everything (needs PostgreSQL; k6 optional)
#   SKIP_LOAD=1 ./scripts/run_all_tests.sh   # skip the k6 load tests (about 4 minutes)
#   ALL_BROWSERS=1 ./scripts/run_all_tests.sh # also Firefox + WebKit (run 'npx playwright install' in e2e/ first)
#
# Databases used (created by scripts/setup_databases.sh): vista_test (pytest), vista_e2e (Playwright), vista_perf (load/NFT).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p test-results/perf
DB_BASE="${DB_BASE:-postgresql+psycopg://vista:vista_dev_pw@localhost:5432}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-$DB_BASE/vista_test}"
export E2E_DATABASE_URL="${E2E_DATABASE_URL:-$DB_BASE/vista_e2e}"
export PERF_DATABASE_URL="${PERF_DATABASE_URL:-$DB_BASE/vista_perf}"
PY="${PYTHON:-python3}"
status=0
step() { printf '\n\033[1;34m== %s ==\033[0m\n' "$1"; }

step "1/6 Backend API tests (pytest)"
(cd backend && $PY -m pytest -q --junitxml=../test-results/pytest-junit.xml) || status=1

step "2/6 Frontend lint, type check, unit tests (Vitest) and build"
(cd frontend && npx eslint . && npx tsc -b --noEmit && npx vitest run && npm run build) || status=1

step "3/6 End-to-end browser tests (Playwright)"
(cd e2e && npx playwright test) || status=1

if [[ -z "${SKIP_LOAD:-}" ]] && command -v k6 >/dev/null; then
  step "4/6 Load tests (k6 at 50, 150, 300 concurrent users)"
  for spec in "50 normal-50vus" "150 peak-150vus" "300 peak-300vus"; do
    set -- $spec
    (cd backend && DATABASE_URL="$PERF_DATABASE_URL" $PY -m app.seed --reset >/dev/null)
    if curl -sf localhost:8002/api/health >/dev/null; then echo "Port 8002 is already in use – stop that server first"; status=1; break; fi
    # 'exec' makes the subshell become uvicorn, so $! is the server's own PID
    (cd backend && exec env DATABASE_URL="$PERF_DATABASE_URL" ESCALATION_CHECK_SECONDS=0 \
      "$PY" -m uvicorn app.main:app --port 8002 --workers 2 --no-access-log >/tmp/vista-perf.log 2>&1) &
    PERF_PID=$!
    for _ in $(seq 1 40); do curl -sf localhost:8002/api/health >/dev/null && break; sleep 0.5; done
    k6 run --quiet -e BASE_URL=http://localhost:8002 -e VUS="$1" -e DURATION=60s -e LABEL="$2" perf/load-test.js >/dev/null || true
    kill "$PERF_PID" 2>/dev/null; wait "$PERF_PID" 2>/dev/null
    for _ in $(seq 1 20); do curl -sf localhost:8002/api/health >/dev/null || break; sleep 0.5; done
  done
else
  step "4/6 Load tests skipped (SKIP_LOAD set or k6 not installed) – previous k6 results, if any, are reused"
fi

step "5/6 Non-functional runner (SOS latency, large data, restart, backup/restore, lint, build, setup, privacy)"
$PY scripts/nft_runner.py || status=1

step "6/6 Collect results and generate reports"
$PY scripts/collect_results.py && $PY scripts/generate_reports.py || status=1

echo
echo "Reports: $ROOT/reports   Raw results: $ROOT/test-results"
exit $status
