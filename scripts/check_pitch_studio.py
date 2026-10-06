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
    official = json.loads((ROOT / "docs/results/mlb_p0/first_pa_media_v1.json").read_bytes())
    registry = json.loads(
        subprocess.check_output(
            [
                "node",
                "-e",
                "console.log(JSON.stringify(require(process.argv[1])))",
                str(SITE / "receiver-media.js"),
            ]
        )
    )
    assert official["game_pk"] == 849843
    assert set(registry) == {f"849843:1:{pitch}" for pitch in (1, 2, 3)}
    for clip in official["clips"]:
        pitch_id = f"{clip['game_pk']}:{clip['at_bat_number']}:{clip['pitch_number']}"
        record = registry[pitch_id]
        assert record["play_id"] == clip["play_id"]
        assert record["page_url"] == clip["official_page_url"]
        for kind, evidence in (("video", "media"), ("poster", "poster")):
            assert record[kind] == clip[f"site_{kind}"]
            assert record[f"{kind}_sha256"] == clip[evidence]["sha256"]
            actual = (SITE / record[kind]).read_bytes()
            assert len(actual) == clip[evidence]["bytes"]
            assert hashlib.sha256(actual).hexdigest() == clip[evidence]["sha256"]
    print("PASS: 3 exact official play IDs, media bytes and provenance")
    reel = json.loads((ROOT / "docs/results/mlb_p0/hero_reel_v1.json").read_bytes())
    assert [clip["pitch_id"] for clip in reel["segments"]] == [
        "849843:1:1",
        "849843:1:2",
        "849843:1:3",
        "849843:2:5",
    ]
    for clip in reel["segments"]:
        assert (
            hashlib.sha256((SITE / "media" / clip["source_asset"]).read_bytes()).hexdigest()
            == clip["source_sha256"]
        )
    output = reel["output"]
    asset = (SITE / "media" / output["file"]).read_bytes()
    assert len(asset) == output["bytes"]
    assert hashlib.sha256(asset).hexdigest() == output["sha256"]
    print("PASS: four-pitch hero reel source and output hashes")
    receiver = subprocess.run(
        [
            "node",
            "--test",
            str(ROOT / "tests/js/pitch_receiver.test.cjs"),
            str(ROOT / "tests/js/pitch_home.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-intake.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-first-pa.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-video.test.cjs"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if receiver.returncode:
        raise RuntimeError(receiver.stdout + receiver.stderr)
    print("PASS: receiver and home playback regression checks")
    print(f"PASS: {len(data['scenarios'])} illustrative distributions, HTML assets, media SHA256")


if __name__ == "__main__":
    check()
