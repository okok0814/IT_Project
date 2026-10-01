# Fashion Search System

A fashion product retrieval system built with **React + Vite** on the frontend and **Flask + FashionCLIP + FAISS** on the backend.

The project supports image-based fashion search and provides a text-search interface with metadata filters for **gender, category, and color**. The system uses Dataset 2 product metadata and a FashionCLIP image index containing **44,419 products**.

---

## Features

### Image Search

- Upload JPG, PNG, or WEBP images.
- Preview the selected image before searching.
- Send the image to the Flask backend.
- Encode the query image using FashionCLIP.
- Retrieve visually similar products using FAISS.
- Display product images, product IDs, and cosine similarity scores.
- Show loading and error states during the search process.

### Text Search Interface

- Search products using a fashion-related text query.
- Filter results by:
  - Gender
  - Category
  - Color
- Filter options are based on real Dataset 2 metadata.
- Display applied filters on the results page.
- Display matching products in a responsive product grid.

> The current runnable Flask backend has not yet integrated the text-search endpoint. The text-search page currently uses a frontend preview based on Dataset 2 metadata so the interface and filtering flow can be tested before backend integration.

### Results Page

- Responsive product grid.
- Product image.
- Product ID.
- Gender.
- Category.
- Color.
- Usage information when available.
- Similarity or text-match score.
- Empty-state handling when no products match the search.

### Responsive Interface

The frontend is designed for:

- Desktop
- Laptop
- Tablet
- Mobile

The visual style uses a pastel pink, white, and black palette with glass-style panels, rounded corners, custom fonts, and a background video.

---

## Technology Stack

### Frontend

- React
- Vite
- React Router
- JavaScript
- CSS

### Backend

- Python
- Flask
- Flask-CORS
- FashionCLIP
- PyTorch
- Transformers
- FAISS
- NumPy
- Pillow

### Data

- Fashion Product Images Dataset
- Dataset 2 metadata
- FashionCLIP embeddings
- FAISS index

---

## Project Structure

```text
IT_Project/
│
├── data/
│   └── d1/
│       └── sample_images/
│
├── docs/
│   ├── API_contract.md
│   ├── API_docs.md
│   └── 25082026-20h50-UI_Wireframe.png
│
├── notebooks/
│   ├── 33_14_EDA_5Datasets_hien_duan.ipynb
│   ├── 34_13_clip_fashionclip.ipynb
│   ├── 35_12_embeddingdataset2.ipynb
│   ├── 36_11_endpointAPIbackend.ipynb
│   └── 37_10_API_Filter.ipynb
│
├── scripts/
│
├── src/
│   ├── api/
│   │   └── fashionApi.js
│   │
│   ├── backend/
│   │   ├── app.py
│   │   └── search.py
│   │
│   ├── components/
│   │   ├── FilterSidebar.jsx
│   │   ├── Header.jsx
│   │   ├── Layout.jsx
│   │   └── ProductCard.jsx
│   │
│   ├── css/
│   │   ├── styles.css
│   │   ├── background/
│   │   ├── fonts/
│   │   └── logo/
│   │
│   ├── data/
│   │   ├── filterOptions.js
│   │   ├── mockProducts.js
│   │   └── textSearchDemoCatalog.js
│   │
│   ├── pages/
│   │   ├── HomePage.jsx
│   │   ├── ImageSearchPage.jsx
│   │   ├── ResultsPage.jsx
│   │   └── TextSearchPage.jsx
│   │
│   ├── App.jsx
│   └── main.jsx
│
├── tests/
│   └── test_image_search.py
│
├── package.json
├── requirements-backend.txt
├── requirements-test.txt
├── requirements.txt
├── vite.config.js
└── README.md
```

---

## Frontend Routes

```text
/
```

Home page.

```text
/search/image
```

Image-based fashion search.

```text
/search/text
```

Text-search interface with gender, category, and color filters.

```text
/results
```

Search results page.

---

## Backend API

### Health Check

```text
GET /health
```

Checks whether the Flask application is running.

Example:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "model_loaded": false
  },
  "error": null
}
```

`model_loaded: false` is normal before the first valid image search because the model is loaded lazily.

---

### Image Search

```text
POST /search/image
```

Alias:

```text
POST /api/v1/search/image
```

The request uses `multipart/form-data`.

Fields:

```text
image   Required image file
top_k   Optional number of returned products
```

Supported formats:

```text
JPG
JPEG
PNG
WEBP
```

Example response:

```json
{
  "success": true,
  "data": [
    {
      "product_id": "10180",
      "image_url": "/dataset2/images/10180.jpg",
      "similarity_score": 0.94
    }
  ],
  "error": null
}
```

---

### Product Images

```text
GET /dataset2/images/<filename>
```

Used by the frontend to display product images from Dataset 2.

---

### Text Search

```text
POST /search/text
```

The route currently exists in the Flask application but backend text-search integration is still pending.

The current frontend text-search page can already be used to test:

- text input;
- gender dropdown;
- category dropdown;
- color dropdown;
- loading state;
- applied filters;
- results grid;
- no-result state.

---

## Requirements

### Node.js

Check:

```powershell
node -v
npm -v
```

### Python

Python 3.11 is suitable for the backend.

Check:

```powershell
python --version
```

---

## Installation

From the repository root:

```powershell
python -m venv .venv
```

Install backend dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-backend.txt
```

Download the FashionCLIP model once:

```powershell
.\.venv\Scripts\python.exe -m scripts.download_search_model
```

Install frontend dependencies:

```powershell
npm install
```

or:

```powershell
npm ci
```

---

## Required Search Files

The image-search backend requires:

```text
fashionclip_image_embeddings_flat.index
product_ids.npy
```

The FAISS index and product IDs must belong to the same embedding pipeline and contain the same number of entries.

The current image index contains:

```text
44,419 products
```

The backend also needs access to the Dataset 2 image directory containing files such as:

```text
10180.jpg
13016.jpg
16806.jpg
...
```

---

## Environment Variables

If the dataset and search artifacts are stored outside the repository, configure their paths before starting the backend.

Example:

```powershell
$env:FASHION_INDEX_PATH="C:\path\to\fashionclip_image_embeddings_flat.index"

$env:PRODUCT_IDS_PATH="C:\path\to\product_ids.npy"

$env:FASHION_IMAGES_DIR="C:\path\to\fashion-dataset\images"
```

The backend also supports:

```text
IMAGE_DIR
INDEX_PATH
PRODUCT_IDS_PATH
MODEL_PATH
MODEL_HF_NAME
PORT
ALLOWED_ORIGIN
VITE_API_BASE_URL
```

---

## Running the Project

Open two terminals in the repository root.

### Terminal 1 — Backend

If required, configure the environment variables first.

Then run:

```powershell
npm run backend
```

or:

```powershell
.\.venv\Scripts\python.exe -m src.backend.app
```

The backend runs at:

```text
http://127.0.0.1:5000
```

Health check:

```text
http://127.0.0.1:5000/health
```

---

### Terminal 2 — Frontend

Run:

```powershell
npm run dev
```

The frontend normally runs at:

```text
http://localhost:5173
```

---

## Using Image Search

Open:

```text
http://localhost:5173/search/image
```

Steps:

1. Select or drag and drop an image.
2. Check the image preview.
3. Click `DISCOVER MATCHES`.
4. Wait while the system processes the image.
5. The application navigates to `/results`.
6. Similar products are displayed in the product grid.

Image-search flow:

```text
User image
   ↓
React frontend
   ↓
Flask API
   ↓
FashionCLIP
   ↓
Image embedding
   ↓
FAISS
   ↓
Top-K similar products
   ↓
JSON response
   ↓
React results grid
```

---

## Using Text Search and Filters

Open:

```text
http://localhost:5173/search/text
```

The interface provides:

```text
Fashion Query
Gender
Category
Color
```

Example:

```text
Query: black shirt
Gender: Men
Category: Shirts
Color: Black
```

Click:

```text
DISCOVER
```

The results page displays the selected filters together with matching Dataset 2 products.

The current text-search result preview is intended for frontend integration and interface testing until the backend text-search endpoint is connected.

---

## Build

To build the frontend:

```powershell
npm run build
```

The production files are created in:

```text
dist/
```

Preview the build with:

```powershell
npm run preview
```

---

## Testing

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt

.\.venv\Scripts\python.exe -m pytest -q
```

Image-search verification scripts are also available under:

```text
scripts/
```

---

## Notes

- The full Dataset 2 should not be committed directly to Git unless necessary.
- Large model files and FAISS artifacts can be stored separately and configured using environment variables.
- The repository mainly contains source code, notebooks, scripts, documentation, tests, and frontend assets.
- Image search currently uses the real FashionCLIP + FAISS backend.
- Text-search and metadata-filter controls are available in the frontend, while the runnable backend text-search endpoint is still pending integration.
