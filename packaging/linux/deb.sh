#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
BUILD_ROOT="${DIST_DIR}/deb-root"
AUDIT_PATH="${DIST_DIR}/linux-deb-audit.json"
DESKTOP_ENTRY="${ROOT_DIR}/packaging/linux/eodinga.desktop"
ICON_ASSET="${ROOT_DIR}/packaging/linux/eodinga.svg"
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
mkdir -p "${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps"

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

install -m 0644 "${DESKTOP_ENTRY}" "${PACKAGE_DIR}/usr/share/applications/eodinga.desktop"
install -m 0644 "${ICON_ASSET}" "${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps/eodinga.svg"
install -m 0644 "${ROOT_DIR}/LICENSE" "${PACKAGE_DIR}/usr/share/doc/eodinga/LICENSE"
python3 - <<PY
import gzip
from pathlib import Path

source = Path("${ROOT_DIR}/CHANGELOG.md")
target = Path("${PACKAGE_DIR}/usr/share/doc/eodinga/changelog.gz")
with source.open("rb") as src, gzip.GzipFile(filename="", mode="wb", fileobj=target.open("wb"), mtime=0) as dst:
    dst.write(src.read())
PY

tar -czf "${ARCHIVE_PATH}" -C "${BUILD_ROOT}" "$(basename "${PACKAGE_DIR}")"
python3 - <<PY
import json
import os
from pathlib import Path

desktop_path = Path("${PACKAGE_DIR}/usr/share/applications/eodinga.desktop")
desktop_entries = {}
for line in desktop_path.read_text(encoding="utf-8").splitlines():
    if not line or line.startswith("[") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    desktop_entries[key] = value

control_path = Path("${PACKAGE_DIR}/DEBIAN/control")
control_entries = {}
for line in control_path.read_text(encoding="utf-8").splitlines():
    if not line or ":" not in line:
        continue
    key, value = line.split(":", 1)
    control_entries[key] = value.strip()

launcher_path = Path("${PACKAGE_DIR}/usr/bin/eodinga")
icon_path = Path("${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps/eodinga.svg")
license_path = Path("${PACKAGE_DIR}/usr/share/doc/eodinga/LICENSE")
changelog_path = Path("${PACKAGE_DIR}/usr/share/doc/eodinga/changelog.gz")
validation_errors = []
if control_entries.get("Package") != "eodinga":
    validation_errors.append("control Package must be eodinga")
if control_entries.get("Version") != "${VERSION}":
    validation_errors.append("control Version must match eodinga.__version__")
if desktop_entries.get("Name") != "eodinga":
    validation_errors.append("desktop entry name must be eodinga")
if desktop_entries.get("Exec") != "eodinga gui":
    validation_errors.append("desktop entry Exec must be 'eodinga gui'")
if desktop_entries.get("Icon") != icon_path.stem:
    validation_errors.append("desktop entry Icon must match the staged icon asset")
if not os.access(launcher_path, os.X_OK):
    validation_errors.append("launcher is not executable")
if not license_path.exists():
    validation_errors.append("LICENSE is missing from the package docs")
if not changelog_path.exists():
    validation_errors.append("changelog.gz is missing from the package docs")
payload = {
    "target": "linux-deb-dry-run" if ${DRY_RUN} else "linux-deb",
    "version": "${VERSION}",
    "arch": "${ARCH}",
    "package_dir": "${PACKAGE_DIR}",
    "control_path": str(control_path),
    "archive": "${ARCHIVE_PATH}",
    "deb_path": "${DEB_PATH}",
    "dry_run": bool(${DRY_RUN}),
    "control": {
        "package": control_entries.get("Package"),
        "version": control_entries.get("Version"),
        "architecture": control_entries.get("Architecture"),
        "depends": control_entries.get("Depends"),
        "description": control_entries.get("Description"),
    },
    "desktop_entry": {
        "path": str(desktop_path),
        "name": desktop_entries.get("Name"),
        "exec": desktop_entries.get("Exec"),
        "icon": desktop_entries.get("Icon"),
        "categories": desktop_entries.get("Categories"),
        "startup_notify": desktop_entries.get("StartupNotify"),
    },
    "icon": {
        "path": str(icon_path),
        "exists": icon_path.exists(),
        "desktop_icon_matches_asset": desktop_entries.get("Icon") == icon_path.stem,
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "executes_python_module": "exec python3 -m eodinga" in launcher_path.read_text(encoding="utf-8"),
    },
    "docs": {
        "license_path": str(license_path),
        "license_exists": license_path.exists(),
        "changelog_path": str(changelog_path),
        "changelog_exists": changelog_path.exists(),
    },
    "valid": not validation_errors,
    "validation_errors": validation_errors,
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
if validation_errors:
    raise SystemExit("\\n".join(validation_errors))
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged Debian package dry run at ${PACKAGE_DIR}"
  exit 0
fi

dpkg-deb --build "${PACKAGE_DIR}" "${DEB_PATH}"
echo "built Debian package at ${DEB_PATH}"
