# RunPod Serverless Minecraft Skin Generator

Generate a usable Minecraft skin from:

- **Text only**
- **Reference image only**
- **Text + reference image**

The worker returns a **64×64 PNG Minecraft skin** using the Classic/Steve player model.

This version is designed for a locked-down/work laptop: **you do not need Git, Docker Desktop, Docker Hub, or Python installed locally.** GitHub Actions builds the Docker image in the cloud and publishes it to GitHub Container Registry (GHCR), then RunPod pulls that image.

## What you need

Only:

1. A **GitHub account**.
2. A **RunPod account**.
3. A **web browser**.
4. Windows PowerShell only if you want to test reference-image uploads from your laptop. PowerShell is already included with Windows.

You do **not** need:

```text
Docker Hub
Docker Desktop
Git
Python
pip
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
├── runpod-client.ps1
└── README.md
```

The important new file is:

```text
.github/workflows/build-ghcr.yml
```

GitHub Actions uses it to build the RunPod Docker image automatically.

---

# 2. Put the project on GitHub without Git

## Option A — ChatGPT GitHub connector

If you connected the GitHub app in ChatGPT, ChatGPT can publish/update the repository for you without Git on your laptop.

A sensible repository name is:

```text
runpod-minecraft-skin-serverless
```

## Option B — GitHub website only

If you want to do it manually:

1. Open GitHub in your browser.
2. Click **New repository**.
3. Repository name:

```text
runpod-minecraft-skin-serverless
```

4. Choose **Public** for the simplest RunPod setup.
5. Create the repository.
6. Use **Add file → Upload files**.
7. Upload the extracted project contents, including the `.github` folder.
8. Commit the files to the repository's default branch (`main` or `master`).

Do not upload only the ZIP as a single file. GitHub Actions needs the actual `Dockerfile`, `handler.py`, `.github/workflows/build-ghcr.yml`, and other project files in the repository.

---

# 3. Let GitHub build the Docker image for you

The included workflow runs automatically whenever files are pushed/committed to `main` or `master`.

You can also start it manually:

```text
GitHub repository
→ Actions
→ Build RunPod Worker
→ Run workflow
```

The workflow performs this in GitHub's cloud:

```text
GitHub source code
      ↓
GitHub Actions
      ↓
Docker build (linux/amd64)
      ↓
GitHub Container Registry
      ↓
ghcr.io/YOUR_USERNAME/runpod-minecraft-skin-serverless:latest
```

You do not need Docker installed on your PC.

To check the build:

```text
Repository → Actions → Build RunPod Worker
```

Wait for the workflow to show a green success check.

---

# 4. Make the GHCR container public

After the first successful workflow, GitHub creates a container package.

Open your GitHub profile/organization and find **Packages**, then open the package for this repository.

The image should be named something like:

```text
runpod-minecraft-skin-serverless
```

Open **Package settings** and change the package visibility to **Public**.

This lets RunPod pull the container without GitHub registry credentials.

Your image URL will normally be:

```text
ghcr.io/YOUR_GITHUB_USERNAME/runpod-minecraft-skin-serverless:latest
```

If the repository belongs to an organization, use the organization name instead of your username.

---

# 5. Create the RunPod Serverless endpoint

Open the RunPod Console.

Go to:

```text
Serverless
```

Create a new endpoint/import a custom container image.

For the container image, enter:

```text
ghcr.io/YOUR_GITHUB_USERNAME/runpod-minecraft-skin-serverless:latest
```

Example only:

```text
ghcr.io/rageoffire/runpod-minecraft-skin-serverless:latest
```

Use your real GitHub username/organization.

---

# 6. RunPod settings

Use these as the initial settings.

## Endpoint type

```text
Queue
```

## GPU

Use an NVIDIA GPU with **24 GB VRAM or more** when possible.

Reference-image mode loads SDXL plus IP-Adapter, so smaller GPUs can run out of VRAM.

## Active workers

For cheaper testing:

```text
0
```

For lower cold-start latency:

```text
1
```

## Max workers

Start with:

```text
1
```

## Execution timeout

Use:

```text
300 seconds or more
```

## Container disk

Use:

```text
20 GB or more
```

---

# 7. Configure RunPod model caching

In the endpoint settings, find the **Model** field.

Enter exactly:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

The large Minecraft SDXL model is then handled by RunPod's model cache.

The reference-image IP-Adapter is already baked into the Docker image, so do not add a second model to this field.

---

# 8. Deploy the endpoint

Click **Deploy Endpoint**.

When the endpoint is created, copy its **Endpoint ID**.

Example:

```text
abc123xyz456
```

You will use this ID when calling the API.

---

# 9. Test text generation entirely in the RunPod website

Open your endpoint's **Requests** area and submit:

```json
{
  "input": {
    "prompt": "white fox warrior, bright blue eyes, navy hoodie, black pants",
    "steps": 35,
    "format": "modern"
  }
}
```

A completed response should contain an output similar to:

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
    "seed": 123456,
    "steps": 35,
    "guidance_scale": 7.5
  }
}
```

The PNG is returned as Base64 in:

```text
output.image_base64
```

For convenient automatic saving to `skin.png`, use the included PowerShell client below.

---

# 10. Create a RunPod API key

In RunPod Console, open the API-key settings and create a key that can invoke your Serverless endpoint.

Keep the key private.

Never commit it to GitHub and never put it into public website JavaScript.

---

# 11. Zero-install Windows client

The project includes:

```text
runpod-client.ps1
```

It uses Windows PowerShell/.NET directly. No Python, pip, Git, curl install, or Docker is required.

Open PowerShell in the extracted project folder and set your credentials for the current PowerShell window:

```powershell
$env:RUNPOD_API_KEY="YOUR_RUNPOD_API_KEY"
$env:RUNPOD_ENDPOINT_ID="YOUR_ENDPOINT_ID"
```

## Generate from text

```powershell
.\runpod-client.ps1 `
  -Prompt "white fox warrior, blue eyes, navy hoodie" `
  -Output ".\skin.png"
```

The script calls RunPod, decodes the Base64 output, and writes:

```text
skin.png
```

---

# 12. Generate from a normal image — no Python required

Put your image somewhere on the laptop, for example:

```text
C:\Users\YOUR_NAME\Pictures\character.png
```

Then run:

```powershell
.\runpod-client.ps1 `
  -Image "C:\Users\YOUR_NAME\Pictures\character.png" `
  -Output ".\skin.png"
```

The image does **not** need to be a Minecraft skin.

You can use normal character art, screenshots, avatars, renders, PNG/JPEG/WebP images, etc.

The worker currently limits the decoded reference image to **6 MB**.

---

# 13. Generate from prompt + image

This is normally the best mode:

```powershell
.\runpod-client.ps1 `
  -Prompt "keep this character's hair, outfit, colors and overall appearance; turn it into a clean Minecraft skin" `
  -Image "C:\Users\YOUR_NAME\Pictures\character.png" `
  -ReferenceStrength 0.75 `
  -Output ".\skin.png"
```

Recommended starting reference strength:

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

---

# 14. Use a fixed seed

For repeatable generation:

```powershell
.\runpod-client.ps1 `
  -Prompt "blue fire mage" `
  -Seed 12345 `
  -Output ".\skin.png"
```

---

# 15. PowerShell execution-policy problem

Some work laptops block running `.ps1` files directly.

If PowerShell reports that script execution is disabled, you can run the file for that one process with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\runpod-client.ps1 `
  -Prompt "white fox warrior with blue eyes" `
  -Output ".\skin.png"
```

This does not require installing software.

If your company policy blocks PowerShell entirely, use the RunPod website's Requests panel for text-only testing or call the API from your own backend/server.

---

# 16. Direct RunPod API

Synchronous endpoint:

```text
POST https://api.runpod.ai/v2/ENDPOINT_ID/runsync
```

Authorization:

```text
Authorization: Bearer YOUR_RUNPOD_API_KEY
```

Request:

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

`runpod-client.ps1` converts your local image to Base64 automatically.

---

# 17. Input options

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

\* Provide at least a prompt, a reference image, or both.

---

# 18. Output

Typical output:

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

# 19. Updating the project later — still no Git required

You have three easy options.

## ChatGPT + GitHub connector

Ask ChatGPT to update the repository files and publish the change.

## GitHub website

Open a file in the repository, click the edit button, make the change, and commit it to your default branch.

For replacing multiple files, use **Add file → Upload files**.

## Automatic rebuild

Every commit to `main` or `master` triggers:

```text
.github/workflows/build-ghcr.yml
```

GitHub Actions rebuilds and republishes:

```text
ghcr.io/YOUR_USERNAME/runpod-minecraft-skin-serverless:latest
```

You therefore never need to run `docker build` or `docker push` yourself.

After a new image is published, restart/redeploy your RunPod endpoint/workers so they use the newest image.

---

# 20. Troubleshooting

## GitHub Actions says package write is denied

Open the repository settings and check the Actions/workflow permissions. The workflow needs permission to write packages.

The included workflow requests:

```yaml
permissions:
  contents: read
  packages: write
```

## RunPod cannot pull the image

Make sure the GHCR package is **Public** and that the URL is correct:

```text
ghcr.io/YOUR_USERNAME/runpod-minecraft-skin-serverless:latest
```

## `CUDA GPU is required`

Your worker is not running on a compatible NVIDIA GPU. Edit the RunPod endpoint GPU selection.

## CUDA out of memory

Choose a GPU with more VRAM. **24 GB+** is recommended for this project, particularly with reference images.

## Model downloads every startup

Check that the RunPod endpoint's Model field is exactly:

```text
monadical-labs/minecraft-skin-generator-sdxl
```

## `reference image is too large`

Use an image of **6 MB or smaller**.

## Poor reference-image resemblance

Try increasing:

```text
0.70 → 0.80
```

Also use a clear image and tell the prompt which visual details are important.

## Broken-looking Minecraft skin

Try a different seed. AI-generated Minecraft UV layouts are not perfect every generation.

For production, generating several candidates and selecting the best one is recommended.

---

# 21. Security

Do not put your RunPod API key into a public website frontend.

Use:

```text
Browser / App
      ↓
Your backend API
      ↓
RunPod Serverless
      ↓
Minecraft skin PNG
```

The RunPod API key should live only on your backend/server or temporarily in your local PowerShell environment for private testing.

---

# 22. Fastest setup checklist

```text
[ ] GitHub repository created
[ ] Project files uploaded to repository
[ ] .github/workflows/build-ghcr.yml exists
[ ] GitHub Actions build succeeded
[ ] GHCR package made Public
[ ] RunPod Queue Serverless endpoint created
[ ] Container image = ghcr.io/YOUR_USERNAME/runpod-minecraft-skin-serverless:latest
[ ] RunPod Model = monadical-labs/minecraft-skin-generator-sdxl
[ ] GPU = about 24 GB VRAM or more
[ ] Endpoint deployed
[ ] Text request works in RunPod Requests panel
[ ] RunPod API key created
[ ] runpod-client.ps1 successfully creates skin.png
[ ] Reference image mode works
```

Once those boxes are checked, the service is ready for use without Git, Docker Desktop, Docker Hub, or Python on your laptop.

---

# Official documentation

- GitHub Actions — publishing Docker images: https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images
- GitHub Container Registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- RunPod documentation: https://docs.runpod.io/
