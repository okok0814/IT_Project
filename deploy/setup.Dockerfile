FROM python:3.11-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY deploy/setup_runtime.py deploy/runtime-manifest.json ./
CMD ["python", "setup_runtime.py", "--manifest", "/app/runtime-manifest.json", "--root", "/data"]
