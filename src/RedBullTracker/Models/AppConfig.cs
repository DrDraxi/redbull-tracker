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
    /// API URL for online mode. Leave empty for offline mode.
    /// </summary>
    [JsonPropertyName("apiUrl")]
    public string? ApiUrl { get; set; }

    /// <summary>
    /// Whether to use online mode (requires apiUrl to be set)
    /// </summary>
    [JsonPropertyName("useOnlineMode")]
    public bool UseOnlineMode { get; set; } = false;

    /// <summary>
    /// Whether to start the app with Windows. Enabled by default.
    /// </summary>
    [JsonPropertyName("startWithWindows")]
    public bool StartWithWindows { get; set; } = true;
}
