using TaskbarWidget;

namespace RedBullTracker;

/// <summary>How the widget gets its numbers.</summary>
public enum CanMode { Offline, Api, Misconfigured }

/// <summary>
/// %LOCALAPPDATA%\RedBullTracker\config.json: rightClickCan, shiftRightClickCan, apiUrl, apiToken,
/// startWithWindows (canType is only used to import an old count.txt). REDBULL_API_URL /
/// REDBULL_API_TOKEN environment variables override the file.
/// </summary>
public sealed class RedBullConfig
{
    readonly JsonConfig _json;

    public RedBullConfig(string? dataDir = null)
    {
        DataDir = dataDir ?? AppKit.DataDir("RedBullTracker");
        _json = new JsonConfig(Path.Combine(DataDir, "config.json"));
        if (!_json.Exists)
        {
            _json.Root["rightClickCan"] = "default";
            _json.Root["shiftRightClickCan"] = "sugarfree";
            _json.Root["apiUrl"] = null;
            _json.Root["apiToken"] = null;
            _json.Root["startWithWindows"] = true;
            _json.Save();
        }
        else if (_json.LoadError == null && (_json["rightClickCan"] == null || _json["shiftRightClickCan"] == null))
        {
            // Older config: add the new keys so they're discoverable in the file.
            if (_json["rightClickCan"] == null) _json.Set("rightClickCan", "default");
            if (_json["shiftRightClickCan"] == null) _json.Set("shiftRightClickCan", "sugarfree");
            _json.Save();
        }
    }

    /// <summary>Re-reads config.json (cheap; called before acting on it so edits apply without a restart).</summary>
    public void Reload() => _json.Reload();

    public string DataDir { get; }
    public string FilePath => _json.Path;
    public string CountsFile => Path.Combine(DataDir, "counts.json");
    /// <summary>Pre-v4.1 single-type counter, imported once into counts.json.</summary>
    public string LegacyCountFile => Path.Combine(DataDir, "count.txt");
    public string LegacyCanType => _json.GetString("canType") ?? "default";

    /// <summary>Can type added by a plain right-click. Default "default" (regular Red Bull).</summary>
    public string RightClickCan => _json.GetString("rightClickCan")?.Trim().ToLowerInvariant() ?? "default";
    /// <summary>Can type added by Shift+right-click. Default "sugarfree".</summary>
    public string ShiftRightClickCan => _json.GetString("shiftRightClickCan")?.Trim().ToLowerInvariant() ?? "sugarfree";
    public bool StartWithWindows => _json.GetBool("startWithWindows", true);

    public string? ApiUrl => First(Environment.GetEnvironmentVariable("REDBULL_API_URL"), _json.GetString("apiUrl"));
    public string? ApiToken => First(Environment.GetEnvironmentVariable("REDBULL_API_TOKEN"), _json.GetString("apiToken"));

    public void SetStartWithWindows(bool enabled)
    {
        _json.Set("startWithWindows", enabled);
        _json.Save();
    }

    /// <summary>Decides the mode. A half-configured API no longer crashes the app at startup; it's shown in the widget instead.</summary>
    public static (CanMode Mode, string? Problem) ResolveMode(string? apiUrl, string? apiToken, string? configError = null)
    {
        if (configError != null) return (CanMode.Misconfigured, configError);
        if (string.IsNullOrWhiteSpace(apiUrl)) return (CanMode.Offline, null);
        if (!Uri.TryCreate(apiUrl, UriKind.Absolute, out var uri) || (uri.Scheme != "https" && uri.Scheme != "http"))
            return (CanMode.Misconfigured, $"apiUrl \"{apiUrl}\" is not a valid http(s) URL");
        if (string.IsNullOrWhiteSpace(apiToken))
            return (CanMode.Misconfigured, "apiUrl is set but apiToken is missing");
        return (CanMode.Api, null);
    }

    public (CanMode Mode, string? Problem) Mode => ResolveMode(ApiUrl, ApiToken, _json.LoadError);

    static string? First(string? a, string? b) => !string.IsNullOrWhiteSpace(a) ? a.Trim() : !string.IsNullOrWhiteSpace(b) ? b.Trim() : null;
}
