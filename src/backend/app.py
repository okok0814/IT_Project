import os

from flask import Flask, jsonify
from flask_cors import CORS

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")

app = Flask(__name__)
CORS(app, origins=[ALLOWED_ORIGIN])


def success_response(data):
    return jsonify({"success": True, "data": data, "error": None})


def error_response(message, status_code=400):
    return jsonify({"success": False, "data": None, "error": message}), status_code


@app.route("/health", methods=["GET"])
def health():
    return success_response({"status": "ok"})


@app.route("/search/image", methods=["POST"])
def search_image():
    # nhận file ảnh upload, encode bằng FashionCLIP, truy vấn FAISS index, trả về top-k sản phẩm.
    return error_response("Chua trien khai.", status_code=501)


@app.route("/search/text", methods=["POST"])
def search_text():
    # nhận câu truy vấn văn bản, encode, truy vấn FAISS index.
    return error_response("Chua trien khai.", status_code=501)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
