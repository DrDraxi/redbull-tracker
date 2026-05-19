namespace RedBullTracker.Services;

public interface IRedBullService
{
    int Count { get; }
    IReadOnlyDictionary<string, int> ByType { get; }

    /// <summary>True when right-click add isn't available (API mode).
    /// Per-can left-click remove still works in all modes.</summary>
    bool IsReadOnly { get; }

    event EventHandler? CountChanged;

    Task AddCanAsync();

    /// <summary>Remove (drink) one can. In API mode <paramref name="type"/> is
    /// required so the server knows which to decrement; in offline mode it is
    /// ignored (offline tracks a single configured type).</summary>
    Task RemoveCanAsync(string? type = null);
}
