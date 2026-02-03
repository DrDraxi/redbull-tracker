using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using System;

namespace RedBullTracker.Widget;

public sealed partial class RedBullWidgetContent : UserControl
{
    private const int CanWidth = 12;
    private const int CanSpacing = 2;

    public event EventHandler? LeftClicked;
    public event EventHandler? RightClicked;
    public event EventHandler<int>? WidthChanged;

    private int _count;
    private string _canType = "default";
    private BitmapImage? _emptyImage;
    private BitmapImage? _canImage;

    public RedBullWidgetContent()
    {
        InitializeComponent();
        RootBorder.PointerPressed += OnPointerPressed;
        RootBorder.PointerEntered += OnPointerEntered;
        RootBorder.PointerExited += OnPointerExited;
    }

    public void SetCanType(string canType)
    {
        _canType = canType?.ToLowerInvariant() switch
        {
            "sugarfree" => "sugarfree",
            _ => "default"
        };
        LoadImages();
    }

    private void LoadImages()
    {
        var basePath = AppContext.BaseDirectory;

        _emptyImage = new BitmapImage(new Uri(System.IO.Path.Combine(basePath, "Assets", "redbull-empty.png")));

        var canFileName = _canType == "sugarfree" ? "redbull-sugarfree.png" : "redbull-default.png";
        _canImage = new BitmapImage(new Uri(System.IO.Path.Combine(basePath, "Assets", canFileName)));
    }

    public int GetDesiredWidth()
    {
        if (_count == 0)
        {
            return CanWidth + 12; // Single empty can + padding
        }
        // Each can is CanWidth + spacing, minus one spacing at the end
        return (_count * CanWidth) + ((_count - 1) * CanSpacing) + 12; // + padding
    }

    public void UpdateCount(int count)
    {
        _count = count;
        CansPanel.Children.Clear();

        // Load images if not loaded yet
        if (_canImage == null)
        {
            LoadImages();
        }

        if (count == 0)
        {
            // Show empty silhouette
            var emptyImage = new Image
            {
                Source = _emptyImage,
                Width = CanWidth,
                Height = 24,
                Stretch = Stretch.Uniform,
                Opacity = 0.5
            };
            CansPanel.Children.Add(emptyImage);
        }
        else
        {
            // Show actual cans with spacing
            for (int i = 0; i < count; i++)
            {
                var canImage = new Image
                {
                    Source = _canImage,
                    Width = CanWidth,
                    Height = 24,
                    Stretch = Stretch.Uniform
                };
                CansPanel.Children.Add(canImage);
            }
        }

        // Update tooltip
        CountToolTip.Content = $"Red Bulls: {count}\nLeft-click: Remove | Right-click: Add";

        // Notify about width change
        WidthChanged?.Invoke(this, GetDesiredWidth());
    }

    private void OnPointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(this);
        if (point.Properties.IsRightButtonPressed)
        {
            RightClicked?.Invoke(this, EventArgs.Empty);
        }
        else
        {
            LeftClicked?.Invoke(this, EventArgs.Empty);
        }
        e.Handled = true;
    }

    private void OnPointerEntered(object sender, PointerRoutedEventArgs e)
    {
        RootBorder.Background = new SolidColorBrush(Windows.UI.Color.FromArgb(40, 255, 255, 255));
    }

    private void OnPointerExited(object sender, PointerRoutedEventArgs e)
    {
        RootBorder.Background = new SolidColorBrush(Windows.UI.Color.FromArgb(0, 0, 0, 0));
    }
}
