using System.Net.Http;

namespace RedBullTracker.Services;

public static class RedBullServiceFactory
{
    public static IRedBullService Create(SettingsService settings)
    {
        var apiUrl = Environment.GetEnvironmentVariable("REDBULL_API_URL");
        var apiToken = Environment.GetEnvironmentVariable("REDBULL_API_TOKEN");

        if (string.IsNullOrEmpty(apiUrl))
            return new OfflineRedBullService(settings);

        if (string.IsNullOrEmpty(apiToken))
            throw new InvalidOperationException(
                "REDBULL_API_URL is set but REDBULL_API_TOKEN is missing");

        var handler = new SocketsHttpHandler
        {
            PooledConnectionLifetime = TimeSpan.FromMinutes(10)
        };
        var http = new HttpClient(handler) { BaseAddress = new Uri(apiUrl) };
        var svc = new ApiRedBullService(http, apiToken);
        svc.StartPolling();
        return svc;
    }
}
