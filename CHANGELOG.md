# Changelog

## 0.1.1 - 2026-04-23

- Repaired merge regressions in shared models, filesystem helpers, observability exports, and test fixtures so the baseline gate is green again.
- Fixed watcher event coalescing so rapid rename-then-delete sequences preserve both `moved` and `deleted` events.
- Added index storage reliability helpers for atomic database replacement and stale WAL recovery on startup.
- Added safety coverage for the no-network source policy and storage recovery behavior.

## 0.1.0 - 2026-04-23

- Added the initial packaging shell for `eodinga` across Windows and Linux.
- Added config loading and saving, a CLI surface, diagnostics, and bilingual i18n catalogs.
- Added PyInstaller, Inno Setup, AppImage, and Debian packaging assets.
- Added CI and release workflows for Ubuntu and Windows.
- Added unit coverage for config, CLI, diagnostics, i18n, packaging assets, and workflow linting.
