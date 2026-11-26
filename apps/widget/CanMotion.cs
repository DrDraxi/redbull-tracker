using TaskbarWidget;

namespace RedBullTracker;

/// <summary>One can on the taskbar, with its animation state and its own render buffer.</summary>
public sealed class CanVisual
{
    public required string Type { get; init; }
    public double Born = double.NaN;        // add animation start (Graphics.Now), NaN = none
    public double DrinkStart = double.NaN;  // drink animation start, NaN = none
    public float YawOffset;                 // a little variety so a row of cans isn't identical
    public readonly PixelCanvas Canvas = new(1, 1);
    public CanPose? Last;                   // pose currently in Canvas (re-render only on change)

    public bool IsDrinking => !double.IsNaN(DrinkStart);
}

/// <summary>Turns hover / add / drink timing into a <see cref="CanPose"/>. Pure function of its inputs.</summary>
public static class CanMotion
{
    public const float CanW = 10, CanH = 26;
    /// <summary>Render area around the can's 10×26 DIP slot: room to pop out, fall in and tip over.</summary>
    public const float AreaLeft = -12, AreaTop = -40, AreaW = CanW + 24, AreaH = CanH + 48;
    public const double AddSeconds = 0.75, DrinkSeconds = 1.05;
    /// <summary>How far above the taskbar the widget may draw (DIP).</summary>
    public const float Overflow = 34;

    const float Deg = MathF.PI / 180f;

    /// <param name="shadow">0..1 strength of the contact shadow (how far the can is lifted).</param>
    /// <returns>True while something is animating and another frame is needed.</returns>
    public static bool Compute(CanVisual v, float hover, float pressed, double now, float scale, float opacity,
        out CanPose pose, out float shadow)
    {
        float zoom = 1, lift = 0, drop = 0, pitch = 8 * Deg, yaw = v.YawOffset, roll = 0;
        float squash = 1, bulge = 1, crumple = 0, tab = 0, op = opacity;
        bool animating = false;

        // Hover: pop up above the taskbar, tip the lid towards you, sway gently.
        if (hover > 0)
        {
            float t = (float)now;
            zoom += 0.75f * hover;
            lift += 5f * hover + MathF.Sin(t * 3.0f) * 0.6f * hover;
            pitch += 20 * Deg * hover;
            yaw += MathF.Sin(t * 2.1f) * 0.45f * hover;
            animating = true;
        }
        lift -= 1.5f * pressed;
        squash -= 0.06f * pressed;

        // Add: falls in from above while spinning, then a squash-and-bounce landing.
        if (!double.IsNaN(v.Born))
        {
            float p = (float)((now - v.Born) / AddSeconds);
            if (p >= 1) v.Born = double.NaN;
            else
            {
                animating = true;
                p = Math.Max(0, p);
                if (p < 0.6f)
                {
                    float q = p / 0.6f;
                    drop = (1 - q * q) * 36f;
                    yaw += (1 - q) * (1 - q) * MathF.Tau * 1.25f;
                    pitch += (1 - q) * 18 * Deg;
                    op *= Math.Min(1, q * 4);
                }
                else
                {
                    float q = (p - 0.6f) / 0.4f;
                    float k = MathF.Sin(MathF.PI * q) * (1 - q);
                    squash *= 1 - 0.2f * k;
                    bulge *= 1 + 0.1f * k;
                }
            }
        }

        // Drink: tab pops, can tips back, gets crushed, fades away.
        if (v.IsDrinking)
        {
            animating = true;
            float d = (float)Math.Clamp((now - v.DrinkStart) / DrinkSeconds, 0, 1);
            float a = Smooth(d / 0.18f);
            zoom = Lerp(zoom, 1.55f, a);
            lift = Lerp(lift, 7f, a);
            pitch = Lerp(pitch, 26 * Deg, a);
            yaw = Lerp(yaw, v.YawOffset, a);
            tab = Math.Clamp(d / 0.18f, 0, 1);

            float b = Smooth((d - 0.18f) / 0.32f);
            roll = -0.55f * b;

            float c = Smooth((d - 0.55f) / 0.22f);
            roll *= 1 - c;
            squash *= 1 - 0.55f * c;
            bulge *= 1 + 0.2f * c;
            crumple = c;
            pitch = Lerp(pitch, 12 * Deg, c);

            float f = Math.Clamp((d - 0.8f) / 0.2f, 0, 1);
            op *= 1 - f;
            zoom *= 1 - 0.25f * f;
            lift -= 4 * f;
        }

        // Bottom-anchored: the can stands on its slot and grows upwards.
        float radius = CanW / 2 * zoom;                 // DIP
        float bottom = CanH - lift - drop;
        float centerY = bottom - 2.525f * radius * squash;
        pose = new CanPose
        {
            CenterX = (CanW / 2 - AreaLeft) * scale,
            CenterY = (centerY - AreaTop) * scale,
            Scale = radius * scale,
            Yaw = yaw, Pitch = pitch, Roll = roll,
            SquashY = squash, Bulge = bulge, Crumple = crumple, TabOpen = tab,
            Opacity = Math.Clamp(op, 0, 1),
        };
        shadow = Math.Clamp((lift + drop * 0.3f) / 8f, 0, 1) * Math.Clamp(op, 0, 1);
        return animating;
    }

    /// <summary>The empty-stock placeholder: a crushed, grey can.</summary>
    public static CanPose Empty(float hover, double now, float scale, float opacity)
    {
        var v = new CanVisual { Type = "", YawOffset = -0.3f };
        Compute(v, hover * 0.5f, 0, now, scale, opacity, out var pose, out _);
        return pose with { Crumple = 0.45f, SquashY = pose.SquashY * 0.72f, Bulge = 1.1f, TabOpen = 1 };
    }

    static float Smooth(float t) { t = Math.Clamp(t, 0, 1); return t * t * (3 - 2 * t); }
    static float Lerp(float a, float b, float t) => a + (b - a) * t;
}
