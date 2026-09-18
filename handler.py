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

# Auto sprite-sheet detection is intentionally conservative. A false negative can
# be overridden with reference_mode="sprite_sheet" + sprite_rows/sprite_columns,
# while a false positive would feed the wrong crop to IP-Adapter.
SPRITE_MIN_CELL = int(os.getenv("SPRITE_MIN_CELL", "16"))
SPRITE_MAX_CELL = int(os.getenv("SPRITE_MAX_CELL", "256"))
SPRITE_MIN_CELLS = int(os.getenv("SPRITE_MIN_CELLS", "6"))
SPRITE_MAX_CELLS = int(os.getenv("SPRITE_MAX_CELLS", "64"))

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


def _optional_int(data: dict, key: str, minimum: int, maximum: int) -> Optional[int]:
    value = data.get(key)
    if value is None or value == "":
        return None
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _decode_reference_image(encoded: Optional[str]) -> Optional[Image.Image]:
    """Decode an optional PNG/JPEG/WebP/GIF first-frame image from Base64/data URI.

    Important: this returns the source image before any IP-Adapter preprocessing.
    The raw source is never passed directly to IP-Adapter; `_prepare_reference_image`
    always normalizes it and crops sprite sheets first.
    """
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
            # Preserve alpha for sprite-sheet detection and only composite later.
            image = ImageOps.exif_transpose(opened).convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("reference image must be a valid PNG, JPEG, WebP, or GIF") from exc

    return image


def _visible_fraction(cell: Image.Image) -> float:
    alpha = np.asarray(cell.getchannel("A"), dtype=np.uint8)
    return float(np.count_nonzero(alpha > 8) / alpha.size)


def _grid_metadata(image: Image.Image, rows: int, columns: int) -> Optional[dict]:
    width, height = image.size
    if rows < 1 or columns < 1:
        return None
    if width % columns != 0 or height % rows != 0:
        return None

    cell_width = width // columns
    cell_height = height // rows
    if cell_width < SPRITE_MIN_CELL or cell_height < SPRITE_MIN_CELL:
        return None
    if cell_width > SPRITE_MAX_CELL or cell_height > SPRITE_MAX_CELL:
        return None

    fractions = []
    for row in range(rows):
        for column in range(columns):
            x1 = column * cell_width
            y1 = row * cell_height
            fractions.append(
                _visible_fraction(image.crop((x1, y1, x1 + cell_width, y1 + cell_height)))
            )

    occupied = [fraction for fraction in fractions if fraction >= 0.03]
    total_cells = rows * columns
    occupied_ratio = len(occupied) / total_cells
    median_visible = float(np.median(occupied)) if occupied else 0.0
    variation = (
        float(np.std(occupied) / max(np.mean(occupied), 1e-6)) if occupied else 999.0
    )

    return {
        "rows": rows,
        "columns": columns,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "total_cells": total_cells,
        "occupied_cells": len(occupied),
        "occupied_ratio": occupied_ratio,
        "median_visible_fraction": median_visible,
        "visible_variation": variation,
    }


def _detect_sprite_grid(image: Image.Image) -> Optional[dict]:
    """Conservatively detect a transparent, repeated-frame sprite sheet.

    The Sraosha-style 3x4 / 48x48 RPG sheet is handled explicitly. For other
    sheets, the detector looks for the largest square-cell grid with many similarly
    occupied transparent frames. Normal illustrations should normally fall through
    to single-image mode.
    """
    rgba = image.convert("RGBA")
    width, height = rgba.size
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.uint8)
    transparent_fraction = float(np.count_nonzero(alpha < 250) / alpha.size)

    # JPEG and opaque art should not be guessed as a sprite sheet in auto mode.
    if transparent_fraction < 0.05:
        return None

    # Common RPG-style character sheet: 3 animation columns x 4 direction rows.
    if width % 3 == 0 and height % 4 == 0 and width // 3 == height // 4:
        meta = _grid_metadata(rgba, 4, 3)
        if meta and meta["occupied_ratio"] >= 0.75 and meta["median_visible_fraction"] >= 0.08:
            meta["layout"] = "rpg_3x4"
            meta["confidence"] = "high"
            return meta

    # Generic square-cell sheets. Prefer the largest plausible cell size so a
    # 48x48 sheet is not misread as a 24x24 or 16x16 grid.
    candidates = []
    max_cell = min(width, height, SPRITE_MAX_CELL)
    for cell in range(max_cell, SPRITE_MIN_CELL - 1, -1):
        if width % cell != 0 or height % cell != 0:
            continue
        columns = width // cell
        rows = height // cell
        total = rows * columns
        if columns < 2 or rows < 2:
            continue
        if not SPRITE_MIN_CELLS <= total <= SPRITE_MAX_CELLS:
            continue

        meta = _grid_metadata(rgba, rows, columns)
        if not meta:
            continue
        if meta["occupied_ratio"] < 0.80:
            continue
        if meta["median_visible_fraction"] < 0.06:
            continue
        if meta["visible_variation"] > 0.55:
            continue

        meta["layout"] = "grid"
        meta["confidence"] = "medium"
        candidates.append(meta)

    return candidates[0] if candidates else None


def _rgba_on_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    white.alpha_composite(rgba)
    return white.convert("RGB")


def _square_for_ip_adapter(image: Image.Image, pixel_art: bool = False) -> Image.Image:
    canvas = max(224, min(REFERENCE_CANVAS, 1536))
    rgb = _rgba_on_white(image)
    method = Image.Resampling.NEAREST if pixel_art else Image.Resampling.LANCZOS
    return ImageOps.pad(
        rgb,
        (canvas, canvas),
        method=method,
        color=(255, 255, 255),
        centering=(0.5, 0.5),
    )


def _prepare_reference_image(
    source: Image.Image,
    reference_mode: str = "auto",
    sprite_rows: Optional[int] = None,
    sprite_columns: Optional[int] = None,
    sprite_front_row: Optional[int] = None,
    sprite_front_column: Optional[int] = None,
) -> tuple[Image.Image, dict]:
    """Preprocess a source reference before it reaches IP-Adapter.

    - auto: detect transparent sprite sheets; otherwise use a normalized single image.
    - single: never split the source.
    - sprite_sheet: require/detect a grid, then send only one selected frame.

    For 3x4 RPG sheets, the default frame is row 0 / column 1: the center idle
    frame of the first direction row, which matches the supplied Sraosha sheet.
    """
    mode = str(reference_mode or "auto").lower().strip()
    aliases = {
        "image": "single",
        "single_image": "single",
        "sprite": "sprite_sheet",
        "spritesheet": "sprite_sheet",
    }
    mode = aliases.get(mode, mode)
    if mode not in {"auto", "single", "sprite_sheet"}:
        raise ValueError("reference_mode must be 'auto', 'single', or 'sprite_sheet'")

    source = source.convert("RGBA")
    width, height = source.size

    grid = None
    if sprite_rows is not None or sprite_columns is not None:
        if sprite_rows is None or sprite_columns is None:
            raise ValueError("sprite_rows and sprite_columns must be provided together")
        grid = _grid_metadata(source, sprite_rows, sprite_columns)
        if grid is None:
            raise ValueError(
                "sprite_rows/sprite_columns do not evenly divide the reference image "
                "or produce a supported cell size"
            )
        grid["layout"] = "manual_grid"
        grid["confidence"] = "manual"
    elif mode != "single":
        grid = _detect_sprite_grid(source)

    use_sprite = grid is not None and mode != "single"
    if mode == "sprite_sheet" and grid is None:
        raise ValueError(
            "could not detect a sprite-sheet grid; provide sprite_rows and sprite_columns"
        )

    if not use_sprite:
        prepared = _square_for_ip_adapter(source, pixel_art=False)
        return prepared, {
            "mode": "single_image",
            "input_width": width,
            "input_height": height,
            "ip_adapter_width": prepared.width,
            "ip_adapter_height": prepared.height,
        }

    rows = int(grid["rows"])
    columns = int(grid["columns"])
    cell_width = int(grid["cell_width"])
    cell_height = int(grid["cell_height"])

    if sprite_front_row is None:
        # In common 3x4 RPG sheets, row 0 is the front/down-facing direction.
        selected_row = 0
    else:
        selected_row = sprite_front_row

    if sprite_front_column is None:
        # Center animation frame is normally the neutral/idle pose.
        selected_column = columns // 2
    else:
        selected_column = sprite_front_column

    if not 0 <= selected_row < rows:
        raise ValueError(f"sprite_front_row must be between 0 and {rows - 1}")
    if not 0 <= selected_column < columns:
        raise ValueError(f"sprite_front_column must be between 0 and {columns - 1}")

    x1 = selected_column * cell_width
    y1 = selected_row * cell_height
    frame = source.crop((x1, y1, x1 + cell_width, y1 + cell_height))
    prepared = _square_for_ip_adapter(frame, pixel_art=True)

    return prepared, {
        "mode": "sprite_sheet",
        "input_width": width,
        "input_height": height,
        "layout": grid.get("layout", "grid"),
        "confidence": grid.get("confidence", "unknown"),
        "rows": rows,
        "columns": columns,
        "cell_width": cell_width,
        "cell_height": cell_height,
        "selected_row": selected_row,
        "selected_column": selected_column,
        "selected_frame_index": selected_row * columns + selected_column,
        "ip_adapter_width": prepared.width,
        "ip_adapter_height": prepared.height,
    }


def handler(event: dict) -> dict:
    data = event.get("input") or {}

    reference_source = _decode_reference_image(data.get("reference_image_base64"))
    prompt = str(data.get("prompt", "")).strip()

    if not prompt and reference_source is None:
        raise ValueError("provide input.prompt, input.reference_image_base64, or both")
    if len(prompt) > 600:
        raise ValueError("input.prompt must be 600 characters or fewer")

    reference_processing = None
    reference_image = None
    if reference_source is not None:
        reference_mode = str(data.get("reference_mode", "auto"))
        sprite_rows = _optional_int(data, "sprite_rows", 1, 64)
        sprite_columns = _optional_int(data, "sprite_columns", 1, 64)
        sprite_front_row = _optional_int(data, "sprite_front_row", 0, 63)
        sprite_front_column = _optional_int(data, "sprite_front_column", 0, 63)
        reference_image, reference_processing = _prepare_reference_image(
            reference_source,
            reference_mode=reference_mode,
            sprite_rows=sprite_rows,
            sprite_columns=sprite_columns,
            sprite_front_row=sprite_front_row,
            sprite_front_column=sprite_front_column,
        )

    if not prompt:
        if reference_processing and reference_processing["mode"] == "sprite_sheet":
            prompt = (
                "Minecraft character skin matching the selected front-facing sprite frame, "
                "faithful outfit, colors, hair, face, and accessories"
            )
        else:
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

    # The IP-Adapter never receives the raw uploaded source. It receives either:
    # 1) the selected sprite frame, normalized to a square; or
    # 2) a normalized single-image reference.
    # For text-only requests, feed a neutral image with scale 0 so the same
    # pipeline remains valid.
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

    output = {
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
    if reference_processing is not None:
        output["reference_processing"] = reference_processing

    return output


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})