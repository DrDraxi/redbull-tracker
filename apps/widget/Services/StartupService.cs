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
        // Always call SetStartupEnabled when enabled to update the exe path
        // in case the app was moved to a new location
        if (startWithWindows)
        {
            SetStartupEnabled(true);
        }
        else if (IsStartupEnabled())
        {
            SetStartupEnabled(false);
        }
    }
}
