"""Capture live Week 8 test logs, artifact hashes, API/browser checks and build output."""
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

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--metadata-path")
    parser.add_argument("--with-ui", action="store_true")
    parser.add_argument("--record-demo", action="store_true")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    output = ROOT / "notebooks/logs" / f"{stamp}-week8"
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}

    def run(name, command):
        with (output / name).open("w", encoding="utf-8") as log:
            log.write(f"UTC: {datetime.now(timezone.utc).isoformat()}\nCWD: {ROOT}\nCOMMAND: {subprocess.list2cmdline(command)}\n\n")
            log.flush()
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace")
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
            log.write(f"\nEXIT_CODE: {code}\nUTC_END: {datetime.now(timezone.utc).isoformat()}\n")
        if code:
            raise SystemExit(f"Failed command; evidence retained in {output / name}")

    metadata_path = Path(args.metadata_path) if args.metadata_path else Path(args.image_dir).parent / "styles.csv"
    sources = [*ROOT.glob("src/backend/*.py"), *ROOT.glob("src/**/*.jsx"), *ROOT.glob("src/**/*.css"), *ROOT.glob("src/api/*.js"),
               *ROOT.glob("src/data/filterOptions.js"), *ROOT.glob("tests/*.py"), *ROOT.glob("scripts/*.py"),
               *ROOT.glob("requirements*.txt"), ROOT / "vite.config.js", ROOT / "package.json", ROOT / "package-lock.json"]
    artifacts = [ROOT / "embeddings/product_ids.npy", ROOT / "embeddings/index/fashionclip_image_embeddings_flat.index",
                 ROOT / "embeddings/fashionclip_image_embeddings.npy", metadata_path]
    provenance = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
                  "python": platform.python_version(), "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  "note": "Working-tree source is identified by SHA-256; git_head alone does not include uncommitted changes.",
                  "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                  "artifact_sha256": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}}
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    run("environment.txt", [sys.executable, "-m", "pip", "freeze"])
    run("pytest.txt", [sys.executable, "-m", "pytest", "-q", f"--junitxml={output / 'pytest.xml'}"])
    command = [sys.executable, "-m", "scripts.verify_text_search", "--image-dir", args.image_dir,
               "--metadata-path", str(metadata_path), "--output-dir", str(output)]
    if args.with_ui:
        command.append("--with-ui")
    if args.record_demo:
        command.append("--record-demo")
    run("text-search.txt", command)
    node = shutil.which("node") or next(str(p) for p in (ROOT / ".cache/node").glob("*/node.exe"))
    run("build.txt", [node, str(ROOT / "node_modules/vite/bin/vite.js"), "build"])
    cases = ET.parse(output / "pytest.xml").getroot().findall(".//testcase")
    result = json.loads((output / "text-search.json").read_text(encoding="utf-8"))
    browser_path = output / "browser-results.json"
    browser = json.loads(browser_path.read_text()) if browser_path.exists() else None
    summary = {"unit_tests": len(cases),
               "unit_passed": sum(not any(c.find(tag) is not None for tag in ["failure", "error", "skipped"]) for c in cases),
               "real_api_cases_passed": result["passed_cases"], "index_vectors": result["index_vectors"],
               "thumbnail_http_200": sum(s == 200 for record in result["records"] for s in record["thumbnail_statuses"]),
               "browser_checks_passed": len(browser["checks"]) if browser else None,
               "warm_mean_ms": result["warm_mean_ms"], "warm_p95_ms": result["warm_p95_ms"],
               "cold_ms": result["records"][0]["elapsed_ms"], "build_passed": True,
               "demo": browser.get("demo_gif") if browser else None}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()
