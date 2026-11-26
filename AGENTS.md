# AGENTS.md

This file provides guidance to OpenAI Codex and other AI coding agents when working with code in this repository. It mirrors the project knowledge in [`CLAUDE.md`](CLAUDE.md); keep the two in sync when either changes.

## Project Overview

RedBull Tracker is a Windows taskbar widget that tracks Red Bull consumption. It displays cans visually in the taskbar, allowing quick add/remove with mouse clicks. Rendered with Direct2D via the TaskbarWidget submodule and published as a NativeAOT exe. Supports offline mode with local persistence and configurable can types.

## Setup

Requirements:

- Windows 10/11
- .NET 10 SDK, plus the Visual Studio "Desktop development with C++" workload for NativeAOT publishing

## Build Commands

```bash
# Build / run (JIT, fast iteration)
dotnet build -p:Platform=x64
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64

# Publish the release exe: NativeAOT, single ~2 MB native file
# (needs the VS "Desktop development with C++" workload; vswhere.exe must be on PATH)
dotnet publish apps/widget/RedBullTracker.csproj -c Release -r win-x64 -p:Platform=x64 -o publish

# Build against a local taskbar-widget checkout instead of the submodule
dotnet build apps/widget/RedBullTracker.csproj -p:Platform=x64 -p:TaskbarWidgetDir=../taskbar-widget
```

```bash
# Widget tests
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

## Architecture

### Solution Structure

- **RedBullTracker** (`apps/widget/`): the widget app, .NET 10 NativeAOT
- **API** (`apps/api/`): Flask + SQLite backend
- **TaskbarWidget** (`lib/taskbar-widget/`): git submodule. Direct2D-rendered taskbar widget toolkit with shared, deterministic cross-widget positioning

After cloning, initialize the submodule:
```bash
git submodule update --init --recursive
```

### Key Components

```
apps/widget/
├── Program.cs         # Entry point: RedBullApp.Start() + Widget.Run()
├── RedBullApp.cs      # Widget UI: one can per Red Bull, hover lift, tooltip, menu
├── CanSources.cs      # ICanSource: OfflineCans (counts.json, per type), ApiCans (polls /api/v1/stock, POST /api/v1/adjust), BrokenCans
├── RedBullConfig.cs   # config.json + env overrides, mode resolution
└── Tests/             # xunit tests for parsing, config and offline counting
```

- Left-click a can drinks it. Offline: right-click adds `rightClickCan`, Shift+right-click adds `shiftRightClickCan`. Ctrl+right-click (or any right-click in API mode) opens the menu (`WidgetOptions.MenuModifier = Ctrl`).
- API mode polls every 5 s on the thread pool and posts results to the UI thread. Drinks are optimistic, and the next poll reconciles them.
- A half-configured API (`apiUrl` without `apiToken`) is shown in the tooltip instead of crashing.

### Data Storage

All data stored in `%LOCALAPPDATA%\RedBullTracker\`:
- `config.json`: `rightClickCan` (default `default`), `shiftRightClickCan` (default `sugarfree`), `apiUrl`, `apiToken`, `startWithWindows`. `REDBULL_API_URL` / `REDBULL_API_TOKEN` override. Legacy `canType` is only used to import `count.txt`.
- `counts.json`: offline counts per can type
- `count.txt`: pre-v4.1 single-type count, imported into `counts.json` once

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
- **Release** (`.github/workflows/release.yml`): Runs on version tags. Builds the NativeAOT exe and zip, extracts changelog notes, creates GitHub release with artifacts.

## Commit Guidelines

- Do not add co-author trailers (e.g. `Co-Authored-By: ...`) to commits.
- Use clear, descriptive commit messages. Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, etc.) are used throughout the history.
