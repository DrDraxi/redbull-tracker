using System.Text.Json.Serialization;

namespace RedBullTracker.Models;

public class AppConfig
{
    /// <summary>
    /// Can type to display: "default" or "sugarfree"
    /// </summary>
    [JsonPropertyName("canType")]
    public string CanType { get; set; } = "default";

    /// <summary>
    /// API URL for online mode. Leave empty/null for offline mode (local count).
    /// When both apiUrl and apiToken are set, the widget polls the API every 5s
    /// and disables clicks. Env vars REDBULL_API_URL / REDBULL_API_TOKEN override.
    /// </summary>
    [JsonPropertyName("apiUrl")]
    public string? ApiUrl { get; set; }

    /// <summary>
    /// Bearer token for the API. Required when apiUrl is set.
    /// </summary>
    [JsonPropertyName("apiToken")]
    public string? ApiToken { get; set; }

    /// <summary>
    /// Whether to start the app with Windows. Enabled by default.
    /// </summary>
    [JsonPropertyName("startWithWindows")]
    public bool StartWithWindows { get; set; } = true;
}
