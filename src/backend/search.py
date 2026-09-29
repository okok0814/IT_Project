"""FashionCLIP image embeddings and the existing normalized, flat FAISS index."""
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import numpy as np


class FashionSearch:
    def __init__(self, config):
        import faiss
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.image_dir = Path(config["IMAGE_DIR"])
        if not self.image_dir.is_dir():
            raise FileNotFoundError(f"Set IMAGE_DIR to the catalog image folder: {self.image_dir}")
        self.index = faiss.read_index(str(config["INDEX_PATH"]))
        # Existing embedding script saved an object array; only load trusted local artifacts.
        self.ids = np.load(config["PRODUCT_IDS_PATH"], allow_pickle=True).astype(str)
        if self.ids.ndim != 1 or self.index.ntotal != len(self.ids) or not len(self.ids):
            raise ValueError("FAISS index and product IDs must have equal, nonzero row counts")
        if not isinstance(self.index, faiss.IndexFlatIP) or self.index.d != 512:
            raise ValueError("Expected a 512-dimensional FashionCLIP IndexFlatIP")
        norms = np.linalg.norm(self.index.reconstruct_n(0, self.index.ntotal), axis=1)
        if not np.allclose(norms, 1, atol=1e-3):
            raise ValueError("Catalog vectors must be L2 normalized for cosine similarity")
        if len(set(self.ids)) != len(self.ids):
            raise ValueError("Duplicate product IDs")
        if any(not (self.image_dir / f"{pid}.jpg").is_file() for pid in self.ids):
            raise FileNotFoundError("IMAGE_DIR must contain a JPG for every indexed product ID")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        kwargs = {"cache_dir": config["MODEL_CACHE"], "local_files_only": True}
        self.processor = CLIPProcessor.from_pretrained(config["MODEL_PATH"], use_fast=False, **kwargs)
        self.model = CLIPModel.from_pretrained(config["MODEL_PATH"], **kwargs).to(self.device).eval()
        self.lock = Lock()

    def search(self, image, top_k):
        import torch

        with self.lock, torch.inference_mode():
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            vector = self.model.get_image_features(**inputs).float().cpu().numpy()
        vector = np.ascontiguousarray(vector, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if vector.shape != (1, self.index.d) or not np.isfinite(vector).all() or norm <= 0:
            raise ValueError("Invalid query embedding")
        vector /= norm
        scores, positions = self.index.search(vector, min(top_k, self.index.ntotal))
        return [
            {"product_id": str(self.ids[pos]),
             "image_url": f"/dataset2/images/{quote(str(self.ids[pos]), safe='')}.jpg",
             "similarity_score": round(float(np.clip(score, -1, 1)), 6)}
            for score, pos in zip(scores[0], positions[0]) if pos >= 0
        ]
