using System.Text.Json.Serialization;

namespace RedBullTracker.Models;

public class AdjustRequest
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "";

    [JsonPropertyName("delta")]
    public int Delta { get; set; }
}
