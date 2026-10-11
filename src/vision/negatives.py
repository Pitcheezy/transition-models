"""Abstention check for the scoreboard reader on frames outside the decision-frame eval set.

A negatives document (``mlb_scoreboard_negatives_v1``) lists playback seconds of the same MP4
where a human verified that the count bug is hidden, replaced or, for control frames, visible
on a cutaway. For each frame ``readable`` holds the fields a human could read (with the value
read); every other field must be abstained by a reader. Scoring counts, per frame and overall:

* ``false_reads``  — non-null output on a field the human could not read (any value);
* ``wrong_reads``  — output differs from the human reading on a readable field;
* ``correct_reads`` — output equals the human reading;
* ``missed_reads`` — null output on a readable field (over-abstention).

Frames here are never labels for a recognizer; they only measure abstention behaviour.
"""

NEGATIVES_SCHEMA = "mlb_scoreboard_negatives_v1"
LABEL_FIELDS = (
    "balls",
    "strikes",
    "outs",
    "runner_on_1b",
    "runner_on_2b",
    "runner_on_3b",
    "inning",
    "inning_topbot",
    "home_score",
    "away_score",
)
KINDS = ("graphic", "flashback", "replay", "line_score", "other_camera", "cutaway_readable")


def validate_negatives(document, evalset):
    """The negatives must describe the same game, manifest and media as the eval set."""
    if document.get("schema") != NEGATIVES_SCHEMA:
        raise ValueError(f"Expected {NEGATIVES_SCHEMA}")
    for field in ("game_pk", "manifest_sha256"):
        if document.get(field) != evalset.get(field):
            raise ValueError(f"Negatives {field} does not match the evaluation set")
    if document.get("media_url") != evalset["source"]["media_url"]:
        raise ValueError("Negatives media_url does not match the evaluation set source")
    if document.get("observed_source") != evalset.get("observed_source"):
        raise ValueError("Negatives must declare human readings, not OCR")
    seen = set()
    decision = {e["frame_seconds"] for e in evalset["entries"]}
    for frame in document.get("frames", []):
        seconds = frame["seconds"]
        if not isinstance(seconds, int | float) or seconds < 0 or seconds in seen:
            raise ValueError(f"Bad or duplicate negative frame time {seconds}")
        if seconds in decision:
            raise ValueError(f"Negative frame {seconds} is a decision frame of the eval set")
        seen.add(seconds)
        if frame.get("kind") not in KINDS:
            raise ValueError(f"Unknown negative frame kind at {seconds}")
        readable = frame.get("readable")
        if not isinstance(readable, dict) or not set(readable) <= set(LABEL_FIELDS):
            raise ValueError(f"readable must map label fields to values at {seconds}")
        if frame["kind"] == "cutaway_readable" and set(readable) != set(LABEL_FIELDS):
            raise ValueError(f"cutaway_readable frames must give every field at {seconds}")
        if frame["kind"] != "cutaway_readable" and frame["kind"] != "line_score" and readable:
            raise ValueError(f"{frame['kind']} frames cannot have readable fields at {seconds}")
    return document["frames"]


def _same(value, truth):
    if type(truth) is bool:
        return type(value) is bool and value == truth
    if type(truth) is int:
        return type(value) is int and value == truth
    return isinstance(value, str) and value == truth


def score_negatives(frames, outputs):
    """``outputs`` maps seconds -> reader fields (None = abstain)."""
    per_frame, totals = (
        [],
        {"false_reads": 0, "wrong_reads": 0, "correct_reads": 0, "missed_reads": 0},
    )
    for frame in frames:
        fields = outputs[frame["seconds"]]
        readable = frame["readable"]
        counts = {"false_reads": [], "wrong_reads": [], "correct_reads": [], "missed_reads": []}
        for name in LABEL_FIELDS:
            value = fields.get(name)
            if name in readable:
                if value is None:
                    counts["missed_reads"].append(name)
                elif _same(value, readable[name]):
                    counts["correct_reads"].append(name)
                else:
                    counts["wrong_reads"].append(name)
            elif value is not None:
                counts["false_reads"].append(name)
        for key, names in counts.items():
            totals[key] += len(names)
        per_frame.append({"seconds": frame["seconds"], "kind": frame["kind"], **counts})
    unreadable_fields = sum(len(LABEL_FIELDS) - len(f["readable"]) for f in frames)
    readable_fields = sum(len(f["readable"]) for f in frames)
    return {
        "schema": "mlb_scoreboard_negatives_score_v1",
        "frames": len(frames),
        "unreadable_fields": unreadable_fields,
        "readable_fields": readable_fields,
        "totals": totals,
        "abstain_rate_on_unreadable": (
            (unreadable_fields - totals["false_reads"]) / unreadable_fields
            if unreadable_fields
            else None
        ),
        "correct_rate_on_readable": (
            totals["correct_reads"] / readable_fields if readable_fields else None
        ),
        "per_frame": per_frame,
        "note": "false_reads are confident outputs where a human could read nothing; the goal is 0",
    }
