using System;
using RedBullTracker.Services;

namespace RedBullTracker.Tests;

public class RedBullServiceFactoryTests
{
    [Fact]
    public void Create_NoApiUrl_ReturnsOffline()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        var settings = new SettingsService();
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
            var settings = new SettingsService();
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
            var settings = new SettingsService();
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
}
