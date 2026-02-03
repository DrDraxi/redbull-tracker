namespace RedBullTracker.Services;

public class OfflineRedBullService : IRedBullService
{
    private readonly SettingsService _settings;
    private int _count;

    public int Count => _count;
    public event EventHandler? CountChanged;

    public OfflineRedBullService(SettingsService settings)
    {
        _settings = settings;
        _count = _settings.LoadCount();
    }

    public Task AddCanAsync()
    {
        _count++;
        _settings.SaveCount(_count);
        CountChanged?.Invoke(this, EventArgs.Empty);
        return Task.CompletedTask;
    }

    public Task RemoveCanAsync()
    {
        if (_count > 0)
        {
            _count--;
            _settings.SaveCount(_count);
            CountChanged?.Invoke(this, EventArgs.Empty);
        }
        return Task.CompletedTask;
    }
}
