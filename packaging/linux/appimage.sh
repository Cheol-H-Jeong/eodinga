#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
APPDIR="${DIST_DIR}/eodinga.AppDir"
AUDIT_PATH="${DIST_DIR}/linux-appimage-audit.json"
APPIMAGE_RECIPE="${ROOT_DIR}/packaging/linux/appimage-builder.yml"
RENDERED_RECIPE="${DIST_DIR}/appimage-builder.yml"
APPIMAGE_ICON="${ROOT_DIR}/packaging/linux/eodinga.svg"
APPIMAGE_VERSION_TOKEN="@@APP_VERSION@@"
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
ARCH="${TARGET_ARCH:-$(uname -m)}"
ARCHIVE_PATH="${DIST_DIR}/eodinga-${VERSION}-linux-${ARCH}-appdir.tar.gz"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${DIST_DIR}"

python3 - <<PY
from pathlib import Path

template_path = Path("${APPIMAGE_RECIPE}")
rendered_path = Path("${RENDERED_RECIPE}")
rendered = template_path.read_text(encoding="utf-8").replace("${APPIMAGE_VERSION_TOKEN}", "${VERSION}")
rendered_path.write_text(rendered, encoding="utf-8")
PY

cp "${ROOT_DIR}/packaging/linux/eodinga.desktop" "${APPDIR}/usr/share/applications/eodinga.desktop"
cp "${APPIMAGE_ICON}" "${APPDIR}/usr/share/icons/hicolor/scalable/apps/eodinga.svg"
cp "${APPIMAGE_ICON}" "${APPDIR}/.DirIcon"
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

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner -czf "${ARCHIVE_PATH}" -C "${DIST_DIR}" "$(basename "${APPDIR}")"
python3 - <<PY
import json
import os
import tarfile
from pathlib import Path

desktop_path = Path("${APPDIR}/usr/share/applications/eodinga.desktop")
desktop_lines = desktop_path.read_text(encoding="utf-8").splitlines()
desktop_entries = {}
for line in desktop_lines:
    if not line or line.startswith("[") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    desktop_entries[key] = value

apprun_path = Path("${APPDIR}/AppRun")
launcher_path = Path("${APPDIR}/usr/bin/eodinga")
icon_path = Path("${APPDIR}/usr/share/icons/hicolor/scalable/apps/eodinga.svg")
diricon_path = Path("${APPDIR}/.DirIcon")
recipe_path = Path("${APPIMAGE_RECIPE}")
rendered_recipe_path = Path("${RENDERED_RECIPE}")
recipe_text = recipe_path.read_text(encoding="utf-8")
rendered_recipe_text = rendered_recipe_path.read_text(encoding="utf-8")
with tarfile.open("${ARCHIVE_PATH}", mode="r:gz") as archive:
    members = archive.getmembers()
payload = {
    "target": "linux-appimage-dry-run" if ${DRY_RUN} else "linux-appimage",
    "version": "${VERSION}",
    "arch": "${ARCH}",
    "appdir": "${APPDIR}",
    "archive": "${ARCHIVE_PATH}",
    "archive_entries_sorted": [member.name for member in members] == sorted(member.name for member in members),
    "archive_mtime_zero": all(member.mtime == 0 for member in members),
    "archive_numeric_owner_zero": all(member.uid == 0 and member.gid == 0 for member in members),
    "dry_run": bool(${DRY_RUN}),
    "desktop_entry": {
        "path": str(desktop_path),
        "name": desktop_entries.get("Name"),
        "exec": desktop_entries.get("Exec"),
        "icon": desktop_entries.get("Icon"),
        "categories": desktop_entries.get("Categories"),
        "startup_notify": desktop_entries.get("StartupNotify"),
        "matches_source_asset": desktop_path.read_text(encoding="utf-8") == Path("${ROOT_DIR}/packaging/linux/eodinga.desktop").read_text(encoding="utf-8"),
    },
    "recipe": {
        "path": str(recipe_path),
        "exists": recipe_path.exists(),
        "contains_version_template": "${APPIMAGE_VERSION_TOKEN}" in recipe_text,
        "rendered_path": str(rendered_recipe_path),
        "rendered_exists": rendered_recipe_path.exists(),
        "rendered_version_matches_package": f"version: ${VERSION}" in rendered_recipe_text,
        "references_desktop_entry": "packaging/linux/eodinga.desktop" in recipe_text,
        "references_icon_asset": "packaging/linux/eodinga.svg" in recipe_text,
        "launches_gui": "exec_args: gui" in recipe_text,
    },
    "icon": {
        "path": str(icon_path),
        "exists": icon_path.exists(),
        "diricon_path": str(diricon_path),
        "diricon_exists": diricon_path.exists(),
        "desktop_icon_matches_asset": desktop_entries.get("Icon") == icon_path.stem,
        "matches_source_asset": icon_path.read_text(encoding="utf-8") == Path("${APPIMAGE_ICON}").read_text(encoding="utf-8"),
    },
    "apprun": {
        "path": str(apprun_path),
        "is_executable": os.access(apprun_path, os.X_OK),
        "launches_gui": 'usr/bin/eodinga" gui ' in apprun_path.read_text(encoding="utf-8"),
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "executes_python_module": "exec python3 -m eodinga" in launcher_path.read_text(encoding="utf-8"),
    },
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged AppImage dry run at ${APPDIR}"
  exit 0
fi

echo "staged source-backed AppDir at ${APPDIR}"
