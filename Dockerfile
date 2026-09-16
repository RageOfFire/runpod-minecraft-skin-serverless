FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_ID=monadical-labs/minecraft-skin-generator-sdxl \
    IP_ADAPTER_ID=h94/IP-Adapter \
    IP_ADAPTER_PATH=/opt/ip-adapter

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RunPod currently allows one cached Hugging Face model per endpoint. Keep the
# large Minecraft SDXL checkpoint in RunPod's Model cache, and bake only the
# IP-Adapter Plus + ViT-H image encoder (~3.4 GB total) into this container.
RUN python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="h94/IP-Adapter",
    local_dir="/opt/ip-adapter",
    allow_patterns=[
        "models/image_encoder/config.json",
        "models/image_encoder/model.safetensors",
        "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
    ],
)
PY

COPY handler.py .
COPY test_input.json .

CMD ["python", "-u", "handler.py"]
