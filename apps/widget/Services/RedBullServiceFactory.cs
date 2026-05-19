using System.Net.Http;

namespace RedBullTracker.Services;

public static class RedBullServiceFactory
{
    public static IRedBullService Create(SettingsService settings)
    {
        // Env vars override config.json so dev can swap targets without editing the file.
        var apiUrl = FirstNonEmpty(
            Environment.GetEnvironmentVariable("REDBULL_API_URL"),
            settings.Config.ApiUrl);
        var apiToken = FirstNonEmpty(
            Environment.GetEnvironmentVariable("REDBULL_API_TOKEN"),
            settings.Config.ApiToken);

        if (string.IsNullOrEmpty(apiUrl))
            return new OfflineRedBullService(settings);

        if (string.IsNullOrEmpty(apiToken))
            throw new InvalidOperationException(
                "apiUrl is set (config.json or REDBULL_API_URL) but apiToken is missing");

        var handler = new SocketsHttpHandler
        {
            PooledConnectionLifetime = TimeSpan.FromMinutes(10)
        };
        var http = new HttpClient(handler) { BaseAddress = new Uri(apiUrl) };
        var svc = new ApiRedBullService(http, apiToken);
        svc.StartPolling();
        return svc;
    }

    private static string? FirstNonEmpty(string? a, string? b)
        => !string.IsNullOrEmpty(a) ? a : b;
}
