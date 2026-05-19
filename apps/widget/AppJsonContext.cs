using System.Text.Json.Serialization;
using RedBullTracker.Models;

namespace RedBullTracker;

[JsonSourceGenerationOptions(WriteIndented = true)]
[JsonSerializable(typeof(AppConfig))]
[JsonSerializable(typeof(StockResponse))]
internal partial class AppJsonContext : JsonSerializerContext { }
