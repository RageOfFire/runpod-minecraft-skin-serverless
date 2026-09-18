using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace MinecraftSkinRunPod;

internal sealed record AppSettings(string EndpointId, string ApiKey);

internal static class SettingsStore
{
    private sealed class SettingsFile
    {
        public string EndpointId { get; set; } = string.Empty;
        public string ProtectedApiKey { get; set; } = string.Empty;
    }

    private static readonly string SettingsDirectory =
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "MinecraftSkinRunPod");

    private static readonly string SettingsPath =
        Path.Combine(SettingsDirectory, "settings.json");

    public static string Location => SettingsPath;

    public static AppSettings Load()
    {
        try
        {
            if (!File.Exists(SettingsPath))
            {
                return new AppSettings(string.Empty, string.Empty);
            }

            var json = File.ReadAllText(SettingsPath);
            var stored = JsonSerializer.Deserialize<SettingsFile>(json) ?? new SettingsFile();

            var apiKey = string.Empty;
            if (!string.IsNullOrWhiteSpace(stored.ProtectedApiKey))
            {
                try
                {
                    var encrypted = Convert.FromBase64String(stored.ProtectedApiKey);
                    var decrypted = ProtectedData.Unprotect(
                        encrypted,
                        optionalEntropy: null,
                        scope: DataProtectionScope.CurrentUser);

                    apiKey = Encoding.UTF8.GetString(decrypted);
                }
                catch (CryptographicException)
                {
                    apiKey = string.Empty;
                }
                catch (FormatException)
                {
                    apiKey = string.Empty;
                }
            }

            return new AppSettings(stored.EndpointId.Trim(), apiKey);
        }
        catch
        {
            return new AppSettings(string.Empty, string.Empty);
        }
    }

    public static void Save(string endpointId, string apiKey)
    {
        endpointId = endpointId.Trim();
        apiKey = apiKey.Trim();

        if (string.IsNullOrWhiteSpace(endpointId))
        {
            throw new ArgumentException("Endpoint ID cannot be empty.", nameof(endpointId));
        }

        if (string.IsNullOrWhiteSpace(apiKey))
        {
            throw new ArgumentException("API key cannot be empty.", nameof(apiKey));
        }

        Directory.CreateDirectory(SettingsDirectory);

        var encrypted = ProtectedData.Protect(
            Encoding.UTF8.GetBytes(apiKey),
            optionalEntropy: null,
            scope: DataProtectionScope.CurrentUser);

        var stored = new SettingsFile
        {
            EndpointId = endpointId,
            ProtectedApiKey = Convert.ToBase64String(encrypted)
        };

        var json = JsonSerializer.Serialize(
            stored,
            new JsonSerializerOptions { WriteIndented = true });

        File.WriteAllText(SettingsPath, json);
    }
}
