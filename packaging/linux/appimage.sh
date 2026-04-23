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
ARCHIVE_PATH="${DIST_DIR}/eodinga-${VERSION}-linux-appdir.tar.gz"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${APPDIR}/usr/lib/eodinga"
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
cp -R "${ROOT_DIR}/eodinga" "${APPDIR}/usr/lib/eodinga/"
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${APPDIR}/usr/bin/eodinga" gui "$@"
EOF
cat > "${APPDIR}/usr/bin/eodinga" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${APPDIR}/usr/lib/eodinga${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m eodinga "$@"
EOF
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/eodinga"

tar -czf "${ARCHIVE_PATH}" -C "${DIST_DIR}" "$(basename "${APPDIR}")"
python3 - <<PY
import json
import os
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
package_root = Path("${APPDIR}/usr/lib/eodinga/eodinga")
recipe_path = Path("${APPIMAGE_RECIPE}")
rendered_recipe_path = Path("${RENDERED_RECIPE}")
recipe_text = recipe_path.read_text(encoding="utf-8")
rendered_recipe_text = rendered_recipe_path.read_text(encoding="utf-8")
launcher_text = launcher_path.read_text(encoding="utf-8")
payload = {
    "target": "linux-appimage-dry-run" if ${DRY_RUN} else "linux-appimage",
    "version": "${VERSION}",
    "appdir": "${APPDIR}",
    "archive": "${ARCHIVE_PATH}",
    "dry_run": bool(${DRY_RUN}),
    "desktop_entry": {
        "path": str(desktop_path),
        "name": desktop_entries.get("Name"),
        "exec": desktop_entries.get("Exec"),
        "icon": desktop_entries.get("Icon"),
        "categories": desktop_entries.get("Categories"),
        "startup_notify": desktop_entries.get("StartupNotify"),
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
    },
    "package": {
        "root": str(package_root),
        "exists": package_root.exists(),
        "main_exists": (package_root / "__main__.py").exists(),
        "i18n_en_exists": (package_root / "i18n" / "en.json").exists(),
        "i18n_ko_exists": (package_root / "i18n" / "ko.json").exists(),
    },
    "apprun": {
        "path": str(apprun_path),
        "is_executable": os.access(apprun_path, os.X_OK),
        "launches_gui": 'usr/bin/eodinga" gui ' in apprun_path.read_text(encoding="utf-8"),
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "sets_pythonpath": "export PYTHONPATH=" in launcher_text and "/usr/lib/eodinga" in launcher_text,
        "executes_python_module": "exec python3 -m eodinga" in launcher_text,
    },
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged AppImage dry run at ${APPDIR}"
  exit 0
fi

echo "staged source-backed AppDir at ${APPDIR}"
