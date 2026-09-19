#!/usr/bin/env bash
# Fold a Vonage Application private key (PEM) into the repo-root .env.
#
# The key never reaches stdout, a log, or a shell history entry: it is read from
# the file you name and written straight into .env. The only thing printed is the
# shape of what landed (byte count, line count) so you can tell it worked.
#
#   usage: scripts/set-vonage-key.sh <path-to-private.key> [application-id]
#          scripts/set-vonage-key.sh --paste [application-id]   # paste, then Ctrl-D
#
# stream-vonage reads VONAGE_PRIVATE_KEY as the PEM *contents*, and normalises a
# literal "\n" back to a real newline (settings.py: vonage_private_key_pem), so
# the key is stored here as one escaped line — multi-line values in a .env are
# parsed inconsistently by docker compose and are not worth the risk.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file="$root/.env"
tmp_key=""
cleanup() { [[ -n "$tmp_key" ]] && rm -f "$tmp_key"; }
trap cleanup EXIT

if [[ ${1:-} == "--paste" ]]; then
  # Paste mode: for when scp/ssh into this box is not available. Read the PEM
  # from stdin into a 600 temp file, then carry on as if it had been a file all
  # along. Run this in a PLAIN SHELL — never in an agent's chat box, or the key
  # becomes part of that conversation's transcript.
  app_id=${2:-}
  tmp_key=$(mktemp); chmod 600 "$tmp_key"
  if [[ -t 0 ]]; then
    echo "Paste the whole private key, including the BEGIN and END lines."
    echo "Then press Enter, then Ctrl-D on an empty line."
    echo
  fi
  cat > "$tmp_key"
  key_path="$tmp_key"
  [[ -s "$key_path" ]] || { echo "nothing was pasted" >&2; exit 1; }
else
  key_path=${1:?usage: set-vonage-key.sh <path-to-private.key|--paste> [application-id]}
  app_id=${2:-}
fi

[[ -f "$key_path" ]] || { echo "no such file: $key_path" >&2; exit 1; }
[[ -f "$env_file" ]] || { echo "no .env at $env_file" >&2; exit 1; }

# Header check only — the first line tells us this is a private key and not, say,
# the public half or an HTML error page. Never the body.
head -1 "$key_path" | grep -q 'BEGIN.*PRIVATE KEY' || {
  echo "that file does not start with a PRIVATE KEY header — wrong file?" >&2
  exit 1
}

cp -p "$env_file" "$env_file.bak"
chmod 600 "$env_file.bak"

python3 - "$env_file" "$key_path" "$app_id" <<'PY'
import sys, pathlib
env_path, key_path, app_id = sys.argv[1], sys.argv[2], sys.argv[3]
pem = pathlib.Path(key_path).read_text().strip()
escaped = pem.replace("\n", "\\n")

lines = pathlib.Path(env_path).read_text().splitlines()
drop = {"VONAGE_PRIVATE_KEY"} | ({"VONAGE_APPLICATION_ID"} if app_id else set())
kept = [l for l in lines if l.split("=", 1)[0] not in drop]

if app_id:
    kept.append(f"VONAGE_APPLICATION_ID={app_id}")
kept.append(f"VONAGE_PRIVATE_KEY={escaped}")
pathlib.Path(env_path).write_text("\n".join(kept) + "\n")

print(f"VONAGE_PRIVATE_KEY written: {len(pem)} bytes, {pem.count(chr(10)) + 1} PEM lines")
if app_id:
    print(f"VONAGE_APPLICATION_ID written: {app_id}")
PY

chmod 600 "$env_file"
echo ".env now 600 (was group-readable). Backup at .env.bak — delete it once this works."
echo "next: docker compose up -d --wait stream-vonage && curl -s localhost:8792/healthz"
