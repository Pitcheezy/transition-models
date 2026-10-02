"""Find, match and assemble the pitches an official MLB condensed game shows (intent v0).

    python -m intent.condensed source --game G      # condensed-game MP4 + live feed (feed -> data/raw, git-ignored)
    python -m intent.condensed sheets --game G      # 2-fps frames and 4x4 contact sheets under outputs/frames/
    #   Workflow intent/workflows/condensed_scan.js  (two readers per ~80 s range; args printed by `sheets`)
    python -m intent.condensed map --game G --scan <journal.jsonl | result.json> [--resolve R.json]
    python -m intent.broadcast_windows --game G --media-url <url> --pitches outputs/frames/G_pitches.json \
        --out outputs/frames/G_windows --manifest docs/results/mlb_p0/game_G_condensed_windows_v0.json --box x0,y0,x1,y1
    python -m intent.condensed read-args --game G
    #   Workflow intent/workflows/condensed_read.js  (two readers per three pitches, args from `read-args`)
    python -m intent.condensed assemble --game G --reads <journal.jsonl | result.json>
    python -m intent.calibrate --game G
    python -m intent.run --game G --out docs/results/mlb_p0/game_G_intent_v0.jsonl

The prototype of this file produced game 849843 (scratch scripts, 2026-10-02); this is the same
procedure made reusable, plus automatic tie-breaks that 849843 resolved by hand (post-pitch
type/speed graphic, then the outcome). Video frames and the feed stay in git-ignored folders
(``outputs/frames/``, ``data/raw/``); the committed files carry times, frame indices, hashes and
coordinates only. Statcast pitch locations are never used to match or to read a pitch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import unicodedata
import urllib.request
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
FRAMES = ROOT / "outputs/frames"
RAW = ROOT / "data/raw/mlb_video"
STATSAPI = "https://statsapi.mlb.com/api"
FPS = Fraction(60000, 1001)
SCAN_FPS = 2
SHEET_GRID = (4, 4)
THUMB = (320, 180)
RANGE_SHEETS = 10  # 10 sheets x 8 s = 80 s per scan range
PAIR_SECONDS = 1.5
AGREE_PX = 15.0
SPEED_TOLERANCE_MPH = 1.0
NAME_SUFFIXES = {"JR", "SR", "II", "III", "IV"}
CATCH_DEPTHS = (-0.5, -1.0, -1.5)
TRAJECTORY_KEYS = ("x0", "y0", "z0", "vX0", "vY0", "vZ0", "aX", "aY", "aZ")

# broadcast pitch-type words -> Statcast pitch type codes
GRAPHIC_TYPES = {
    "FOURSEAM": {"FF"},
    "4SEAM": {"FF"},
    "FASTBALL": {"FF", "SI", "FC"},
    "SINKER": {"SI"},
    "2SEAM": {"SI"},
    "TWOSEAM": {"SI"},
    "CUTTER": {"FC"},
    "SLIDER": {"SL"},
    "SWEEPER": {"ST"},
    "SLURVE": {"SV"},
    "CHANGEUP": {"CH"},
    "CHANGE": {"CH"},
    "KNUCKLECURVE": {"KC"},
    "CURVEBALL": {"CU", "KC"},
    "CURVE": {"CU", "KC"},
    "SPLITTER": {"FS"},
    "SPLITFINGER": {"FS"},
    "SPLINKER": {"FS"},
    "FORKBALL": {"FO"},
    "KNUCKLEBALL": {"KN"},
}


# ----------------------------------------------------------------------------- helpers


def _get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "transition-models-intent"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def surname(full_name):
    words = [w for w in fold(full_name).replace(".", " ").split() if w not in NAME_SUFFIXES]
    return words[-1] if words else None


def surname_from_bug(text):
    """'2. BREGMAN' -> 'BREGMAN' (lineup numbers and initials dropped)."""
    if not text:
        return None
    words = [w for w in fold(text).replace(".", " ").split() if not w.isdigit()]
    words = [w for w in words if w not in NAME_SUFFIXES]
    return words[-1] if words else None


def outcome_category(text):
    """Coarse category of a feed call or a reader's free-text outcome."""
    t = fold(text)
    if not t:
        return None
    if "HIT BY PITCH" in t or "HBP" in t:
        return "hit_by_pitch"
    if any(
        k in t
        for k in (
            "IN PLAY",
            "GROUND",
            "FLY",
            "LINE DRIVE",
            "LINER",
            "POP",
            "SINGLE",
            "DOUBLE",
            "TRIPLE",
            "HOME RUN",
            "HOMER",
            "BUNT",
        )
    ):
        return "in_play"
    if "FOUL TIP" in t:
        return "swinging_strike"
    if "FOUL" in t:
        return "foul"
    if "CALLED" in t or "LOOKING" in t:
        return "called_strike"
    if "SWING" in t or "WHIFF" in t:
        return "swinging_strike"
    if "BALL" in t or "WALK" in t:
        return "ball"
    return None


def graphic_types(type_text):
    key = re.sub(r"[^A-Z0-9]", "", fold(type_text))
    if not key:
        return None
    for word in sorted(GRAPHIC_TYPES, key=len, reverse=True):
        if word in key:
            return GRAPHIC_TYPES[word]
    return None


def graphic_agreement(graphic, pitch):
    """Compare a reader's post-pitch graphic with the feed pitch; None when nothing to compare."""
    if not graphic:
        return None
    checks = []
    codes = graphic_types(graphic.get("type_text"))
    if codes and pitch.get("pitch_type"):
        checks.append(pitch["pitch_type"] in codes)
    mph = graphic.get("mph")
    if mph is not None and pitch.get("start_speed") is not None:
        checks.append(abs(float(mph) - float(pitch["start_speed"])) <= SPEED_TOLERANCE_MPH)
    return all(checks) if checks else None


# ----------------------------------------------------------------------------- source


def find_condensed(content):
    items = ((content.get("highlights") or {}).get("highlights") or {}).get("items") or []
    for item in items:
        title = item.get("title") or item.get("headline") or ""
        if not title.lower().startswith("condensed game"):
            continue
        urls = {p.get("name"): p.get("url") for p in item.get("playbacks") or []}
        if urls.get("mp4Avc"):
            return {
                "title": title,
                "duration": item.get("duration"),
                "content_id": item.get("id") or item.get("guid"),
                "media_url": urls["mp4Avc"],
            }
    return None


def probe(media_url, ffprobe="ffprobe"):
    out = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,sample_aspect_ratio:format=duration",
            "-of",
            "json",
            media_url,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(out.stdout)
    stream = data["streams"][0]
    return {
        "width": stream.get("width"),
        "height": stream.get("height"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "duration_seconds": float(data["format"]["duration"]),
    }


def cmd_source(args):
    content = _get_json(f"{STATSAPI}/v1/game/{args.game}/content")
    found = find_condensed(content)
    if found is None:
        raise SystemExit(f"no condensed game with an mp4Avc playback for {args.game}")
    feed_url = f"{STATSAPI}/v1.1/game/{args.game}/feed/live"
    feed = _get_json(feed_url)
    feed_path = RAW / str(args.game) / "feed.json"
    feed_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(feed, ensure_ascii=False).encode("utf-8")
    feed_path.write_bytes(blob)
    game = feed["gameData"]
    source = {
        "schema": "intent_condensed_source_v0",
        "game_pk": args.game,
        "game": {
            "date": game["datetime"].get("officialDate"),
            "type": game["game"].get("type"),
            "away": game["teams"]["away"]["name"],
            "home": game["teams"]["home"]["name"],
            "venue": game["venue"]["name"],
        },
        "condensed_game": {**found, "probe": probe(found["media_url"], args.ffprobe)},
        "feed": {
            "url": feed_url,
            "local_path": feed_path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "pitches": len(feed_pitches(feed)),
        },
        "rights": "MLB video and data; frames and the feed stay in git-ignored folders",
    }
    out = RESULTS / f"game_{args.game}_condensed_source_v0.json"
    _write_json(out, source)
    print(json.dumps(source, ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------- sheets


def scan_time(k):
    """Playback time of scan frame scan_KKKKK.jpg (1-based, 2 fps)."""
    return (k - 1) / SCAN_FPS


def make_sheets(scan_dir, sheet_dir):
    from PIL import Image, ImageDraw

    frames = sorted(Path(scan_dir).glob("scan_*.jpg"))
    per = SHEET_GRID[0] * SHEET_GRID[1]
    Path(sheet_dir).mkdir(parents=True, exist_ok=True)
    names = []
    for start in range(0, len(frames), per):
        group = frames[start : start + per]
        sheet = Image.new("RGB", (THUMB[0] * SHEET_GRID[0], THUMB[1] * SHEET_GRID[1]), (0, 0, 0))
        for i, path in enumerate(group):
            k = int(path.stem.split("_")[1])
            with Image.open(path) as im:
                thumb = im.convert("RGB").resize(THUMB)
            d = ImageDraw.Draw(thumb)
            label = f"t={scan_time(k):.1f}"
            d.rectangle((THUMB[0] - 64, THUMB[1] - 16, THUMB[0], THUMB[1]), fill=(0, 0, 0))
            d.text((THUMB[0] - 60, THUMB[1] - 14), label, fill=(255, 255, 0))
            sheet.paste(thumb, ((i % SHEET_GRID[0]) * THUMB[0], (i // SHEET_GRID[0]) * THUMB[1]))
        k0 = int(group[0].stem.split("_")[1])
        name = f"sheet_{scan_time(k0):06.1f}.jpg"
        sheet.save(Path(sheet_dir) / name, quality=85)
        names.append((scan_time(k0), name))
    return names, len(frames)


def scan_ranges(sheet_names, n_frames):
    seconds_per_sheet = SHEET_GRID[0] * SHEET_GRID[1] / SCAN_FPS
    last = scan_time(n_frames)
    ranges = []
    for i in range(0, len(sheet_names), RANGE_SHEETS):
        block = sheet_names[i : i + RANGE_SHEETS]
        start = block[0][0]
        end = min(last, block[-1][0] + seconds_per_sheet)
        ranges.append({"start": start, "end": end, "sheets": [n for _, n in block]})
    return ranges


def cmd_sheets(args):
    source = _load(RESULTS / f"game_{args.game}_condensed_source_v0.json")
    scan_dir = FRAMES / str(args.game)
    sheet_dir = FRAMES / f"{args.game}_sheets"
    scan_dir.mkdir(parents=True, exist_ok=True)
    if not any(scan_dir.glob("scan_*.jpg")):
        subprocess.run(
            [
                args.ffmpeg,
                "-v",
                "error",
                "-y",
                "-i",
                source["condensed_game"]["media_url"],
                "-vf",
                f"fps={SCAN_FPS}",
                "-q:v",
                "3",
                str(scan_dir / "scan_%05d.jpg"),
            ],
            check=True,
        )
    names, n_frames = make_sheets(scan_dir, sheet_dir)
    ranges = scan_ranges(names, n_frames)
    g = source["game"]
    workflow_args = {
        "game": args.game,
        "gameLabel": f"game {args.game} ({g['date']}, {g['away']} at {g['home']}, {g['venue']})",
        "awayTeam": g["away"],
        "homeTeam": g["home"],
        "duration": source["condensed_game"]["probe"]["duration_seconds"],
        "sheetDir": sheet_dir.as_posix(),
        "frameDir": scan_dir.as_posix(),
        "ranges": ranges,
    }
    _write_json(sheet_dir / "scan_args.json", workflow_args)
    print(
        json.dumps(
            {
                "frames": n_frames,
                "sheets": len(names),
                "ranges": len(ranges),
                "args": (sheet_dir / "scan_args.json").as_posix(),
            }
        )
    )


# ----------------------------------------------------------------------------- reader results


def load_reader_results(path):
    """{'A': [result, ...], 'B': [...]} from a workflow journal (.jsonl) or its returned JSON."""
    path = Path(path)
    out = {"A": [], "B": []}
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        labels = {r["agentId"]: r.get("label") or "" for r in rows if r.get("type") == "started"}
        last = {}
        for r in rows:
            if r.get("type") == "result" and r.get("result"):
                last[r["agentId"]] = r["result"]
        for agent_id, result in last.items():
            reader = labels.get(agent_id, "").split(":")[0][-1:]
            if reader in out:
                out[reader].append(result)
        return out
    data = _load(path)
    for block in data.get("results") or data.get("reads") or []:
        if not block:
            continue
        for reader in ("A", "B"):
            value = block.get(reader)
            if value is None:
                continue
            out[reader].append(value if isinstance(value, dict) else {"items": value})
    return out


# ----------------------------------------------------------------------------- map


def feed_pitches(feed):
    pitches = []
    for play in feed["liveData"]["plays"]["allPlays"]:
        pa = play["about"]["atBatIndex"] + 1
        balls = strikes = 0
        for e in play["playEvents"]:
            if not e.get("isPitch"):
                if "count" in e:
                    balls, strikes = e["count"]["balls"], e["count"]["strikes"]
                continue
            details = e.get("details") or {}
            pitches.append(
                {
                    "at_bat_number": pa,
                    "pitch_number": e["pitchNumber"],
                    "play_id": e.get("playId"),
                    "half": play["about"]["halfInning"],
                    "inning": play["about"]["inning"],
                    "batter": play["matchup"]["batter"]["fullName"],
                    "pitcher": play["matchup"]["pitcher"]["fullName"],
                    "balls_before": balls,
                    "strikes_before": strikes,
                    "call": (details.get("call") or {}).get("description"),
                    "pitch_type": (details.get("type") or {}).get("code"),
                    "start_speed": (e.get("pitchData") or {}).get("startSpeed"),
                }
            )
            balls, strikes = e["count"]["balls"], e["count"]["strikes"]
    return pitches


def pair_readers(by_reader):
    a_list = sorted(
        (p for r in by_reader["A"] for p in r.get("pitches", [])), key=lambda p: p["release_t"]
    )
    b_list = sorted(
        (p for r in by_reader["B"] for p in r.get("pitches", [])), key=lambda p: p["release_t"]
    )
    merged, used = [], set()
    for a in a_list:
        best, best_d = None, None
        for j, b in enumerate(b_list):
            d = abs(a["release_t"] - b["release_t"])
            if j not in used and d <= PAIR_SECONDS and (best_d is None or d < best_d):
                best, best_d = j, d
        if best is None:
            merged.append({"A": a, "B": None})
        else:
            used.add(best)
            merged.append({"A": a, "B": b_list[best]})
    merged += [{"A": None, "B": b} for j, b in enumerate(b_list) if j not in used]
    merged.sort(key=lambda m: (m["A"] or m["B"])["release_t"])
    return merged


def _field(m, key):
    vals = [m[r][key] for r in ("A", "B") if m[r] is not None and m[r].get(key) is not None]
    if not vals:
        return None, "none"
    if len(vals) == 2 and vals[0] != vals[1]:
        return vals, "disagree"
    return vals[0], ("both" if len(vals) == 2 else "one")


def _readers(m):
    return [m[r] for r in ("A", "B") if m[r] is not None]


def match_detections(merged, pitches):
    """Assign each paired detection to a feed pitch (in feed order); never uses pitch location."""
    out, last_index = [], -1
    for m in merged:
        rec = {"A": m["A"], "B": m["B"]}
        both = m["A"] is not None and m["B"] is not None
        rec["release_t"] = (
            round((m["A"]["release_t"] + m["B"]["release_t"]) / 2, 2)
            if both
            else (m["A"] or m["B"])["release_t"]
        )
        rec["readers"] = "both" if both else ("A only" if m["A"] else "B only")
        half, half_s = _field(m, "half")
        inning, inning_s = _field(m, "inning")
        balls, balls_s = _field(m, "balls_before")
        strikes, strikes_s = _field(m, "strikes_before")
        if inning_s == "none" and balls_s == "none" and strikes_s == "none":
            rec.update(match=None, match_status="no_scoreboard", candidates=[])
            out.append(rec)
            continue
        batters = [surname_from_bug(r.get("batter_text")) for r in _readers(m)]
        batters = [b for b in batters if b]
        cands = []
        for i, p in enumerate(pitches):
            if i <= last_index:
                continue
            if half_s in ("both", "one") and p["half"] != half:
                continue
            if inning_s in ("both", "one") and p["inning"] != inning:
                continue
            if batters and not any(
                b == surname(p["batter"]) or b in fold(p["batter"]) for b in batters
            ):
                continue
            score = 0
            for value, status, key in (
                (balls, balls_s, "balls_before"),
                (strikes, strikes_s, "strikes_before"),
            ):
                if status in ("both", "one") and p[key] == value:
                    score += 2
                elif status == "disagree" and p[key] in value:
                    score += 1
            cands.append((score, i, p))
        rec["candidates"] = [
            f"{p['at_bat_number']}:{p['pitch_number']}" for _, _, p in sorted(cands)[-6:]
        ]
        if not cands:
            rec.update(match=None, match_status="no_candidate")
            out.append(rec)
            continue
        top = max(c[0] for c in cands)
        best = sorted((c for c in cands if c[0] == top), key=lambda c: c[1])
        status = "unique" if len(best) == 1 and top == 4 else "count_partial"
        graphics = [r.get("post_pitch_graphic") for r in _readers(m)]
        if len(best) > 1:
            by_graphic = [
                c for c in best if any(graphic_agreement(g, c[2]) is True for g in graphics)
            ]
            outcomes = {outcome_category(r.get("outcome_seen")) for r in _readers(m)} - {None}
            by_outcome = [c for c in best if outcome_category(c[2]["call"]) in outcomes]
            if len(by_graphic) == 1:
                best, status = by_graphic, "resolved_by_pitch_graphic"
            elif len(outcomes) == 1 and len(by_outcome) == 1:
                best, status = by_outcome, "resolved_by_outcome"
            else:
                status = f"ambiguous_{len(best)}"
        choice = best[0]
        p = choice[2]
        rec["match"] = {
            k: p[k]
            for k in (
                "at_bat_number",
                "pitch_number",
                "play_id",
                "half",
                "inning",
                "batter",
                "pitcher",
                "balls_before",
                "strikes_before",
                "call",
            )
        }
        rec["match_score"] = top
        agreement = [graphic_agreement(g, p) for g in graphics]
        seen = [g for g in graphics if g]
        rec["pitch_graphic"] = (
            {
                "seen": [[g.get("type_text"), g.get("mph")] for g in seen],
                "feed": [p["pitch_type"], p["start_speed"]],
                "agrees": all(a for a in agreement if a is not None)
                if any(a is not None for a in agreement)
                else None,
            }
            if seen
            else None
        )
        outcomes = [outcome_category(r.get("outcome_seen")) for r in _readers(m)]
        rec["outcome_consistent"] = (
            outcome_category(p["call"]) in outcomes if any(outcomes) else None
        )
        if rec["pitch_graphic"] and rec["pitch_graphic"]["agrees"] is False:
            status = "check_graphic_conflict"
        rec["match_status"] = status
        if not status.startswith(("ambiguous", "check")):
            last_index = choice[1]
        out.append(rec)
    return out


def apply_resolutions(detections, pitches, decisions):
    """Operator decisions: {release_t, action: assign|drop, at_bat_number, pitch_number, status, reason}."""
    by_key = {(p["at_bat_number"], p["pitch_number"]): p for p in pitches}
    for d in decisions:
        hits = [x for x in detections if abs(x["release_t"] - d["release_t"]) <= 0.3]
        if len(hits) != 1:
            raise ValueError(f"resolution at t={d['release_t']} matches {len(hits)} detections")
        rec = hits[0]
        if not d.get("reason"):
            raise ValueError(f"resolution at t={d['release_t']} has no reason")
        if d["action"] == "drop":
            rec.update(match=None, match_status=d.get("status", "dropped"))
        elif d["action"] == "assign":
            p = by_key[(d["at_bat_number"], d["pitch_number"])]
            rec["match"] = {
                k: p[k]
                for k in (
                    "at_bat_number",
                    "pitch_number",
                    "play_id",
                    "half",
                    "inning",
                    "batter",
                    "pitcher",
                    "balls_before",
                    "strikes_before",
                    "call",
                )
            }
            rec["match_status"] = d.get("status", "resolved_by_operator")
        else:
            raise ValueError(f"unknown resolution action {d['action']}")
        rec["resolution"] = {"action": d["action"], "reason": d["reason"]}
    return detections


USABLE = ("unique", "count_partial", "resolved_by_pitch_graphic", "resolved_by_outcome")


def usable(rec):
    return rec.get("match") is not None and (
        rec["match_status"] in USABLE or rec.get("resolution", {}).get("action") == "assign"
    )


def cmd_map(args):
    feed = _load(RAW / str(args.game) / "feed.json")
    pitches = feed_pitches(feed)
    detections = match_detections(pair_readers(load_reader_results(args.scan)), pitches)
    decisions = _load(args.resolve)["decisions"] if args.resolve else []
    detections = apply_resolutions(detections, pitches, decisions)
    keys = [
        (x["match"]["at_bat_number"], x["match"]["pitch_number"]) for x in detections if usable(x)
    ]
    if len(keys) != len(set(keys)):
        raise SystemExit("two detections map to the same feed pitch; resolve before cutting")
    from collections import Counter

    scan = {
        "schema": "intent_condensed_scan_v0",
        "game_pk": args.game,
        "feed_pitches": len(pitches),
        "method": "two Claude Code workflow agents per ~80 s range read 2-fps contact sheets "
        "(intent/workflows/condensed_scan.js); detections paired by release time (<= 1.5 s) and "
        "matched in feed order by half, inning, batter surname and count; ties broken by the "
        "post-pitch type/speed graphic, then by the outcome; no-scoreboard detections, unresolved "
        "ties and graphic conflicts are left out unless an operator decision (with reason) "
        "assigns them (python -m intent.condensed map)",
        "operator_decisions": decisions,
        "summary": {
            "detections": len(detections),
            "usable": len(keys),
            "status": dict(Counter(x["match_status"] for x in detections)),
            "pitch_graphic_checked": sum(
                1
                for x in detections
                if usable(x) and (x.get("pitch_graphic") or {}).get("agrees") is not None
            ),
            "pitch_graphic_agrees": sum(
                1
                for x in detections
                if usable(x) and (x.get("pitch_graphic") or {}).get("agrees") is True
            ),
        },
        "detections": detections,
    }
    _write_json(RESULTS / f"game_{args.game}_condensed_scan_v0.json", scan)
    pitch_list = [
        {
            "at_bat_number": x["match"]["at_bat_number"],
            "pitch_number": x["match"]["pitch_number"],
            "release_t": x["release_t"],
        }
        for x in detections
        if usable(x)
    ]
    _write_json(FRAMES / f"{args.game}_pitches.json", pitch_list)
    print(json.dumps(scan["summary"], ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------- read args


def cmd_read_args(args):
    feed = _load(RAW / str(args.game) / "feed.json")
    by_key = {(p["at_bat_number"], p["pitch_number"]): p for p in feed_pitches(feed)}
    source = _load(RESULTS / f"game_{args.game}_condensed_source_v0.json")
    windows = _load(RESULTS / f"game_{args.game}_condensed_windows_v0.json")
    scan = _load(RESULTS / f"game_{args.game}_condensed_scan_v0.json")
    release = {
        f"{x['match']['at_bat_number']}:{x['match']['pitch_number']}": x["release_t"]
        for x in scan["detections"]
        if usable(x)
    }
    items = []
    for w in windows["windows"]:
        pa, pn = (int(v) for v in w["pitch"].split(":"))
        p = by_key[(pa, pn)]
        items.append(
            {
                "at_bat_number": pa,
                "pitch_number": pn,
                "dir": (ROOT / w["dir"]).as_posix(),
                "desc": f"{p['batter']} vs {p['pitcher']}, count {p['balls_before']}-"
                f"{p['strikes_before']}, {p['call']}, est. release {release[w['pitch']]} s",
            }
        )
    g = source["game"]
    out = {
        "game": args.game,
        "gameLabel": f"game {args.game} ({g['date']}, {g['away']} at {g['home']}, {g['venue']})",
        "cropBox": [int(v) for v in windows["crop_box"]],
        "frameSize": [
            source["condensed_game"]["probe"]["width"],
            source["condensed_game"]["probe"]["height"],
        ],
        "gridModule": "python -m intent.grid",
        "repoRoot": ROOT.as_posix(),
        "chunk": 3,
        "items": items,
    }
    path = FRAMES / f"{args.game}_windows" / "read_args.json"
    _write_json(path, out)
    print(json.dumps({"items": len(items), "args": path.as_posix()}))


# ----------------------------------------------------------------------------- assemble


def traj_at_y(c, y_target):
    a, b, cc = 0.5 * c["aY"], c["vY0"], c["y0"] - y_target
    t = (-b - math.sqrt(b * b - 4 * a * cc)) / (2 * a)
    return (
        round(c["x0"] + c["vX0"] * t + 0.5 * c["aX"] * t * t, 4),
        round(c["z0"] + c["vZ0"] * t + 0.5 * c["aZ"] * t * t, 4),
    )


def _mean_pt(a, b):
    return [round((a[0] + b[0]) / 2, 2), round((a[1] + b[1]) / 2, 2)]


def collect_reads(by_reader):
    reads = {}
    for reader in ("A", "B"):
        for result in by_reader[reader]:
            for it in result.get("items", []):
                reads.setdefault(f"{it['at_bat_number']}:{it['pitch_number']}", {})[reader] = it
    return reads


def decide_setup(a, b):
    """The consensus rule (unchanged from 849843): returns a dict for the points file."""
    cands = [
        x
        for x in (a, b)
        if x
        and x.get("setup_frame") is not None
        and x.get("mitt_center")
        and x.get("setup_plate_front")
    ]
    res = {"status": "unavailable", "reason": None, "mitt": None, "front": None, "unc": None}
    res["frame_index"], res["note"] = None, ""
    if not cands:
        res["reason"] = next(
            (x.get("setup_reason") for x in (a, b) if x and x.get("setup_reason")),
            "no_setup_frame",
        )
        res["frame_index"] = next(
            (x.get("release_frame") for x in (a, b) if x and x.get("release_frame") is not None),
            None,
        )
    elif len(cands) == 2:
        ca, cb = cands
        dist = math.dist(ca["mitt_center"], cb["mitt_center"])
        res["frame_index"] = ca["setup_frame"]
        if dist > AGREE_PX:
            res["reason"] = "readers_disagree_on_mitt"
            res["note"] = (
                f"reader mitt points {dist:.1f} px apart "
                f"(frames {ca['setup_frame']}, {cb['setup_frame']})"
            )
        else:
            same = ca["setup_frame"] == cb["setup_frame"]
            fa, fb = ca["setup_plate_front"], cb["setup_plate_front"]
            res["status"] = "estimated"
            res["mitt"] = (
                _mean_pt(ca["mitt_center"], cb["mitt_center"]) if same else ca["mitt_center"]
            )
            res["front"] = (
                {
                    "front_left": _mean_pt(fa["left_end"], fb["left_end"]),
                    "front_right": _mean_pt(fa["right_end"], fb["right_end"]),
                }
                if same
                else {"front_left": fa["left_end"], "front_right": fa["right_end"]}
            )
            res["unc"] = max(
                float(ca.get("setup_uncertainty_pixels") or 10),
                float(cb.get("setup_uncertainty_pixels") or 10),
                dist / 2,
            )
            res["note"] = "two readers " + (
                "same frame, averaged"
                if same
                else f"different frames; reader A frame and points, reader B within {dist:.1f} px"
            )
    else:
        one = cands[0]
        other = b if one is a else a
        res["frame_index"] = one["setup_frame"]
        res["reason"] = "only_one_reader_found_a_setup_frame"
        res["note"] = f"other reader: {(other or {}).get('setup_reason')}"
    return res


def assemble(game, reads, windows, scan, feed, source):
    plays = feed["liveData"]["plays"]["allPlays"]
    win = {w["pitch"]: w for w in windows["windows"]}
    release = {
        f"{x['match']['at_bat_number']}:{x['match']['pitch_number']}": x["release_t"]
        for x in scan["detections"]
        if usable(x)
    }

    def event(pa, pn):
        return next(
            e for e in plays[pa - 1]["playEvents"] if e.get("isPitch") and e["pitchNumber"] == pn
        )

    def frame_file(key, index):
        rel = Path(win[key]["dir"]) / f"frame_{index:06d}.jpg"
        full = ROOT / rel
        if not full.is_file():
            return None
        return {
            "path": rel.as_posix(),
            "image_sha256": hashlib.sha256(full.read_bytes()).hexdigest(),
        }

    timing_rows, point_frames, decision_frames, box_frames, rubber_frames, catches = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    stats = {"estimated": 0, "unavailable": 0}
    for key in sorted(win, key=lambda k: tuple(int(v) for v in k.split(":"))):
        pa, pn = (int(v) for v in key.split(":"))
        a, b = reads.get(key, {}).get("A"), reads.get(key, {}).get("B")
        e = event(pa, pn)
        s = decide_setup(a, b)
        if s["frame_index"] is None:
            s["frame_index"] = int(round(Fraction(str(release[key])) * FPS))
        ff = frame_file(key, s["frame_index"])
        if ff is None:
            idx = min(
                (f["frame_index"] for f in win[key]["frames"]),
                key=lambda i: abs(i - s["frame_index"]),
            )
            s["note"] += f"; frame {s['frame_index']} not in the cut window, evidence uses {idx}"
            s["frame_index"], ff = idx, frame_file(key, idx)
            if s["status"] == "estimated":
                s.update(status="unavailable", reason="setup_frame_outside_cut_window", mitt=None)
                s.update(front=None, unc=None)
        t = float(Fraction(s["frame_index"]) / FPS)
        release_frame = next(
            (x.get("release_frame") for x in (a, b) if x and x.get("release_frame") is not None),
            None,
        )
        timing_rows.append(
            {
                "game_pk": game,
                "at_bat_number": pa,
                "pitch_number": pn,
                "play_id": e.get("playId"),
                "status": "annotated",
                "decision_seconds": t,
                "decision_frame_index": s["frame_index"],
                "release_seconds": float(Fraction(release_frame) / FPS)
                if release_frame is not None
                else None,
                "uncertainty_seconds": 0.05,
                "note": "condensed game; decision frame = last live centre-field frame before "
                "release with the glove presented (two assistant readers)",
            }
        )
        stats[s["status"]] += 1
        point_frames.append(
            {
                "at_bat_number": pa,
                "pitch_number": pn,
                "frame_seconds": t,
                "frame_index": s["frame_index"],
                "image_sha256": ff["image_sha256"],
                "path": ff["path"],
                "status": s["status"],
                "unavailable_reason": None if s["status"] == "estimated" else s["reason"],
                "mitt_center": s["mitt"],
                "mitt_visible_fraction": (a or b or {}).get("mitt_visible_fraction")
                if s["status"] == "estimated"
                else None,
                "uncertainty_pixels": s["unc"],
                "plate_corners": s["front"],
                "plate_corners_reason": None if s["front"] else "not read",
                "camera": "centre_field",
                "note": s["note"],
            }
        )
        pair = [(k, x) for k, x in (("A", a), ("B", b)) if x]
        decision_frames.append(
            {
                "at_bat_number": pa,
                "pitch_number": pn,
                "frame_index": s["frame_index"],
                "readers": {
                    k: {"plate_front": x.get("setup_plate_front"), "chalk": None, "kzone": None}
                    for k, x in pair
                },
            }
        )
        box_frames.append(
            {
                "at_bat_number": pa,
                "pitch_number": pn,
                "plate_front_width_px": math.dist(
                    s["front"]["front_left"], s["front"]["front_right"]
                )
                if s["front"]
                else None,
                "plate_front_width_source": "averaged setup-frame front edge (assistant readers)",
                "readers": {
                    k: {"left_box": x.get("left_box"), "right_box": x.get("right_box")}
                    for k, x in pair
                },
            }
        )
        rubber_frames.append(
            {
                "frame": key,
                "readers": {
                    k: {
                        "plate_front": x.get("setup_plate_front"),
                        "rubber_center": x.get("rubber_center"),
                        "rubber_width_px": x.get("rubber_width_px"),
                    }
                    for k, x in pair
                },
            }
        )
        c = (e.get("pitchData") or {}).get("coordinates") or {}
        if all(k in c for k in TRAJECTORY_KEYS):
            depth = {}
            for y in CATCH_DEPTHS:
                x_, z_ = traj_at_y(c, y)
                depth[str(y)] = {"x": x_, "z": z_}
            catches.append(
                {
                    "at_bat_number": pa,
                    "pitch_number": pn,
                    "call": e["details"]["call"]["description"],
                    "pitch_type": (e["details"].get("type") or {}).get("code"),
                    "statcast_front": {"pX": c.get("pX"), "pZ": c.get("pZ")},
                    "statcast_at_depth_y": depth,
                    "readers": {
                        k: {
                            "chosen_offset": x.get("catch_frame"),
                            "chosen_reason": x.get("catch_reason"),
                            "pocket_center": x.get("pocket_center"),
                            "plate_front": x.get("catch_plate_front"),
                            "uncertainty_pixels": x.get("catch_uncertainty_pixels"),
                            "frames": [
                                {
                                    "offset": x.get("catch_frame"),
                                    "ball_center": x.get("pocket_center")
                                    if x.get("ball_visible_in_catch_frame")
                                    else None,
                                }
                            ],
                            "note": x.get("note"),
                        }
                        for k, x in pair
                    },
                }
            )
    cg = source["condensed_game"]
    num, den = (int(v) for v in cg["probe"]["r_frame_rate"].split("/"))
    selection = (
        f"only the {len(win)} of {scan['feed_pitches']} pitches the condensed game shows and the "
        "scan matched (mostly the last pitch of a plate appearance); not a random sample"
    )
    timing = {
        "schema": "intent_broadcast_timing_v0",
        "game_pk": game,
        "source": {
            "kind": "official MLB condensed game (mp4Avc rendition from the statsapi content endpoint)",
            "media_url": cg["media_url"],
            "fps": f"{num}/{den}",
            "selection": selection,
        },
        "annotations": timing_rows,
    }
    points = {
        "schema": "intent_points_v0",
        "game_pk": game,
        "method": {"kind": "assistant_visual_estimate", "version": "v0"},
        "label_source": "assistant_visual_estimate",
        "video": {
            "fps_num": num,
            "fps_den": den,
            "basis": "ffprobe r_frame_rate of the condensed-game MP4",
            "frame_index_rule": "frames cut by source frame index (accurate seek), so frame_index is exact",
        },
        "uncertainty_basis": "max of the two readers' stated +/- and half their disagreement, "
        "original pixels; not measured against ground truth",
        "method_notes": {
            "description": "Two Claude Code workflow agents per pitch read 20-fps frame windows "
            "(2x gridded crops) of the official condensed game (intent/workflows/condensed_read.js); "
            "the decision frame is the last live centre-field frame before release with the glove "
            "presented; points averaged when both readers chose the same frame, otherwise reader "
            "A's; abstain when the readers' mitt points are more than 15 px apart or only one "
            "reader found a setup frame (python -m intent.condensed assemble).",
            "selection_bias": "condensed games show mostly plate-appearance-ending pitches "
            "(balls in play, strikeouts); the pitches are not representative of the game",
        },
        "frames": point_frames,
    }
    readings = {
        "schema": "intent_calibration_readings_v0",
        "game_pk": game,
        "readers": "two independent Claude Code workflow agents (A, B) per pitch on 20-fps windows "
        "of the condensed game; no human reading",
        "decision_frames": decision_frames,
        "catch_pitches": catches,
        "box_frames": box_frames,
        "rubber_frames": rubber_frames,
        "pan_from_plate_quads": None,
        "critique": [],
    }
    blob = json.dumps(readings, ensure_ascii=False, indent=1, allow_nan=False)
    readings["readings_sha256"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return timing, points, readings, stats


def cmd_assemble(args):
    reads = collect_reads(load_reader_results(args.reads))
    timing, points, readings, stats = assemble(
        args.game,
        reads,
        _load(RESULTS / f"game_{args.game}_condensed_windows_v0.json"),
        _load(RESULTS / f"game_{args.game}_condensed_scan_v0.json"),
        _load(RAW / str(args.game) / "feed.json"),
        _load(RESULTS / f"game_{args.game}_condensed_source_v0.json"),
    )
    _write_json(RESULTS / f"game_{args.game}_timing.json", timing)
    _write_json(RESULTS / f"game_{args.game}_intent_points_v0.json", points)
    _write_json(RESULTS / f"game_{args.game}_intent_calibration_readings_v0.json", readings)
    reasons = {}
    for f in points["frames"]:
        if f["status"] != "estimated":
            reasons[f["unavailable_reason"]] = reasons.get(f["unavailable_reason"], 0) + 1
    print(json.dumps({"pitches": len(points["frames"]), **stats, "reasons": reasons}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("source")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--ffprobe", default="ffprobe")
    p.set_defaults(func=cmd_source)
    p = sub.add_parser("sheets")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.set_defaults(func=cmd_sheets)
    p = sub.add_parser("map")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--scan", type=Path, required=True)
    p.add_argument("--resolve", type=Path, default=None)
    p.set_defaults(func=cmd_map)
    p = sub.add_parser("read-args")
    p.add_argument("--game", type=int, required=True)
    p.set_defaults(func=cmd_read_args)
    p = sub.add_parser("assemble")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--reads", type=Path, required=True)
    p.set_defaults(func=cmd_assemble)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
