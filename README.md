# RunPod Serverless Minecraft Skin Generator

Generate a directly usable Minecraft skin from:

- **Text only**
- **Reference image only**
- **Text + reference image**

The RunPod worker returns a **64×64 PNG Minecraft skin** using the Classic/Steve player model.

The project is designed for a locked-down Windows laptop. The recommended local client is now a **C# WinForms self-contained x64 EXE** built by GitHub Actions. You do not need Visual Studio, the .NET SDK, Python, PowerShell, Git, Docker Desktop, or Docker Hub on the laptop.

---

# 1. Project structure

```text
runpod-minecraft-skin-serverless/
├── .github/
│   └── workflows/
│       ├── build-ghcr.yml
│       └── build-windows-client.yml
├── windows-client/
│   ├── MinecraftSkinRunPod.csproj
│   ├── Program.cs
│   ├── MainForm.cs
│   ├── SettingsDialog.cs
│   ├── SettingsStore.cs
│   └── RunPodClient.cs
├── tests/
│   └── test_postprocess.py
├── Dockerfile
├── handler.py
├── requirements.txt
├── test_input.json
├── client.py
├── runpod-client.cmd
├── runpod-client.js
├── runpod-client.hta
└── README.md
```

The old CMD/HTA/JS client is kept as a legacy fallback. The C# Windows app is the recommended client.

---

# 2. RunPod worker build

The workflow:

```text
.github/workflows/build-ghcr.yml
```

builds and publishes the RunPod worker when the worker/Docker files change.

Published image:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Make sure the GitHub Container Registry package is **Public** so RunPod can pull it without registry credentials.

---

# 3. Create the RunPod Serverless endpoint

Create a custom Queue endpoint using:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Recommended starting settings:

```text
GPU: RTX 4090 24 GB
Active Workers: 0
Max Workers: 1
Execution Timeout: 300 seconds or more
Container Disk: 20-30 GB
```

If CUDA runs out of memory, use a GPU with more VRAM.

---

# 4. Configure RunPod model caching

Set the endpoint **Model** field to exactly:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

The IP-Adapter reference-image files are already included in the Docker image.

Optional initialization timeout:

```text
RUNPOD_INIT_TIMEOUT=800
```

---

# 5. Test the worker in RunPod

In the endpoint **Requests** tab:

```json
{
  "input": {
    "prompt": "white fox warrior, bright blue eyes, navy hoodie, black pants",
    "steps": 35,
    "guidance_scale": 7.5,
    "format": "modern"
  }
}
```

Successful output includes:

```json
{
  "status": "COMPLETED",
  "output": {
    "image_base64": "iVBORw0KGgoAAA...",
    "mime_type": "image/png",
    "width": 64,
    "height": 64,
    "format": "modern",
    "player_model": "classic",
    "source_mode": "text",
    "seed": 123456
  }
}
```

---

# 6. C# Windows app

The recommended Windows client is:

```text
MinecraftSkinRunPod.exe
```

Technology:

```text
C#
WinForms
.NET 10
Windows x64
Self-contained
Single-file publish
```

Because it is self-contained, the target PC does **not** need the .NET runtime installed.

The GUI provides:

- prompt input
- PNG/JPG/WebP/GIF reference-image selection
- reference-image preview
- reference strength
- diffusion steps
- guidance scale
- optional seed
- optional negative prompt
- output PNG selection
- **Generate Skin**
- cancellation
- generated-skin preview
- **Open Folder**
- **Save As**

The app always requests the modern **64×64** skin format.

---

# 7. Build/download the Windows EXE

GitHub Actions builds the Windows app automatically whenever `windows-client/**` changes.

Open:

```text
GitHub repository
→ Actions
→ Build Windows Client
→ latest successful run
→ Artifacts
→ MinecraftSkinRunPod-win-x64
```

Download the artifact ZIP, extract it, and run:

```text
MinecraftSkinRunPod.exe
```

You do not need to compile anything locally.

The EXE is currently unsigned, so Windows SmartScreen or company security software may show an unknown-publisher warning.

---

# 8. First launch / local settings

On first launch, the app opens **RunPod Settings**.

Enter:

```text
RunPod Endpoint ID
RunPod API Key
```

The endpoint ID is stored locally.

The API key is encrypted with Windows **DPAPI CurrentUser**, so the settings file cannot simply be copied to another Windows account and decrypted there.

Settings are stored under the current Windows profile:

```text
%APPDATA%\MinecraftSkinRunPod\settings.json
```

Your real API key is never stored in this public GitHub repository.

Use the **Settings** button in the app to change the endpoint or API key later.

---

# 9. Generate from text

Example prompt:

```text
white fox girl, bright blue eyes, navy hoodie, black pants
```

Leave the reference image empty and click **Generate Skin**.

The app:

```text
sends request to RunPod
        ↓
waits for generation
        ↓
receives output.image_base64
        ↓
decodes the PNG
        ↓
saves the 64×64 skin
        ↓
shows a preview
```

---

# 10. Generate from a normal reference image

Click **Choose Image...** and select a normal character image.

Supported request-file types include:

```text
PNG
JPEG/JPG
WebP
GIF
```

Maximum reference-image size:

```text
6 MB
```

The source image does not need to be a Minecraft skin.

The Windows app converts the file to Base64 internally. You never need to copy Base64 manually.

---

# 11. Prompt + image

This is usually the most useful mode.

Example:

```text
Prompt:
keep this character's hair, outfit, face and colors

Reference strength:
0.75

Steps:
35

Guidance:
7.5
```

Reference-strength guideline:

```text
0.40 - 0.55 = loose inspiration
0.60 - 0.70 = balanced
0.70 - 0.85 = stronger appearance preservation
0.90+       = very strong image influence; UV stability can decrease
```

If resemblance is too weak, increase the value slightly.

If the Minecraft UV becomes unstable, reduce it slightly.

---

# 12. Direct RunPod API

Synchronous endpoint:

```text
POST https://api.runpod.ai/v2/ENDPOINT_ID/runsync
```

Authorization:

```text
Authorization: Bearer YOUR_RUNPOD_API_KEY
```

Reference-image request:

```json
{
  "input": {
    "prompt": "preserve this character's outfit and colors",
    "reference_image_base64": "BASE64_IMAGE_HERE",
    "reference_strength": 0.75,
    "steps": 35,
    "format": "modern"
  }
}
```

The C# client handles Base64 conversion automatically.

---

# 13. Worker input options

| Field | Required | Default | Description |
|---|---:|---:|---|
| `prompt` | No* | empty | Character description |
| `reference_image_base64` | No* | empty | Base64 reference image |
| `reference_strength` | No | `0.70` | Reference-image influence |
| `steps` | No | `35` | Diffusion steps, allowed `10-60` |
| `guidance_scale` | No | `7.5` | Prompt guidance, allowed `1-15` |
| `seed` | No | random | Reproducible generation seed |
| `format` | No | `modern` | `modern` = 64×64, `legacy` = 64×32 |
| `negative_prompt` | No | empty | Things the model should avoid |
| `transparency_cutoff` | No | `50` | Overlay-background cleanup threshold |

*Provide at least a prompt, a reference image, or both.

---

# 14. Updating the project

You can ask ChatGPT to update the connected GitHub repository or edit files on GitHub.

Worker changes trigger:

```text
Build RunPod Worker
        ↓
GHCR
        ↓
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Windows-client changes trigger:

```text
Build Windows Client
        ↓
self-contained win-x64 publish
        ↓
MinecraftSkinRunPod-win-x64 artifact
```

C#-only changes no longer rebuild the large RunPod Docker image.

---

# 15. Legacy Windows client

These files remain available as a fallback:

```text
runpod-client.cmd
runpod-client.js
runpod-client.hta
```

The legacy client uses Windows Script Host / HTA. It is no longer the recommended client.

This is useful only if the C# EXE is blocked and your PC still allows `cscript.exe` or `mshta.exe`.

---

# 16. Troubleshooting

## RunPod cannot pull the container

Use exactly:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

and make sure the GHCR package is public.

## Model cache error

RunPod Model must be:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

## CUDA out of memory

Use a GPU with more VRAM.

## Reference image is too large

Use a file of 6 MB or smaller.

## Windows app says RunPod is not configured

Open **Settings** and enter the endpoint ID and API key.

## Windows blocks the EXE

The app is currently unsigned. SmartScreen or corporate endpoint protection may block unknown executables. The source and GitHub Actions workflow are in this repository so the build process is visible.

## Job fails

Check:

```text
RunPod endpoint
→ Workers
→ Logs
```

## Poor reference resemblance

Increase reference strength slightly and use a clean character reference.

## Broken-looking skin

Try a different seed or reduce reference strength. Generative UV output is not perfect on every generation.

---

# 17. Security

Never commit a real RunPod API key to this public repository.

The C# app stores the key locally and encrypts it for the current Windows user with DPAPI.

For a future public/distributed version of the application, the stronger production architecture is still:

```text
Desktop app
     ↓
Your backend
     ↓
RunPod Serverless
```

That keeps the RunPod API key entirely off end-user machines.

---

# 18. Fast setup checklist

```text
[ ] Build RunPod Worker is green
[ ] GHCR package is Public
[ ] RunPod Queue endpoint created
[ ] Container image = ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
[ ] Model = monadical-labs/minecraft-skin-generator-sdxl
[ ] GPU = RTX 4090 24 GB or larger
[ ] Endpoint request works in RunPod
[ ] RunPod API key created
[ ] Build Windows Client is green
[ ] MinecraftSkinRunPod-win-x64 artifact downloaded
[ ] MinecraftSkinRunPod.exe launched
[ ] Endpoint ID + API key saved in Settings
[ ] Prompt-only generation works
[ ] Reference-image generation works
[ ] 64×64 skin PNG is saved correctly
```

---

# Official documentation

- GitHub Actions: https://docs.github.com/actions
- GitHub Container Registry: https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- RunPod documentation: https://docs.runpod.io/
- .NET deployment: https://learn.microsoft.com/dotnet/core/deploying/
