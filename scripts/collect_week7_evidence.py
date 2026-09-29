"""Save live test output and immutable per-run evidence for the weekly report."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--with-ui", action="store_true", help="Run browser checks; requires Vite on port 5173 and a free backend port 5000")
    parser.add_argument("--with-build", action="store_true", help="Build the frontend and save its output")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    output = Path(args.output_dir).resolve() if args.output_dir else ROOT / "notebooks/logs" / f"{stamp}-week7"
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}

    def run(name, command):
        with (output / name).open("w", encoding="utf-8") as log:
            log.write(f"UTC: {datetime.now(timezone.utc).isoformat()}\nCWD: {ROOT}\n")
            log.write("COMMAND: " + subprocess.list2cmdline(command) + "\n\n")
            log.flush()
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
            log.write(f"\nEXIT_CODE: {code}\nUTC_END: {datetime.now(timezone.utc).isoformat()}\n")
        if code:
            raise SystemExit(f"Command failed ({code}). Evidence retained in {output / name}")

    provenance = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                  "platform": platform.platform(), "processor": platform.processor(),
                  "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  "note": "Working-tree files were tested; git_head is NOT a commit containing these uncommitted changes.",
                  "source_sha256": {}}
    sources = [*ROOT.glob("src/backend/*.py"), *ROOT.glob("tests/*.py"),
               *ROOT.glob("src/**/*.jsx"), *ROOT.glob("src/api/*.js"), *ROOT.glob("src/css/*.css"),
               *ROOT.glob("scripts/*.py"), ROOT / "vite.config.js", ROOT / "package.json", ROOT / "package-lock.json",
               *ROOT.glob("requirements*.txt")]
    for path in sources:
        provenance["source_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ["embeddings/product_ids.npy", "embeddings/index/fashionclip_image_embeddings_flat.index"]:
        provenance.setdefault("artifact_sha256", {})[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    run("environment.txt", [sys.executable, "-m", "pip", "freeze"])
    run("pytest.txt", [sys.executable, "-m", "pytest", "-q", f"--junitxml={output / 'pytest.xml'}"])
    run("image-search.txt", [sys.executable, "-m", "scripts.verify_image_search", "--image-dir", args.image_dir,
                            "--output", str(output / "image-search.json")])
    if args.with_ui:
        run("browser.txt", [sys.executable, "-m", "scripts.verify_image_search_ui", "--image-dir", args.image_dir,
                            "--output-dir", str(output)])
    if args.with_build:
        node = shutil.which("node") or next((str(p) for p in (ROOT / ".cache/node").glob("*/node.exe")), None)
        if not node:
            raise SystemExit("Node.js is required to build the frontend")
        run("build.txt", [node, str(ROOT / "node_modules/vite/bin/vite.js"), "build"])
    cases = ET.parse(output / "pytest.xml").getroot().findall(".//testcase")
    result = json.loads((output / "image-search.json").read_text(encoding="utf-8"))
    rows = result["records"]
    warm = [r["elapsed_ms"] for r in rows if not r["includes_model_load"]]
    summary = {
        "run_directory": str(output), "unit_cases": len(cases),
        "unit_passed": sum(not any(c.find(tag) is not None for tag in ["failure", "error", "skipped"]) for c in cases),
        "real_images": len(rows), "real_images_passed": sum(r["passed"] for r in rows),
        "unique_sha256": len({r["sha256"] for r in rows}), "index_vectors": result["index_vectors"],
        "thumbnail_requests": sum(len(r["result_image_statuses"]) for r in rows),
        "thumbnail_http_200": sum(s == 200 for r in rows for s in r["result_image_statuses"]),
        "variants_passed": sum(v["passed"] for v in result["variants"]), "variants_total": len(result["variants"]),
        "cold_ms": next(r["elapsed_ms"] for r in rows if r["includes_model_load"]),
        "warm_count": len(warm), "warm_mean_ms": round(float(np.mean(warm)), 2),
        "warm_p95_ms": round(float(np.percentile(warm, 95)), 2),
        "self_rank_1": sum(r["self_rank"] == 1 for r in rows),
        "non_top1": [{"file": r["file"], "rank": r["self_rank"]} for r in rows if r["self_rank"] != 1],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
