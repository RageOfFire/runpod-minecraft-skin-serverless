import base64
import binascii
import hashlib
import io
import os
import secrets
from pathlib import Path
from threading import Lock
from typing import Optional

import numpy as np
import runpod
import torch
from diffusers import StableDiffusionXLPipeline
from PIL import Image, ImageOps, UnidentifiedImageError
from transformers import CLIPVisionModelWithProjection

MODEL_ID = os.getenv("MODEL_ID", "monadical-labs/minecraft-skin-generator-sdxl")
IP_ADAPTER_ID = os.getenv("IP_ADAPTER_ID", "h94/IP-Adapter")
IP_ADAPTER_PATH = os.getenv("IP_ADAPTER_PATH", "/opt/ip-adapter")
IP_ADAPTER_WEIGHT = os.getenv(
    "IP_ADAPTER_WEIGHT", "ip-adapter-plus_sdxl_vit-h.safetensors"
)
IMAGE_WIDTH = 768
IMAGE_HEIGHT = 768
MAX_REFERENCE_BYTES = int(os.getenv("MAX_REFERENCE_BYTES", str(6 * 1024 * 1024)))
MAX_REFERENCE_PIXELS = int(os.getenv("MAX_REFERENCE_PIXELS", str(20_000_000)))
REFERENCE_CANVAS = int(os.getenv("REFERENCE_CANVAS", "1024"))

# Empty UV rectangles used by the original model's generated legacy skin sheet.
BACKGROUND_REGIONS = [
    (32, 0, 40, 8),
    (56, 0, 64, 8),
]

# Renderable head-overlay faces. Pixels close to the learned background color
# are converted to alpha=0 so hair/helmet transparency works correctly.
HEAD_OVERLAY_REGIONS = [
    (40, 0, 48, 8),
    (48, 0, 56, 8),
    (32, 8, 40, 16),
    (40, 8, 48, 16),
    (48, 8, 56, 16),
    (56, 8, 64, 16),
]

_pipeline: Optional[StableDiffusionXLPipeline] = None
_pipeline_lock = Lock()
_inference_lock = Lock()
_blank_reference = Image.new("RGB", (224, 224), (127, 127, 127))


def _resolve_runpod_cached_model(model_id: str) -> str:
    """Return the local RunPod cached-model snapshot when available."""
    model_dir = (
        Path("/runpod-volume/huggingface-cache/hub")
        / f"models--{model_id.replace('/', '--')}"
    )

    main_ref = model_dir / "refs" / "main"
    snapshots = model_dir / "snapshots"

    try:
        if main_ref.is_file():
            revision = main_ref.read_text(encoding="utf-8").strip()
            candidate = snapshots / revision
            if candidate.is_dir():
                return str(candidate)

        if snapshots.is_dir():
            candidates = [p for p in snapshots.iterdir() if p.is_dir()]
            if candidates:
                return str(max(candidates, key=lambda p: p.stat().st_mtime))
    except OSError:
        pass

    # Fallback: Diffusers/Hugging Face downloads normally. For production on
    # RunPod, configure MODEL_ID in the endpoint's Model field to avoid this.
    return model_id


def _ip_adapter_source() -> str:
    local_path = Path(IP_ADAPTER_PATH)
    if local_path.is_dir():
        return str(local_path)
    return IP_ADAPTER_ID


def get_pipeline() -> StableDiffusionXLPipeline:
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA GPU is required. Deploy this worker on a RunPod Serverless GPU endpoint."
            )

        source = _resolve_runpod_cached_model(MODEL_ID)
        adapter_source = _ip_adapter_source()
        print(f"Loading Minecraft skin model from: {source}")
        print(f"Loading IP-Adapter reference-image model from: {adapter_source}")

        image_encoder = CLIPVisionModelWithProjection.from_pretrained(
            adapter_source,
            subfolder="models/image_encoder",
            torch_dtype=torch.float16,
            use_safetensors=True,
        )

        pipe = StableDiffusionXLPipeline.from_pretrained(
            source,
            image_encoder=image_encoder,
            torch_dtype=torch.float16,
            use_safetensors=True,
        )
        pipe.load_ip_adapter(
            adapter_source,
            subfolder="sdxl_models",
            weight_name=IP_ADAPTER_WEIGHT,
        )
        pipe.set_ip_adapter_scale(0.0)
        pipe.set_progress_bar_config(disable=True)

        # Diffusers has exposed VAE slicing on different objects across versions.
        # Support both APIs and simply skip the optimization if neither exists.
        if hasattr(pipe, "enable_vae_slicing"):
            pipe.enable_vae_slicing()
        elif getattr(pipe, "vae", None) is not None and hasattr(pipe.vae, "enable_slicing"):
            pipe.vae.enable_slicing()

        pipe.to("cuda")

        # Ampere+ GPUs benefit from TF32 for some matmuls without materially
        # changing this use case's output quality.
        if hasattr(torch.backends.cuda.matmul, "allow_tf32"):
            torch.backends.cuda.matmul.allow_tf32 = True

        _pipeline = pipe
        print("Minecraft skin + reference-image pipeline loaded.")
        return _pipeline


def _background_color(legacy_rgb: Image.Image) -> np.ndarray:
    samples = []
    for box in BACKGROUND_REGIONS:
        crop = np.asarray(legacy_rgb.crop(box).convert("RGB"), dtype=np.float32)
        samples.append(crop.reshape(-1, 3))
    return np.concatenate(samples, axis=0).mean(axis=0)


def _restore_head_overlay_transparency(
    legacy_rgb: Image.Image, cutoff: float = 50.0
) -> Image.Image:
    background = _background_color(legacy_rgb)
    rgba = legacy_rgb.convert("RGBA")
    data = np.array(rgba, dtype=np.uint8)

    for x1, y1, x2, y2 in HEAD_OVERLAY_REGIONS:
        rgb = data[y1:y2, x1:x2, :3].astype(np.float32)
        distance = np.linalg.norm(rgb - background, axis=2)
        alpha = data[y1:y2, x1:x2, 3]
        alpha[distance <= cutoff] = 0
        data[y1:y2, x1:x2, 3] = alpha

    # These two rectangles are not mapped onto the player model at all.
    for x1, y1, x2, y2 in BACKGROUND_REGIONS:
        data[y1:y2, x1:x2, 3] = 0

    return Image.fromarray(data, mode="RGBA")


def extract_legacy_skin(generated: Image.Image, cutoff: float = 50.0) -> Image.Image:
    """Convert the model's 768x768 output into a usable legacy 64x32 skin."""
    generated = generated.convert("RGB")
    top_half = generated.crop((0, 0, IMAGE_WIDTH, IMAGE_HEIGHT // 2))
    legacy = top_half.resize((64, 32), Image.Resampling.NEAREST)
    return _restore_head_overlay_transparency(legacy, cutoff=cutoff)


def legacy_to_modern(legacy: Image.Image) -> Image.Image:
    """Convert a classic 64x32 skin to modern 64x64 classic/Steve geometry."""
    if legacy.size != (64, 32):
        raise ValueError("legacy skin must be exactly 64x32")

    src = legacy.convert("RGBA")
    out = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    out.alpha_composite(src, (0, 0))

    # Mirror legacy right-leg faces into modern left-leg UV coordinates.
    leg_map = [
        ((4, 16, 8, 20), (20, 48)),
        ((8, 16, 12, 20), (24, 48)),
        ((8, 20, 12, 32), (16, 52)),
        ((4, 20, 8, 32), (20, 52)),
        ((0, 20, 4, 32), (24, 52)),
        ((12, 20, 16, 32), (28, 52)),
    ]

    # Mirror legacy right-arm faces into modern left-arm UV coordinates.
    arm_map = [
        ((44, 16, 48, 20), (36, 48)),
        ((48, 16, 52, 20), (40, 48)),
        ((48, 20, 52, 32), (32, 52)),
        ((44, 20, 48, 32), (36, 52)),
        ((40, 20, 44, 32), (40, 52)),
        ((52, 20, 56, 32), (44, 52)),
    ]

    for box, destination in leg_map + arm_map:
        piece = src.crop(box).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        out.alpha_composite(piece, destination)

    return out


def _encode_png(image: Image.Image) -> tuple[str, int, str]:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    raw = buffer.getvalue()
    return (
        base64.b64encode(raw).decode("ascii"),
        len(raw),
        hashlib.sha256(raw).hexdigest(),
    )


def _int_value(data: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    value = int(data.get(key, default))
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _float_value(
    data: dict, key: str, default: float, minimum: float, maximum: float
) -> float:
    value = float(data.get(key, default))
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _decode_reference_image(encoded: Optional[str]) -> Optional[Image.Image]:
    """Decode an optional PNG/JPEG/WebP/GIF first-frame image from Base64/data URI."""
    if encoded is None:
        return None

    encoded = str(encoded).strip()
    if not encoded:
        return None

    if encoded.startswith("data:"):
        try:
            _header, encoded = encoded.split(",", 1)
        except ValueError as exc:
            raise ValueError("reference_image_base64 contains an invalid data URI") from exc

    # Base64 is ~4/3 the raw size. Check before decoding to avoid oversized allocations.
    max_encoded_chars = ((MAX_REFERENCE_BYTES + 2) // 3) * 4 + 16
    if len(encoded) > max_encoded_chars:
        raise ValueError(
            f"reference image is too large; decoded image must be <= {MAX_REFERENCE_BYTES} bytes"
        )

    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("reference_image_base64 is not valid Base64") from exc

    if len(raw) > MAX_REFERENCE_BYTES:
        raise ValueError(
            f"reference image is too large; maximum decoded size is {MAX_REFERENCE_BYTES} bytes"
        )

    try:
        with Image.open(io.BytesIO(raw)) as opened:
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > MAX_REFERENCE_PIXELS:
                raise ValueError(
                    f"reference image dimensions are too large; max pixels is {MAX_REFERENCE_PIXELS}"
                )
            opened.seek(0)
            opened.load()
            image = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("reference image must be a valid PNG, JPEG, WebP, or GIF") from exc

    # Preserve the full character instead of letting CLIP center-crop a tall/wide image.
    canvas = max(224, min(REFERENCE_CANVAS, 1536))
    return ImageOps.pad(
        image,
        (canvas, canvas),
        method=Image.Resampling.LANCZOS,
        color=(255, 255, 255),
        centering=(0.5, 0.5),
    )


def handler(event: dict) -> dict:
    data = event.get("input") or {}

    reference_image = _decode_reference_image(data.get("reference_image_base64"))
    prompt = str(data.get("prompt", "")).strip()

    if not prompt and reference_image is None:
        raise ValueError("provide input.prompt, input.reference_image_base64, or both")
    if len(prompt) > 600:
        raise ValueError("input.prompt must be 600 characters or fewer")

    if not prompt:
        prompt = (
            "Minecraft character skin matching the reference character, faithful outfit, "
            "colors, hair, face, and accessories"
        )
        source_mode = "image"
    elif reference_image is not None:
        source_mode = "text+image"
    else:
        source_mode = "text"

    steps = _int_value(data, "steps", 35, 10, 60)
    guidance = _float_value(data, "guidance_scale", 7.5, 1.0, 15.0)
    cutoff = _float_value(data, "transparency_cutoff", 50.0, 0.0, 200.0)
    reference_strength = _float_value(data, "reference_strength", 0.70, 0.0, 1.25)

    requested_seed = data.get("seed")
    seed = int(requested_seed) if requested_seed is not None else secrets.randbelow(2**31)
    if not 0 <= seed <= 2**31 - 1:
        raise ValueError("seed must be between 0 and 2147483647")

    output_format = str(data.get("format", "modern")).lower().strip()
    if output_format not in {"modern", "legacy"}:
        raise ValueError("format must be 'modern' or 'legacy'")

    negative_prompt = data.get("negative_prompt")
    if negative_prompt is not None:
        negative_prompt = str(negative_prompt)[:600]

    pipe = get_pipeline()
    generator = torch.Generator(device="cuda").manual_seed(seed)

    # The IP-Adapter is installed on the pipeline once. For text-only requests,
    # feed a neutral image with scale 0 so the same pipeline remains valid.
    ip_image = reference_image if reference_image is not None else _blank_reference
    ip_scale = reference_strength if reference_image is not None else 0.0

    # Diffusers pipelines and adapter scales are mutable and not safe for
    # simultaneous calls on one pipeline object. RunPod scales via more workers.
    with _inference_lock, torch.inference_mode():
        pipe.set_ip_adapter_scale(ip_scale)
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            ip_adapter_image=ip_image,
            num_inference_steps=steps,
            guidance_scale=guidance,
            height=IMAGE_HEIGHT,
            width=IMAGE_WIDTH,
            num_images_per_prompt=1,
            generator=generator,
        )

    legacy = extract_legacy_skin(result.images[0], cutoff=cutoff)
    skin = legacy_to_modern(legacy) if output_format == "modern" else legacy
    png_b64, png_bytes, sha256 = _encode_png(skin)

    return {
        "image_base64": png_b64,
        "mime_type": "image/png",
        "width": skin.width,
        "height": skin.height,
        "format": output_format,
        "player_model": "classic",
        "source_mode": source_mode,
        "reference_strength": ip_scale,
        "seed": seed,
        "steps": steps,
        "guidance_scale": guidance,
        "bytes": png_bytes,
        "sha256": sha256,
        "model": MODEL_ID,
        "image_adapter": f"{IP_ADAPTER_ID}/{IP_ADAPTER_WEIGHT}",
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
