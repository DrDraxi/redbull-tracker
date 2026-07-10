# AGENTS.md

This file provides guidance to OpenAI Codex and other AI coding agents when working with code in this repository. It mirrors the project knowledge in [`CLAUDE.md`](CLAUDE.md); keep the two in sync when either changes.

## Project Overview

RedBull Tracker is a Windows taskbar widget that tracks Red Bull consumption. It displays cans visually in the taskbar, allowing quick add/remove with mouse clicks. Uses pure Win32 GDI rendering via the TaskbarWidget submodule. Supports offline mode with local persistence and configurable can types.

## Setup

After cloning, initialize the submodule before building:

```bash
git submodule update --init --recursive
```

Requirements:

- Windows 10/11 (the widget is a Win32 GDI app)
- .NET 8.0 SDK

## Build Commands

```bash
# Build the solution
dotnet build -p:Platform=x64

# Build release
dotnet build --configuration Release -p:Platform=x64

# Run the app (x64)
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64

# Publish single-file exe (x64)
dotnet publish apps/widget/RedBullTracker.csproj --configuration Release --runtime win-x64 --self-contained true -p:Platform=x64 -p:PublishSingleFile=true -p:WindowsPackageType=None -o publish
```

## Architecture

### Solution Structure

- **RedBullTracker** (`apps/widget/`) - Win32 GDI app with taskbar widget
- **API** (`apps/api/`) - Flask + SQLite backend (planned; see `docs/superpowers/specs/2026-05-18-api-monorepo-receipt-tracking-design.md`)
- **TaskbarWidget** (`lib/taskbar-widget/`) - Git submodule for immediate-mode GDI widget toolkit

### Key Components

```
apps/widget/
├── Program.cs              # Entry point, creates services, runs message loop
├── Widget/
│   └── RedBullWidget.cs    # Render callback with can images + click handlers
├── Services/
│   ├── IRedBullService.cs         # Interface for count operations
│   ├── OfflineRedBullService.cs   # Local counter with file persistence
│   ├── SettingsService.cs         # Config and count persistence
│   └── StartupService.cs          # Windows startup registry
└── Models/
    ├── RedBull.cs                 # RedBullCount record
    └── AppConfig.cs               # Configuration model
```

### Widget System

RedBullWidget uses the `TaskbarWidget.Widget` API (immediate-mode Win32 GDI):

1. Loads can images via `WidgetImage.FromFile()` from `Assets/` directory
2. Creates `new Widget("RedBull", render: ctx => { ... })` with a render callback
3. Render callback draws can images horizontally using `ctx.Panel()` and `h.DrawImage()`
4. Left-click removes a can, right-click adds a can (via `p.OnClick()` / `p.OnRightClick()`)
5. `widget.Invalidate()` re-renders when `IRedBullService.CountChanged` fires
6. `Widget.RunMessageLoop()` runs the Win32 message loop

### Services

- **OfflineRedBullService**: Manages count with file persistence, fires `CountChanged` event
- **SettingsService**: Loads/saves `config.json` and `count.txt`
- **StartupService**: Manages Windows startup via registry

### Data Storage

All data stored in `%LOCALAPPDATA%\RedBullTracker\`:

- `config.json` - App configuration
- `count.txt` - Current Red Bull count

### Configuration Options

```json
{
  "canType": "default",      // "default" or "sugarfree"
  "apiUrl": null,            // Future: API URL for online mode
  "useOnlineMode": false,    // Future: Enable online sync
  "startWithWindows": true   // Launch on Windows startup
}
```

### API Vision Recognition (receipts & photos)

The API recognizes Red Bull cans in two kinds of images:

- `POST /api/v1/receipts` — parse Red Bull line items on a shopping receipt.
- `POST /api/v1/photos` — count Red Bull cans in an ordinary photo (e.g. cans
  on a desk). Records a batch with `source='photo'`.

Both dispatch through `redbull_api/vision.py:recognize(cfg, mode=...)`, which
selects a backend via the `VISION_PROVIDER` env var:

| `VISION_PROVIDER` | Module | Auth | Notes |
|---|---|---|---|
| `codex` (default) | `codex_vision.py` | `codex login` (Codex/ChatGPT subscription) | Shells out to `codex exec "<prompt>" --image <file> --output-last-message <file> --sandbox read-only --skip-git-repo-check`. No metered API key; requires the `codex` CLI installed + logged in on the host. |
| `openai` | `openai_vision.py` | `OPENAI_API_KEY` | Calls an OpenAI-compatible `/v1/chat/completions`. Point `OPENAI_BASE_URL` at a subscription proxy to bill a ChatGPT/Codex subscription instead of a metered API. **Production uses the private `codex-proxy` service** over Railway private networking: `OPENAI_BASE_URL=http://codex.railway.internal:8000/v1`, `OPENAI_API_KEY=dummy`, `OPENAI_MODEL=gpt-5.6-terra`. |
| `anthropic` | `receipts.py` | `ANTHROPIC_API_KEY` | Anthropic vision path (Haiku → Sonnet). Also the automatic **fallback** for the `codex`/`openai` providers when their call fails and `ANTHROPIC_API_KEY` is set. |

Relevant env vars: `VISION_PROVIDER`, `CODEX_BIN`, `CODEX_MODEL`, `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, `OPENAI_MODEL`, `ANTHROPIC_API_KEY`. `codex exec` requires the
prompt *before* its flags, and reuses the auth from `codex login` (use
`codex login --device-auth` on headless hosts). The proxy passes model slugs
through verbatim unless remapped, so `gpt-5.6-terra` reaches the Codex backend as-is.

## Gotchas

- **Platform required**: Use `-p:Platform=x64` for all build commands.
- **Submodule**: Must initialize the submodule before building.
- **Assets**: Can images must exist in `Assets/` directory (`redbull-default.png`, `redbull-sugarfree.png`, `redbull-empty.png`).

## Releases

Version is derived from git tags. The GitHub Actions workflow automatically creates releases when a tag is pushed.

### How to Release

1. **Update CHANGELOG.md** with the new version section:

   ```markdown
   ## [v1.1.0] - YYYY-MM-DD

   ### Added
   - New feature description

   ### Changed
   - Changed behavior description

   ### Fixed
   - Bug fix description
   ```

2. **Commit the changelog**:

   ```bash
   git add CHANGELOG.md
   git commit -m "docs: update changelog for v1.1.0"
   git push
   ```

3. **Create and push the tag**:

   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```

4. The workflow will automatically build artifacts, extract release notes from CHANGELOG.md, and create a GitHub release.

### Changelog Format

Follow [Keep a Changelog](https://keepachangelog.com/) format:

- `### Added` - New features
- `### Changed` - Changes in existing functionality
- `### Deprecated` - Soon-to-be removed features
- `### Removed` - Removed features
- `### Fixed` - Bug fixes
- `### Security` - Security fixes

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **Major** (v2.0.0): Breaking changes
- **Minor** (v1.1.0): New features, backwards compatible
- **Patch** (v1.0.1): Bug fixes, backwards compatible

## CI/CD

- **CI** (`.github/workflows/ci-widget.yml`): Runs on widget-related changes (pushes to main, all PRs). Builds debug and release, uploads portable exe artifact.
- **Release** (`.github/workflows/release.yml`): Runs on version tags. Builds single-file exe and zip, extracts changelog notes, creates GitHub release with artifacts.

## Commit Guidelines

- Do not add co-author trailers (e.g. `Co-Authored-By: ...`) to commits.
- Use clear, descriptive commit messages. Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, etc.) are used throughout the history.
