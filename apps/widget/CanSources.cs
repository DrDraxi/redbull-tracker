using System.Text.Json;
using TaskbarWidget;

namespace RedBullTracker;

/// <summary>Where the cans come from. All members are used on the UI thread only.</summary>
public interface ICanSource
{
    /// <summary>Cans in stock per type (only types with a count &gt; 0).</summary>
    IReadOnlyDictionary<string, int> ByType { get; }
    int Total { get; }
    bool CanAdd { get; }
    /// <summary>Last refresh failed; numbers may be out of date.</summary>
    bool IsStale { get; }
    string? Problem { get; }
    event Action? Changed;
    void Add(string type);
    void Drink(string type);
    void Refresh();
}

/// <summary>
/// Local per-type counts in counts.json (e.g. {"default": 2, "sugarfree": 1}).
/// On first run the old single-type count.txt is imported as <c>legacyType</c> (count.txt itself is left alone).
/// </summary>
public sealed class OfflineCans : ICanSource
{
    readonly string _file;
    readonly SortedDictionary<string, int> _counts = new(StringComparer.Ordinal);

    public OfflineCans(string countsFile, string? legacyCountFile = null, string legacyType = "default")
    {
        _file = countsFile;
        if (File.Exists(countsFile))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllBytes(countsFile));
                if (doc.RootElement.ValueKind == JsonValueKind.Object)
                    foreach (var p in doc.RootElement.EnumerateObject())
                        if (p.Value.ValueKind == JsonValueKind.Number && p.Value.TryGetInt32(out var n) && n > 0)
                            _counts[Normalize(p.Name)] = n;
            }
            catch { /* corrupt file: start empty */ }
        }
        else if (legacyCountFile != null && File.Exists(legacyCountFile))
        {
            try
            {
                if (int.TryParse(File.ReadAllText(legacyCountFile).Trim(), out var n) && n > 0)
                {
                    _counts[Normalize(legacyType)] = n;
                    Save();
                }
            }
            catch { }
        }
    }

    public IReadOnlyDictionary<string, int> ByType => new Dictionary<string, int>(_counts);
    public int Total => _counts.Values.Sum();
    public bool CanAdd => true;
    public bool IsStale => false;
    public string? Problem => null;
    public event Action? Changed;

    public void Add(string type)
    {
        type = Normalize(type);
        _counts[type] = _counts.GetValueOrDefault(type) + 1;
        Save();
        Changed?.Invoke();
    }

    public void Drink(string type)
    {
        type = Normalize(type);
        if (!_counts.TryGetValue(type, out var n) || n <= 0) return;
        if (n == 1) _counts.Remove(type); else _counts[type] = n - 1;
        Save();
        Changed?.Invoke();
    }

    public void Refresh() { }

    static string Normalize(string type) => string.IsNullOrWhiteSpace(type) ? "default" : type.Trim().ToLowerInvariant();

    void Save()
    {
        var body = string.Join(",\n", _counts.Select(kv => $"  \"{JsonEncodedText.Encode(kv.Key)}\": {kv.Value}"));
        try { AppKit.WriteAllTextAtomic(_file, _counts.Count == 0 ? "{}" : "{\n" + body + "\n}"); } catch { }
    }
}

/// <summary>Stock synced from the RedBull Tracker API (GET /api/v1/stock, POST /api/v1/adjust).</summary>
public sealed class ApiCans : ICanSource
{
    static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(5);

    readonly Uri _base;
    readonly string _token;
    readonly Action<Action> _post; // marshal to the UI thread
    Dictionary<string, int> _byType = new();
    int _total, _busy, _pendingDrinks;
    int _generation; // bumped on every local change; polls started before it are discarded

    public ApiCans(string apiUrl, string token, Action<Action> postToUi)
    {
        _base = new Uri(apiUrl);
        _token = token;
        _post = postToUi;
    }

    public IReadOnlyDictionary<string, int> ByType => _byType;
    public int Total => _total;
    public bool CanAdd => false; // adding happens through receipts/photos on the server
    public bool IsStale { get; private set; } = true;
    public string? Problem { get; private set; }
    public bool HasLoaded { get; private set; }
    public TimeSpan Interval => PollInterval;
    public event Action? Changed;

    public string DashboardUrl => _base.GetLeftPart(UriPartial.Authority) + "/";

    public void Add(string type) { }

    public void Refresh()
    {
        if (Interlocked.Exchange(ref _busy, 1) == 1) return;
        int generation = _generation;
        ThreadPool.QueueUserWorkItem(_ =>
        {
            Stock? stock = null; string? error = null;
            try
            {
                var res = Http.Get(Url("/api/v1/stock"), Auth(), timeoutMs: 4000);
                if (res.Status is 401 or 403) error = "API rejected the token";
                else if (!res.IsSuccess) error = $"API error (HTTP {res.Status})";
                else stock = Stock.Parse(res.Body);
            }
            catch (Exception ex) { error = ex.Message; }

            _post(() =>
            {
                _busy = 0;
                // Don't let a snapshot taken before/while a drink was being recorded undo it.
                if (_pendingDrinks > 0 || generation != _generation) return;
                Apply(stock, error);
            });
        });
    }

    public void Drink(string type)
    {
        if (!_byType.TryGetValue(type, out var n) || n <= 0) return;

        // Optimistic: the can disappears immediately; the next poll reconciles with the server.
        var next = new Dictionary<string, int>(_byType);
        if (n == 1) next.Remove(type); else next[type] = n - 1;
        _byType = next; _total = Math.Max(0, _total - 1);
        _pendingDrinks++;
        _generation++;
        Changed?.Invoke();

        var body = $"{{\"type\":\"{JsonEncodedText.Encode(type)}\",\"delta\":-1}}";
        ThreadPool.QueueUserWorkItem(_ =>
        {
            string? error = null;
            try
            {
                var res = Http.PostJson(Url("/api/v1/adjust"), body, Auth(), timeoutMs: 6000);
                if (!res.IsSuccess) error = $"Couldn't record drink (HTTP {res.Status})";
            }
            catch (Exception ex) { error = ex.Message; }

            _post(() =>
            {
                _pendingDrinks--;
                if (error != null) { Problem = error; IsStale = true; }
                Refresh(); // reconcile either way
            });
        });
    }

    void Apply(Stock? stock, string? error)
    {
        if (stock == null)
        {
            bool changed = !IsStale || Problem != error;
            IsStale = true; Problem = error;
            if (changed) Changed?.Invoke();
            return;
        }

        bool diff = stock.Total != _total || IsStale || !HasLoaded || !Same(stock.ByType, _byType);
        _byType = stock.ByType; _total = stock.Total;
        IsStale = false; Problem = null; HasLoaded = true;
        if (diff) Changed?.Invoke();
    }

    string Url(string path) => new Uri(_base, path).ToString();
    KeyValuePair<string, string>[] Auth() => new[] { new KeyValuePair<string, string>("Authorization", "Bearer " + _token) };

    static bool Same(Dictionary<string, int> a, Dictionary<string, int> b) =>
        a.Count == b.Count && a.All(kv => b.TryGetValue(kv.Key, out var v) && v == kv.Value);
}

/// <summary>Static source shown when the config is broken, so the problem is visible instead of a silent crash.</summary>
public sealed class BrokenCans(string problem) : ICanSource
{
    public IReadOnlyDictionary<string, int> ByType { get; } = new Dictionary<string, int>();
    public int Total => 0;
    public bool CanAdd => false;
    public bool IsStale => true;
    public string? Problem => problem;
    public event Action? Changed { add { } remove { } }
    public void Add(string type) { }
    public void Drink(string type) { }
    public void Refresh() { }
}

public sealed record Stock(int Total, Dictionary<string, int> ByType)
{
    /// <summary>Parses {"total": n, "by_type": {"default": 2, ...}, "updated_at": ...}.</summary>
    public static Stock Parse(byte[] json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        var byType = new Dictionary<string, int>();
        if (root.TryGetProperty("by_type", out var bt) && bt.ValueKind == JsonValueKind.Object)
            foreach (var p in bt.EnumerateObject())
                if (p.Value.ValueKind == JsonValueKind.Number && p.Value.TryGetInt32(out var n) && n > 0)
                    byType[p.Name] = n;

        int total = root.TryGetProperty("total", out var t) && t.ValueKind == JsonValueKind.Number && t.TryGetInt32(out var tv)
            ? Math.Max(0, tv) : byType.Values.Sum();
        return new Stock(total, byType);
    }
}
