"""Build a private, offline demo bundle without changing frozen presentation assets."""

import argparse
import base64
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SITE_FILES = (
    "app.js",
    "data.js",
    "home.js",
    "index.html",
    "preview-data.js",
    "product.css",
    "receiver-contract.js",
    "receiver-sample.js",
    "receiver.css",
    "receiver.html",
    "receiver.js",
    "report-theme.css",
    "report.html",
    "service.html",
    "studio.css",
    "studio.js",
    "styles.css",
    "media/pitch-849843-1-3.jpg",
    "media/pitch-849843-1-3.mp4",
    "media/pitch-849843-2-5.jpg",
    "media/pitch-849843-2-5.mp4",
)
SLIDES = ("intent_cv_summary_20261006.png", "intent_cv_summary_20261006.pptx")
COMPARISON_FILES = ("index.html", "manifest.json", "README.txt")


def sha(data):
    """Hash exact bytes, including original line endings."""
    return hashlib.sha256(data).hexdigest()


class References(HTMLParser):
    """Read references without loading or executing the document."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src", "poster"} and value:
                self.links.append((tag, key, value))
            if tag == "img" and key == "src" and value:
                self.images.append(value)


def verify_comparison(root, comparison):
    """Bind the unchanged private gallery to its original report and image hashes."""
    manifest = json.loads((comparison / "manifest.json").read_bytes())
    if manifest["distribution"] != "private_teammate_attachment_and_local_rehearsal_only":
        raise ValueError("Unexpected comparison distribution scope")
    report = root / "docs/results/mlb_p0/intent_accuracy_report_v0.json"
    if sha(report.read_bytes()) != manifest["source_report_sha256"]:
        raise ValueError("Comparison report hash mismatch")
    html = (comparison / "index.html").read_bytes()
    if sha(html) != manifest["index_html_sha256"]:
        raise ValueError("Comparison gallery hash mismatch")
    parser = References()
    parser.feed(html.decode("utf-8"))
    image_hashes = []
    for image in parser.images:
        if not image.startswith("data:image/jpeg;base64,"):
            raise ValueError("Comparison images must remain embedded JPEGs")
        image_hashes.append(sha(base64.b64decode(image.split(",", 1)[1], validate=True)))
    if image_hashes != [figure["sha256"] for figure in manifest["figures"]]:
        raise ValueError("Embedded comparison images differ from their manifest")
    return manifest


def check_links(bundle):
    """Check explicit HTML href/src/poster references, not arbitrary runtime requests."""
    bundle = bundle.resolve()
    for page in bundle.rglob("*.html"):
        parser = References()
        parser.feed(page.read_text(encoding="utf-8"))
        for tag, attribute, reference in parser.links:
            url = urlsplit(reference)
            if url.scheme == "data":
                continue
            if url.scheme or url.netloc:
                if tag != "a" or attribute != "href" or url.scheme not in {"http", "https"}:
                    raise ValueError(f"External load dependency in {page.name}")
                continue
            if not url.path:
                continue
            target = (page.parent / unquote(url.path)).resolve()
            if not target.is_relative_to(bundle) or not target.is_file():
                raise ValueError(f"Broken or escaping reference: {page.name}: {reference}")


def verify_bundle(bundle):
    """Check contents against a local inventory; this does not authenticate the source."""
    bundle = bundle.resolve()
    manifest = json.loads((bundle / "bundle_manifest.json").read_bytes())
    expected = set(manifest["files"])
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}
    if actual != expected | {"bundle_manifest.json"}:
        raise ValueError("Bundle file inventory changed")
    for relative, info in manifest["files"].items():
        path = bundle / relative
        if path.is_symlink() or not path.resolve().is_relative_to(bundle):
            raise ValueError("Bundle contains a link or escaping path")
        data = path.read_bytes()
        if len(data) != info["bytes"] or sha(data) != info["sha256"]:
            raise ValueError(f"Bundle file changed: {relative}")
    check_links(bundle)
    return manifest


def build(root, comparison, out):
    """Copy only allowlisted assets into a new folder and a new ZIP."""
    root, comparison, out = root.resolve(), comparison.resolve(), out.resolve()
    archive = out.parent / f"{out.name}.zip"
    if out.exists() or archive.exists():
        raise FileExistsError("Use a new output name; existing folders and ZIPs are preserved")
    comparison_manifest = verify_comparison(root, comparison)
    mappings = [(root / "web/pitch-studio" / p, f"site/{p}") for p in SITE_FILES]
    mappings += [(root / "docs/demo" / p, f"slides/{p}") for p in SLIDES]
    mappings += [(comparison / p, f"comparison/{p}") for p in COMPARISON_FILES]
    mappings += [
        (root / "docs/demo/offline_start.html", "START_HERE.html"),
        (root / "docs/PITCH_STUDIO_DEMO_RUNBOOK.md", "PRESENTER_NOTES.md"),
        (root / "docs/demo/offline_readme.txt", "README.txt"),
    ]
    for source, _ in mappings:
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Source must be a regular file: {source}")
        if not source.resolve().is_relative_to(root):
            raise ValueError("Source must stay in the selected repository")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    out.mkdir(parents=True, exist_ok=False)
    files = {}
    for source, relative in mappings:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        original = source.read_bytes()
        data = original
        transformation = None
        if relative.startswith("site/") and relative.endswith(".html"):
            data = original.replace(b'href="./"', b'href="index.html"')
            if data != original:
                transformation = "explicit_index_link_for_offline_file_urls"
        target.write_bytes(data)
        files[relative] = {
            "source": source.relative_to(root).as_posix(),
            "source_sha256": sha(original),
            "transformation": transformation,
            "bytes": len(data),
            "sha256": sha(data),
        }
    manifest = {
        "schema": "pitcheezy_private_offline_demo_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "repository_head_at_build": head,
        "source_binding": "Source/output hashes bind exact bytes and declared link rewrites; HEAD may precede additions.",
        "distribution": "private_teammate_transfer_and_local_demo_only",
        "comparison_scope": comparison_manifest["distribution"],
        "live_model_connected": False,
        "song_ui_rehearsal_completed": False,
        "files": files,
    }
    (out / "bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verify_bundle(out)
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zipped.write(path, f"{out.name}/{path.relative_to(out).as_posix()}")
    with ZipFile(archive) as zipped:
        for relative in [*files, "bundle_manifest.json"]:
            if zipped.read(f"{out.name}/{relative}") != (out / relative).read_bytes():
                raise ValueError("ZIP content mismatch")
    return {
        "bundle": str(out),
        "archive": str(archive),
        "files": len(files),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha(archive.read_bytes()),
    }


def main():
    """Build or verify a private offline presentation bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser("build")
    create.add_argument("--comparison", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    check = actions.add_parser("check")
    check.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        result = build(ROOT, args.comparison, args.out)
    else:
        manifest = verify_bundle(args.bundle)
        result = {"status": "verified", "files": len(manifest["files"])}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
