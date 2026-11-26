using System.Text;
using RedBullTracker;

namespace RedBullTracker.Tests;

public class StockParseTests
{
    static Stock Parse(string json) => Stock.Parse(Encoding.UTF8.GetBytes(json));

    [Fact]
    public void ParsesTotalAndTypes()
    {
        var s = Parse("""{"total":3,"by_type":{"default":2,"sugarfree":1},"updated_at":"2026-01-01T00:00:00Z"}""");
        Assert.Equal(3, s.Total);
        Assert.Equal(2, s.ByType["default"]);
        Assert.Equal(1, s.ByType["sugarfree"]);
    }

    [Fact]
    public void DropsEmptyAndInvalidTypes()
    {
        var s = Parse("""{"total":1,"by_type":{"default":1,"sugarfree":0,"zero":-2,"weird":"x"}}""");
        Assert.Single(s.ByType);
        Assert.Equal(1, s.ByType["default"]);
    }

    [Fact]
    public void MissingTotalIsSumOfTypes()
    {
        var s = Parse("""{"by_type":{"default":2,"sugarfree":3}}""");
        Assert.Equal(5, s.Total);
    }

    [Fact]
    public void EmptyObjectIsZero()
    {
        var s = Parse("{}");
        Assert.Equal(0, s.Total);
        Assert.Empty(s.ByType);
    }
}

public class ModeTests
{
    [Fact] public void NoUrlMeansOffline() =>
        Assert.Equal(CanMode.Offline, RedBullConfig.ResolveMode(null, null).Mode);

    [Fact] public void UrlAndTokenMeansApi() =>
        Assert.Equal(CanMode.Api, RedBullConfig.ResolveMode("https://example.test", "tok").Mode);

    [Fact]
    public void UrlWithoutTokenIsReportedNotThrown()
    {
        var (mode, problem) = RedBullConfig.ResolveMode("https://example.test", "  ");
        Assert.Equal(CanMode.Misconfigured, mode);
        Assert.Contains("apiToken", problem);
    }

    [Theory]
    [InlineData("not a url")]
    [InlineData("ftp://example.test")]
    public void InvalidUrlIsReported(string url) =>
        Assert.Equal(CanMode.Misconfigured, RedBullConfig.ResolveMode(url, "tok").Mode);

    [Fact]
    public void BrokenConfigFileIsReported()
    {
        var (mode, problem) = RedBullConfig.ResolveMode(null, null, "config.json is invalid");
        Assert.Equal(CanMode.Misconfigured, mode);
        Assert.Equal("config.json is invalid", problem);
    }
}

public sealed class OfflineCansTests : IDisposable
{
    readonly string _dir = Directory.CreateTempSubdirectory("rbt-test-").FullName;
    string CountFile => Path.Combine(_dir, "count.txt");

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    [Fact]
    public void ReadsExistingCount()
    {
        File.WriteAllText(CountFile, " 4 \n");
        var cans = new OfflineCans(CountFile, "sugarfree");
        Assert.Equal(4, cans.Total);
        Assert.Equal(4, cans.ByType["sugarfree"]);
    }

    [Fact]
    public void MissingOrCorruptFileStartsAtZero()
    {
        Assert.Equal(0, new OfflineCans(CountFile, "default").Total);
        File.WriteAllText(CountFile, "lots");
        Assert.Equal(0, new OfflineCans(CountFile, "default").Total);
    }

    [Fact]
    public void AddAndDrinkPersistAndNotify()
    {
        var cans = new OfflineCans(CountFile, "default");
        int changes = 0;
        cans.Changed += () => changes++;

        cans.Add(); cans.Add(); cans.Drink("default");

        Assert.Equal(1, cans.Total);
        Assert.Equal(3, changes);
        Assert.Equal("1", File.ReadAllText(CountFile));
        Assert.Equal(1, new OfflineCans(CountFile, "default").Total);
    }

    [Fact]
    public void DrinkingNeverGoesNegative()
    {
        var cans = new OfflineCans(CountFile, "default");
        int changes = 0;
        cans.Changed += () => changes++;
        cans.Drink("default");
        Assert.Equal(0, cans.Total);
        Assert.Equal(0, changes);
        Assert.Empty(cans.ByType);
    }
}

public sealed class ConfigTests : IDisposable
{
    readonly string _dir = Directory.CreateTempSubdirectory("rbt-cfg-").FullName;
    public void Dispose() => Directory.Delete(_dir, recursive: true);

    [Fact]
    public void CreatesDefaultConfig()
    {
        var cfg = new RedBullConfig(_dir);
        Assert.True(File.Exists(cfg.FilePath));
        Assert.Equal("default", cfg.CanType);
        Assert.True(cfg.StartWithWindows);
    }

    [Fact]
    public void ReadsKeysCaseInsensitivelyAndKeepsUnknownKeys()
    {
        File.WriteAllText(Path.Combine(_dir, "config.json"),
            """{ "CanType": "sugarfree", "startWithWindows": true, "myNote": "keep me" }""");
        var cfg = new RedBullConfig(_dir);
        Assert.Equal("sugarfree", cfg.CanType);

        cfg.SetStartWithWindows(false);
        var saved = File.ReadAllText(cfg.FilePath);
        Assert.Contains("keep me", saved);
        Assert.False(new RedBullConfig(_dir).StartWithWindows);
    }

    [Fact]
    public void InvalidJsonIsNeverOverwritten()
    {
        var path = Path.Combine(_dir, "config.json");
        File.WriteAllText(path, "{ not json");
        var cfg = new RedBullConfig(_dir);
        Assert.Equal(CanMode.Misconfigured, cfg.Mode.Mode);
        cfg.SetStartWithWindows(false);
        Assert.Equal("{ not json", File.ReadAllText(path));
    }
}
