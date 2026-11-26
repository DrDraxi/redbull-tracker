# RedBull Tracker

A Windows taskbar widget to track your Red Bull consumption.

![RedBull Tracker Widget](docs/screenshot.png)

## Features

- **3D cans**: one real-time-rendered can per Red Bull in stock. Hover pops a can out above the taskbar, new cans fall in spinning, drinking one crushes it
- **Modern Windows 11 look**: crisp Direct2D rendering, cans lift when you hover them, smooth tooltips
- **Offline or synced**: keep a local count, or sync stock with the Red Bull Tracker API (`apps/api`)
- **Tiny**: a single ~2 MB native exe, a few MB of memory, no CPU while idle
- **Plays nicely with other widgets**: drag to reorder; widgets never overlap or jump around

## Installation

1. Download `RedBullTracker-vX.Y.Z-win-x64.exe` from [Releases](https://github.com/DrDraxi/redbull-tracker/releases)
2. Run it. The widget appears next to the system tray. No installer or .NET runtime needed.

## Usage

- **Left-click a can** to drink it
- **Right-click** to add a Red Bull, **Shift+right-click** to add a Sugarfree (configurable, see below)
- **Ctrl+right-click** for the menu: add cans, settings, start with Windows, exit (in API mode a plain right-click opens it)
- **Drag** the widget to reorder it among other taskbar widgets
- **Hover** for counts per can type

## Configuration

Configuration is stored in `%LOCALAPPDATA%\RedBullTracker\config.json` (menu → *Edit settings…*):

```json
{
  "rightClickCan": "default",
  "shiftRightClickCan": "sugarfree",
  "apiUrl": null,
  "apiToken": null,
  "startWithWindows": true
}
```

| Option | Description | Values |
|--------|-------------|--------|
| `rightClickCan` | Can added by right-click | `"default"`, `"sugarfree"` (any name works; unknown types use a generic can) |
| `shiftRightClickCan` | Can added by Shift+right-click | same as above |
| `apiUrl` | Red Bull Tracker API base URL. When set, the widget syncs stock every 5 s | URL or `null` |
| `apiToken` | Bearer token for the API (required with `apiUrl`) | string or `null` |
| `startWithWindows` | Launch on Windows startup | `true`, `false` |

The `REDBULL_API_URL` and `REDBULL_API_TOKEN` environment variables override the file.

Offline counts are kept per can type in `counts.json` next to the config. An old `count.txt` is imported once, using the legacy `canType` setting for its type.

## Building from Source

This is a monorepo. The widget lives in `apps/widget/`; the API lives in `apps/api/`.

```bash
# Clone with submodules
git clone --recursive https://github.com/DrDraxi/redbull-tracker.git
cd redbull-tracker

# Build
dotnet build -p:Platform=x64

# Run
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64
```

## Requirements

- Windows 10/11
- Nothing at runtime. The release exe is native (NativeAOT). Building needs the .NET 10 SDK.

## License

MIT
