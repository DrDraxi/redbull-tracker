using TaskbarWidget;

namespace RedBullTracker;

/// <summary>
/// One can per Red Bull in stock. Hover lifts a can, click drinks it; right-click adds one (offline mode).
/// </summary>
public sealed class RedBullApp
{
    const string AppName = "RedBullTracker";
    const float CanW = 10, CanH = 26, Lift = 2.5f; // can art is 99×256, so 10×26 keeps the aspect ratio
    const int MaxVisibleCans = 12;
    static readonly TextStyle MoreStyle = new(12, 600);

    readonly RedBullConfig _config = new();
    readonly Dictionary<string, WidgetImage> _icons = new();
    WidgetImage _generic = null!, _empty = null!;
    ICanSource _source = null!;
    Widget _widget = null!;

    public void Start()
    {
        AppKit.SetStartWithWindows(AppName, _config.StartWithWindows);
        LoadImages();

        _widget = new Widget("RedBull", Build, new WidgetOptions { Menu = BuildMenu });

        var (mode, problem) = _config.Mode;
        _source = mode switch
        {
            CanMode.Offline => new OfflineCans(_config.CountFile, _config.CanType),
            CanMode.Api => new ApiCans(_config.ApiUrl!, _config.ApiToken!, _widget.Post),
            _ => new BrokenCans(problem ?? "Invalid configuration"),
        };
        _source.Changed += _widget.Invalidate;

        _widget.Show();

        if (_source is ApiCans api)
        {
            _widget.SetInterval(api.Interval, api.Refresh);
            _widget.Resumed += api.Refresh;
            api.Refresh();
        }
    }

    void LoadImages()
    {
        var asm = typeof(RedBullApp).Assembly;
        WidgetImage Load(string name) => WidgetImage.FromResource(asm, $"RedBullTracker.Assets.{name}.png");
        _icons["default"] = Load("redbull-default");
        _icons["sugarfree"] = Load("redbull-sugarfree");
        _generic = Load("redbull-generic");
        _empty = Load("redbull-empty");
    }

    WidgetImage Icon(string type) => _icons.TryGetValue(type, out var i) ? i : _generic;

    static string DisplayName(string type) => type switch
    {
        "default" => "Red Bull",
        "sugarfree" => "Red Bull Sugarfree",
        _ => "Red Bull " + (type.Length > 0 ? char.ToUpperInvariant(type[0]) + type[1..] : type),
    };

    // ── UI ──────────────────────────────────────────────────────────────

    void Build(Ui ui)
    {
        ui.Spacing = 3;
        var theme = ui.Theme;
        var src = _source;
        float opacity = src.IsStale && src is not OfflineCans ? 0.45f : 1f;
        bool loading = src is ApiCans { HasLoaded: false } && src.Problem == null;

        if (src.Total == 0)
        {
            ui.Custom(CanW, CanH, (g, s) => g.Image(_empty, 0, -Lift * s.Hover * 0.5f, CanW, CanH, loading ? 0.35f : 0.6f));
        }
        else
        {
            int shown = 0;
            foreach (var (type, count) in src.ByType.OrderBy(kv => kv.Key, StringComparer.Ordinal))
            {
                var icon = Icon(type);
                for (int i = 0; i < count && shown < MaxVisibleCans; i++, shown++)
                {
                    string t = type;
                    ui.Custom(CanW, CanH, (g, s) =>
                        {
                            // Lift on hover, dip on press — like picking the can up.
                            float y = -Lift * s.Hover + 1.5f * s.Pressed;
                            g.Image(icon, 0, y, CanW, CanH, opacity);
                        })
                      .OnClick(() => src.Drink(t))
                      .Tooltip(DisplayName(t), "Click to drink this one" + (src.CanAdd ? "\nRight-click to add a can" : ""));
                }
            }
            if (src.Total > shown)
            {
                ui.Gap(4);
                ui.Text($"+{src.Total - shown}", MoreStyle, theme.TextSecondary.WithOpacity(opacity));
            }
        }

        if (src.CanAdd) ui.OnRightClick(src.Add);
        var (title, body) = Tooltip(src, loading);
        ui.Tooltip(title, body);
    }

    (string, string) Tooltip(ICanSource src, bool loading)
    {
        var lines = new List<string>();
        if (src.Problem != null && src is BrokenCans) return ("Red Bull Tracker", $"{src.Problem}\nRight-click to edit settings");

        if (loading) lines.Add("Loading stock…");
        else if (src.Total == 0) lines.Add("None left in stock");
        else lines.Add(string.Join(", ", src.ByType.OrderBy(kv => kv.Key, StringComparer.Ordinal)
            .Select(kv => $"{kv.Value}× {DisplayName(kv.Key)}")));

        if (src is ApiCans)
        {
            if (src.Problem != null) lines.Add($"Offline — {src.Problem}");
            lines.Add("Synced with your Red Bull Tracker server");
        }
        lines.Add(src.CanAdd ? "Click a can to drink it · right-click to add" : "Click a can to drink it");

        string title = src.Total == 1 ? "1 Red Bull" : $"{src.Total} Red Bulls";
        return (title, string.Join("\n", lines));
    }

    void BuildMenu(MenuBuilder m)
    {
        if (_source.CanAdd)
            m.Item("Add a can", _source.Add)
             .Item("Drink a can", () => { if (_source.ByType.Count > 0) _source.Drink(_source.ByType.Keys.First()); }, _source.Total > 0);
        if (_source is ApiCans api)
            m.Item("Refresh now", api.Refresh)
             .Item("Open dashboard", () => AppKit.Open(api.DashboardUrl));
        m.Item("Edit settings…", () => AppKit.Open(_config.FilePath))
         .Separator()
         .Check("Start with Windows", _config.StartWithWindows, () =>
         {
             bool enabled = !_config.StartWithWindows;
             _config.SetStartWithWindows(enabled);
             AppKit.SetStartWithWindows(AppName, enabled);
         });
    }
}
