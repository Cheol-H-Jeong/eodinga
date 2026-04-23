#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
BUILD_ROOT="${DIST_DIR}/deb-root"
AUDIT_PATH="${DIST_DIR}/linux-deb-audit.json"
DESKTOP_ENTRY="${ROOT_DIR}/packaging/linux/eodinga.desktop"
ICON_ASSET="${ROOT_DIR}/packaging/linux/eodinga.svg"
DEBIAN_CONTROL_TEMPLATE="${ROOT_DIR}/packaging/linux/debian/control"
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
SOURCE_BUNDLE_DIR="${PACKAGE_DIR}/usr/lib/eodinga"
ARCHIVE_PATH="${DIST_DIR}/eodinga_${VERSION}_${ARCH}_debroot.tar.gz"
DEB_PATH="${DIST_DIR}/eodinga_${VERSION}_${ARCH}.deb"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}/DEBIAN" "${PACKAGE_DIR}/usr/bin" "${PACKAGE_DIR}/usr/share/applications" "${PACKAGE_DIR}/usr/share/doc/eodinga"
mkdir -p "${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${SOURCE_BUNDLE_DIR}"

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
export PYTHONPATH="/usr/lib/eodinga${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m eodinga "$@"
EOF
chmod 0755 "${PACKAGE_DIR}/usr/bin/eodinga"

cp -R "${ROOT_DIR}/eodinga" "${SOURCE_BUNDLE_DIR}/eodinga"
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
import gzip
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
source_bundle_path = Path("${SOURCE_BUNDLE_DIR}")
bundled_package_path = source_bundle_path / "eodinga"
icon_path = Path("${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps/eodinga.svg")
license_path = Path("${PACKAGE_DIR}/usr/share/doc/eodinga/LICENSE")
changelog_path = Path("${PACKAGE_DIR}/usr/share/doc/eodinga/changelog.gz")
debian_control_template_path = Path("${DEBIAN_CONTROL_TEMPLATE}")
template_control_entries = {}
for line in debian_control_template_path.read_text(encoding="utf-8").splitlines():
    if not line or ":" not in line:
        continue
    key, value = line.split(":", 1)
    template_control_entries[key] = value.strip()
changelog_text = gzip.decompress(changelog_path.read_bytes()).decode("utf-8")
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
    "debian_control_template": {
        "path": str(debian_control_template_path),
        "exists": debian_control_template_path.exists(),
        "source": template_control_entries.get("Source"),
        "maintainer": template_control_entries.get("Maintainer"),
        "binary_package": template_control_entries.get("Package"),
        "description": template_control_entries.get("Description"),
    },
    "desktop_entry": {
        "path": str(desktop_path),
        "name": desktop_entries.get("Name"),
        "exec": desktop_entries.get("Exec"),
        "icon": desktop_entries.get("Icon"),
        "categories": desktop_entries.get("Categories"),
        "startup_notify": desktop_entries.get("StartupNotify"),
        "launches_gui": desktop_entries.get("Exec") == "eodinga gui",
        "icon_matches_package": desktop_entries.get("Icon") == icon_path.stem,
    },
    "icon": {
        "path": str(icon_path),
        "exists": icon_path.exists(),
        "desktop_icon_matches_asset": desktop_entries.get("Icon") == icon_path.stem,
    },
    "source_bundle": {
        "path": str(source_bundle_path),
        "exists": source_bundle_path.exists(),
        "package_path": str(bundled_package_path),
        "package_exists": bundled_package_path.exists(),
        "contains_init": (bundled_package_path / "__init__.py").exists(),
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "executes_python_module": "exec python3 -m eodinga" in launcher_path.read_text(encoding="utf-8"),
        "uses_bundled_source": "/usr/lib/eodinga" in launcher_path.read_text(encoding="utf-8"),
    },
    "docs": {
        "license_path": str(license_path),
        "license_exists": license_path.exists(),
        "changelog_path": str(changelog_path),
        "changelog_exists": changelog_path.exists(),
        "changelog_has_current_release_heading": changelog_text.startswith("# Changelog\n\n## ${VERSION} - "),
    },
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged Debian package dry run at ${PACKAGE_DIR}"
  exit 0
fi

dpkg-deb --build "${PACKAGE_DIR}" "${DEB_PATH}"
echo "built Debian package at ${DEB_PATH}"
