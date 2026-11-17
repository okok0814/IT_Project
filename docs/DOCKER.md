# Docker setup with managed storage

## Release status

All **15 catalog/index archives (15,042,867,200 bytes)** are published in
[runtime-v1](https://github.com/okok0814/IT_Project/releases/tag/runtime-v1).
GitHub's reported sizes and SHA256 hashes match the setup manifest; every public
download URL returned HTTP 200. Evidence: [asset metadata](../logs/20261117-runtime-release/assets.json)
and [public URL verification](../logs/20261117-runtime-release/verified.json).

Publication did not commit or push the local setup code or manifest. Those changes
must also reach the repository before a fresh clone includes automatic setup.
On **18 November 2026 (Vietnam time)**, the full application passed **9/9 deployment
check groups** at `http://localhost:8081`, including real model inference and
Chrome desktop/mobile flows. The separate Compose project `fashion-search-check`
uses `fashion-search-check_runtime-data`, mounted read-only by the backend.
After restart, setup exited with code 0, backend/frontend were healthy, and logs
showed reuse of all 15 archives and 8 model files. Evidence:
[deployment checks](../logs/20261117-172857Z-deployment/results.json),
[browser results](../logs/20261117-172857Z-deployment/browser.json), and
[restart verification](../logs/20261117-173824Z-runtime-reuse/summary.json).

The operator confirmed completing the initial setup in the separate test project;
the saved setup log covers the subsequent reuse run. The old installation on
port 8080 is separate. A fresh GitHub clone on a second computer has not been tested.

## Starting with the setup-enabled source

Install Docker Desktop with Linux containers, clone the repository, and run:

```powershell
docker compose up -d --build
```

No Python installation, manual dataset download or host path configuration is
needed. `.env` is optional for `APP_PORT`, `SEARCH_CACHE_SIZE` and
`SEARCH_CACHE_TTL_SECONDS`. Default Compose does not use host data paths.

Setup downloads release archives and FashionCLIP files pinned to a Hugging Face
revision. It verifies download sizes/SHA256, archive paths, required files and
image count. Backend startup validates the index/IDs/metadata/images and warms
both encoders. Frontend starts once the backend is healthy.

```powershell
docker compose logs -f setup
docker compose ps -a
```

`setup` should finish with `Exited (0)`. When backend and frontend are healthy,
open **http://localhost:8080**. The default command does not wait for frontend's
health check. First downloads can take much longer than five minutes; do not
apply the old 300-second wait timeout to first setup.

## Storage and retries

The `runtime-data` named volume contains catalog, index, model and completion
receipts. Setup writes; backend mounts it read-only and serves offline. A manifest
identifies a version directory. `current` switches only after all parts complete;
a failed new version leaves the previous version available.

First download is about 15.7 GB including original full-size images. Allow at
least 25 GB free Docker storage for one version, temporary downloads and images;
additional versions require more space. Images are not resized and embeddings
are not recomputed. Packaged IDs are converted from the legacy object array to a
plain string array with the same ordering.

Completed parts are reused after checking installed paths and sizes. SHA256 is
checked on downloads, not on every image at every startup. Missing/truncated files
trigger download of that part again. An interrupted part restarts from the
beginning; completed parts remain. Same-size manual corruption requires repair
of that part/volume. The volume is not intended for manual editing.

```powershell
docker compose stop
docker compose up -d --build
docker compose down
```

`stop` and `down` keep the volume. **`docker compose down -v` deletes downloaded
runtime data** and forces a new download. Existing host dataset/model folders
are separate from this volume.

## Testing alongside an existing installation

If port 8080 already serves an old installation, use a separate project and port:

```powershell
$env:APP_PORT = "8081"
docker compose -p fashion-search-check up -d --build
docker compose -p fashion-search-check logs -f setup
docker compose -p fashion-search-check ps -a
```

Open `http://localhost:8081`. Keep `APP_PORT=8081` in the terminal when running
later `up` commands for this project. The project name creates a separate runtime
volume and containers. `Ctrl+C` exits log following without stopping services.

For maintainers with the local Python test environment and Chrome installed:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.verify_deployment --base-url http://localhost:8081 --with-ui
```

The verifier writes results, browser screenshots and source hashes to a new
`logs/<UTC timestamp>-deployment/` directory. This test environment is optional;
end users only need Docker to run the application.

To verify persistence, use the same project and port:

```powershell
docker compose -p fashion-search-check down
docker compose -p fashion-search-check up -d --build
docker compose -p fashion-search-check logs setup
```

Expect `Reusing ...` messages and successful setup. Omit `-v` to keep downloaded data.

## Maintainer release preparation

This is a publishing task for the maintainer, not for end users. Prepared files:

- `.cache/runtime-release-v1/search-artifacts.tar`: metadata, exact Flat index and IDs.
- `.cache/runtime-release-v1/catalog-001.tar` through `catalog-014.tar`: original indexed images.
- `deploy/runtime-manifest.json`: committed download URLs, sizes, hashes and model revision.

The **runtime-v1** release in **okok0814/IT_Project** now contains the
**15 tar files**, unchanged (about 15.04 GB total). Keep these archives out of
normal Git commits. Each part is under the 2 GiB release-asset limit. The model
downloads from its original source and does not need uploading. Include the
Fashion Product Images Dataset attribution and applicable license with the
release. This upload was completed with the repository owner's authorization.

To package a future version from matching local artifacts:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.package_runtime --dataset-dir "D:/datasets/fashion-dataset" --output-dir .cache/runtime-release-v2 --base-url https://github.com/okok0814/IT_Project/releases/download/runtime-v2
```

The output directory must not exist. The script validates index/IDs, metadata
and image coverage before packaging. It records the local model cache revision;
the maintainer must ensure the index was generated with that revision. Hashes
cannot establish the original embedding-generation process.

Upload the generated tar files, copy the generated `runtime-manifest.json` into
`deploy/`, and commit it with the code. Verify public URLs and a full startup
from a fresh volume before announcing readiness. Update the release-status
notice after publication and verification.

## Checks and troubleshooting

```powershell
docker compose config --quiet
docker compose logs --tail 100 setup backend frontend
python -m pytest -q tests/test_setup_runtime.py
```

- 404: publish the exact filenames in the manifest to a public release.
- Network error: restore access and retry startup. Each download has three attempts.
- SHA256/size mismatch: check the release asset; incomplete versions are not activated.
- Backend unhealthy: inspect backend logs for artifact consistency or memory errors.
- Port conflict: set `APP_PORT=8081` in an optional root `.env` and restart.

Fixture tests cover integrity, recovery, reuse, unsafe archives, version isolation
and missing images. They do not prove public release availability or replace a
full-model deployment test.

References: [Compose dependencies](https://docs.docker.com/compose/how-tos/startup-order/),
[Docker volumes](https://docs.docker.com/engine/storage/volumes/),
[GitHub release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).
