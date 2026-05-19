namespace RedBullTracker.Services;

public class OfflineRedBullService : IRedBullService
{
    private readonly SettingsService _settings;
    private readonly string _canType;
    private int _count;

    public int Count => _count;
    public bool IsReadOnly => false;
    public IReadOnlyDictionary<string, int> ByType
    {
        get
        {
            if (_count == 0)
                return new Dictionary<string, int>();
            return new Dictionary<string, int> { [_canType] = _count };
        }
    }

    public event EventHandler? CountChanged;

    public OfflineRedBullService(SettingsService settings)
    {
        _settings = settings;
        _canType = settings.Config.CanType ?? "default";
        _count = _settings.LoadCount();
    }

    public Task AddCanAsync()
    {
        _count++;
        _settings.SaveCount(_count);
        CountChanged?.Invoke(this, EventArgs.Empty);
        return Task.CompletedTask;
    }

    public Task RemoveCanAsync(string? type = null)
    {
        // Offline tracks a single type; ignore the type parameter.
        if (_count > 0)
        {
            _count--;
            _settings.SaveCount(_count);
            CountChanged?.Invoke(this, EventArgs.Empty);
        }
        return Task.CompletedTask;
    }
}
