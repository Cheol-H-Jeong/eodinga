#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
APPDIR="${DIST_DIR}/eodinga.AppDir"
AUDIT_PATH="${DIST_DIR}/linux-appimage-audit.json"
VERSION="$(python3 - <<'PY'
import pathlib
import re

text = pathlib.Path("eodinga/__init__.py").read_text(encoding="utf-8")
match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
if match is None:
    raise SystemExit("missing __version__")
print(match.group(1))
PY
)"
ARCHIVE_PATH="${DIST_DIR}/eodinga-${VERSION}-linux-appdir.tar.gz"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications"
mkdir -p "${DIST_DIR}"

cp "${ROOT_DIR}/packaging/linux/eodinga.desktop" "${APPDIR}/usr/share/applications/eodinga.desktop"
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${APPDIR}/usr/bin/eodinga" gui "$@"
EOF
cat > "${APPDIR}/usr/bin/eodinga" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../" && pwd)"
cd "${ROOT_DIR}"
exec python3 -m eodinga "$@"
EOF
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/eodinga"

tar -czf "${ARCHIVE_PATH}" -C "${DIST_DIR}" "$(basename "${APPDIR}")"
python3 - <<PY
import json
from pathlib import Path

payload = {
    "target": "linux-appimage-dry-run",
    "version": "${VERSION}",
    "appdir": "${APPDIR}",
    "archive": "${ARCHIVE_PATH}",
    "dry_run": bool(${DRY_RUN}),
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged AppImage dry run at ${APPDIR}"
  exit 0
fi

echo "staged source-backed AppDir at ${APPDIR}"
