using System.Text.Json;
using RedBullTracker.Models;

namespace RedBullTracker.Services;

public class SettingsService
{
    private readonly string _dataFolder;
    private readonly string _countFilePath;
    private readonly string _configFilePath;

    /// <summary>Loaded config. Setter is public so tests can swap a known
    /// AppConfig in without relying on whatever lives in %LOCALAPPDATA%.</summary>
    public AppConfig Config { get; set; } = new();

    public SettingsService()
    {
        _dataFolder = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RedBullTracker");
        _countFilePath = Path.Combine(_dataFolder, "count.txt");
        _configFilePath = Path.Combine(_dataFolder, "config.json");

        EnsureDataFolder();
        LoadConfig();
    }

    private void EnsureDataFolder()
    {
        if (!Directory.Exists(_dataFolder))
        {
            Directory.CreateDirectory(_dataFolder);
        }
    }

    public void LoadConfig()
    {
        try
        {
            if (File.Exists(_configFilePath))
            {
                var json = File.ReadAllText(_configFilePath);
                Config = JsonSerializer.Deserialize(json, AppJsonContext.Default.AppConfig) ?? new AppConfig();
            }
            else
            {
                // Create default config file
                Config = new AppConfig();
                SaveConfig();
            }
        }
        catch
        {
            Config = new AppConfig();
        }
    }

    public void SaveConfig()
    {
        try
        {
            var json = JsonSerializer.Serialize(Config, AppJsonContext.Default.AppConfig);
            File.WriteAllText(_configFilePath, json);
        }
        catch
        {
            // Ignore save errors
        }
    }

    public int LoadCount()
    {
        try
        {
            if (File.Exists(_countFilePath))
            {
                var text = File.ReadAllText(_countFilePath);
                if (int.TryParse(text.Trim(), out var count))
                {
                    return count;
                }
            }
        }
        catch
        {
            // Ignore errors, return default
        }
        return 0;
    }

    public void SaveCount(int count)
    {
        try
        {
            EnsureDataFolder();
            File.WriteAllText(_countFilePath, count.ToString());
        }
        catch
        {
            // Ignore save errors
        }
    }
}
