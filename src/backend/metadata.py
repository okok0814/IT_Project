"""Align Dataset 2 attributes to FAISS positions by product ID, never CSV row order."""
import csv
from pathlib import Path

import numpy as np

FILTER_FIELDS = ("gender", "category", "color")
ALIASES = {"color": {"off-white": "Off White", "navy": "Navy Blue"}}


def normalize_value(value, field):
    value = " ".join(str(value or "").split())
    return ALIASES.get(field, {}).get(value.casefold(), value).casefold()


class ProductMetadata:
    def __init__(self, path, product_ids):
        self.path = Path(path)
        self.skipped_rows = 0
        with self.path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            fields = set(reader.fieldnames or [])
            if {"product_id", "gender", "category", "color"} <= fields:
                mapping = {key: key for key in ["product_id", *FILTER_FIELDS, "usage", "master_category", "sub_category", "name"]}
            elif {"id", "gender", "articleType", "baseColour"} <= fields:
                mapping = {"product_id": "id", "gender": "gender", "category": "articleType", "color": "baseColour",
                           "usage": "usage", "master_category": "masterCategory", "sub_category": "subCategory", "name": "productDisplayName"}
            else:
                raise ValueError("Metadata CSV must contain product_id/gender/category/color or Dataset 2 styles.csv columns")
            by_id = {}
            for row in reader:
                # Match the existing embedding pipeline's on_bad_lines='skip' policy.
                if None in row or any(row.get(key) is None for key in reader.fieldnames):
                    self.skipped_rows += 1
                    continue
                pid = row[mapping["product_id"]].strip()
                if not pid:
                    raise ValueError("Metadata contains an empty product ID")
                if pid in by_id:
                    raise ValueError(f"Duplicate metadata product ID: {pid}")
                meta = {}
                for key, column in mapping.items():
                    if key == "product_id":
                        continue
                    raw = " ".join((row.get(column) or "").split())
                    meta[key] = raw if key == "name" else normalize_value(raw or "Unknown", key).title()
                by_id[pid] = meta
        missing = [pid for pid in product_ids if str(pid) not in by_id]
        if missing:
            raise ValueError(f"Metadata is missing {len(missing)} indexed product IDs")
        self.rows = [by_id[str(pid)] for pid in product_ids]
        self.values = {key: np.array([normalize_value(row[key], key) for row in self.rows]) for key in FILTER_FIELDS}

    def mask(self, filters):
        result = np.ones(len(self.rows), dtype=bool)
        for field, value in filters.items():
            result &= self.values[field] == normalize_value(value, field)
        return result
