using System.Text.Json.Serialization;
using RedBullTracker.Models;

namespace RedBullTracker;

[JsonSourceGenerationOptions(WriteIndented = true)]
[JsonSerializable(typeof(AppConfig))]
internal partial class AppJsonContext : JsonSerializerContext { }
