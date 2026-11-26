using TaskbarWidget;

namespace RedBullTracker;

/// <summary>How the widget gets its numbers.</summary>
public enum CanMode { Offline, Api, Misconfigured }

/// <summary>
/// %LOCALAPPDATA%\RedBullTracker\config.json (same keys as before: canType, apiUrl, apiToken,
/// startWithWindows). REDBULL_API_URL / REDBULL_API_TOKEN environment variables override the file.
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
            _json.Root["canType"] = "default";
            _json.Root["apiUrl"] = null;
            _json.Root["apiToken"] = null;
            _json.Root["startWithWindows"] = true;
            _json.Save();
        }
    }

    public string DataDir { get; }
    public string FilePath => _json.Path;
    public string CountFile => Path.Combine(DataDir, "count.txt");

    public string CanType => _json.GetString("canType") ?? "default";
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
