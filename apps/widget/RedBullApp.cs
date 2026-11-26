using TaskbarWidget;

namespace RedBullTracker;

/// <summary>
/// One 3D can per Red Bull in stock. Hovering pops a can out above the taskbar and tips its lid towards
/// you; clicking drinks it (tab pops, it tips back, gets crushed, fades); new cans fall in spinning.
/// Offline: right-click adds the configured can, Shift+right-click the other one; Ctrl+right-click = menu.
/// </summary>
public sealed class RedBullApp
{
    const string AppName = "RedBullTracker";
    const float CanW = CanMotion.CanW, CanH = CanMotion.CanH;
    const int MaxVisibleCans = 12;
    static readonly TextStyle MoreStyle = new(12, 600);

    readonly RedBullConfig _config = new();
    Dictionary<string, CanLabel>? _labels;
    readonly List<CanVisual> _visuals = new();
    readonly CanVisual _emptyVisual = new() { Type = "empty" };
    bool _synced;
    int _serial;
    ICanSource _source = null!;
    Widget _widget = null!;

    public void Start()
    {
        AppKit.SetStartWithWindows(AppName, _config.StartWithWindows);

        _widget = new Widget("RedBull", Build, new WidgetOptions
        {
            Menu = BuildMenu,
            MenuModifier = MenuModifier.Ctrl,
            OverflowTop = CanMotion.Overflow, // cans pop out above the taskbar
        });

        var (mode, problem) = _config.Mode;
        _source = mode switch
        {
            CanMode.Offline => new OfflineCans(_config.CountsFile, _config.LegacyCountFile, _config.LegacyCanType),
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

    /// <summary>Wrap-around labels unprojected from the front-view can art (needs COM initialised; UI thread).</summary>
    public static Dictionary<string, CanLabel> LoadLabels()
    {
        var asm = typeof(RedBullApp).Assembly;
        CanLabel Load(string name, bool grey = false)
        {
            var img = WidgetImage.FromResource(asm, $"RedBullTracker.Assets.{name}.png");
            var (w, h) = img.NaturalSize;
            // The art's straight body spans ~3%..95% of its height; above/below are the rounded ends,
            // which the renderer models as metal neck and base.
            return CanLabel.FromFrontArt(img.GetPixels(w, h), w, h, (int)(h * 0.03f), (int)(h * 0.95f), grey);
        }
        return new Dictionary<string, CanLabel>
        {
            ["default"] = Load("redbull-default"),
            ["sugarfree"] = Load("redbull-sugarfree"),
            ["generic"] = Load("redbull-generic"),
            ["empty"] = Load("redbull-default", grey: true),
        };
    }

    CanLabel Label(string type)
    {
        _labels ??= LoadLabels();
        return _labels.TryGetValue(type, out var l) ? l : _labels["generic"];
    }

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

        int hidden = SyncVisuals();
        if (_visuals.Count == 0)
        {
            var empty = _emptyVisual;
            ui.Custom(CanW, CanH, (g, s) =>
            {
                var pose = CanMotion.Empty(s.Hover, g.Time, g.Scale, loading ? 0.3f : 0.55f);
                DrawCan(g, empty, Label("empty"), pose, 0, s.Hover > 0);
            });
        }
        else
        {
            foreach (var v in _visuals)
            {
                var visual = v;
                ui.Custom(CanW, CanH, (g, s) =>
                    {
                        bool animating = CanMotion.Compute(visual, s.Hover, s.Pressed, g.Time, g.Scale, opacity, out var pose, out var shadow);
                        DrawCan(g, visual, Label(visual.Type), pose, shadow, animating);
                    })
                  .OnClick(() => Drink(visual))
                  .Tooltip(DisplayName(v.Type), "Click to drink this one");
            }
            if (hidden > 0)
            {
                ui.Gap(4);
                ui.Text($"+{hidden}", MoreStyle, theme.TextSecondary.WithOpacity(opacity));
            }
        }

        if (src.CanAdd) ui.OnRightClick(AddFromClick);
        var (title, body) = Tooltip(src, loading);
        ui.Tooltip(title, body);
    }

    static void DrawCan(Graphics g, CanVisual v, CanLabel label, in CanPose pose, float shadow, bool animating)
    {
        int w = (int)MathF.Ceiling(CanMotion.AreaW * g.Scale), h = (int)MathF.Ceiling(CanMotion.AreaH * g.Scale);
        if (v.Canvas.Width != w || v.Canvas.Height != h) { v.Canvas.Resize(w, h); v.Last = null; }
        if (v.Last != pose)
        {
            CanRenderer.Render(v.Canvas, label, pose);
            v.Last = pose;
        }
        // Soft contact shadow on the taskbar while the can is lifted.
        if (shadow > 0.02f)
            g.FillEllipse(CanW / 2, CanH - 0.5f, 4.2f + 1.6f * shadow, 1.3f, Color.Black.WithOpacity(0.32f * shadow));
        g.Pixels(v.Canvas, CanMotion.AreaLeft, CanMotion.AreaTop);
        if (animating) g.RequestFrame();
    }

    /// <summary>
    /// Keeps one visual per can (up to <see cref="MaxVisibleCans"/>), so cans keep their animation state across
    /// rebuilds. New cans (after the first sync) get the fall-in animation. Returns how many cans aren't shown.
    /// </summary>
    int SyncVisuals()
    {
        var want = new List<(string Type, int Count)>();
        int budget = MaxVisibleCans, total = 0;
        foreach (var (type, count) in _source.ByType.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            total += count;
            int n = Math.Min(count, budget);
            budget -= n;
            want.Add((type, n));
        }

        double now = Graphics.Now;
        foreach (var (type, n) in want)
        {
            int have = _visuals.Count(v => v.Type == type);
            for (; have < n; have++)
                _visuals.Add(new CanVisual
                {
                    Type = type,
                    Born = _synced ? now : double.NaN,
                    YawOffset = ((_serial++ * 7919) % 13 - 6) * 0.035f, // ±12° of variety
                });
            for (int i = _visuals.Count - 1; i >= 0 && have > n; i--)
                if (_visuals[i].Type == type && !_visuals[i].IsDrinking) { _visuals.RemoveAt(i); have--; }
        }
        _visuals.RemoveAll(v => !v.IsDrinking && want.All(w => w.Type != v.Type));
        // Stable order: by type, then by age.
        var ordered = _visuals.OrderBy(v => v.Type, StringComparer.Ordinal).ToList();
        _visuals.Clear(); _visuals.AddRange(ordered);
        _synced = true;
        return Math.Max(0, total - _visuals.Count);
    }

    void Drink(CanVisual v)
    {
        if (v.IsDrinking) return;
        v.DrinkStart = Graphics.Now;
        _widget.Invalidate(); // start the frame clock
        // The count changes when the animation is over, so the can stays in place while it plays.
        _widget.SetTimeout(TimeSpan.FromSeconds(CanMotion.DrinkSeconds), () =>
        {
            _visuals.Remove(v);
            _source.Drink(v.Type);
            _widget.Invalidate();
        });
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
        lines.Add("Click a can to drink it");
        if (src.CanAdd)
        {
            lines.Add($"Right-click: add {DisplayName(_config.RightClickCan)}");
            lines.Add($"Shift+right-click: add {DisplayName(_config.ShiftRightClickCan)}");
        }
        lines.Add("Ctrl+right-click: options");

        string title = src.Total == 1 ? "1 Red Bull" : $"{src.Total} Red Bulls";
        return (title, string.Join("\n", lines));
    }

    void AddFromClick()
    {
        _config.Reload(); // edits to rightClickCan / shiftRightClickCan apply immediately
        _source.Add(Input.Shift ? _config.ShiftRightClickCan : _config.RightClickCan);
    }

    void BuildMenu(MenuBuilder m)
    {
        if (_source.CanAdd)
        {
            _config.Reload();
            foreach (var type in new[] { _config.RightClickCan, _config.ShiftRightClickCan }.Distinct())
                m.Item($"Add {DisplayName(type)}", () => _source.Add(type));
        }
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
