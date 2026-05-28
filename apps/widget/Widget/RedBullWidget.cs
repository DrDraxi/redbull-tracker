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
    private TaskbarWidget.Widget? _widget;
    private readonly Dictionary<string, WidgetImage> _icons = new();
    private WidgetImage? _genericIcon;
    private WidgetImage? _emptyIcon;
    private bool _disposed;

    public RedBullWidget(IRedBullService service)
    {
        _service = service;
        _service.CountChanged += OnCountChanged;
    }

    public void Initialize()
    {
        LoadImages();

        _widget = new TaskbarWidget.Widget("RedBull", render: ctx =>
        {
            ctx.Panel(p =>
            {
                var byType = _service.ByType;
                int total = _service.Count;
                bool stale = (_service as ApiRedBullService)?.IsStale ?? false;

                p.Horizontal(CanSpacing, h =>
                {
                    if (total == 0)
                    {
                        h.DrawImage(_emptyIcon!, widthDip: CanWidthDip, heightDip: CanHeightDip);
                    }
                    else
                    {
                        // Stable ordering across renders. Each can lives in its own
                        // panel so left-click can drink THIS specific can (typed).
                        foreach (var (type, count) in byType.OrderBy(kv => kv.Key))
                        {
                            var icon = GetIcon(type);
                            var canType = type;  // capture for the closure
                            for (int i = 0; i < count; i++)
                            {
                                h.Panel(CanWidthDip, CanHeightDip, can =>
                                {
                                    can.DrawImage(icon, CanWidthDip, CanHeightDip);
                                    can.OnClick(() => _ = _service.RemoveCanAsync(canType));
                                    // No event bubbling: a can panel is the deepest
                                    // hit target, so right-click-to-add must live
                                    // here too or it's shadowed once any can exists.
                                    if (!_service.IsReadOnly)
                                        can.OnRightClick(() => _ = _service.AddCanAsync());
                                    can.Tooltip($"Drink one {canType}");
                                });
                            }
                        }
                    }
                });

                // Right-click on the whole widget adds — offline mode only.
                if (!_service.IsReadOnly)
                {
                    p.OnRightClick(() => _ = _service.AddCanAsync());
                }

                p.Tooltip(BuildTooltip(byType, total, stale));
            });
        });

        _widget.Show();
    }

    private string BuildTooltip(IReadOnlyDictionary<string, int> byType, int total, bool stale)
    {
        if (_service.IsReadOnly)
        {
            string staleNote = stale ? " (stale)" : "";
            if (total == 0)
                return $"Red Bulls: 0\nSynced from API{staleNote}";
            var breakdown = string.Join(", ", byType.OrderBy(kv => kv.Key).Select(kv => $"{kv.Value} {kv.Key}"));
            return $"Red Bulls: {breakdown} ({total} total)\n"
                 + $"Click a can to drink it{staleNote}";
        }
        return $"Red Bulls: {total}\nLeft-click a can: Drink | Right-click: Add";
    }

    private WidgetImage GetIcon(string type)
    {
        if (_icons.TryGetValue(type, out var icon))
            return icon;
        return _genericIcon!;
    }

    private void LoadImages()
    {
        var asm = typeof(RedBullWidget).Assembly;
        _icons["default"] = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-default.png");
        _icons["sugarfree"] = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-sugarfree.png");
        _genericIcon = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-generic.png");
        _emptyIcon = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-empty.png");
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
        (_service as IDisposable)?.Dispose();
    }
}
