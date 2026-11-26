using TaskbarWidget;

namespace RedBullTracker;

/// <summary>
/// The can's label as a wrap-around texture (angle × height), unprojected from front-view art.
/// A front view shows the label at screen x = R·sin(angle), so sampling the art at sin(angle) recovers the
/// visible half; the back half repeats it (real cans carry the logo on both sides).
/// </summary>
public sealed class CanLabel
{
    public const int W = 192, H = 160;
    readonly float[] _r = new float[W * H], _g = new float[W * H], _b = new float[W * H];

    /// <param name="bgra">Premultiplied BGRA pixels of the front-view art.</param>
    /// <param name="rowTop">First art row of the straight body (below the rounded top).</param>
    /// <param name="rowBottom">Last art row of the straight body.</param>
    public static CanLabel FromFrontArt(byte[] bgra, int width, int height, int rowTop, int rowBottom, bool greyscale = false)
    {
        var label = new CanLabel();
        for (int k = 0; k < W; k++)
        {
            float phi = (k + 0.5f) / W * MathF.Tau - MathF.PI;
            float a = phi > MathF.PI / 2 ? phi - MathF.PI : phi < -MathF.PI / 2 ? phi + MathF.PI : phi;
            // 0.94: stay clear of the art's darkened outermost columns.
            float col = (0.5f + 0.5f * 0.94f * MathF.Sin(a)) * (width - 1);
            for (int j = 0; j < H; j++)
            {
                float row = rowTop + (j + 0.5f) / H * (rowBottom - rowTop);
                Bilinear(bgra, width, height, col, row, out var r, out var g, out var b);
                if (greyscale) { float l = 0.3f * r + 0.59f * g + 0.11f * b; r = g = b = l * 0.75f; }
                int i = j * W + k;
                label._r[i] = r; label._g[i] = g; label._b[i] = b;
            }
        }
        return label;
    }

    static void Bilinear(byte[] px, int w, int h, float x, float y, out float r, out float g, out float b)
    {
        int x0 = Math.Clamp((int)x, 0, w - 1), y0 = Math.Clamp((int)y, 0, h - 1);
        int x1 = Math.Min(x0 + 1, w - 1), y1 = Math.Min(y0 + 1, h - 1);
        float fx = Math.Clamp(x - x0, 0, 1), fy = Math.Clamp(y - y0, 0, 1);
        float sr = 0, sg = 0, sb = 0, sa = 0;
        void Add(int xx, int yy, float wgt)
        {
            int o = (yy * w + xx) * 4;
            sb += px[o] * wgt; sg += px[o + 1] * wgt; sr += px[o + 2] * wgt; sa += px[o + 3] * wgt;
        }
        Add(x0, y0, (1 - fx) * (1 - fy)); Add(x1, y0, fx * (1 - fy));
        Add(x0, y1, (1 - fx) * fy); Add(x1, y1, fx * fy);
        if (sa < 1) { r = g = b = 0.75f; return; }      // transparent pixel: assume bare aluminium
        r = sr / sa; g = sg / sa; b = sb / sa;            // un-premultiply
    }

    /// <summary>u wraps around the can (0..1), v runs top (0) to bottom (1).</summary>
    public void Sample(float u, float v, out float r, out float g, out float b)
    {
        float x = (u - MathF.Floor(u)) * W - 0.5f, y = Math.Clamp(v, 0, 1) * (H - 1);
        int x0 = (int)MathF.Floor(x), y0 = (int)y;
        float fx = x - x0, fy = y - y0;
        int xa = (x0 % W + W) % W, xb = (xa + 1) % W, ya = y0, yb = Math.Min(y0 + 1, H - 1);
        float w00 = (1 - fx) * (1 - fy), w10 = fx * (1 - fy), w01 = (1 - fx) * fy, w11 = fx * fy;
        int i00 = ya * W + xa, i10 = ya * W + xb, i01 = yb * W + xa, i11 = yb * W + xb;
        r = _r[i00] * w00 + _r[i10] * w10 + _r[i01] * w01 + _r[i11] * w11;
        g = _g[i00] * w00 + _g[i10] * w10 + _g[i01] * w01 + _g[i11] * w11;
        b = _b[i00] * w00 + _b[i10] * w10 + _b[i01] * w01 + _b[i11] * w11;
    }
}

/// <summary>Everything that defines one rendered frame of a can.</summary>
public record struct CanPose
{
    public float CenterX, CenterY;  // canvas pixels
    public float Scale;             // canvas pixels per can radius
    public float Yaw, Pitch, Roll;  // radians: spin, tilt-top-towards-viewer, lean
    public float SquashY, Bulge;    // 1 = undeformed
    public float Crumple;           // 0..1 dents when crushed
    public float TabOpen;           // 0..1
    public float Opacity;

    public static CanPose Rest(float cx, float cy, float scale) =>
        new() { CenterX = cx, CenterY = cy, Scale = scale, SquashY = 1, Bulge = 1, Opacity = 1 };
}

/// <summary>
/// Tiny CPU ray caster for a slim 250 ml can (53 × 134 mm). Orthographic camera, analytic intersections,
/// 2×2 supersampling. A hovered can is ~4k rays per frame, i.e. a fraction of a millisecond, and nothing
/// is rendered unless the pose changes.
/// </summary>
public static class CanRenderer
{
    // Can geometry in body-radius units. Total height 5.05 ≈ 134 / 26.5.
    const float YTop = 2.525f, YNeck = 2.30f, YBase = -2.37f, YBot = -2.525f;
    const float RTop = 0.88f, RBot = 0.84f;
    const float NeckB = (RTop - 1f) / (YTop - YNeck), NeckA = 1f - NeckB * YNeck;
    const float BaseB = (1f - RBot) / (YBase - YBot), BaseA = 1f - BaseB * YBase;
    const int PartNone = 0, PartBody = 1, PartNeck = 2, PartBase = 3, PartTop = 4, PartBottom = 5;

    // Lighting (view space: x right, y up, z into the screen; vectors point towards the light).
    static readonly (float X, float Y, float Z) Key = Norm(-0.45f, 0.58f, -0.68f);
    static readonly (float X, float Y, float Z) Fill = Norm(0.75f, 0.15f, -0.64f);
    static readonly (float X, float Y, float Z) HalfKey = Norm(Key.X, Key.Y, Key.Z - 1f);
    static readonly (float X, float Y, float Z) HalfFill = Norm(Fill.X, Fill.Y, Fill.Z - 1f);

    public static void Render(PixelCanvas canvas, CanLabel label, in CanPose p)
    {
        Array.Clear(canvas.Pixels);
        if (p.Opacity <= 0.003f || p.Scale <= 0) { canvas.Commit(); return; }

        // Object → view rotation: yaw (about the can axis), then tilt, then lean (about the view axis).
        float cy = MathF.Cos(p.Yaw), sy = MathF.Sin(p.Yaw);
        float cp = MathF.Cos(p.Pitch), sp = MathF.Sin(p.Pitch);
        float cr = MathF.Cos(p.Roll), sr = MathF.Sin(p.Roll);
        var m = new float[9];
        BuildRotation(m, cy, sy, cp, sp, cr, sr);

        float bx = p.Bulge, by = p.SquashY;
        float invS = 1f / p.Scale;
        float w = canvas.Width, h = canvas.Height;

        // Screen-space bounding box from the 8 corners of the (deformed) object box.
        float minX = float.MaxValue, maxX = float.MinValue, minY = float.MaxValue, maxY = float.MinValue;
        for (int c = 0; c < 8; c++)
        {
            float ox = ((c & 1) == 0 ? -1.05f : 1.05f) * bx, oy = ((c & 2) == 0 ? YBot : YTop) * by, oz = ((c & 4) == 0 ? -1.05f : 1.05f) * bx;
            float vx = m[0] * ox + m[1] * oy + m[2] * oz, vy = m[3] * ox + m[4] * oy + m[5] * oz;
            float sxp = p.CenterX + vx * p.Scale, syp = p.CenterY - vy * p.Scale;
            minX = MathF.Min(minX, sxp); maxX = MathF.Max(maxX, sxp); minY = MathF.Min(minY, syp); maxY = MathF.Max(maxY, syp);
        }
        int x0 = Math.Max(0, (int)MathF.Floor(minX) - 1), x1 = Math.Min((int)w - 1, (int)MathF.Ceiling(maxX) + 1);
        int y0 = Math.Max(0, (int)MathF.Floor(minY) - 1), y1 = Math.Min((int)h - 1, (int)MathF.Ceiling(maxY) + 1);

        // View ray direction (0,0,1) in object space (transpose rotation, then undo the scale).
        float dxO = m[6] / bx, dyO = m[7] / by, dzO = m[8] / bx;

        var px = canvas.Pixels;
        int cw = canvas.Width;
        for (int yy = y0; yy <= y1; yy++)
        {
            for (int xx = x0; xx <= x1; xx++)
            {
                float accR = 0, accG = 0, accB = 0; int hits = 0;
                for (int s = 0; s < 4; s++)
                {
                    float sxs = xx + ((s & 1) == 0 ? 0.25f : 0.75f), sys = yy + ((s & 2) == 0 ? 0.25f : 0.75f);
                    float vx = (sxs - p.CenterX) * invS, vy = -(sys - p.CenterY) * invS, vz = -20f;
                    // Origin in object space.
                    float ox = (m[0] * vx + m[3] * vy + m[6] * vz) / bx;
                    float oy = (m[1] * vx + m[4] * vy + m[7] * vz) / by;
                    float oz = (m[2] * vx + m[5] * vy + m[8] * vz) / bx;
                    if (!Shade(label, p, m, bx, by, ox, oy, oz, dxO, dyO, dzO, out var r, out var g, out var b)) continue;
                    accR += r; accG += g; accB += b; hits++;
                }
                if (hits == 0) continue;
                float cov = hits / 4f * p.Opacity;
                float inv = 1f / hits;
                byte A = (byte)Math.Clamp(cov * 255f + 0.5f, 0, 255);
                byte R = (byte)Math.Clamp(accR * inv * cov * 255f + 0.5f, 0, A);
                byte G = (byte)Math.Clamp(accG * inv * cov * 255f + 0.5f, 0, A);
                byte B = (byte)Math.Clamp(accB * inv * cov * 255f + 0.5f, 0, A);
                px[yy * cw + xx] = (uint)(A << 24 | R << 16 | G << 8 | B);
            }
        }
        canvas.Commit();
    }

    static void SetCol(float[] m, int c, float a, float b, float d) { m[c] = a; m[3 + c] = b; m[6 + c] = d; }

    /// <summary>Row-major 3×3 object→view matrix: view = M · object.</summary>
    static void BuildRotation(float[] m, float cy, float sy, float cp, float sp, float cr, float sr)
    {
        // Apply to each object basis vector and store as columns.
        for (int axis = 0; axis < 3; axis++)
        {
            float x = axis == 0 ? 1 : 0, y = axis == 1 ? 1 : 0, z = axis == 2 ? 1 : 0;
            float x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y1 = y;          // yaw
            float y2 = y1 * cp + z1 * sp, z2 = -y1 * sp + z1 * cp, x2 = x1;     // tilt: +pitch brings the top (+y) towards the viewer (-z)
            float x3 = x2 * cr - y2 * sr, y3 = x2 * sr + y2 * cr, z3 = z2;      // lean
            SetCol(m, axis, x3, y3, z3);
        }
    }

    static bool Shade(CanLabel label, in CanPose p, float[] m, float bx, float by,
        float ox, float oy, float oz, float dx, float dy, float dz, out float r, out float g, out float b)
    {
        r = g = b = 0;
        float t = float.MaxValue; int part = PartNone;
        Side(ox, oy, oz, dx, dy, dz, 1f, 0f, YBase, YNeck, PartBody, ref t, ref part);
        Side(ox, oy, oz, dx, dy, dz, NeckA, NeckB, YNeck, YTop, PartNeck, ref t, ref part);
        Side(ox, oy, oz, dx, dy, dz, BaseA, BaseB, YBot, YBase, PartBase, ref t, ref part);
        Cap(ox, oy, oz, dx, dy, dz, YTop, RTop, PartTop, ref t, ref part);
        Cap(ox, oy, oz, dx, dy, dz, YBot, RBot, PartBottom, ref t, ref part);
        if (part == PartNone) return false;

        float x = ox + t * dx, y = oy + t * dy, z = oz + t * dz;

        // Object-space normal.
        float nx, ny, nz;
        switch (part)
        {
            case PartTop: nx = 0; ny = 1; nz = 0; break;
            case PartBottom: nx = 0; ny = -1; nz = 0; break;
            case PartNeck: nx = x; ny = -NeckB * (NeckA + NeckB * y); nz = z; break;
            case PartBase: nx = x; ny = -BaseB * (BaseA + BaseB * y); nz = z; break;
            default: nx = x; ny = 0; nz = z; break;
        }

        float ar, ag, ab;          // albedo
        float specK, specPow, diffK;
        if (part == PartBody)
        {
            float phi = MathF.Atan2(x, -z);
            float v = (YNeck - y) / (YNeck - YBase);
            label.Sample(phi / MathF.Tau + 0.5f, v, out ar, out ag, out ab);
            specK = 0.42f; specPow = 26f; diffK = 0.70f;

            if (p.Crumple > 0.001f)
            {
                // Crushed cans buckle in horizontal folds: tilt the normal up/down along a wavy fold pattern
                // (a little irregular around the can) and shade the creases slightly.
                float c = p.Crumple;
                float wobble = Noise(phi * 1.9f + 7.3f, y * 0.7f) - 0.5f;
                float fold = MathF.Sin((y + wobble * 0.9f) * 6.5f);
                float dent = Noise(phi * 3.2f, y * 1.3f + 2.1f) - 0.5f;
                ny += fold * 0.85f * c;
                float radial = 1f + dent * 0.5f * c;
                nx *= radial; nz *= radial;
                float crease = 1f - c * 0.18f * (1f - MathF.Abs(fold));
                ar *= crease; ag *= crease; ab *= crease;
            }
        }
        else if (part == PartTop)
        {
            Lid(x, z, p.TabOpen, out ar);
            ag = ar; ab = ar * 1.02f;
            specK = 0.55f; specPow = 18f; diffK = 0.55f;
        }
        else
        {
            ar = ag = 0.80f; ab = 0.83f;      // bare aluminium neck / base
            specK = 0.75f; specPow = 16f; diffK = 0.55f;
        }

        // Normal to view space (inverse-transpose of the scale is 1/scale for a diagonal scale).
        float snx = nx / bx, sny = ny / by, snz = nz / bx;
        float vx = m[0] * snx + m[1] * sny + m[2] * snz;
        float vy = m[3] * snx + m[4] * sny + m[5] * snz;
        float vz = m[6] * snx + m[7] * sny + m[8] * snz;
        float len = MathF.Sqrt(vx * vx + vy * vy + vz * vz);
        if (len < 1e-6f) return false;
        vx /= len; vy /= len; vz /= len;

        float nlKey = MathF.Max(0, vx * Key.X + vy * Key.Y + vz * Key.Z);
        float nlFill = MathF.Max(0, vx * Fill.X + vy * Fill.Y + vz * Fill.Z);
        float spec = specK * MathF.Pow(MathF.Max(0, vx * HalfKey.X + vy * HalfKey.Y + vz * HalfKey.Z), specPow)
                   + specK * 0.45f * MathF.Pow(MathF.Max(0, vx * HalfFill.X + vy * HalfFill.Y + vz * HalfFill.Z), specPow);
        // Darken towards the silhouette so the cylinder reads as round even at 10 px wide.
        float facing = MathF.Max(0, -vz);
        float rim = 0.62f + 0.38f * MathF.Sqrt(facing);
        float light = (0.34f + diffK * nlKey + 0.22f * nlFill) * rim;

        r = MathF.Min(1, ar * light + spec);
        g = MathF.Min(1, ag * light + spec);
        b = MathF.Min(1, ab * light + spec * 1.02f);
        return true;
    }

    /// <summary>Lid shade at (x, z) on the top cap (front of the can is -z).</summary>
    static void Lid(float x, float z, float tabOpen, out float c)
    {
        float rr = MathF.Sqrt(x * x + z * z) / RTop;
        if (rr > 0.90f) { c = 0.90f; return; }                  // rolled rim
        if (rr > 0.80f) { c = 0.52f + (rr - 0.80f) * 2.0f; return; } // countersink groove
        c = 0.76f - rr * 0.08f;                                 // centre panel

        // Mouth (score line) at the front; opens into a dark hole.
        float mx = x / 0.24f, mz = (z + 0.42f) / 0.17f;
        float md = mx * mx + mz * mz;
        if (md < 1f) c = tabOpen > 0.35f ? Lerp(c, 0.05f, MathF.Min(1, (tabOpen - 0.35f) * 3f)) : (md > 0.75f ? 0.6f : c);

        // Pull tab lying towards the back, with a finger hole; brightens as it lifts.
        float tx = x / 0.17f, tz = (z - 0.18f) / 0.36f;
        float td = tx * tx + tz * tz;
        if (td < 1f)
        {
            float hx = x / 0.09f, hz = (z - 0.32f) / 0.12f;
            bool hole = hx * hx + hz * hz < 1f;
            c = hole ? (tabOpen > 0.5f ? 0.08f : 0.45f) : (td > 0.8f ? 0.62f : 0.84f + tabOpen * 0.08f);
        }
        if (x * x + z * z < 0.004f) c = 0.66f;                  // rivet
    }

    static void Side(float ox, float oy, float oz, float dx, float dy, float dz, float a, float bb, float yMin, float yMax,
        int id, ref float tBest, ref int part)
    {
        // (ox + t dx)^2 + (oz + t dz)^2 = (a + bb (oy + t dy))^2
        float ra = a + bb * oy, rd = bb * dy;
        float A = dx * dx + dz * dz - rd * rd;
        float B = 2 * (ox * dx + oz * dz - ra * rd);
        float C = ox * ox + oz * oz - ra * ra;
        if (MathF.Abs(A) < 1e-9f) return;
        float disc = B * B - 4 * A * C;
        if (disc < 0) return;
        float sq = MathF.Sqrt(disc);
        float t1 = (-B - sq) / (2 * A), t2 = (-B + sq) / (2 * A);
        if (t1 > t2) (t1, t2) = (t2, t1);
        TrySide(t1, oy, dy, a, bb, yMin, yMax, id, ref tBest, ref part);
        TrySide(t2, oy, dy, a, bb, yMin, yMax, id, ref tBest, ref part);
    }

    static void TrySide(float t, float oy, float dy, float a, float bb, float yMin, float yMax, int id, ref float tBest, ref int part)
    {
        if (t <= 0 || t >= tBest) return;
        float y = oy + t * dy;
        if (y < yMin || y > yMax || a + bb * y <= 0) return;
        tBest = t; part = id;
    }

    static void Cap(float ox, float oy, float oz, float dx, float dy, float dz, float yc, float rc, int id, ref float tBest, ref int part)
    {
        if (MathF.Abs(dy) < 1e-9f) return;
        float t = (yc - oy) / dy;
        if (t <= 0 || t >= tBest) return;
        float x = ox + t * dx, z = oz + t * dz;
        if (x * x + z * z > rc * rc) return;
        tBest = t; part = id;
    }

    static float Noise(float x, float y)
    {
        int xi = (int)MathF.Floor(x), yi = (int)MathF.Floor(y);
        float fx = x - xi, fy = y - yi;
        fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
        float a = Hash(xi, yi), b = Hash(xi + 1, yi), c = Hash(xi, yi + 1), d = Hash(xi + 1, yi + 1);
        return Lerp(Lerp(a, b, fx), Lerp(c, d, fx), fy);
    }

    static float Hash(int x, int y)
    {
        uint h = (uint)(x * 374761393 + y * 668265263);
        h = (h ^ (h >> 13)) * 1274126177u;
        return (h ^ (h >> 16)) / (float)uint.MaxValue;
    }

    static float Lerp(float a, float b, float t) => a + (b - a) * t;

    static (float, float, float) Norm(float x, float y, float z)
    {
        float l = MathF.Sqrt(x * x + y * y + z * z);
        return (x / l, y / l, z / l);
    }
}
