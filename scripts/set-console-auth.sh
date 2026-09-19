#!/usr/bin/env bash
# Put the ears operator console behind HTTPS basic auth and switch its Traefik route on.
#
# The console is the control plane — it starts and ends sessions and makes Karen speak
# into a live call — so it is never published without a credential.
#
# The password is read with echo off, never appears in argv, never reaches the shell
# history, and is never printed back. Only the bcrypt hash is stored, in the repo-root
# .env, which is gitignored and chmod 600 here.
#
# Usage:  scripts/set-console-auth.sh [username]      (default username: karen)
# Then:   docker compose up -d ears
set -euo pipefail
user=${1:-karen}
env_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"
[[ -f $env_file ]] || { echo "no .env at $env_file" >&2; exit 1; }

read -rsp "password for console user '$user': " pw; echo
read -rsp "again: " pw2; echo
[[ $pw == "$pw2" ]] || { echo "passwords differ" >&2; exit 1; }
[[ ${#pw} -ge 12 ]] || { echo "use at least 12 characters — this route is the control plane" >&2; exit 1; }

# bcrypt via the httpd image so nothing needs installing on the host. The password goes
# in on stdin-free argv inside a throwaway container, not into this shell's history.
line=$(PW="$pw" docker run --rm -i -e PW httpd:2.4-alpine sh -c 'htpasswd -nbB "$0" "$PW"' "$user" | tr -d '\r\n')
unset pw pw2
[[ $line == "$user:"* ]] || { echo "htpasswd produced nothing usable" >&2; exit 1; }

python3 - "$env_file" "$line" <<'PY'
import sys
path, line = sys.argv[1], sys.argv[2]
keep = [l for l in open(path).read().splitlines()
        if not l.startswith(("GAVEL_CONSOLE_USERS=", "GAVEL_CONSOLE_PUBLIC="))]
keep += [f"GAVEL_CONSOLE_USERS={line}", "GAVEL_CONSOLE_PUBLIC=true"]
open(path, "w").write("\n".join(keep) + "\n")
print(f"stored: user={line.split(':', 1)[0]} hash={len(line.split(':', 1)[1])} bytes; route enabled")
PY
chmod 600 "$env_file"
echo "now run:  docker compose up -d ears"
