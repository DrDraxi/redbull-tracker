using TaskbarWidget;

namespace RedBullTracker;

public static class Program
{
    [STAThread]
    public static void Main()
    {
        new RedBullApp().Start();
        Widget.Run();
    }
}
