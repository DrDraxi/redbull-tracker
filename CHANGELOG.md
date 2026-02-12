# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
