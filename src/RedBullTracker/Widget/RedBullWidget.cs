using RedBullTracker.Services;
using TaskbarWidget;
using TaskbarWidget.Rendering;

namespace RedBullTracker.Widget;

public class RedBullWidget : IDisposable
{
    private const int CanWidthDip = 12;
    private const int CanHeightDip = 24;
    private const int CanSpacing = 2;

    private readonly IRedBullService _service;
    private readonly string _canType;
    private TaskbarWidget.Widget? _widget;
    private WidgetImage? _canImage;
    private WidgetImage? _emptyImage;
    private bool _disposed;

    public RedBullWidget(IRedBullService service, string canType = "default")
    {
        _service = service;
        _canType = canType;
        _service.CountChanged += OnCountChanged;
    }

    public void Initialize()
    {
        LoadImages();

        _widget = new TaskbarWidget.Widget("RedBull", render: ctx =>
        {
            ctx.Panel(p =>
            {
                int count = _service.Count;

                p.Horizontal(CanSpacing, h =>
                {
                    if (count == 0)
                    {
                        h.DrawImage(_emptyImage!, widthDip: CanWidthDip, heightDip: CanHeightDip);
                    }
                    else
                    {
                        for (int i = 0; i < count; i++)
                            h.DrawImage(_canImage!, widthDip: CanWidthDip, heightDip: CanHeightDip);
                    }
                });

                p.OnClick(() => _ = _service.RemoveCanAsync());
                p.OnRightClick(() => _ = _service.AddCanAsync());
                p.Tooltip($"Red Bulls: {count}\nLeft-click: Remove | Right-click: Add");
            });
        });

        _widget.Show();
    }

    private void LoadImages()
    {
        var asm = typeof(RedBullWidget).Assembly;
        var canFileName = _canType?.ToLowerInvariant() == "sugarfree"
            ? "redbull-sugarfree.png"
            : "redbull-default.png";

        _canImage = WidgetImage.FromResource(asm, $"RedBullTracker.Assets.{canFileName}");
        _emptyImage = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-empty.png");
    }

    private void OnCountChanged(object? sender, EventArgs e)
    {
        _widget?.Invalidate();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _service.CountChanged -= OnCountChanged;
        _widget?.Dispose();
    }
}
