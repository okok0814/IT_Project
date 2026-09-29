"""One-time download. Serving requests never downloads model files."""
from huggingface_hub import snapshot_download

from src.backend.app import ROOT


if __name__ == "__main__":
    print(snapshot_download(
        "patrickjohncyh/fashion-clip",
        cache_dir=str(ROOT / ".cache/huggingface"),
        allow_patterns=["*.json", "*.txt", "*.safetensors", "pytorch_model.bin"],
    ))
