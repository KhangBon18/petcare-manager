#!/usr/bin/env bash
set -euo pipefail
set +x

usage() {
  printf '%s\n' 'Usage: scripts/demo/classroom.sh --target qa'
  printf '%s\n' 'Creates an isolated QA database; enter r to reset it or q to stop.'
}

if [[ $# -ne 2 || "$1" != "--target" || "$2" != "qa" ]]; then
  usage >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
for command_name in "$PYTHON_BIN" docker; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing prerequisite: %s\n' "$command_name" >&2
    exit 2
  fi
done
if ! docker compose version >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  printf '%s\n' 'Docker Engine and the Docker Compose plugin must be running.' >&2
  exit 2
fi
if ! "$PYTHON_BIN" -c 'import flask, mysql.connector, PIL, cryptography' >/dev/null 2>&1; then
  printf '%s\n' 'Python dependencies are missing. Activate the project venv and install requirements.txt with requirements.lock.' >&2
  exit 2
fi
if [[ "${APP_ENV:-}" == "production" ]]; then
  printf '%s\n' 'Refusing production APP_ENV. Start this launcher from a local QA shell.' >&2
  exit 2
fi
for forbidden_var in DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD PETCARE_TEST_DB_NAME MIGRATION_DB_HOST MIGRATION_DB_PORT MIGRATION_DB_NAME MIGRATION_DB_USER MIGRATION_DB_PASSWORD; do
  if [[ -n "${!forbidden_var:-}" ]]; then
    printf 'Refusing inherited database configuration (%s is set). Unset it and retry.\n' "$forbidden_var" >&2
    exit 2
  fi
done

if [[ -n "${PETCARE_DEMO_ADMIN_PASSWORD:-}" || -n "${PETCARE_DEMO_STAFF_PASSWORD:-}" ]]; then
  if [[ -z "${PETCARE_DEMO_ADMIN_PASSWORD:-}" || -z "${PETCARE_DEMO_STAFF_PASSWORD:-}" ]]; then
    printf '%s\n' 'Supply both demo account passwords or neither.' >&2
    exit 2
  fi
else
  if [[ ! -t 0 ]]; then
    printf '%s\n' 'Interactive input is required for demo passwords; provide both PETCARE_DEMO_*_PASSWORD variables for automation.' >&2
    exit 2
  fi
  read -r -s -p 'Choose admin demo password (16+ characters): ' PETCARE_DEMO_ADMIN_PASSWORD
  printf '\n'
  read -r -s -p 'Choose a different staff demo password (16+ characters): ' PETCARE_DEMO_STAFF_PASSWORD
  printf '\n'
fi
if [[ ${#PETCARE_DEMO_ADMIN_PASSWORD} -lt 16 || ${#PETCARE_DEMO_STAFF_PASSWORD} -lt 16 || "$PETCARE_DEMO_ADMIN_PASSWORD" == "$PETCARE_DEMO_STAFF_PASSWORD" ]]; then
  printf '%s\n' 'Demo passwords must be different and at least 16 characters long.' >&2
  exit 2
fi
export PETCARE_DEMO_ADMIN_PASSWORD PETCARE_DEMO_STAFF_PASSWORD

PORTS="$("$PYTHON_BIN" - <<'PY'
import socket
sockets = []
try:
    for _ in range(3):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sockets.append(sock)
    print(*(sock.getsockname()[1] for sock in sockets))
finally:
    for sock in sockets:
        sock.close()
PY
)"
read -r MYSQL_PORT APP_PORT VISION_PORT <<<"$PORTS"
RUN_TOKEN="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_hex(5))')"
PROJECT="petcare-demo-$(id -u)-$RUN_TOKEN"
DATABASE="petcare_demo_${RUN_TOKEN}_test"
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")" ]] ||
   [[ -n "$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT")" ]]; then
  printf '%s\n' 'Generated QA project identifier already exists; refusing to reuse it.' >&2
  exit 2
fi
QA_RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/petcare-classroom.XXXXXX")"
chmod 700 "$QA_RUN_DIR"
printf '%s\n' 'petcare-classroom-run-v1' >"$QA_RUN_DIR/.petcare-classroom-owned"
mkdir -p "$QA_RUN_DIR/pets" "$QA_RUN_DIR/products" "$QA_RUN_DIR/exports" "$QA_RUN_DIR/logs"
for storage_dir in pets products exports logs; do
  printf '%s\n' 'petcare-classroom-storage-v1' >"$QA_RUN_DIR/$storage_dir/.petcare-classroom-owned"
done
chmod -R go-rwx "$QA_RUN_DIR"

export PETCARE_QA_PROJECT="$PROJECT" PETCARE_QA_DATABASE="$DATABASE" PETCARE_QA_USER=petcare_qa PETCARE_QA_MYSQL_PORT="$MYSQL_PORT"
export PETCARE_QA_MYSQL_PASSWORD="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PETCARE_QA_MYSQL_ROOT_PASSWORD="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(32))')"
export APP_ENV=test PETCARE_DEMO_MODE=1
export DB_HOST=127.0.0.1 DB_PORT="$MYSQL_PORT" DB_NAME="$DATABASE" DB_USER="$PETCARE_QA_USER" DB_PASSWORD="$PETCARE_QA_MYSQL_PASSWORD"
export PETCARE_TEST_DB_NAME="$DATABASE"
export MIGRATION_DB_HOST= MIGRATION_DB_PORT= MIGRATION_DB_NAME= MIGRATION_DB_USER= MIGRATION_DB_PASSWORD=
export SECRET_KEY="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')"
export APP_PORT PUBLIC_BASE_URL="http://127.0.0.1:$APP_PORT"
export COOKIE_SECURE=0 LAN_ACCESS_ENABLED=0
export AI_API_BASE_URL="http://127.0.0.1:$VISION_PORT/v1" AI_API_KEY="$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(32))')"
export AI_MODEL=petcare-local-demo-mock AI_VISION_ENABLED=1 AI_TEST_ALLOW_LOOPBACK_PROVIDER=1
export MAIL_HOST= MAIL_PORT=587 MAIL_USERNAME= MAIL_PASSWORD= MAIL_FROM=
export MAIL_OUTBOX_KEY="$("$PYTHON_BIN" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export TENANT_EXPORT_JOB_KEY="$("$PYTHON_BIN" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export MEDIA_STORAGE_BACKEND=local TENANT_EXPORT_STORAGE_BACKEND=local
export PET_IMAGE_DIR="$QA_RUN_DIR/pets" PRODUCT_IMAGE_DIR="$QA_RUN_DIR/products" TENANT_EXPORT_DIR="$QA_RUN_DIR/exports"
export OPS_METRICS_TOKEN= TRUST_PROXY=0

COMPOSE=(docker compose -p "$PETCARE_QA_PROJECT" -f "$ROOT_DIR/compose.qa-test.yml")
WEB_PID= MAIL_PID= EXPORT_PID= MOCK_PID=

owned_run_dir() {
  [[ -d "$QA_RUN_DIR" && ! -L "$QA_RUN_DIR" && -f "$QA_RUN_DIR/.petcare-classroom-owned" ]] || return 1
  [[ "$(cat "$QA_RUN_DIR/.petcare-classroom-owned")" == 'petcare-classroom-run-v1' ]]
}

stop_services() {
  for service_pid in "$WEB_PID" "$MAIL_PID" "$EXPORT_PID" "$MOCK_PID"; do
    if [[ -n "$service_pid" ]] && kill -0 "$service_pid" 2>/dev/null; then kill -TERM "$service_pid" 2>/dev/null || true; fi
  done
  for service_pid in "$WEB_PID" "$MAIL_PID" "$EXPORT_PID" "$MOCK_PID"; do
    if [[ -n "$service_pid" ]]; then wait "$service_pid" 2>/dev/null || true; fi
  done
  WEB_PID= MAIL_PID= EXPORT_PID= MOCK_PID=
}

remove_owned_storage() {
  owned_run_dir || { printf '%s\n' 'Refusing to remove an unrecognized QA run directory.' >&2; return 1; }
  for storage_dir in pets products exports; do
    target="$QA_RUN_DIR/$storage_dir"
    [[ -d "$target" && ! -L "$target" && -f "$target/.petcare-classroom-owned" ]] || {
      printf 'Refusing to remove unrecognized QA storage: %s\n' "$storage_dir" >&2; return 1;
    }
    [[ "$(cat "$target/.petcare-classroom-owned")" == 'petcare-classroom-storage-v1' ]] || return 1
    rm -rf -- "$target"
    mkdir -m 700 "$target"
    printf '%s\n' 'petcare-classroom-storage-v1' >"$target/.petcare-classroom-owned"
  done
}

wait_for_http() {
  local url="$1" expected="$2" attempt
  for ((attempt = 1; attempt <= 45; attempt++)); do
    if "$PYTHON_BIN" -c 'import json,sys; from urllib.request import urlopen; r=urlopen(sys.argv[1],timeout=1); p=json.loads(r.read(4096)); assert r.status==int(sys.argv[2]) and p.get("status") in {"ready","ok"}' "$url" "$expected" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

start_services() {
  "$PYTHON_BIN" -m scripts.demo.vision_mock --port "$VISION_PORT" >"$QA_RUN_DIR/logs/vision-mock.log" 2>&1 &
  MOCK_PID=$!
  wait_for_http "http://127.0.0.1:$VISION_PORT/healthz" 200 || {
    printf 'Local Vision mock did not start; inspect %s/logs/vision-mock.log\n' "$QA_RUN_DIR" >&2; return 1;
  }
  "$PYTHON_BIN" -m petcare.services.mail_worker --poll-seconds 3 >"$QA_RUN_DIR/logs/mail-worker.log" 2>&1 &
  MAIL_PID=$!
  "$PYTHON_BIN" -m petcare.services.tenant_export_worker_cli --poll-seconds 3 >"$QA_RUN_DIR/logs/export-worker.log" 2>&1 &
  EXPORT_PID=$!
  "$PYTHON_BIN" "$ROOT_DIR/run.py" >"$QA_RUN_DIR/logs/web.log" 2>&1 &
  WEB_PID=$!
  wait_for_http "$PUBLIC_BASE_URL/readyz" 200 || {
    printf 'Flask did not become ready; inspect %s/logs/web.log\n' "$QA_RUN_DIR" >&2; return 1;
  }
  "$PYTHON_BIN" "$ROOT_DIR/run.py" prepare-demo --json >/dev/null
  wait_for_http "$PUBLIC_BASE_URL/workersz" 200 || {
    printf 'Local workers did not become ready; inspect %s/logs/*worker.log\n' "$QA_RUN_DIR" >&2; return 1;
  }
}

cleanup() {
  local exit_status=$?
  trap - EXIT INT TERM
  stop_services
  "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true
  if owned_run_dir; then rm -rf -- "$QA_RUN_DIR"; fi
  exit "$exit_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker compose -p "$PETCARE_QA_PROJECT" -f "$ROOT_DIR/compose.qa-test.yml" config --quiet

start_database() {
  "${COMPOSE[@]}" up -d --wait mysql
  "$PYTHON_BIN" -m petcare.database.initialize
  "$PYTHON_BIN" -m petcare.database.seed
}

reset_demo() {
  printf '%s\n' 'Stopping only this disposable QA project and resetting its tmpfs database.'
  stop_services
  "${COMPOSE[@]}" down --remove-orphans
  remove_owned_storage
  start_database
  start_services
  printf 'Reset complete. Open %s\n' "$PUBLIC_BASE_URL"
}

start_database
start_services
printf '\nQA demo ready at %s\n' "$PUBLIC_BASE_URL"
printf '%s\n' 'Demo sign-in names: admin and staff1 (passwords supplied privately at launch).'
printf '%s\n' 'AI Assistant uses local deterministic database services. Vision uses a loopback-only fixed mock, not a real model.'
printf 'QA logs are private to this run: %s/logs\n' "$QA_RUN_DIR"
printf '%s\n' 'Enter r to reset this temporary QA demo; enter q or Ctrl-C to stop and clean up.'

while true; do
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    printf 'Flask stopped unexpectedly; inspect %s/logs/web.log\n' "$QA_RUN_DIR" >&2
    exit 1
  fi
  read -r -p 'petcare-demo> ' action || break
  case "$action" in
    r|reset) reset_demo ;;
    q|quit|stop) break ;;
    *) printf '%s\n' 'Commands: r/reset or q/quit/stop.' ;;
  esac
done
