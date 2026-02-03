# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RedBull Tracker is a Windows taskbar widget that tracks Red Bull consumption. It displays cans visually in the taskbar, allowing quick add/remove with mouse clicks. Supports offline mode with local persistence and configurable can types.

## Build Commands

```bash
# Build the solution
dotnet build -p:Platform=x64

# Build release
dotnet build --configuration Release -p:Platform=x64

# Run the app (x64)
dotnet run --project src/RedBullTracker/RedBullTracker.csproj -p:Platform=x64

# Publish single-file exe (x64)
dotnet publish src/RedBullTracker/RedBullTracker.csproj --configuration Release --runtime win-x64 --self-contained true -p:Platform=x64 -p:PublishSingleFile=true -p:WindowsPackageType=None -o publish
```

## Architecture

### Solution Structure

- **RedBullTracker** (`src/RedBullTracker/`) - WinUI 3 app with taskbar widget
- **TaskbarWidget** (`lib/taskbar-widget/`) - Git submodule for taskbar widget injection

After cloning, initialize the submodule:
```bash
git submodule update --init --recursive
```

### Key Components

```
src/RedBullTracker/
├── Program.cs              # Entry point with ComWrappers init
├── App.xaml.cs             # Creates widget, syncs startup settings
├── MainWindow.xaml.cs      # Hidden window (WinUI lifecycle requirement)
├── Widget/
│   ├── RedBullWidget.cs           # Injection orchestrator
│   └── RedBullWidgetContent.xaml  # Visual UI with can images
├── Services/
│   ├── IRedBullService.cs         # Interface for count operations
│   ├── OfflineRedBullService.cs   # Local counter with persistence
│   ├── OnlineRedBullService.cs    # API mock (placeholder)
│   ├── SettingsService.cs         # Config and count persistence
│   └── StartupService.cs          # Windows startup registry
└── Models/
    ├── RedBull.cs                 # Count model
    └── AppConfig.cs               # Configuration model
```

### Widget System

The widget uses `TaskbarInjectionHelper` from the submodule:
1. Creates a host window with `DeferInjection=true`
2. Sets up `DesktopWindowXamlSource` for WinUI content
3. Injects into taskbar after XAML setup
4. Dynamically resizes based on can count

### Services

- **OfflineRedBullService**: Manages count with file persistence
- **SettingsService**: Loads/saves config.json and count.txt
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

## Gotchas

- **Platform required**: WinUI 3 requires explicit platform. Use `-p:Platform=x64` for all commands.
- **Hidden MainWindow**: Don't call `Activate()` on MainWindow - it must stay hidden for widget-only mode.
- **Submodule**: Must initialize submodule before building.

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

4. The workflow will automatically:
   - Build the exe and zip artifacts
   - Extract release notes from CHANGELOG.md for this version
   - Create a GitHub release with the artifacts and notes

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

### Workflows

- **CI** (`.github/workflows/ci.yml`): Runs on all pushes and PRs
  - Builds debug and release
  - Uploads portable exe artifact

- **Release** (`.github/workflows/release.yml`): Runs on version tags
  - Builds single-file exe and zip
  - Extracts changelog notes
  - Creates GitHub release with artifacts

## Commit Guidelines

Do not add `Co-Authored-By: Claude` or similar co-author lines to commits.
