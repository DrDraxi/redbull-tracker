namespace RedBullTracker.Services;

public interface IRedBullService
{
    int Count { get; }
    event EventHandler? CountChanged;
    Task AddCanAsync();
    Task RemoveCanAsync();
}
