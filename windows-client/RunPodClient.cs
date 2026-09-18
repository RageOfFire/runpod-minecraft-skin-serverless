using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace MinecraftSkinRunPod;

internal sealed class GenerationOptions
{
    public string Prompt { get; init; } = string.Empty;
    public string? ReferenceImagePath { get; init; }
    public decimal ReferenceStrength { get; init; } = 0.75m;
    public int Steps { get; init; } = 35;
    public decimal GuidanceScale { get; init; } = 7.5m;
    public int? Seed { get; init; }
    public string NegativePrompt { get; init; } = string.Empty;
}

internal sealed class GenerationResult
{
    public required byte[] PngBytes { get; init; }
    public int Width { get; init; }
    public int Height { get; init; }
    public int? Seed { get; init; }
    public string SourceMode { get; init; } = string.Empty;
    public string RawResponse { get; init; } = string.Empty;
}

internal sealed class RunPodClient
{
    private const long MaxReferenceBytes = 6L * 1024L * 1024L;

    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromMinutes(6)
    };

    public async Task<GenerationResult> GenerateAsync(
        AppSettings settings,
        GenerationOptions options,
        CancellationToken cancellationToken)
    {
        Validate(settings, options);

        var input = new Dictionary<string, object?>
        {
            ["prompt"] = options.Prompt.Trim(),
            ["steps"] = options.Steps,
            ["guidance_scale"] = options.GuidanceScale,
            ["format"] = "modern"
        };

        if (!string.IsNullOrWhiteSpace(options.NegativePrompt))
        {
            input["negative_prompt"] = options.NegativePrompt.Trim();
        }

        if (options.Seed.HasValue)
        {
            input["seed"] = options.Seed.Value;
        }

        if (!string.IsNullOrWhiteSpace(options.ReferenceImagePath))
        {
            var file = new FileInfo(options.ReferenceImagePath);

            if (!file.Exists)
            {
                throw new FileNotFoundException("Reference image was not found.", file.FullName);
            }

            if (file.Length > MaxReferenceBytes)
            {
                throw new InvalidOperationException("Reference image must be 6 MB or smaller.");
            }

            var imageBytes = await File.ReadAllBytesAsync(file.FullName, cancellationToken);
            input["reference_image_base64"] = Convert.ToBase64String(imageBytes);
            input["reference_strength"] = options.ReferenceStrength;
        }

        var requestBody = JsonSerializer.Serialize(new Dictionary<string, object?>
        {
            ["input"] = input
        });

        var endpoint =
            $"https://api.runpod.ai/v2/{Uri.EscapeDataString(settings.EndpointId)}/runsync?wait=300000";

        using var request = new HttpRequestMessage(HttpMethod.Post, endpoint);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", settings.ApiKey);
        request.Content = new StringContent(requestBody, Encoding.UTF8, "application/json");

        using var response = await Http.SendAsync(
            request,
            HttpCompletionOption.ResponseContentRead,
            cancellationToken);

        var responseText = await response.Content.ReadAsStringAsync(cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"RunPod HTTP {(int)response.StatusCode} ({response.ReasonPhrase}).\n\n{responseText}");
        }

        using var document = JsonDocument.Parse(responseText);
        var root = document.RootElement;

        var status = ReadString(root, "status");
        if (!string.Equals(status, "COMPLETED", StringComparison.OrdinalIgnoreCase))
        {
            var error = ReadElementText(root, "error");
            if (string.IsNullOrWhiteSpace(error))
            {
                error = responseText;
            }

            throw new InvalidOperationException(
                $"RunPod job did not complete. Status: {status ?? "unknown"}\n\n{error}");
        }

        if (!root.TryGetProperty("output", out var output) ||
            output.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidOperationException(
                "RunPod response does not contain an output object.\n\n" + responseText);
        }

        var imageBase64 = ReadString(output, "image_base64");
        if (string.IsNullOrWhiteSpace(imageBase64))
        {
            throw new InvalidOperationException(
                "RunPod response does not contain output.image_base64.\n\n" + responseText);
        }

        byte[] pngBytes;
        try
        {
            pngBytes = Convert.FromBase64String(imageBase64);
        }
        catch (FormatException ex)
        {
            throw new InvalidOperationException(
                "RunPod returned invalid Base64 image data.", ex);
        }

        return new GenerationResult
        {
            PngBytes = pngBytes,
            Width = ReadInt(output, "width"),
            Height = ReadInt(output, "height"),
            Seed = ReadNullableInt(output, "seed"),
            SourceMode = ReadString(output, "source_mode") ?? string.Empty,
            RawResponse = responseText
        };
    }

    private static void Validate(AppSettings settings, GenerationOptions options)
    {
        if (string.IsNullOrWhiteSpace(settings.EndpointId))
        {
            throw new InvalidOperationException("RunPod endpoint ID is not configured.");
        }

        if (string.IsNullOrWhiteSpace(settings.ApiKey))
        {
            throw new InvalidOperationException("RunPod API key is not configured.");
        }

        var hasPrompt = !string.IsNullOrWhiteSpace(options.Prompt);
        var hasImage = !string.IsNullOrWhiteSpace(options.ReferenceImagePath);

        if (!hasPrompt && !hasImage)
        {
            throw new InvalidOperationException(
                "Type a prompt, choose a reference image, or use both.");
        }

        if (options.Prompt.Length > 600)
        {
            throw new InvalidOperationException("Prompt must be 600 characters or fewer.");
        }

        if (options.NegativePrompt.Length > 600)
        {
            throw new InvalidOperationException(
                "Negative prompt must be 600 characters or fewer.");
        }

        if (options.ReferenceStrength < 0 || options.ReferenceStrength > 1.25m)
        {
            throw new InvalidOperationException(
                "Reference strength must be between 0 and 1.25.");
        }

        if (options.Steps < 10 || options.Steps > 60)
        {
            throw new InvalidOperationException("Steps must be between 10 and 60.");
        }

        if (options.GuidanceScale < 1 || options.GuidanceScale > 15)
        {
            throw new InvalidOperationException("Guidance must be between 1 and 15.");
        }

        if (options.Seed is < 0)
        {
            throw new InvalidOperationException("Seed cannot be negative.");
        }
    }

    private static string? ReadString(JsonElement element, string name)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return null;
        }

        return value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : value.ToString();
    }

    private static int ReadInt(JsonElement element, string name)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return 0;
        }

        if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var number))
        {
            return number;
        }

        return int.TryParse(value.ToString(), out number) ? number : 0;
    }

    private static int? ReadNullableInt(JsonElement element, string name)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return null;
        }

        if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var number))
        {
            return number;
        }

        return int.TryParse(value.ToString(), out number) ? number : null;
    }

    private static string ReadElementText(JsonElement element, string name)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return string.Empty;
        }

        return value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : value.GetRawText();
    }
}
