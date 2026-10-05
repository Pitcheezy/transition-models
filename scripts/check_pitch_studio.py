"""Check the static studio's illustrative contracts, local links and media hashes."""

import hashlib
import json
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "web/pitch-studio"


class Links(HTMLParser):
    """Collect references in the deployed HTML documents."""

    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        self.references.extend(v for k, v in attrs if k in {"src", "href", "poster"} and v)


def check():
    """Fail on mock/live confusion, invalid distributions or changed source assets."""
    for script in SITE.glob("*.js"):
        subprocess.run(["node", "--check", str(script)], check=True)
    source = SITE / "preview-data.js"
    program = (
        "const fs=require('fs'),vm=require('vm');const c={window:{}};"
        "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),c);"
        "console.log(JSON.stringify(c.window.PRODUCT_PREVIEW));"
    )
    data = json.loads(subprocess.check_output(["node", "-e", program, str(source)]))
    assert data["source_kind"] == "illustrative"
    assert data["model_connected"] is False and data["causal_attribution"] is False
    classes = data["class_order"]
    assert len(classes) == len(set(classes)) == 10
    for scenario in data["scenarios"].values():
        probabilities = scenario["probabilities"]
        assert set(probabilities) == set(classes)
        assert all(0 <= value <= 1 for value in probabilities.values())
        assert abs(sum(probabilities.values()) - 1) < 1e-8
        assert sum(choice["share"] for choice in scenario["choices"]) == 100
        assert all(0 <= choice["share"] <= 100 for choice in scenario["choices"])
        assert 1 <= scenario["zone"] <= 9
    for page in SITE.glob("*.html"):
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        for ref in parser.references:
            url = urlsplit(ref)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (page.parent / unquote(url.path)).resolve()
            assert target.is_relative_to(SITE.resolve()), f"Outside site: {ref}"
            assert target.exists(), f"Broken local reference: {page.name}: {ref}"
    manifest = json.loads(
        (ROOT / "docs/results/mlb_p0/pitch_studio_media_provenance_v1.json").read_bytes()
    )
    for item in manifest["items"]:
        for key in ("video", "poster"):
            actual = hashlib.sha256((SITE / "media" / item[key]).read_bytes()).hexdigest()
            assert actual == item[f"{key}_sha256"], f"Media changed: {item[key]}"
    for key in ("source_windows_manifest", "source_points_manifest"):
        actual = hashlib.sha256((ROOT / manifest[key]).read_bytes()).hexdigest()
        assert actual == manifest[f"{key}_sha256"], f"Source changed: {key}"
    receiver = subprocess.run(
        ["node", "--test", str(ROOT / "tests/js/pitch_receiver.test.cjs")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if receiver.returncode:
        raise RuntimeError(receiver.stdout + receiver.stderr)
    print("PASS: response receiver regression checks")
    print(f"PASS: {len(data['scenarios'])} illustrative distributions, HTML assets, media SHA256")


if __name__ == "__main__":
    check()
