import os
from pathlib import Path

import faiss
import numpy as np
import torch
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


BASE_DIR = Path(__file__).resolve().parents[2]

ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN",
    "http://localhost:5173",
)

MODEL_HF_NAME = os.environ.get(
    "MODEL_HF_NAME",
    "patrickjohncyh/fashion-clip",
)

INDEX_PATH = Path(
    os.environ.get(
        "FASHION_INDEX_PATH",
        BASE_DIR / "embeddings" / "fashionclip_image_faiss.index",
    )
)

PRODUCT_IDS_PATH = Path(
    os.environ.get(
        "PRODUCT_IDS_PATH",
        BASE_DIR / "embeddings" / "product_ids.npy",
    )
)

IMAGES_DIR = Path(
    os.environ.get(
        "FASHION_IMAGES_DIR",
        BASE_DIR / "data" / "d2" / "images",
    )
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


app = Flask(__name__)

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                ALLOWED_ORIGIN,
                "http://127.0.0.1:5173",
            ]
        }
    },
)


def success_response(data):
    return jsonify(
        {
            "success": True,
            "data": data,
            "error": None,
        }
    )


def error_response(message, status_code=400):
    return (
        jsonify(
            {
                "success": False,
                "data": None,
                "error": message,
            }
        ),
        status_code,
    )


def load_search_assets():
    missing = []

    if not INDEX_PATH.exists():
        missing.append(str(INDEX_PATH))

    if not PRODUCT_IDS_PATH.exists():
        missing.append(str(PRODUCT_IDS_PATH))

    if missing:
        raise FileNotFoundError(
            "Missing search artifact(s): "
            + ", ".join(missing)
            + ". Configure FASHION_INDEX_PATH and PRODUCT_IDS_PATH if your files are elsewhere."
        )

    index = faiss.read_index(str(INDEX_PATH))
    product_ids = np.load(PRODUCT_IDS_PATH, allow_pickle=True)

    if index.ntotal != len(product_ids):
        raise ValueError(
            f"FAISS index contains {index.ntotal} vectors but "
            f"product_ids.npy contains {len(product_ids)} IDs."
        )

    processor = CLIPProcessor.from_pretrained(MODEL_HF_NAME)
    model = CLIPModel.from_pretrained(MODEL_HF_NAME).to(DEVICE)
    model.eval()

    return index, product_ids, processor, model


try:
    INDEX, PRODUCT_IDS, PROCESSOR, MODEL = load_search_assets()
    STARTUP_ERROR = None
except Exception as exc:
    INDEX = None
    PRODUCT_IDS = None
    PROCESSOR = None
    MODEL = None
    STARTUP_ERROR = str(exc)


def ensure_backend_ready():
    if STARTUP_ERROR:
        return error_response(
            "Backend search assets are not ready. " + STARTUP_ERROR,
            status_code=503,
        )

    return None


def embed_image(image):
    inputs = PROCESSOR(
        images=image,
        return_tensors="pt",
    ).to(DEVICE)

    with torch.no_grad():
        features = MODEL.get_image_features(**inputs)

    vector = features.cpu().numpy().astype("float32")

    faiss.normalize_L2(vector)

    return vector


@app.route("/health", methods=["GET"])
def health():
    return success_response(
        {
            "status": "ok" if STARTUP_ERROR is None else "degraded",
            "device": DEVICE,
            "index_path": str(INDEX_PATH),
            "product_ids_path": str(PRODUCT_IDS_PATH),
            "images_dir": str(IMAGES_DIR),
            "index_vectors": int(INDEX.ntotal) if INDEX is not None else 0,
            "startup_error": STARTUP_ERROR,
        }
    )


@app.route("/dataset2/images/<path:filename>", methods=["GET"])
def dataset2_image(filename):
    if not IMAGES_DIR.exists():
        return error_response(
            f"Image directory does not exist: {IMAGES_DIR}",
            status_code=404,
        )

    return send_from_directory(IMAGES_DIR, filename)


@app.route("/search/image", methods=["POST"])
@app.route("/api/v1/search/image", methods=["POST"])
def search_image():
    ready_error = ensure_backend_ready()

    if ready_error is not None:
        return ready_error

    image_file = request.files.get("image")

    if image_file is None or image_file.filename == "":
        return error_response(
            "Request must include an image file in form field 'image'.",
            status_code=400,
        )

    if not (image_file.mimetype or "").startswith("image/"):
        return error_response(
            "Uploaded file must be an image.",
            status_code=400,
        )

    try:
        top_k = int(request.form.get("top_k", 8))
    except ValueError:
        return error_response(
            "top_k must be an integer.",
            status_code=400,
        )

    top_k = max(1, min(top_k, 50))

    try:
        image = Image.open(image_file.stream).convert("RGB")

        query_vector = embed_image(image)

        scores, indices = INDEX.search(
            query_vector,
            min(top_k, INDEX.ntotal),
        )

        results = []

        for score, index_position in zip(scores[0], indices[0]):
            if index_position < 0:
                continue

            product_id = str(PRODUCT_IDS[index_position]).strip()

            results.append(
                {
                    "product_id": product_id,
                    "image_url": f"/dataset2/images/{product_id}.jpg",
                    "similarity_score": round(float(score), 4),
                }
            )

        return success_response(results)

    except Exception as exc:
        return error_response(
            f"Image search failed: {exc}",
            status_code=500,
        )


@app.route("/search/text", methods=["POST"])
def search_text():
    return error_response(
        "Text search is not implemented in this Week 39 backend yet.",
        status_code=501,
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=True,
    )
