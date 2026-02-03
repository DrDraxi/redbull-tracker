using Microsoft.UI.Xaml;

namespace RedBullTracker;

public sealed partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        // Keep window hidden - we only need it for WinUI lifecycle
    }
}
