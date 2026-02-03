using Microsoft.UI.Xaml;
using RedBullTracker.Services;
using RedBullTracker.Widget;

namespace RedBullTracker;

public partial class App : Application
{
    private MainWindow? _mainWindow;
    private RedBullWidget? _widget;
    private readonly SettingsService _settings;
    private readonly IRedBullService _redBullService;

    public App()
    {
        InitializeComponent();
        _settings = new SettingsService();
        _redBullService = new OfflineRedBullService(_settings);

        // Sync startup with Windows setting
        StartupService.SyncWithConfig(_settings.Config.StartWithWindows);
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        // Create hidden window (required for WinUI lifecycle)
        _mainWindow = new MainWindow();
        // Don't call Activate() - keep window hidden

        // Create and show the widget with configured can type
        var canType = _settings.Config.CanType;
        _widget = new RedBullWidget(_redBullService, canType);
        _widget.Initialize();
    }
}
