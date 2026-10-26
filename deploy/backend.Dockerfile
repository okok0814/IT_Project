FROM python:3.11-slim-bookworm@sha256:f06d01d4ba3f8ad5af45a3ec87df19c1d317d8e8961edc0fabda61811af6f7cf

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser
COPY requirements.txt ./
COPY deploy/constraints.txt deploy/runtime_requirements.py ./deploy/
# CPU-only wheel avoids shipping CUDA runtimes for this Docker Desktop demo.
RUN python deploy/runtime_requirements.py \
    && pip install --no-cache-dir -c deploy/constraints.txt torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -c deploy/constraints.txt -r /tmp/requirements-runtime.txt
COPY src/backend/ ./src/backend/
COPY deploy/gunicorn.conf.py ./deploy/gunicorn.conf.py
USER appuser
EXPOSE 8000
CMD ["gunicorn", "--config", "deploy/gunicorn.conf.py", "src.backend.wsgi:app"]
