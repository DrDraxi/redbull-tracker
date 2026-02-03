using Microsoft.UI;
using Microsoft.UI.Content;
using Microsoft.UI.Xaml.Hosting;
using Microsoft.UI.Xaml.Media;
using RedBullTracker.Services;
using TaskbarWidget;

namespace RedBullTracker.Widget;

public class RedBullWidget : IDisposable
{
    private const string WidgetClassName = "RedBullTrackerTaskbarWidget";
    private const int MinWidthDip = 32;

    private readonly IRedBullService _service;
    private readonly string _canType;
    private TaskbarInjectionHelper? _injectionHelper;
    private DesktopWindowXamlSource? _xamlSource;
    private RedBullWidgetContent? _content;
    private bool _disposed;

    public RedBullWidget(IRedBullService service, string canType = "default")
    {
        _service = service;
        _canType = canType;
        _service.CountChanged += OnCountChanged;
    }

    public void Initialize()
    {
        // Calculate initial width based on current count
        var initialWidth = CalculateWidth(_service.Count);

        var config = new TaskbarInjectionConfig
        {
            ClassName = WidgetClassName,
            WindowTitle = "RedBullTracker",
            WidthDip = initialWidth,
            DeferInjection = true
        };

        _injectionHelper = new TaskbarInjectionHelper(config);
        var result = _injectionHelper.Initialize();

        if (!result.Success || result.WindowHandle == IntPtr.Zero)
        {
            return;
        }

        var windowId = Win32Interop.GetWindowIdFromWindow(result.WindowHandle);
        _xamlSource = new DesktopWindowXamlSource();
        _xamlSource.Initialize(windowId);
        _xamlSource.SiteBridge.ResizePolicy = ContentSizePolicy.ResizeContentToParentWindow;

        _content = new RedBullWidgetContent();
        _content.SetCanType(_canType);
        _content.LeftClicked += OnLeftClicked;
        _content.RightClicked += OnRightClicked;
        _content.WidthChanged += OnWidthChanged;
        _content.UpdateCount(_service.Count);

        var rootGrid = new Microsoft.UI.Xaml.Controls.Grid
        {
            Background = new SolidColorBrush(Windows.UI.Color.FromArgb(0, 0, 0, 0))
        };
        rootGrid.Children.Add(_content);

        _xamlSource.Content = rootGrid;
        _injectionHelper.Inject();
        _injectionHelper.Show();
    }

    private int CalculateWidth(int count)
    {
        if (count == 0)
        {
            return MinWidthDip;
        }
        // 12px per can + 2px spacing between cans + padding
        return Math.Max(MinWidthDip, (count * 12) + ((count - 1) * 2) + 12);
    }

    private void OnWidthChanged(object? sender, int newWidth)
    {
        _injectionHelper?.Resize(Math.Max(MinWidthDip, newWidth));
    }

    private void OnCountChanged(object? sender, EventArgs e)
    {
        _content?.DispatcherQueue?.TryEnqueue(() =>
        {
            _content?.UpdateCount(_service.Count);
        });
    }

    private async void OnLeftClicked(object? sender, EventArgs e)
    {
        await _service.RemoveCanAsync();
    }

    private async void OnRightClicked(object? sender, EventArgs e)
    {
        await _service.AddCanAsync();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        _service.CountChanged -= OnCountChanged;

        if (_content != null)
        {
            _content.LeftClicked -= OnLeftClicked;
            _content.RightClicked -= OnRightClicked;
            _content.WidthChanged -= OnWidthChanged;
        }

        _xamlSource?.Dispose();
        _injectionHelper?.Dispose();
    }
}
