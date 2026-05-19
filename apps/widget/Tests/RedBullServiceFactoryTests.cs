using System;
using RedBullTracker.Models;
using RedBullTracker.Services;

namespace RedBullTracker.Tests;

public class RedBullServiceFactoryTests
{
    // SettingsService reads %LOCALAPPDATA%\RedBullTracker\config.json on
    // construction. Tests must overwrite Config with a known blank one so the
    // real user config (which may contain apiUrl + apiToken) doesn't leak in.
    private static SettingsService FreshSettings(AppConfig? cfg = null)
        => new SettingsService { Config = cfg ?? new AppConfig() };

    [Fact]
    public void Create_NoApiUrl_ReturnsOffline()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        var settings = FreshSettings();
        var svc = RedBullServiceFactory.Create(settings);

        Assert.IsType<OfflineRedBullService>(svc);
        Assert.False(svc.IsReadOnly);
    }

    [Fact]
    public void Create_WithApiUrlButNoToken_Throws()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", "http://localhost:5000");
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        try
        {
            var settings = FreshSettings();
            Assert.Throws<InvalidOperationException>(() => RedBullServiceFactory.Create(settings));
        }
        finally
        {
            Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        }
    }

    [Fact]
    public void Create_WithApiUrlAndToken_ReturnsApi()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", "http://localhost:5000");
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", "tok");

        try
        {
            var settings = FreshSettings();
            var svc = RedBullServiceFactory.Create(settings);

            Assert.IsType<ApiRedBullService>(svc);
            Assert.True(svc.IsReadOnly);
            (svc as IDisposable)?.Dispose();
        }
        finally
        {
            Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
            Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);
        }
    }

    [Fact]
    public void Create_WithConfigApiUrlAndToken_ReturnsApi()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        var settings = FreshSettings(new AppConfig
        {
            ApiUrl = "http://example.com",
            ApiToken = "from-config",
        });

        var svc = RedBullServiceFactory.Create(settings);
        Assert.IsType<ApiRedBullService>(svc);
        (svc as IDisposable)?.Dispose();
    }
}
