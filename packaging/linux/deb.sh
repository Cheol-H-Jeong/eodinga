#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
BUILD_ROOT="${DIST_DIR}/deb-root"
AUDIT_PATH="${DIST_DIR}/linux-deb-audit.json"
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
ARCH="${TARGET_ARCH:-amd64}"
PACKAGE_DIR="${BUILD_ROOT}/eodinga_${VERSION}_${ARCH}"
ARCHIVE_PATH="${DIST_DIR}/eodinga_${VERSION}_${ARCH}_debroot.tar.gz"
DEB_PATH="${DIST_DIR}/eodinga_${VERSION}_${ARCH}.deb"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}/DEBIAN" "${PACKAGE_DIR}/usr/bin" "${PACKAGE_DIR}/usr/share/applications" "${PACKAGE_DIR}/usr/share/doc/eodinga"

cat > "${PACKAGE_DIR}/DEBIAN/control" <<EOF
Package: eodinga
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Cheol-H-Jeong
Depends: python3 (>= 3.11)
Description: Instant lexical file search for Windows and Linux
EOF

cat > "${PACKAGE_DIR}/usr/bin/eodinga" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec python3 -m eodinga "$@"
EOF
chmod 0755 "${PACKAGE_DIR}/usr/bin/eodinga"

install -m 0644 "${ROOT_DIR}/packaging/linux/eodinga.desktop" "${PACKAGE_DIR}/usr/share/applications/eodinga.desktop"
install -m 0644 "${ROOT_DIR}/LICENSE" "${PACKAGE_DIR}/usr/share/doc/eodinga/LICENSE"

tar -czf "${ARCHIVE_PATH}" -C "${BUILD_ROOT}" "$(basename "${PACKAGE_DIR}")"
python3 - <<PY
import json
from pathlib import Path

payload = {
    "target": "linux-deb-dry-run" if ${DRY_RUN} else "linux-deb",
    "version": "${VERSION}",
    "arch": "${ARCH}",
    "package_dir": "${PACKAGE_DIR}",
    "control_path": "${PACKAGE_DIR}/DEBIAN/control",
    "archive": "${ARCHIVE_PATH}",
    "deb_path": "${DEB_PATH}",
    "dry_run": bool(${DRY_RUN}),
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged Debian package dry run at ${PACKAGE_DIR}"
  exit 0
fi

dpkg-deb --build "${PACKAGE_DIR}" "${DEB_PATH}"
echo "built Debian package at ${DEB_PATH}"
