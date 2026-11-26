using TaskbarWidget;

namespace RedBullTracker;

public static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--preview")
        {
            Preview.Run(args[1]);
            return;
        }
        new RedBullApp().Start();
        Widget.Run();
    }
}
