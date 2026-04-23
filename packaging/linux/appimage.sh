#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="${ROOT_DIR}/packaging/dist"
APPDIR="${DIST_DIR}/eodinga.AppDir"
AUDIT_PATH="${DIST_DIR}/linux-appimage-audit.json"
APPIMAGE_RECIPE="${ROOT_DIR}/packaging/linux/appimage-builder.yml"
RENDERED_RECIPE="${DIST_DIR}/appimage-builder.yml"
APPIMAGE_ICON="${ROOT_DIR}/packaging/linux/eodinga.svg"
RUNTIME_ROOT="${APPDIR}/usr/lib/eodinga"
STAGE_RUNTIME="${ROOT_DIR}/packaging/linux/stage_runtime.py"
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
APPIMAGE_PATH="${DIST_DIR}/eodinga-${VERSION}-linux-${ARCH}.AppImage"
APPIMAGE_TOOL="${APPIMAGE_TOOL:-appimagetool}"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

rm -rf "${APPDIR}"
rm -f "${APPIMAGE_PATH}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${RUNTIME_ROOT}"
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
python3 "${STAGE_RUNTIME}" "${RUNTIME_ROOT}"
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
exec python3 -Im eodinga "$@"
EOF
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/eodinga"

tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner -czf "${ARCHIVE_PATH}" -C "${DIST_DIR}" "$(basename "${APPDIR}")"
python3 - <<PY
import json
import os
import tarfile
import hashlib
import subprocess
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
runtime_root = Path("${RUNTIME_ROOT}")
runtime_package_root = runtime_root / "eodinga"
recipe_path = Path("${APPIMAGE_RECIPE}")
rendered_recipe_path = Path("${RENDERED_RECIPE}")
recipe_text = recipe_path.read_text(encoding="utf-8")
rendered_recipe_text = rendered_recipe_path.read_text(encoding="utf-8")
archive_path = Path("${ARCHIVE_PATH}")
appdir_root = Path("${APPDIR}")
appdir_manifest = sorted(
    str(path.relative_to(appdir_root))
    for path in appdir_root.rglob("*")
    if path.is_file()
)
launcher_help = subprocess.run(
    [str(launcher_path), "--help"],
    capture_output=True,
    text=True,
    check=False,
    cwd="/",
    env={
        "HOME": str(Path("${DIST_DIR}").resolve()),
        "PATH": os.environ.get("PATH", ""),
    },
)
launcher_help_output = launcher_help.stdout + launcher_help.stderr
launcher_version = subprocess.run(
    [str(launcher_path), "version"],
    capture_output=True,
    text=True,
    check=False,
    cwd="/",
    env={
        "HOME": str(Path("${DIST_DIR}").resolve()),
        "PATH": os.environ.get("PATH", ""),
    },
)
with tarfile.open("${ARCHIVE_PATH}", mode="r:gz") as archive:
    members = archive.getmembers()
payload = {
    "target": "linux-appimage-dry-run" if ${DRY_RUN} else "linux-appimage",
    "version": "${VERSION}",
    "arch": "${ARCH}",
    "appdir": "${APPDIR}",
    "archive": "${ARCHIVE_PATH}",
    "appimage_path": "${APPIMAGE_PATH}",
    "appdir_manifest": appdir_manifest,
    "archive_entries_sorted": [member.name for member in members] == sorted(member.name for member in members),
    "archive_mtime_zero": all(member.mtime == 0 for member in members),
    "archive_numeric_owner_zero": all(member.uid == 0 and member.gid == 0 for member in members),
    "archive_artifact": {
        "path": str(archive_path),
        "exists": archive_path.exists(),
        "size_bytes": archive_path.stat().st_size if archive_path.exists() else None,
        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path.exists() else None,
    },
    "appimage_artifact": {
        "path": "${APPIMAGE_PATH}",
        "exists": False,
        "size_bytes": None,
        "sha256": None,
        "is_executable": False,
        "build_tool": "${APPIMAGE_TOOL}",
    },
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
    "runtime_bundle": {
        "path": str(runtime_root),
        "exists": runtime_root.exists(),
        "package_root": str(runtime_package_root),
        "package_exists": runtime_package_root.exists(),
        "package_init_exists": (runtime_package_root / "__init__.py").exists(),
        "module_entry_exists": (runtime_package_root / "__main__.py").exists(),
        "i18n_en_exists": (runtime_package_root / "i18n" / "en.json").exists(),
    },
    "apprun": {
        "path": str(apprun_path),
        "is_executable": os.access(apprun_path, os.X_OK),
        "launches_gui": 'usr/bin/eodinga" gui ' in apprun_path.read_text(encoding="utf-8"),
        "has_strict_shell": "set -euo pipefail" in apprun_path.read_text(encoding="utf-8"),
    },
    "launcher": {
        "path": str(launcher_path),
        "is_executable": os.access(launcher_path, os.X_OK),
        "has_strict_shell": "set -euo pipefail" in launcher_path.read_text(encoding="utf-8"),
        "uses_bundled_runtime": "/usr/lib/eodinga" in launcher_path.read_text(encoding="utf-8")
        and "PYTHONPATH=" in launcher_path.read_text(encoding="utf-8"),
        "executes_python_module": "exec python3 -Im eodinga" in launcher_path.read_text(encoding="utf-8"),
        "help_exit_code": launcher_help.returncode,
        "help_mentions_search_command": "{index,watch,search,stats,gui,doctor,version}" in launcher_help_output,
        "version_exit_code": launcher_version.returncode,
        "version_matches_package": launcher_version.stdout.strip() == "${VERSION}",
    },
}
Path("${AUDIT_PATH}").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "staged AppImage dry run at ${APPDIR}"
  exit 0
fi

ARCH="${ARCH}" "${APPIMAGE_TOOL}" "${APPDIR}" "${APPIMAGE_PATH}"
python3 - <<PY
import hashlib
import json
import os
from pathlib import Path

audit_path = Path("${AUDIT_PATH}")
payload = json.loads(audit_path.read_text(encoding="utf-8"))
appimage_path = Path("${APPIMAGE_PATH}")
payload["appimage_artifact"] = {
    "path": str(appimage_path),
    "exists": appimage_path.exists(),
    "size_bytes": appimage_path.stat().st_size if appimage_path.exists() else None,
    "sha256": hashlib.sha256(appimage_path.read_bytes()).hexdigest() if appimage_path.exists() else None,
    "is_executable": os.access(appimage_path, os.X_OK),
    "build_tool": "${APPIMAGE_TOOL}",
}
audit_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

echo "staged AppImage at ${APPIMAGE_PATH}"
