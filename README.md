# RunPod Serverless Minecraft Skin Generator

Generate a usable Minecraft skin from:

- **Text only**
- **Reference image only**
- **Text + reference image**

The worker returns a **64×64 PNG Minecraft skin** using the Classic/Steve player model.

This project is designed for a locked-down/work laptop. You do **not** need Git, Docker Desktop, Docker Hub, Python, or PowerShell locally. GitHub Actions builds the Docker image in the cloud, GitHub Container Registry stores it, and RunPod runs it.

## What you need

1. A **GitHub account**
2. A **RunPod account**
3. A **web browser**
4. **Command Prompt (`cmd.exe`)** if you want to run the included local client

You do **not** need:

```text
Docker Hub
Docker Desktop
Git
Python
pip
PowerShell
```

---

# 1. Project structure

```text
runpod-minecraft-skin-serverless/
├── .github/
│   └── workflows/
│       └── build-ghcr.yml
├── tests/
│   └── test_postprocess.py
├── .dockerignore
├── .gitignore
├── Dockerfile
├── handler.py
├── requirements.txt
├── test_input.json
├── client.py
├── runpod-client.cmd
├── runpod-client.js
└── README.md
```

For Windows without Python, use:

```text
runpod-client.cmd
```

The `.cmd` file launches `runpod-client.js` through Windows Script Host (`cscript.exe`), which is included with normal Windows installations.

---

# 2. GitHub build

The included workflow:

```text
.github/workflows/build-ghcr.yml
```

runs automatically on pushes to `main` or `master` and builds the Docker image as `linux/amd64`.

Check it here:

```text
GitHub repository
→ Actions
→ Build RunPod Worker
```

The published image for this repository is:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Make sure the GitHub Container Registry package is **Public** so RunPod can pull it without registry credentials.

---

# 3. Create the RunPod Serverless endpoint

Open RunPod and go to:

```text
Serverless
→ New Endpoint
→ Import from Docker Registry
```

Use this container image:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Recommended endpoint name:

```text
minecraft-skin-ai
```

Endpoint type:

```text
Queue
```

---

# 4. Recommended GPU/settings

Start with:

```text
GPU: RTX 4090 24 GB
Active Workers: 0
Max Workers: 1
Execution Timeout: 300 seconds or more
Container Disk: 20 GB or more
```

If the worker reports CUDA out-of-memory errors, move to a 48 GB GPU such as A6000/A40/L40S-class hardware.

For faster responses with fewer cold starts, change:

```text
Active Workers: 1
```

For cheap testing, keep:

```text
Active Workers: 0
```

---

# 5. Configure RunPod model caching

In the RunPod endpoint settings, set the **Model** field to exactly:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

The Minecraft SDXL model is then loaded from RunPod's Hugging Face cache.

The reference-image IP-Adapter is already included in the Docker image, so do not configure a second model.

Optional environment variable if model initialization times out:

```text
RUNPOD_INIT_TIMEOUT=800
```

---

# 6. Deploy the endpoint

Click **Deploy Endpoint**.

After deployment, copy the endpoint ID. It will look similar to:

```text
abc123xyz456
```

You need this ID for the Command Prompt client.

---

# 7. Test directly in RunPod

Open the endpoint's **Requests** tab and send:

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

A successful result should include:

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

The PNG data is returned in:

```text
output.image_base64
```

The included Command Prompt client automatically decodes this and saves a real `skin.png` file.

---

# 8. Create a RunPod API key

In RunPod, create an API key that can invoke your Serverless endpoint.

Keep the API key private. Never commit it to GitHub and never put it in public frontend JavaScript.

You need:

```text
RUNPOD_API_KEY
RUNPOD_ENDPOINT_ID
```

---

# 9. Command Prompt client — zero install

Download these two files from the repository and put them in the same folder:

```text
runpod-client.cmd
runpod-client.js
```

Open **Command Prompt** in that folder.

Set your credentials for the current Command Prompt window:

```cmd
set RUNPOD_API_KEY=YOUR_RUNPOD_API_KEY
set RUNPOD_ENDPOINT_ID=YOUR_ENDPOINT_ID
```

Check that they are set:

```cmd
echo %RUNPOD_ENDPOINT_ID%
```

Do not share the API key or paste it into screenshots.

---

# 10. Generate from text in Command Prompt

Run:

```cmd
runpod-client.cmd --prompt "white fox warrior, blue eyes, navy hoodie" --output skin.png
```

The client will:

```text
Send request to RunPod
        ↓
Wait for generation
        ↓
Read output.image_base64
        ↓
Decode PNG
        ↓
Save skin.png
```

When successful you should see output similar to:

```text
Sending request to RunPod...
Saved: C:\...\skin.png
Size: 64x64
Seed: 123456
Mode: text
```

---

# 11. Generate from a normal image

Your source image does **not** need to be a Minecraft skin.

Supported examples include normal character art, avatars, screenshots, renders, PNG/JPEG/WebP images, etc.

Example:

```cmd
runpod-client.cmd --image "C:\Users\YOUR_NAME\Pictures\character.png" --output skin.png
```

The decoded reference image must currently be **6 MB or smaller**.

---

# 12. Generate from prompt + image

This is usually the best mode:

```cmd
runpod-client.cmd --prompt "keep this character's hair, outfit, colors and appearance" --image "C:\Users\YOUR_NAME\Pictures\character.png" --strength 0.75 --output skin.png
```

Recommended starting strength:

```text
0.70 - 0.75
```

General guideline:

```text
0.40 - 0.55 = loose inspiration
0.60 - 0.70 = balanced
0.70 - 0.85 = stronger appearance preservation
0.90+       = very strong image influence; UV quality can become less stable
```

If resemblance is too weak:

```text
0.75 → 0.80
```

If the Minecraft UV starts looking broken:

```text
0.75 → 0.65
```

---

# 13. Fixed seed

For repeatable generation:

```cmd
runpod-client.cmd --prompt "blue fire mage" --seed 12345 --output skin.png
```

---

# 14. Other Command Prompt options

Show help:

```cmd
runpod-client.cmd --help
```

Available options:

```text
--prompt TEXT
--image PATH
--strength NUMBER
--reference-strength NUMBER
--steps NUMBER
--guidance NUMBER
--seed NUMBER
--output PATH
--format modern|legacy
--negative TEXT
--help
```

Example with more settings:

```cmd
runpod-client.cmd --prompt "cyberpunk girl with purple hair" --steps 40 --guidance 7.5 --seed 777 --negative "blurry, broken skin" --output cyberpunk.png
```

---

# 15. How the Command Prompt client works

`cmd.exe` launches:

```text
runpod-client.cmd
        ↓
cscript.exe
        ↓
runpod-client.js
```

The JavaScript uses built-in Windows components:

```text
Windows Script Host
WinHTTP
MSXML
ADODB.Stream
```

No Python or PowerShell is required.

For image input, the JavaScript reads the image as binary, converts it to Base64, sends it to RunPod, receives the generated Minecraft skin, decodes it, and writes the PNG to disk.

---

# 16. If `cscript.exe` is blocked

Some company-managed Windows computers disable Windows Script Host.

If you receive an error saying `cscript.exe` is unavailable or Windows Script Host is disabled, the local `.cmd` client cannot run on that machine.

You can still use:

```text
RunPod endpoint
→ Requests
```

for testing, or call the RunPod API from your own backend/server.

This does not affect the RunPod worker itself.

---

# 17. Direct RunPod API

Synchronous endpoint:

```text
POST https://api.runpod.ai/v2/ENDPOINT_ID/runsync
```

Authorization header:

```text
Authorization: Bearer YOUR_RUNPOD_API_KEY
```

Text request:

```json
{
  "input": {
    "prompt": "cyberpunk girl, purple hair, black jacket",
    "steps": 35,
    "format": "modern"
  }
}
```

Reference-image request shape:

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

`runpod-client.cmd` handles the Base64 conversion automatically.

---

# 18. Input options

| Field | Required | Default | Description |
|---|---:|---:|---|
| `prompt` | No* | empty | Character description |
| `reference_image_base64` | No* | empty | Base64 reference image |
| `reference_strength` | No | `0.70` | Reference-image influence |
| `steps` | No | `35` | Diffusion steps; allowed `10-60` |
| `guidance_scale` | No | `7.5` | Prompt guidance; allowed `1-15` |
| `seed` | No | random | Reproducible generation seed |
| `format` | No | `modern` | `modern` = 64×64; `legacy` = 64×32 |
| `negative_prompt` | No | empty | Things the model should avoid |
| `transparency_cutoff` | No | `50` | Overlay-background cleanup threshold |

*Provide at least a prompt, a reference image, or both.

---

# 19. Output

Typical worker output:

```json
{
  "image_base64": "iVBORw0KGgoAAA...",
  "mime_type": "image/png",
  "width": 64,
  "height": 64,
  "format": "modern",
  "player_model": "classic",
  "source_mode": "text+image",
  "reference_strength": 0.75,
  "seed": 12345,
  "steps": 35,
  "guidance_scale": 7.5,
  "bytes": 1234,
  "sha256": "...",
  "model": "monadical-labs/minecraft-skin-generator-sdxl"
}
```

---

# 20. Updating the project later

No Git installation is required.

You can ask ChatGPT to update the connected GitHub repository, or edit files directly on GitHub's website.

Every commit to `main` or `master` automatically triggers the GitHub Actions Docker build and republishes:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

After publishing a new container, restart/redeploy the RunPod worker if necessary so it pulls the newest image.

---

# 21. Troubleshooting

## RunPod cannot pull the image

Make sure the GHCR package is public and use the lowercase image path:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Docker/GHCR repository image names must be lowercase.

## `CUDA GPU is required`

Make sure the endpoint is using an NVIDIA GPU worker.

## CUDA out of memory

Use a GPU with more VRAM. Start around 24 GB; use 48 GB if needed.

## Model downloads every startup

Check that RunPod's Model field is exactly:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

## Reference image is too large

Use an image of 6 MB or smaller.

## `cscript.exe is not available`

Windows Script Host is missing or disabled by your organization. Use the RunPod Requests panel or your own backend instead.

## Job does not complete

Check:

```text
RunPod endpoint
→ Workers
→ Logs
```

Look for CUDA errors, model loading errors, or initialization timeout messages.

## Poor reference-image resemblance

Increase the reference strength slightly and use a clean reference image.

## Broken-looking Minecraft skin

Try another seed. Generative UV output is not guaranteed to be perfect on every generation.

---

# 22. Security

Never put your RunPod API key in public frontend code.

Recommended production architecture:

```text
Browser / App
      ↓
Your backend API
      ↓
RunPod Serverless
      ↓
Minecraft skin PNG
```

For private local testing, the API key can be stored temporarily in the current Command Prompt process using:

```cmd
set RUNPOD_API_KEY=YOUR_KEY
```

Closing that Command Prompt window removes that process environment variable.

---

# 23. Fast setup checklist

```text
[ ] GitHub Actions build is green
[ ] GHCR package is Public
[ ] RunPod Queue endpoint created
[ ] Container image = ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
[ ] Model = monadical-labs/minecraft-skin-generator-sdxl
[ ] GPU = RTX 4090 24 GB or larger
[ ] Active Workers = 0 for testing
[ ] Max Workers = 1
[ ] Endpoint deployed
[ ] Text request works in RunPod Requests
[ ] RunPod API key created
[ ] RUNPOD_API_KEY set in Command Prompt
[ ] RUNPOD_ENDPOINT_ID set in Command Prompt
[ ] runpod-client.cmd creates skin.png
[ ] Reference-image generation works
```

Once those steps work, the service is ready without Git, Docker Desktop, Docker Hub, Python, or PowerShell on your laptop.

---

# Official documentation

- GitHub Actions — publishing Docker images: https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images
- GitHub Container Registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- RunPod documentation: https://docs.runpod.io/
