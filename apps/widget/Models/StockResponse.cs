using System.Text.Json.Serialization;

namespace RedBullTracker.Models;

public class StockResponse
{
    [JsonPropertyName("total")]
    public int Total { get; set; }

    [JsonPropertyName("by_type")]
    public Dictionary<string, int> ByType { get; set; } = new();

    [JsonPropertyName("updated_at")]
    public string? UpdatedAt { get; set; }
}
