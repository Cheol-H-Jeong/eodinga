#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
BUILD_ROOT="${DIST_DIR}/deb-root"
AUDIT_PATH="${DIST_DIR}/linux-deb-audit.json"
DESKTOP_ENTRY="${ROOT_DIR}/packaging/linux/eodinga.desktop"
ICON_ASSET="${ROOT_DIR}/packaging/linux/eodinga.svg"
DEBIAN_CONTROL_TEMPLATE="${ROOT_DIR}/packaging/linux/debian/control"
DEBIAN_CONTROL_RENDERED="${DIST_DIR}/debian-control"
APP_VERSION_TOKEN="@@APP_VERSION@@"
TARGET_ARCH_TOKEN="@@TARGET_ARCH@@"
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
ARCHIVE_SHA256_PATH="${ARCHIVE_PATH}.sha256"
DEB_PATH="${DIST_DIR}/eodinga_${VERSION}_${ARCH}.deb"
DEB_SHA256_PATH="${DEB_PATH}.sha256"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${PACKAGE_DIR}"
mkdir -p "${PACKAGE_DIR}/DEBIAN" "${PACKAGE_DIR}/usr/bin" "${PACKAGE_DIR}/usr/share/applications" "${PACKAGE_DIR}/usr/share/doc/eodinga"
mkdir -p "${PACKAGE_DIR}/usr/share/icons/hicolor/scalable/apps"

python3 - <<PY
from pathlib import Path

template_path = Path("${DEBIAN_CONTROL_TEMPLATE}")
rendered_path = Path("${DEBIAN_CONTROL_RENDERED}")
template_text = template_path.read_text(encoding="utf-8")
rendered = template_text.replace("${APP_VERSION_TOKEN}", "${VERSION}")
rendered = rendered.replace("${TARGET_ARCH_TOKEN}", "${ARCH}")
paragraphs = [paragraph.strip() for paragraph in rendered.split("\n\n") if paragraph.strip()]
binary_paragraph = next(
    (paragraph for paragraph in paragraphs if paragraph.startswith("Package: ")),
    None,
)
if binary_paragraph is None:
    raise SystemExit("missing binary package stanza in Debian control template")
rendered_path.write_text(binary_paragraph + "\n", encoding="utf-8")
Path("${PACKAGE_DIR}/DEBIAN/control").write_text(binary_paragraph + "\n", encoding="utf-8")
PY

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

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner -czf "${ARCHIVE_PATH}" -C "${BUILD_ROOT}" "$(basename "${PACKAGE_DIR}")"
python3 - <<PY
import hashlib
import gzip
import json
import os
import tarfile
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
debian_control_template_path = Path("${DEBIAN_CONTROL_TEMPLATE}")
template_control_entries = {}
for line in debian_control_template_path.read_text(encoding="utf-8").splitlines():
    if not line or ":" not in line:
        continue
    key, value = line.split(":", 1)
    template_control_entries[key] = value.strip()
changelog_text = gzip.decompress(changelog_path.read_bytes()).decode("utf-8")
archive_path = Path("${ARCHIVE_PATH}")
archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
archive_sha256_path = Path("${ARCHIVE_SHA256_PATH}")
archive_sha256_path.write_text(f"{archive_sha256}  {archive_path.name}\n", encoding="utf-8")
deb_path = Path("${DEB_PATH}")
deb_sha256_path = Path("${DEB_SHA256_PATH}")
with tarfile.open("${ARCHIVE_PATH}", mode="r:gz") as archive:
    members = archive.getmembers()
payload = {
    "target": "linux-deb-dry-run" if ${DRY_RUN} else "linux-deb",
    "version": "${VERSION}",
    "arch": "${ARCH}",
    "package_dir": "${PACKAGE_DIR}",
    "control_path": str(control_path),
    "archive": "${ARCHIVE_PATH}",
    "archive_sha256_path": str(archive_sha256_path),
    "archive_entries_sorted": [member.name for member in members] == sorted(member.name for member in members),
    "archive_mtime_zero": all(member.mtime == 0 for member in members),
    "archive_numeric_owner_zero": all(member.uid == 0 and member.gid == 0 for member in members),
    "archive_sha256": archive_sha256,
    "archive_sha256_file_exists": archive_sha256_path.exists(),
    "archive_sha256_matches_file": archive_sha256_path.read_text(encoding="utf-8").strip() == f"{archive_sha256}  {archive_path.name}",
    "deb_path": "${DEB_PATH}",
    "deb_sha256_path": str(deb_sha256_path),
    "deb_sha256": None,
    "deb_sha256_file_exists": False,
    "deb_sha256_matches_file": False,
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
        "contains_version_template": "${APP_VERSION_TOKEN}" in debian_control_template_path.read_text(encoding="utf-8"),
        "contains_arch_template": "${TARGET_ARCH_TOKEN}" in debian_control_template_path.read_text(encoding="utf-8"),
        "rendered_path": "${DEBIAN_CONTROL_RENDERED}",
        "rendered_exists": Path("${DEBIAN_CONTROL_RENDERED}").exists(),
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
        "matches_source_asset": desktop_path.read_text(encoding="utf-8") == Path("${DESKTOP_ENTRY}").read_text(encoding="utf-8"),
    },
    "icon": {
        "path": str(icon_path),
        "exists": icon_path.exists(),
        "desktop_icon_matches_asset": desktop_entries.get("Icon") == icon_path.stem,
        "matches_source_asset": icon_path.read_text(encoding="utf-8") == Path("${ICON_ASSET}").read_text(encoding="utf-8"),
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "has_strict_shell": "set -euo pipefail" in launcher_path.read_text(encoding="utf-8"),
        "executes_python_module": "exec python3 -m eodinga" in launcher_path.read_text(encoding="utf-8"),
    },
    "docs": {
        "license_path": str(license_path),
        "license_exists": license_path.exists(),
        "changelog_path": str(changelog_path),
        "changelog_exists": changelog_path.exists(),
        "changelog_has_current_release_heading": changelog_text.startswith("# Changelog\n\n## ${VERSION} - "),
        "changelog_gzip_mtime_zero": changelog_path.read_bytes()[4:8] == b"\x00\x00\x00\x00",
    },
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged Debian package dry run at ${PACKAGE_DIR}"
  exit 0
fi

dpkg-deb --build "${PACKAGE_DIR}" "${DEB_PATH}"
python3 - <<PY
import hashlib
import json
from pathlib import Path

deb_path = Path("${DEB_PATH}")
deb_sha256 = hashlib.sha256(deb_path.read_bytes()).hexdigest()
deb_sha256_path = Path("${DEB_SHA256_PATH}")
deb_sha256_path.write_text(f"{deb_sha256}  {deb_path.name}\n", encoding="utf-8")
audit_path = Path("${AUDIT_PATH}")
payload = json.loads(audit_path.read_text(encoding="utf-8"))
payload["deb_sha256"] = deb_sha256
payload["deb_sha256_file_exists"] = deb_sha256_path.exists()
payload["deb_sha256_matches_file"] = deb_sha256_path.read_text(encoding="utf-8").strip() == f"{deb_sha256}  {deb_path.name}"
audit_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
echo "built Debian package at ${DEB_PATH}"
