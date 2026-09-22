#!/usr/bin/env bash
# Is this box ready to bring Karen into a Google Meet? Checks, reports, changes nothing.
#
# One PASS/FAIL line per check; exit 1 if anything FAILed. Settings are checked for
# PRESENCE only — no value is ever printed, and .env is never read by this script: the
# variables reach us through `docker compose config`, which is the same interpolation
# `up` will do, so what is checked is what will run.
#
# Usage:  scripts/demo-preflight.sh [-h]
# Then:   scripts/demo-up.sh          (runs this first, then brings the `meet` profile up)
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root/compose.yaml"
profile=meet
fails=0

pass() { printf 'PASS  %-34s %s\n' "$1" "${2:-}"; }
fail() { printf 'FAIL  %-34s %s\n' "$1" "${2:-}"; fails=$((fails + 1)); }
compose() { docker compose -f "$compose_file" --profile "$profile" "$@"; }

# --- 1. docker + compose -------------------------------------------------------
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  pass "docker" "$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo present)"
else
  fail "docker" "not installed, or the daemon is not reachable by this user"
  echo "cannot continue without docker" >&2
  exit 1
fi
if docker compose version >/dev/null 2>&1; then
  pass "docker compose" "$(docker compose version --short 2>/dev/null || echo present)"
else
  fail "docker compose" "the compose plugin is missing"
  exit 1
fi

# One interpolated view of the stack, used by every check below. `--format json` is what
# lets us read ports and images without parsing YAML by hand.
if config_err=$(compose config --quiet 2>&1); then
  pass "compose --profile $profile config" "validates"
else
  fail "compose --profile $profile config" "${config_err##*$'\n'}"
  exit 1
fi
config_json=$(compose config --format json)

# Small helpers over the JSON. python3 is already a hard dependency of scripts/.
cfg() { printf '%s' "$config_json" | python3 -c "$1" "${@:2}"; }

# --- 2. images ---------------------------------------------------------------
missing_images=()
while IFS= read -r image; do
  [[ -n $image ]] || continue
  if docker image inspect "$image" >/dev/null 2>&1; then
    pass "image $image" "built"
  else
    fail "image $image" "not built — scripts/demo-up.sh --build, or: docker compose --profile $profile build"
    missing_images+=("$image")
  fi
done < <(cfg 'import json,sys
c=json.load(sys.stdin)
seen=set()
for s in c["services"].values():
    i=s.get("image")
    if i and "build" in s and i not in seen:
        seen.add(i); print(i)')

# --- 3. required settings: presence only -----------------------------------------
# Read from the ears-meet service's environment after interpolation. The value is
# compared to "" inside python and only the verdict comes out.
env_set() {
  cfg 'import json,sys
c=json.load(sys.stdin)
v=c["services"][sys.argv[1]]["environment"].get(sys.argv[2],"")
sys.exit(0 if v not in ("",None) else 1)' "$1" "$2"
}
if env_set ears-meet MEET_URL; then
  pass "MEET_URL" "set"
else
  fail "MEET_URL" "not set — the Meet link, in .env at the repo root"
fi

# The bind-mount source for /profile is MEET_PROFILE_HOST_DIR after interpolation.
profile_dir=$(cfg 'import json,sys
c=json.load(sys.stdin)
for v in c["services"]["ears-meet"].get("volumes",[]):
    if v.get("target")=="/profile": print(v.get("source","")); break')
if [[ ! -d $profile_dir && $profile_dir == "$root/secrets/meet-profile" ]]; then
  fail "MEET_PROFILE_HOST_DIR" "not set, and the default ./secrets/meet-profile is absent (docs/EARS-MEET.md §6.1)"
elif [[ ! -d $profile_dir ]]; then
  fail "MEET_PROFILE_HOST_DIR" "set, but the directory does not exist"
elif [[ -z $(ls -A "$profile_dir" 2>/dev/null) ]]; then
  fail "MEET_PROFILE_HOST_DIR" "set, but the directory is empty — run \`just login\` in packages/ears-meet"
elif [[ " ${missing_images[*]:-} " != *" gavel-ears-meet:local "* ]] \
  && ! docker run --rm --entrypoint sh -v "$profile_dir:/profile" gavel-ears-meet:local -c 'test -w /profile' 2>/dev/null; then
  # Chromium writes SingletonLock & co. into the profile as the image's `pwuser` (uid 1001);
  # a directory copied over as your own user is read-only to it and the join crashes.
  fail "MEET_PROFILE_HOST_DIR" "exists, but not writable by the container's pwuser (uid 1001) — sudo chown -R 1001:1001 \"\$MEET_PROFILE_HOST_DIR\""
else
  pass "MEET_PROFILE_HOST_DIR" "exists, non-empty, writable by the container"
fi

# --- 4. the still Karen shows as her camera --------------------------------------
face=$(cfg 'import json,sys
c=json.load(sys.stdin)
print(c["services"]["ears-meet"]["environment"].get("MEET_FACE_IMAGE",""))')
case $face in
  assets/persona/*)
    if [[ -f $root/$face ]]; then
      pass "MEET_FACE_IMAGE" "$face"
    else
      fail "MEET_FACE_IMAGE" "$face is not in assets/persona/ (have: $(cd "$root/assets/persona" && ls *.png | tr '\n' ' '))"
    fi ;;
  "") fail "MEET_FACE_IMAGE" "empty — Karen would join camera-off" ;;
  *) fail "MEET_FACE_IMAGE" "$face — must be a path under assets/persona/, that is what the image carries" ;;
esac

# --- 5. host ports -------------------------------------------------------------
# Every port the stack publishes must be free, unless it is held by this very stack
# (a second run against a live stack is not a failure).
ours=$(compose ps --format json 2>/dev/null | python3 -c '
import json,sys
ports=set()
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    for c in (json.loads(line) if line.startswith("[") else [json.loads(line)]):
        for p in c.get("Publishers") or []:
            if p.get("PublishedPort"): ports.add(str(p["PublishedPort"]))
print(" ".join(sorted(ports)))' || true)
listening() {
  # bash's /dev/tcp: a connect that succeeds means something is listening.
  (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null
}
while read -r service host port; do
  [[ -n $port ]] || continue
  if [[ " $ours " == *" $port "* ]]; then
    pass "port $host:$port ($service)" "held by this stack"
  elif listening "$host" "$port"; then
    fail "port $host:$port ($service)" "in use by something else"
  else
    pass "port $host:$port ($service)" "free"
  fi
done < <(cfg 'import json,sys
c=json.load(sys.stdin)
for name,s in c["services"].items():
    for p in s.get("ports",[]):
        print(name, p.get("host_ip") or "0.0.0.0", p.get("published",""))')

# --- 6. the brain must listen to THIS ears -------------------------------------
# brain's wire URL is ${EARS_WIRE_URL:-ws://ears:8787}. Left alone it is the Discord
# ears: Karen would join the Meet and the brain would never hear a word of it.
wire=$(cfg 'import json,sys
c=json.load(sys.stdin)
print(c["services"]["brain"]["environment"].get("EARS_WIRE_URL",""))')
case $wire in
  ws://ears-meet:8787) pass "EARS_WIRE_URL" "brain -> ears-meet" ;;
  *)
    fail "EARS_WIRE_URL" "brain -> $wire"
    cat >&2 <<'WARN'

  !!  EARS_WIRE_URL points the brain at the Discord ears, not at ears-meet.  !!
  !!  With the meet profile the brain would hear nothing from the call.       !!
  !!  In .env:  EARS_WIRE_URL=ws://ears-meet:8787                              !!
  !!            EARS_HTTP_URL=http://ears-meet:8787                            !!

WARN
    ;;
esac

# --- 7. the external Traefik network compose expects -----------------------------
net=$(cfg 'import json,sys
c=json.load(sys.stdin)
print(c["networks"]["traefik-public"].get("name","traefik-public"))')
if docker network inspect "$net" >/dev/null 2>&1; then
  pass "network $net" "exists"
else
  fail "network $net" "missing (external) — docker network create $net"
fi

echo
if (( fails > 0 )); then
  echo "preflight: $fails FAIL"
  exit 1
fi
echo "preflight: all PASS"
