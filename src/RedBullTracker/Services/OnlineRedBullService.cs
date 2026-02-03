namespace RedBullTracker.Services;

/// <summary>
/// Placeholder for future API-backed implementation.
/// Currently just wraps OfflineRedBullService.
/// </summary>
public class OnlineRedBullService : IRedBullService
{
    private readonly OfflineRedBullService _offlineService;

    public int Count => _offlineService.Count;
    public event EventHandler? CountChanged
    {
        add => _offlineService.CountChanged += value;
        remove => _offlineService.CountChanged -= value;
    }

    public OnlineRedBullService(SettingsService settings)
    {
        _offlineService = new OfflineRedBullService(settings);
    }

    public Task AddCanAsync() => _offlineService.AddCanAsync();
    public Task RemoveCanAsync() => _offlineService.RemoveCanAsync();
}
