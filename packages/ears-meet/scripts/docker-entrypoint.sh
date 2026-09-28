#!/bin/sh
# Runs as root only long enough to make the mounts writable, then becomes pwuser.
#
# Bind mounts (`./secrets/meet-profile:/profile`, `./recordings:/recordings`) that do not
# exist on the host are created by Docker as root-owned directories; Chromium then cannot
# write its profile and the browser never launches. Chromium and PulseAudio both refuse to
# run as root, so the fix has to happen here, before dropping privileges.
set -eu

if [ "$(id -u)" = "0" ]; then
    for dir in /profile /recordings; do
        if [ -d "$dir" ] && [ "$(stat -c %u "$dir")" != "$(id -u pwuser)" ]; then
            chown -R pwuser:pwuser "$dir"
        fi
    done
    exec setpriv --reuid=pwuser --regid=pwuser --init-groups env HOME=/home/pwuser "$@"
fi

exec "$@"
