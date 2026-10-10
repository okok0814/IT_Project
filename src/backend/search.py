"""FashionCLIP image embeddings and the existing normalized, flat FAISS index."""
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import numpy as np

from .metadata import ProductMetadata
from .related import COMPLEMENTARY_CATEGORIES, COMPATIBLE_GENDERS


class ProductNotFoundError(LookupError):
    pass


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
        self.metadata_path = config.get("METADATA_PATH") or str(self.image_dir.parent / "styles.csv")
        self.metadata = None
        self.metadata_lock = Lock()

    def search(self, image, top_k):
        import torch

        with self.lock, torch.inference_mode():
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            vector = self.model.get_image_features(**inputs).float().cpu().numpy()
        return self._search_vector(vector, top_k)

    def _embed_text(self, query):
        import torch

        with self.lock, torch.inference_mode():
            inputs = self.processor(text=[query], return_tensors="pt", padding=True,
                                    truncation=True, max_length=self.model.config.text_config.max_position_embeddings).to(self.device)
            return self.model.get_text_features(**inputs).float().cpu().numpy()

    def _ensure_metadata(self):
        # Lazy metadata loading keeps existing image search independent of the CSV.
        with self.metadata_lock:
            if self.metadata is None:
                self.metadata = ProductMetadata(self.metadata_path, self.ids)

    def search_text(self, query, top_k, filters):
        self._ensure_metadata()
        mask = self.metadata.mask(filters)
        if not mask.any():
            return []
        if not query:
            # Filter-only browsing has deterministic ID ordering and no embedding score.
            positions = sorted(np.flatnonzero(mask), key=lambda pos: str(self.ids[pos]))[:top_k]
            return [self._result(pos, None, include_metadata=True) for pos in positions]
        return self._search_vector(self._embed_text(query), top_k, mask)

    def related_products(self, product_id, top_k):
        positions = np.flatnonzero(self.ids == product_id)
        if not len(positions):
            raise ProductNotFoundError(product_id)
        self._ensure_metadata()
        position = int(positions[0])
        categories = COMPLEMENTARY_CATEGORIES.get(self.metadata.values["category"][position], frozenset())
        genders = COMPATIBLE_GENDERS.get(self.metadata.values["gender"][position], frozenset())
        mask = np.isin(self.metadata.values["category"], list(categories))
        mask &= np.isin(self.metadata.values["gender"], list(genders))
        mask[position] = False
        if not mask.any():
            return []
        # The catalog product already has an embedding: no image/text inference.
        vector = self.index.reconstruct(position).reshape(1, -1)
        results = self._search_vector(vector, top_k, mask)
        for result in results:
            result["match_type"] = "complementary"
            result["source_product_id"] = product_id
        return results

    def _result(self, position, score, include_metadata=False):
        result = {"product_id": str(self.ids[position]),
                  "image_url": f"/dataset2/images/{quote(str(self.ids[position]), safe='')}.jpg",
                  "similarity_score": None if score is None else round(float(np.clip(score, -1, 1)), 6)}
        if include_metadata:
            result.update(self.metadata.rows[position])
            result["name"] = result["name"] or f"Product {self.ids[position]}"
            result["match_type"] = "metadata" if score is None else "semantic"
        return result

    def _search_vector(self, vector, top_k, mask=None):
        vector = np.ascontiguousarray(vector, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if vector.shape != (1, self.index.d) or not np.isfinite(vector).all() or norm <= 0:
            raise ValueError("Invalid query embedding")
        vector /= norm
        # Exact ranking over the full catalog when filtering: never filter only an
        # unfiltered top-k shortlist, which can discard all valid matches.
        candidate_k = self.index.ntotal if mask is not None else min(top_k, self.index.ntotal)
        scores, positions = self.index.search(vector, candidate_k)
        results = []
        for score, pos in zip(scores[0], positions[0]):
            if pos >= 0 and (mask is None or mask[pos]):
                results.append(self._result(pos, score, include_metadata=mask is not None))
                if len(results) == top_k:
                    break
        return results
