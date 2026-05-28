# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [v3.0.1] - 2026-05-28

### Fixed

- Offline widget could only ever hold one can: right-click-to-add was
  registered on the parent panel only, but per-can panels are the deepest
  hit target (no event bubbling), so the add was shadowed once any can
  existed. Right-click-to-add is now wired on each can in offline mode.
- Receipt upload returned a 500 for large photos: images over Anthropic's
  5 MB limit are now downscaled (max 2000 px, JPEG) before being sent to
  Claude, with the original still stored unchanged.

## [v3.0.0] - 2026-05-19

Big release. RedBull Tracker now has an optional cloud backend so the widget
can sync across machines, log purchases from receipt photos, and even
surface real-time grocery prices when stock hits zero.

### Added

#### Cloud API (`apps/api/`)
- Flask + SQLite backend with per-type stock, manual adjust, and activity log
  with one-tap reversal
- Receipt scanning: upload a photo, Claude vision (Haiku 4.5 primary, Sonnet
  4.6 fallback on low confidence) extracts Red Bull line items and updates
  stock automatically
- Camera capture or file upload from the dashboard
- Bearer-token + signed-cookie auth (shared secret, internet-safe)
- Tesco / any-grocery-store price lookup via Claude's `web_fetch` server
  tool — users can add product URLs from any store, dashboard shows
  normal + loyalty-card price when stock is empty
- Dockerfile + `railway.toml` for one-command deploys to Railway

#### Web dashboard
- Red Bull-styled dark UI (Anton display + Inter body, electric yellow
  accents)
- Camera capture button using `<input type="file" capture="environment">`
  for mobile, falls through to file picker on desktop
- Type dropdown on manual adjust with Tesco CZ Red Bull SKUs (default,
  sugarfree, zero, plus seasonal editions and a custom "other" slot)
- Activity log with receipt thumbnails inline

#### Widget API mode
- New `apiUrl` + `apiToken` fields in `config.json` (env vars
  `REDBULL_API_URL` / `REDBULL_API_TOKEN` override during dev)
- Polls the API every 5s and renders mixed-type cans in the right order
- Per-can left-click drinks one of that specific type via the API
- Right-click adding stays offline-mode-only
- Stale-state dimming when the API is unreachable

### Changed
- Repo is now a monorepo: widget at `apps/widget/`, API at `apps/api/`
- `IRedBullService.RemoveCanAsync()` takes an optional type parameter
- CI split into `ci-widget.yml` (path-filtered to widget changes) and
  new `ci-api.yml`

### Removed
- Custom `getUserMedia` camera modal (native `capture` attribute is simpler
  and the user's OS camera UI is what they expect)

## [v2.0.5] - 2026-02-17

### Fixed
- Hover overlay now activates over the entire widget area, not just the can images

## [v2.0.4] - 2026-02-16

### Fixed
- Widget now auto-positions correctly when running as the only widget
- Periodic position drift detection keeps widget aligned with tray area
- Widget repositions on display resolution and system settings changes
- Rapid left-clicks no longer ignored on every other click

## [v2.0.3] - 2026-02-13

### Fixed
- Standalone single-file exe now works (images embedded as resources instead of loose files)

## [v2.0.2] - 2026-02-13

### Fixed
- Widgets no longer display over fullscreen applications

## [v2.0.1] - 2026-02-12

### Changed
- Smooth lerp animation when dragging widgets to reorder
- Smooth animation when widget resizes (neighboring widgets slide instead of snapping)
- Enabled IL trimming — exe size reduced from 89 MB to ~13 MB
- Removed unused `System.Drawing.Common` dependency
- Switched to source-generated JSON serialization (trim-safe)

### Fixed
- Right-click no longer ignored on every other rapid click
- Widget no longer jumps to wrong position when adding cans

## [v2.0.0] - 2026-02-12

### Changed
- Replaced WinUI 3 / Windows App SDK with pure Win32 GDI rendering (~10 MB exe vs ~153 MB)
- Widget rendering now uses `TaskbarWidget.Widget` API with immediate-mode GDI
- No runtime prerequisites needed (removed WinUI 3 framework dependency)

### Added
- Drag-to-reorder support — reorder widgets by dragging
- Cross-widget atomic repositioning when widget resizes

### Removed
- All XAML files (`App.xaml`, `MainWindow.xaml`, `RedBullWidgetContent.xaml`)
- `Microsoft.WindowsAppSDK` and `Microsoft.Windows.SDK.BuildTools` NuGet dependencies
- `OnlineRedBullService` (unused placeholder)

## [v1.2.2] - 2026-02-11

### Fixed
- Startup registry path now updates when app is moved to a new location

## [v1.2.1] - 2026-02-05

### Changed
- Reduced hoverable area height with 4px margin for better taskbar fit

## [v1.2.0] - 2026-02-03

### Changed
- Adjusted vertical padding for better taskbar fit

## [v1.1.0] - 2026-02-03

### Changed
- Improved hover effect to look more native (added padding, reduced opacity)

## [v1.0.0] - 2026-02-03

### Added
- Initial release
- Windows taskbar widget showing Red Bull consumption
- Visual can display (cans shown side by side)
- Support for default and sugar-free can types
- Left-click to remove cans, right-click to add
- Offline mode with local persistence
- Configuration file for can type, API URL, and startup settings
- Start with Windows enabled by default
- Hover effect and tooltip showing count
