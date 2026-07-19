#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
SERVICE="$ROOT/packaging/systemd/openstock-daily-pipeline.service"
TIMER="$ROOT/packaging/systemd/openstock-daily-pipeline.timer"
CONTROL="$ROOT/packaging/deb/DEBIAN/control"
POSTINST="$ROOT/packaging/deb/DEBIAN/postinst"
PRERM="$ROOT/packaging/deb/DEBIAN/prerm"
POSTRM="$ROOT/packaging/deb/DEBIAN/postrm"

systemd-analyze verify "$SERVICE" "$TIMER"
grep -Fx 'ExecStart=/usr/bin/flock -n -E 75 /run/openstock-pipeline.lock /usr/bin/vnalpha maintain daily --date today --json' "$SERVICE"
grep -Fx 'SuccessExitStatus=3' "$SERVICE"
grep -Fx 'OnCalendar=Mon..Fri *-*-* 17:30:00 Asia/Ho_Chi_Minh' "$TIMER"
grep -Fx 'Persistent=true' "$TIMER"
grep -Fx 'Unit=openstock-daily-pipeline.service' "$TIMER"
! grep -q '^\[Install\]' "$SERVICE"
! grep -q '^Requires=openstock-daily-pipeline.service' "$TIMER"
grep -q 'util-linux' "$CONTROL"
grep -q 'systemd' "$CONTROL"
grep -q 'tzdata' "$CONTROL"
test -f "$ROOT/packaging/deb/usr/lib/systemd/system/openstock-daily-pipeline.service"
test -f "$ROOT/packaging/deb/usr/lib/systemd/system/openstock-daily-pipeline.timer"
grep -q 'systemctl daemon-reload' "$POSTINST"
! grep -Eq 'systemctl (enable|start)|deb-systemd-helper enable' "$POSTINST"
grep -q 'systemctl stop openstock-daily-pipeline.service' "$PRERM"
grep -q 'systemctl daemon-reload' "$POSTRM"
! grep -q 'rm -f.*LOCK_FILE' "$ROOT/packaging/scripts/openstock-run-pipeline"
