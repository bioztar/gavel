#!/usr/bin/env bash
# Bring Karen up for a live Google Meet: preflight, then the `meet` compose profile,
# then wait for every service to be healthy. One command on stage, no variables to remember.
#
# Usage:  scripts/demo-up.sh [--build] [--timeout SECONDS] [--skip-preflight]
#         scripts/demo-up.sh --down                    tear everything down (volumes kept)
#
#   --build           build the images first (docker compose --profile meet build)
#   --timeout N       how long to wait for health before giving up (default 180)
#   --skip-preflight  you know what you are doing
#
# On any service failing to become healthy: its last 50 log lines, exit 1.
# Safe to run twice: `up -d` is idempotent, a healthy stack just reports its addresses.
set -euo pipefail

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root/compose.yaml"
profile=meet
timeout=180
build=false
preflight=true
down=false

while (( $# )); do
  case $1 in
    -h|--help) usage; exit 0 ;;
    --down) down=true ;;
    --build) build=true ;;
    --skip-preflight) preflight=false ;;
    --timeout) shift; timeout=${1:?--timeout needs a number} ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

compose() { docker compose -f "$compose_file" --profile "$profile" "$@"; }

if $down; then
  # --remove-orphans also catches services that were in the profile last time and are
  # not any more. Named volumes (postgres, recordings) stay: `down -v` is a human decision.
  compose down --remove-orphans
  echo "demo stack is down"
  exit 0
fi

if $build; then
  compose build
fi

if $preflight; then
  "$root/scripts/demo-preflight.sh" || {
    echo "preflight failed — fix the FAIL lines above, then run again" >&2
    exit 1
  }
  echo
fi

# Every service the profile brings up. Compose lists them in dependency order.
services=$(compose config --services)

echo "bringing the $profile profile up..."
compose up -d --remove-orphans --quiet-pull

# --- wait for health -------------------------------------------------------------
# A service is done when it is `healthy`, or `exited (0)` for one-shot jobs (migrations).
# Anything `exited` non-zero, `dead`, or unhealthy is a failure right away; a container
# that never turns healthy before the deadline is a failure too, and so is one Docker had
# to restart (a crash loop briefly looks healthy between crashes).
state_of() {
  docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.State.ExitCode}} {{.RestartCount}}' "$1" 2>/dev/null || echo "missing none 0 0"
}

deadline=$(( $(date +%s) + timeout ))
declare -A done_svc=()
failed=()
while :; do
  pending=()
  for svc in $services; do
    [[ -n ${done_svc[$svc]:-} ]] && continue
    cid=$(compose ps -a -q "$svc" 2>/dev/null | head -n1)
    if [[ -z $cid ]]; then pending+=("$svc"); continue; fi
    read -r status health exit_code restarts <<<"$(state_of "$cid")"
    if (( restarts > 0 )); then
      done_svc[$svc]=fail; failed+=("$svc (restarted ${restarts}x)"); continue
    fi
    case "$status/$health" in
      running/healthy)        done_svc[$svc]=ok ;;
      running/none)           done_svc[$svc]=ok ;;              # no healthcheck defined
      exited/*)
        if [[ $exit_code == 0 ]]; then done_svc[$svc]=ok; else done_svc[$svc]=fail; failed+=("$svc"); fi ;;
      dead/*|restarting/*|running/unhealthy) done_svc[$svc]=fail; failed+=("$svc") ;;
      *)                      pending+=("$svc") ;;
    esac
  done
  (( ${#failed[@]} )) && break
  (( ${#pending[@]} == 0 )) && break
  if (( $(date +%s) >= deadline )); then
    failed+=("${pending[@]}")
    break
  fi
  printf '\r  waiting (%3ds left): %s' "$(( deadline - $(date +%s) ))" "${pending[*]}"
  sleep 3
done
printf '\r%-100s\r' ''

if (( ${#failed[@]} )); then
  for entry in "${failed[@]}"; do
    svc=${entry%% *}
    echo
    echo "==== $entry did not become healthy — last 50 log lines ===="
    compose logs --no-color --tail 50 "$svc" 2>&1 || true
  done
  echo
  echo "FAILED: ${failed[*]}" >&2
  echo "the stack is still up for inspection; scripts/demo-up.sh --down removes it" >&2
  exit 1
fi

# --- where things are -------------------------------------------------------------
host_port() {
  # published host port of a service's container port, from the interpolated config
  compose config --format json | python3 -c '
import json,sys
c=json.load(sys.stdin)
for p in c["services"][sys.argv[1]].get("ports",[]):
    if str(p.get("target"))==sys.argv[2]:
        print("%s:%s" % (p.get("host_ip") or "127.0.0.1", p["published"])); break' "$1" "$2"
}
board=$(host_port stage 8793)
console=$(host_port ears 8787)
brain=$(host_port brain 8788)
meet_wire=$(host_port ears-meet 8787)

echo "all services healthy:"
compose ps --format 'table {{.Service}}\t{{.Status}}'
cat <<EOF

  board (what Karen shares)   http://$board/          demo mode: http://$board/?demo=1
  console (operator)          http://$console/console
  brain state                 http://$brain/state
  ears-meet wire / REST       ws://$meet_wire  http://$meet_wire/api/selfcheck

  Karen is joining MEET_URL now. Admit her from the lobby if Meet asks.
  Follow along:  docker compose --profile $profile logs -f ears-meet
  Tear down:     scripts/demo-up.sh --down
EOF
