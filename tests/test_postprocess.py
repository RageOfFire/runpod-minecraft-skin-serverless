import base64
import importlib.util
import io
import sys
import types
from pathlib import Path

# Stub heavy runtime dependencies so pure image helpers can be tested here.
runpod = types.SimpleNamespace(serverless=types.SimpleNamespace(start=lambda *_a, **_k: None))
sys.modules.setdefault("runpod", runpod)
sys.modules.setdefault("torch", types.SimpleNamespace())


class DummyPipeline:
    pass


class DummyEncoder:
    pass


sys.modules.setdefault(
    "diffusers", types.SimpleNamespace(StableDiffusionXLPipeline=DummyPipeline)
)
sys.modules.setdefault(
    "transformers", types.SimpleNamespace(CLIPVisionModelWithProjection=DummyEncoder)
)

module_path = Path(__file__).resolve().parents[1] / "handler.py"
spec = importlib.util.spec_from_file_location("skin_handler", module_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from PIL import Image


def test_legacy_to_modern_size_and_alpha():
    legacy = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
    legacy.putpixel((4, 16), (255, 0, 0, 255))
    modern = mod.legacy_to_modern(legacy)
    assert modern.size == (64, 64)
    assert modern.mode == "RGBA"
    assert modern.getpixel((23, 48))[3] == 255


def test_extract_legacy_skin_size():
    generated = Image.new("RGB", (768, 768), (10, 20, 30))
    legacy = mod.extract_legacy_skin(generated)
    assert legacy.size == (64, 32)
    assert legacy.mode == "RGBA"


def test_decode_reference_image_from_base64_and_data_uri():
    source = Image.new("RGB", (80, 120), (12, 34, 56))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    decoded = mod._decode_reference_image(encoded)
    assert decoded.mode == "RGB"
    assert decoded.size == (1024, 1024)

    decoded_data_uri = mod._decode_reference_image(f"data:image/png;base64,{encoded}")
    assert decoded_data_uri.size == (1024, 1024)


def test_decode_reference_image_rejects_bad_base64():
    try:
        mod._decode_reference_image("this-is-not-base64!!")
    except ValueError as exc:
        assert "Base64" in str(exc)
    else:
        raise AssertionError("invalid Base64 should be rejected")
