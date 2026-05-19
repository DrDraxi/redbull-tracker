using RedBullTracker.Services;
using RedBullTracker.Widget;

namespace RedBullTracker;

public static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        var settings = new SettingsService();
        var service = RedBullServiceFactory.Create(settings);

        StartupService.SyncWithConfig(settings.Config.StartWithWindows);

        var widget = new RedBullWidget(service);
        widget.Initialize();

        TaskbarWidget.Widget.RunMessageLoop();
    }
}
