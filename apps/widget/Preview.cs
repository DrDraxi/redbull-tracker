using System.Runtime.InteropServices;
using TaskbarWidget;

namespace RedBullTracker;

/// <summary>
/// Developer aid: <c>RedBullTracker.exe --preview out.bmp</c> renders a contact sheet of can poses
/// (rest, hover, add and drink animations) at large scale, for tuning the 3D look without the taskbar.
/// </summary>
public static class Preview
{
    [DllImport("ole32.dll")] static extern int CoInitializeEx(IntPtr reserved, uint coinit);

    public static void Run(string outPath)
    {
        CoInitializeEx(IntPtr.Zero, 2);
        var labels = RedBullApp.LoadLabels();
        const float scale = 4f;
        const int cols = 8;
        int cw = (int)MathF.Ceiling(CanMotion.AreaW * scale), ch = (int)MathF.Ceiling(CanMotion.AreaH * scale);

        var frames = new List<(string Type, Func<CanPose> Pose)>();
        void Add(string type, Func<CanVisual, (bool, CanPose)> f) =>
            frames.Add((type, () => f(new CanVisual { Type = type, YawOffset = 0.15f }).Item2));

        // Row 1: rest poses + hover ramp
        foreach (var t in new[] { "default", "sugarfree" })
            Add(t, v => { CanMotion.Compute(v, 0, 0, 0, scale, 1, out var p, out _); return (true, p); });
        foreach (var h in new[] { 0.25f, 0.5f, 0.75f, 1f })
            Add("default", v => { CanMotion.Compute(v, h, 0, 0.3, scale, 1, out var p, out _); return (true, p); });
        Add("sugarfree", v => { CanMotion.Compute(v, 1, 0, 1.1, scale, 1, out var p, out _); return (true, p); });
        // Row 2: add animation
        for (int i = 0; i < 8; i++)
        {
            double t = CanMotion.AddSeconds * (i + 0.5) / 8;
            Add("sugarfree", v => { v.Born = 0; CanMotion.Compute(v, 0, 0, t, scale, 1, out var p, out _); return (true, p); });
        }
        // Rows 3–4: drink animation (hovered, as it is when clicked)
        for (int i = 0; i < 16; i++)
        {
            double t = CanMotion.DrinkSeconds * i / 15.0;
            Add("default", v => { v.DrinkStart = 0; CanMotion.Compute(v, 1, 0, t, scale, 1, out var p, out _); return (true, p); });
        }

        int rows = (frames.Count + cols - 1) / cols;
        int W = cols * cw, H = rows * ch;
        var sheet = new uint[W * H];
        Array.Fill(sheet, 0xFF1C1C24u);
        var canvas = new PixelCanvas(cw, ch);
        for (int i = 0; i < frames.Count; i++)
        {
            var (type, pose) = frames[i];
            CanRenderer.Render(canvas, labels[type], pose());
            int ox = i % cols * cw, oy = i / cols * ch;
            for (int y = 0; y < ch; y++)
                for (int x = 0; x < cw; x++)
                {
                    uint s = canvas.Pixels[y * cw + x], d = sheet[(oy + y) * W + ox + x];
                    uint a = s >> 24;
                    uint Ch(int sh) => ((s >> sh) & 255) + (((d >> sh) & 255) * (255 - a) + 127) / 255;
                    sheet[(oy + y) * W + ox + x] = 0xFF000000u | Ch(16) << 16 | Ch(8) << 8 | Ch(0);
                }
        }
        WriteBmp(outPath, sheet, W, H);
    }

    static void WriteBmp(string path, uint[] px, int w, int h)
    {
        using var f = new BinaryWriter(File.Create(path));
        int rowBytes = w * 4, size = 54 + rowBytes * h;
        f.Write((ushort)0x4D42); f.Write(size); f.Write(0); f.Write(54);
        f.Write(40); f.Write(w); f.Write(-h); f.Write((ushort)1); f.Write((ushort)32); f.Write(0); f.Write(rowBytes * h);
        f.Write(2835); f.Write(2835); f.Write(0); f.Write(0);
        foreach (var p in px) f.Write(p);
    }
}
