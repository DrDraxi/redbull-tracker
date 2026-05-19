namespace RedBullTracker.Services;

public interface IRedBullService
{
    int Count { get; }
    IReadOnlyDictionary<string, int> ByType { get; }
    bool IsReadOnly { get; }
    event EventHandler? CountChanged;
    Task AddCanAsync();
    Task RemoveCanAsync();
}
