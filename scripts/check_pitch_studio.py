"""Check actual-replay pages, isolated legacy fixtures, links and media hashes."""

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
            assert target.name not in {"preview-data.js", "studio.js", "studio.css"}, (
                f"Legacy illustrative studio must not be linked by a product page: {page.name}: {ref}"
            )
    catalog = json.loads(
        subprocess.check_output(
            ["node", "-e", "console.log(JSON.stringify(require(process.argv[1]).list()))",
             str(SITE / "game-catalog.js")]
        )
    )
    assert {entry["game_pk"] for entry in catalog} == {849843, 849845, 823407}
    game_links = Links()
    game_links.feed((SITE / "games.html").read_text(encoding="utf-8"))
    for entry in catalog:
        game_id = entry["game_pk"]
        for suffix, field in (("", "game_sha256"), ("-media", "media_sha256"),
                              ("-zones", "zones_sha256")):
            actual = (SITE / f"game-{game_id}{suffix}.json").read_bytes()
            assert hashlib.sha256(actual).hexdigest() == entry[field], (
                f"Catalog asset hash mismatch: {game_id}{suffix}"
            )
        packet = json.loads((SITE / f"game-{game_id}.json").read_bytes())
        media = json.loads((SITE / f"game-{game_id}-media.json").read_bytes())
        zones = json.loads((SITE / f"game-{game_id}-zones.json").read_bytes())
        assert packet["game"]["game_pk"] == game_id
        assert len(packet["pitches"]) == entry["pitches"]
        assert len(media["records"]) == entry["media_count"]
        assert len(media["records"]) + len(media["excluded"]) == entry["pitches"]
        assert len(zones["pitches"]) == entry["zones_count"]
        assert len({p["pitch_id"] for p in packet["pitches"]}) == entry["pitches"]
        assert any(ref.startswith(f"watch.html?game={game_id}") for ref in game_links.references)
        assert f"receiver.html?game={game_id}" in game_links.references
        for status in ("ready", "unsupported", "missing"):
            assert sum(p["pre"]["status"] == status for p in packet["pitches"]) == entry[status]
        if game_id != 849843:
            assert packet["source"]["kind"] == "official_record"
            assert packet["source"]["model_id"] is None
            assert entry["ready"] == entry["unsupported"] == 0
            assert entry["missing"] == entry["pitches"]
            assert all(
                p["pre"]["provenance"] == "absent"
                and p["pre"]["candidates"] == []
                and p["pre"]["policy"] is None
                and p["post"]["setup"] is None
                for p in packet["pitches"]
            )
    print("PASS: three curated games, fixed asset hashes and explicit missing recommendations")
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
            str(ROOT / "tests/js/pitch_receiver_location.test.cjs"),
            str(ROOT / "tests/js/pitch_fullgame.test.cjs"),
            str(ROOT / "tests/js/pitch_game_catalog.test.cjs"),
            str(ROOT / "tests/js/pitch_game_media.test.cjs"),
            str(ROOT / "tests/js/pitch_zones.test.cjs"),
            str(ROOT / "tests/js/pitch_receiver_route.test.cjs"),
            str(ROOT / "tests/js/pitch_home.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-intake.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-first-pa.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-video.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/receiver-sequence.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/watch.test.cjs"),
            str(ROOT / "web/pitch-studio-tests/watch-timing.test.cjs"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if receiver.returncode:
        raise RuntimeError(receiver.stdout + receiver.stderr)
    print("PASS: receiver and home playback regression checks")
    print(f"PASS: {len(data['scenarios'])} isolated legacy fixtures; no illustrative studio page dependency")
    print("PASS: HTML assets and media SHA256")


if __name__ == "__main__":
    check()
