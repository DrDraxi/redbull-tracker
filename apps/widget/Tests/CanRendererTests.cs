using RedBullTracker;
using TaskbarWidget;

namespace RedBullTracker.Tests;

public class CanRendererTests
{
    // Synthetic front-view art: solid red, 20×40, premultiplied BGRA.
    static CanLabel RedLabel()
    {
        var px = new byte[20 * 40 * 4];
        for (int i = 0; i < px.Length; i += 4) { px[i] = 0; px[i + 1] = 0; px[i + 2] = 200; px[i + 3] = 255; }
        return CanLabel.FromFrontArt(px, 20, 40, 1, 38);
    }

    static uint At(PixelCanvas c, int x, int y) => c.Pixels[y * c.Width + x];

    [Fact]
    public void RestPoseCoversTheMiddleAndLeavesCornersTransparent()
    {
        var canvas = new PixelCanvas(60, 140);
        CanRenderer.Render(canvas, RedLabel(), CanPose.Rest(30, 70, 20));
        uint mid = At(canvas, 30, 70);
        Assert.Equal(255u, mid >> 24);                       // opaque
        Assert.True(((mid >> 16) & 255) > ((mid >> 8) & 255)); // red label shows through the lighting
        Assert.Equal(0u, At(canvas, 0, 0));
        Assert.Equal(0u, At(canvas, 59, 139));
    }

    [Fact]
    public void ShapeMatchesSlimCanProportions()
    {
        var canvas = new PixelCanvas(80, 200);
        CanRenderer.Render(canvas, RedLabel(), CanPose.Rest(40, 100, 15) with { Pitch = 0 });
        int top = -1, bottom = -1, left = -1, right = -1;
        for (int y = 0; y < 200; y++) if (At(canvas, 40, y) >> 24 > 128) { if (top < 0) top = y; bottom = y; }
        for (int x = 0; x < 80; x++) if (At(canvas, x, 100) >> 24 > 128) { if (left < 0) left = x; right = x; }
        float ratio = (bottom - top + 1f) / (right - left + 1f);
        Assert.InRange(ratio, 2.35f, 2.75f);                  // 134 mm / 53 mm ≈ 2.53
    }

    [Fact]
    public void PremultipliedChannelsNeverExceedAlpha()
    {
        var canvas = new PixelCanvas(60, 140);
        CanRenderer.Render(canvas, RedLabel(), CanPose.Rest(30, 70, 20) with { Yaw = 0.7f, Pitch = 0.4f, Roll = -0.5f, Opacity = 0.6f });
        foreach (var p in canvas.Pixels)
        {
            uint a = p >> 24;
            Assert.True(((p >> 16) & 255) <= a && ((p >> 8) & 255) <= a && (p & 255) <= a);
        }
    }

    [Fact]
    public void FinishedDrinkIsInvisibleAndStillAnimating()
    {
        var v = new CanVisual { Type = "default", DrinkStart = 0 };
        bool animating = CanMotion.Compute(v, 1, 0, CanMotion.DrinkSeconds, 2, 1, out var pose, out _);
        Assert.True(animating);
        Assert.Equal(0f, pose.Opacity, 3);
    }

    [Fact]
    public void AddAnimationEndsAndClearsItself()
    {
        var v = new CanVisual { Type = "default", Born = 0 };
        Assert.True(CanMotion.Compute(v, 0, 0, 0.1, 2, 1, out var falling, out _));
        Assert.False(CanMotion.Compute(v, 0, 0, CanMotion.AddSeconds + 0.01, 2, 1, out var rest, out _));
        Assert.True(double.IsNaN(v.Born));
        Assert.True(falling.CenterY < rest.CenterY);          // it starts above its slot
    }

    [Fact]
    public void RestingCanDoesNotRequestFrames() =>
        Assert.False(CanMotion.Compute(new CanVisual { Type = "default" }, 0, 0, 5, 2, 1, out _, out _));
}
