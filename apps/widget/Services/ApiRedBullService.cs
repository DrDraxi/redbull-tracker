using System.Net.Http.Headers;
using System.Text.Json;
using RedBullTracker.Models;

namespace RedBullTracker.Services;

public class ApiRedBullService : IRedBullService, IDisposable
{
    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan HttpTimeout = TimeSpan.FromSeconds(3);

    private readonly HttpClient _http;
    private readonly string _token;
    private System.Threading.Timer? _timer;
    private Dictionary<string, int> _byType = new();
    private int _count;
    private bool _isStale;
    private bool _disposed;

    public int Count => _count;
    public IReadOnlyDictionary<string, int> ByType => _byType;
    public bool IsReadOnly => true;
    public bool IsStale => _isStale;
    public event EventHandler? CountChanged;

    public ApiRedBullService(HttpClient http, string token)
    {
        _http = http;
        _token = token;
        _http.Timeout = HttpTimeout;
    }

    public void StartPolling()
    {
        _timer = new System.Threading.Timer(
            async _ => await RefreshAsync(),
            null,
            TimeSpan.Zero,
            PollInterval);
    }

    public async Task RefreshAsync()
    {
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Get, "/api/v1/stock");
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
            using var resp = await _http.SendAsync(req).ConfigureAwait(false);

            if (!resp.IsSuccessStatusCode)
            {
                MarkStale();
                return;
            }

            var stream = await resp.Content.ReadAsStreamAsync().ConfigureAwait(false);
            var stock = await JsonSerializer.DeserializeAsync(stream, AppJsonContext.Default.StockResponse).ConfigureAwait(false);
            if (stock is null)
            {
                MarkStale();
                return;
            }

            var newByType = stock.ByType ?? new Dictionary<string, int>();
            var newTotal = stock.Total;
            var changed = newTotal != _count || !DictEquals(newByType, _byType) || _isStale;

            _byType = newByType;
            _count = newTotal;
            _isStale = false;

            if (changed)
                CountChanged?.Invoke(this, EventArgs.Empty);
        }
        catch
        {
            MarkStale();
        }
    }

    private void MarkStale()
    {
        if (!_isStale)
        {
            _isStale = true;
            CountChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    private static bool DictEquals(IDictionary<string, int> a, IDictionary<string, int> b)
    {
        if (a.Count != b.Count) return false;
        foreach (var kv in a)
            if (!b.TryGetValue(kv.Key, out var v) || v != kv.Value) return false;
        return true;
    }

    public Task AddCanAsync() => throw new InvalidOperationException("Widget is in read-only API mode");
    public Task RemoveCanAsync() => throw new InvalidOperationException("Widget is in read-only API mode");

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _timer?.Dispose();
        _http.Dispose();
    }
}
