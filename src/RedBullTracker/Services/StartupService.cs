using Microsoft.Win32;

namespace RedBullTracker.Services;

public static class StartupService
{
    private const string AppName = "RedBullTracker";
    private const string StartupRegistryKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";

    public static bool IsStartupEnabled()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(StartupRegistryKey, false);
            return key?.GetValue(AppName) != null;
        }
        catch
        {
            return false;
        }
    }

    public static void SetStartupEnabled(bool enabled)
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(StartupRegistryKey, true);
            if (key == null) return;

            if (enabled)
            {
                var exePath = Environment.ProcessPath;
                if (!string.IsNullOrEmpty(exePath))
                {
                    key.SetValue(AppName, $"\"{exePath}\"");
                }
            }
            else
            {
                key.DeleteValue(AppName, false);
            }
        }
        catch
        {
            // Ignore registry errors
        }
    }

    /// <summary>
    /// Syncs the registry state with the config setting.
    /// Call this on app startup.
    /// </summary>
    public static void SyncWithConfig(bool startWithWindows)
    {
        var currentState = IsStartupEnabled();
        if (currentState != startWithWindows)
        {
            SetStartupEnabled(startWithWindows);
        }
    }
}
