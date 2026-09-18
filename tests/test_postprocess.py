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

from PIL import Image, ImageDraw


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


def test_decode_reference_image_preserves_source_for_preprocessing():
    source = Image.new("RGBA", (80, 120), (12, 34, 56, 200))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    decoded = mod._decode_reference_image(encoded)
    assert decoded.mode == "RGBA"
    assert decoded.size == (80, 120)

    decoded_data_uri = mod._decode_reference_image(f"data:image/png;base64,{encoded}")
    assert decoded_data_uri.size == (80, 120)


def test_single_reference_is_normalized_before_ip_adapter():
    source = Image.new("RGBA", (80, 120), (12, 34, 56, 255))
    prepared, metadata = mod._prepare_reference_image(source, reference_mode="single")
    assert prepared.mode == "RGB"
    assert prepared.size == (1024, 1024)
    assert metadata["mode"] == "single_image"


def _synthetic_rpg_3x4_sheet():
    sheet = Image.new("RGBA", (144, 192), (0, 0, 0, 0))
    colors = []
    for row in range(4):
        for column in range(3):
            color = (
                20 + row * 45,
                30 + column * 70,
                40 + (row * 3 + column) * 10,
                255,
            )
            colors.append(color)
            draw = ImageDraw.Draw(sheet)
            x1 = column * 48 + 5
            y1 = row * 48 + 4
            draw.rectangle((x1, y1, x1 + 37, y1 + 39), fill=color)
    return sheet, colors


def test_detects_sraosha_style_3x4_sprite_sheet():
    sheet, _colors = _synthetic_rpg_3x4_sheet()
    grid = mod._detect_sprite_grid(sheet)
    assert grid is not None
    assert grid["layout"] == "rpg_3x4"
    assert grid["rows"] == 4
    assert grid["columns"] == 3
    assert grid["cell_width"] == 48
    assert grid["cell_height"] == 48


def test_sprite_sheet_sends_only_front_idle_frame_to_ip_adapter():
    sheet, colors = _synthetic_rpg_3x4_sheet()
    prepared, metadata = mod._prepare_reference_image(sheet, reference_mode="auto")

    assert metadata["mode"] == "sprite_sheet"
    assert metadata["selected_row"] == 0
    assert metadata["selected_column"] == 1
    assert metadata["selected_frame_index"] == 1
    assert prepared.size == (1024, 1024)

    # Center pixel comes from row 0 / column 1 rather than another sprite frame.
    expected = colors[1][:3]
    assert prepared.getpixel((512, 512)) == expected


def test_manual_sprite_frame_override():
    sheet, colors = _synthetic_rpg_3x4_sheet()
    prepared, metadata = mod._prepare_reference_image(
        sheet,
        reference_mode="sprite_sheet",
        sprite_rows=4,
        sprite_columns=3,
        sprite_front_row=3,
        sprite_front_column=2,
    )
    assert metadata["selected_row"] == 3
    assert metadata["selected_column"] == 2
    assert prepared.getpixel((512, 512)) == colors[11][:3]


def test_decode_reference_image_rejects_bad_base64():
    try:
        mod._decode_reference_image("this-is-not-base64!!")
    except ValueError as exc:
        assert "Base64" in str(exc)
    else:
        raise AssertionError("invalid Base64 should be rejected")


def test_handler_never_passes_whole_sprite_sheet_to_ip_adapter():
    from contextlib import nullcontext

    sheet, colors = _synthetic_rpg_3x4_sheet()
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    captured = {}

    class FakeGenerator:
        def __init__(self, device=None):
            self.device = device

        def manual_seed(self, seed):
            return self

    class FakePipe:
        def set_ip_adapter_scale(self, scale):
            captured["scale"] = scale

        def __call__(self, **kwargs):
            captured["ip_image"] = kwargs["ip_adapter_image"]
            return types.SimpleNamespace(
                images=[Image.new("RGB", (768, 768), (80, 80, 80))]
            )

    mod.get_pipeline = lambda: FakePipe()
    mod.torch = types.SimpleNamespace(
        Generator=FakeGenerator,
        inference_mode=lambda: nullcontext(),
    )

    output = mod.handler(
        {
            "input": {
                "reference_image_base64": encoded,
                "reference_mode": "auto",
                "reference_strength": 0.7,
                "seed": 123,
            }
        }
    )

    ip_image = captured["ip_image"]
    assert ip_image.size == (1024, 1024)
    assert ip_image.size != sheet.size
    assert ip_image.getpixel((512, 512)) == colors[1][:3]
    assert output["reference_processing"]["mode"] == "sprite_sheet"
    assert output["reference_processing"]["selected_frame_index"] == 1