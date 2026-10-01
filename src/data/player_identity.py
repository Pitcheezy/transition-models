"""Manual player-name evidence and conservative roster resolution, separate from feed truth."""

import math
import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

from src.data.blind_review import canonical_hash
from src.data.broadcast_timing import KEYS

ROOT = Path(__file__).resolve().parents[2]
REVIEW_SCHEMA = "mlb_player_identity_review_v1"
SCHEMA = "mlb_player_identity_evalset_v1"
ROLES = ("pitcher", "batter")
VISUAL_FIELDS = {"role", "name_text", "readability", "team", "lineup_order", "evidence", "note"}
NAME_FIELDS = (
    "fullName",
    "nameFirstLast",
    "firstLastName",
    "lastName",
    "useLastName",
    "boxscoreName",
)


def bytes_hash(content):
    """Digest exact input bytes; canonical JSON hashes serve a different purpose."""
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError(f"Unexpected {label} fields")


def _positive(value):
    return type(value) is int and value > 0


def _key(row):
    key = tuple(row.get(k) for k in KEYS)
    if not all(_positive(value) for value in key):
        raise ValueError("Player evidence requires positive integer pitch keys")
    return key


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Evidence times and age limits must be finite nonnegative numbers")
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a SHA256 hex digest")


def normalize_name(text):
    """Normalize case, accents and whitespace only; never fuzzy-match or complete fragments."""
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).upper().split())


def build_name_roster(feed):
    """Freeze names for both complete game-boxscore rosters, without expected-role filtering."""
    people = feed["gameData"]["players"]
    roster = []
    for side in ("away", "home"):
        box = feed["liveData"]["boxscore"]["teams"][side]
        team = feed["gameData"]["teams"][side]
        if box["team"]["id"] != team["id"]:
            raise ValueError("Boxscore and game team identities disagree")
        for person in box["players"].values():
            player_id = person["person"]["id"]
            if not _positive(player_id):
                raise ValueError("Invalid roster player ID")
            details = people.get(f"ID{player_id}", {})
            if details.get("id", player_id) != player_id:
                raise ValueError("Player-name record has the wrong ID")
            aliases = {person["person"]["fullName"]}
            aliases.update(details.get(field) for field in NAME_FIELDS)
            roster.append(
                {
                    "player_id": player_id,
                    "full_name": person["person"]["fullName"],
                    "team": team["abbreviation"],
                    "aliases": sorted(
                        {normalize_name(n) for n in aliases if isinstance(n, str) and n.strip()}
                    ),
                }
            )
    _validate_roster(roster)
    return sorted(roster, key=lambda row: row["player_id"])


def _validate_roster(roster):
    if not isinstance(roster, list) or not roster:
        raise ValueError("A complete frozen name roster is required")
    seen = set()
    for person in roster:
        _fields(person, {"player_id", "full_name", "team", "aliases"}, "roster")
        if not _positive(person["player_id"]) or person["player_id"] in seen:
            raise ValueError("Duplicate or invalid roster player ID")
        seen.add(person["player_id"])
        if any(
            not isinstance(person[k], str) or not person[k].strip() for k in ("full_name", "team")
        ):
            raise ValueError("Roster names and teams must be nonempty strings")
        aliases = person["aliases"]
        if (
            not isinstance(aliases, list)
            or not aliases
            or any(not isinstance(n, str) or not n or normalize_name(n) != n for n in aliases)
            or len(set(aliases)) != len(aliases)
        ):
            raise ValueError("Roster aliases must be distinct normalized strings")


def resolve_name(name_text, readability, team, roster):
    """Return exact-name candidates over the whole roster; neither role nor feed truth is input."""
    if readability != "readable" or name_text is None:
        return []
    name = normalize_name(name_text)
    return sorted(
        person["player_id"]
        for person in roster
        if name in person["aliases"]
        and (team is None or normalize_name(team) == normalize_name(person["team"]))
    )


def _visual(row, source, *, verify_frames=False, root=ROOT):
    if row["role"] not in ROLES or row["readability"] not in ("readable", "partial", "unreadable"):
        raise ValueError("Invalid role or name readability")
    name = row["name_text"]
    if row["readability"] == "unreadable":
        if name is not None:
            raise ValueError("Unreadable names must be null")
    elif not isinstance(name, str) or not name.strip():
        raise ValueError("Readable/partial names require literal visible text")
    if row["team"] is not None and (not isinstance(row["team"], str) or not row["team"].strip()):
        raise ValueError("Observed team must be null or literal text")
    order = row["lineup_order"]
    if order is not None and (
        type(order) is not int or not 1 <= order <= 9 or row["role"] != "batter"
    ):
        raise ValueError("Observed lineup order must be a batter slot 1..9 or null")
    if not isinstance(row["note"], str) or not row["note"].strip():
        raise ValueError("Direct observation notes are required")
    evidence = row["evidence"]
    _fields(evidence, {"media_url", "frame_seconds", "image_sha256", "path"}, "visual evidence")
    if evidence["media_url"] != source["media_url"]:
        raise ValueError("Evidence is from a different media source")
    _number(evidence["frame_seconds"])
    if evidence["frame_seconds"] > source["duration_seconds"]:
        raise ValueError("Evidence exceeds the source duration")
    _hash(evidence["image_sha256"])
    if not isinstance(evidence["path"], str) or not evidence["path"]:
        raise ValueError("Evidence requires an image path")
    root = Path(root).resolve()
    path = (root / evidence["path"]).resolve()
    if Path(evidence["path"]).is_absolute() or not path.is_relative_to(root):
        raise ValueError("Evidence paths must stay within the repository")
    if verify_frames:
        from src.vision.frames import verify_cached_frame

        if bytes_hash(path.read_bytes()) != evidence["image_sha256"]:
            raise ValueError("Evidence image hash changed")
        if not verify_cached_frame(
            path, evidence["media_url"], evidence["frame_seconds"], root=root
        ):
            raise ValueError("Image lacks a matching source/time/hash cache receipt or provenance")


def _derive(document, *, verify_frames=False, root=ROOT):
    """Recompute decisions using only frozen observations, roster and the declared hold policy."""
    review, source = document["review"], document["source"]
    _fields(source, {"page_url", "media_url", "duration_seconds"}, "source")
    if (
        any(
            not isinstance(source[k], str) or not source[k].strip()
            for k in ("page_url", "media_url")
        )
        or _number(source["duration_seconds"]) <= 0
    ):
        raise ValueError("An identified positive-duration source is required")
    _fields(
        document["protocol"],
        {"stale_after_seconds", "reference_kind", "name_matching", "lineup_order"},
        "identity protocol",
    )
    if (
        document["protocol"]["reference_kind"] != "feed_final_hindsight_not_live_availability"
        or document["protocol"]["name_matching"]
        != "exact_normalized_full_game_roster_no_expected_role_filter"
        or document["protocol"]["lineup_order"] != "visual_metadata_only_never_used_to_infer_ID"
    ):
        raise ValueError("Unsupported identity protocol semantics")
    _fields(
        review,
        {
            "schema",
            "game_pk",
            "manifest_sha256",
            "timing_sha256",
            "feed_sha256",
            "source",
            "reviewed_by",
            "reviewer_kind",
            "reviewed_on",
            "rows",
            "context_observations",
        },
        "manual review",
    )
    if review["schema"] != REVIEW_SCHEMA or review["game_pk"] != document["game_pk"]:
        raise ValueError("Wrong manual review schema or game")
    _fields(review["source"], {"media_url"}, "review source")
    if review["source"]["media_url"] != source["media_url"]:
        raise ValueError("Review source mismatch")
    for name in ("manifest_sha256", "timing_sha256", "feed_sha256"):
        _hash(review[name])
        if review[name] != document["input_hashes"][name]:
            raise ValueError(f"Review {name} does not match frozen inputs")
    if (
        not isinstance(review["reviewed_by"], str)
        or not review["reviewed_by"].strip()
        or review["reviewer_kind"] not in ("human", "ai", "ai_assisted", "mixed")
    ):
        raise ValueError("Reviewer identity and method are required")
    if (
        not isinstance(review["reviewed_on"], str)
        or date.fromisoformat(review["reviewed_on"]).isoformat() != review["reviewed_on"]
    ):
        raise ValueError("Review date must be YYYY-MM-DD")
    _validate_roster(document["roster"])
    if any(
        not isinstance(value, list)
        for value in (document["opportunities"], review["rows"], review["context_observations"])
    ):
        raise ValueError("Opportunities, observations and context must be lists")
    opportunities, first_in_pa, play_ids = {}, {}, set()
    ids = {person["player_id"] for person in document["roster"]}
    for opportunity in document["opportunities"]:
        _fields(opportunity, {*KEYS, "play_id", "decision_seconds", "reference_ids"}, "opportunity")
        key = _key(opportunity)
        if (
            key[0] != document["game_pk"]
            or key in opportunities
            or opportunity["play_id"] in play_ids
        ):
            raise ValueError("Unknown or duplicate opportunity identity")
        if not isinstance(opportunity["play_id"], str) or not opportunity["play_id"]:
            raise ValueError("Opportunity play_id is required")
        decision = _number(opportunity["decision_seconds"])
        if decision > source["duration_seconds"]:
            raise ValueError("Decision exceeds source duration")
        _fields(opportunity["reference_ids"], ROLES, "reference IDs")
        if any(
            not _positive(value) or value not in ids
            for value in opportunity["reference_ids"].values()
        ):
            raise ValueError("Reference identity is not in the frozen roster")
        opportunities[key] = opportunity
        first_in_pa[key[1]] = min(first_in_pa.get(key[1], decision), decision)
        play_ids.add(opportunity["play_id"])
    if not opportunities:
        raise ValueError("No player identity opportunities")
    observed = {}
    for row in review["rows"]:
        _fields(row, {*KEYS, "play_id", "continuity", *VISUAL_FIELDS}, "observed row")
        key = _key(row)
        if key not in opportunities or row["play_id"] != opportunities[key]["play_id"]:
            raise ValueError("Observed pitch/play_id does not match opportunity")
        _visual(row, source, verify_frames=verify_frames, root=root)
        identity = (*key, row["role"])
        if identity in observed or row["continuity"] not in ("confirmed", "changed", "unknown"):
            raise ValueError("Duplicate role observation or invalid continuity")
        observed[identity] = row
        t = row["evidence"]["frame_seconds"]
        if t > opportunities[key]["decision_seconds"]:
            raise ValueError("Future evidence cannot identify a pre-pitch player")
        if t != opportunities[key]["decision_seconds"]:
            raise ValueError(
                "Row evidence must be the decision frame; held IDs require prior confirmed state"
            )
    if set(observed) != {(*key, role) for key in opportunities for role in ROLES}:
        raise ValueError("Every selected pitch requires exactly two role observations")
    for row in review["context_observations"]:
        _fields(row, {"scope_at_bat_number", *VISUAL_FIELDS}, "context observation")
        if (
            not _positive(row["scope_at_bat_number"])
            or row["scope_at_bat_number"] not in first_in_pa
        ):
            raise ValueError("Context observation has an unknown PA scope")
        _visual(row, source, verify_frames=verify_frames, root=root)
    limit = _number(document["protocol"]["stale_after_seconds"])
    state, results = {}, []
    ordered = sorted(opportunities)
    if any(
        opportunities[b]["decision_seconds"] <= opportunities[a]["decision_seconds"]
        for a, b in zip(ordered, ordered[1:], strict=False)
    ):
        raise ValueError("Decision times contradict pitch order")
    for key in ordered:
        opportunity = opportunities[key]
        for role in ROLES:
            row = observed[(*key, role)]
            decision, t = opportunity["decision_seconds"], row["evidence"]["frame_seconds"]
            scope = (key[1], role)
            if row["continuity"] != "confirmed":
                state.pop(scope, None)
            candidates = resolve_name(
                row["name_text"], row["readability"], row["team"], document["roster"]
            )
            player_id, age, stale, status, reason, origin = (
                None,
                None,
                False,
                "abstain",
                "name_not_readable",
                None,
            )
            if len(candidates) == 1:
                age, origin = decision - t, row["evidence"]
                player_id, status, reason = candidates[0], "observed", "unique_exact_name"
                state[scope] = (player_id, t, origin)
            elif row["readability"] != "unreadable":
                reason = "ambiguous_name" if len(candidates) > 1 else "partial_or_unmatched_name"
                state.pop(scope, None)
            elif row["continuity"] == "confirmed" and scope in state:
                previous, seen_at, origin = state[scope]
                age, stale = decision - seen_at, decision - seen_at > limit
                previous_team = next(
                    person["team"]
                    for person in document["roster"]
                    if person["player_id"] == previous
                )
                if row["team"] is not None and normalize_name(row["team"]) != normalize_name(
                    previous_team
                ):
                    reason = "held_team_contradiction"
                    state.pop(scope, None)
                elif not stale:
                    player_id, status, reason = previous, "held", "confirmed_continuity"
                else:
                    reason = "stale"
                    state.pop(scope, None)
            elif row["continuity"] != "confirmed":
                reason = "continuity_" + row["continuity"]
            reference_id = opportunity["reference_ids"][role]
            results.append(
                {
                    **dict(zip(KEYS, key, strict=True)),
                    "play_id": opportunity["play_id"],
                    "role": role,
                    "decision_seconds": decision,
                    "status": status,
                    "resolved_player_id": player_id,
                    "candidate_ids": candidates,
                    "age_seconds": age,
                    "stale": stale,
                    "reason": reason,
                    "identity_evidence": origin,
                    "reference_player_id": reference_id,
                    "matches_hindsight_reference": None
                    if player_id is None
                    else player_id == reference_id,
                }
            )
    counts = Counter(row["status"] for row in results)
    summary = {
        "role_opportunities": len(results),
        **{name: counts[name] for name in ("observed", "held", "abstain")},
        "matches_hindsight_reference": sum(
            row["matches_hindsight_reference"] is True for row in results
        ),
        "mismatches_hindsight_reference": sum(
            row["matches_hindsight_reference"] is False for row in results
        ),
        "context_only": len(review["context_observations"]),
        "note": "Manual selected-frame name resolution against a frozen final-feed roster; not automatic recognition accuracy.",
    }
    return results, summary


def build_player_identity_evalset(
    manifest, timing, feed, review, *, feed_sha256, stale_after_seconds=30
):
    """Freeze references separately; derive identity only from observed names and the full roster."""
    if (
        manifest.get("schema") != "mlb_video_manifest_v1"
        or timing.get("schema") != "mlb_broadcast_timing_v1"
    ):
        raise ValueError("Unsupported manifest or timing schema")
    game = manifest["game_pk"]
    hashes = {
        "manifest_sha256": canonical_hash(manifest),
        "timing_sha256": canonical_hash(timing),
        "feed_sha256": feed_sha256,
        "review_sha256": canonical_hash(review),
    }
    _hash(feed_sha256)
    if (
        feed["gamePk"] != game
        or timing["game_pk"] != game
        or timing["manifest_sha256"] != hashes["manifest_sha256"]
    ):
        raise ValueError("Manifest, timing and feed identities disagree")
    if feed["gameData"]["status"]["abstractGameState"] != "Final":
        raise ValueError("This evaluation contract requires a frozen final-feed reference")
    if manifest.get("feed_sha256") != feed_sha256:
        raise ValueError("Feed bytes do not match the manifest's frozen feed hash")
    scoped_pas = {_key(row)[1] for row in review["rows"]}
    reference = {}
    for play in feed["liveData"]["plays"]["allPlays"]:
        pa = play["about"]["atBatIndex"] + 1
        if pa in scoped_pas:
            # A substitution or defensive switch recorded BEFORE the plate appearance's first
            # pitch only explains who starts the PA, so the PA-level matchup still holds for
            # every pitch. One recorded after a pitch could change the pitcher or batter in
            # the middle of the PA, where no per-pitch reference exists: refuse that PA.
            events = play["playEvents"]
            first_pitch = next((i for i, e in enumerate(events) if e.get("isPitch")), len(events))
            if any(
                i >= first_pitch
                and (
                    event.get("isSubstitution")
                    or "substitution" in str(event.get("details", {}).get("eventType", ""))
                    or event.get("details", {}).get("eventType") == "defensive_switch"
                )
                for i, event in enumerate(events)
            ):
                raise ValueError(
                    "Scoped PA has a substitution/switch after its first pitch; "
                    "PA-level matchup is not a safe per-pitch reference"
                )
        for event in play["playEvents"]:
            if event.get("isPitch"):
                key = (game, pa, event["pitchNumber"])
                if key in reference:
                    raise ValueError("Duplicate feed pitch key")
                reference[key] = {
                    "play_id": event["playId"],
                    "reference_ids": {role: play["matchup"][role]["id"] for role in ROLES},
                }
    times = {_key(row): row for row in timing["annotations"]}
    if len(times) != len(timing["annotations"]):
        raise ValueError("Duplicate timing pitch key")
    opportunities = []
    seen = set()
    for pitch in manifest["pitches"]:
        key = _key(pitch)
        if key in seen:
            raise ValueError("Duplicate manifest pitch key")
        seen.add(key)
        if key[1] not in scoped_pas:
            continue
        ref, timed = reference.get(key), times.get(key)
        play_id = pitch["video"]["play_id"]
        if (
            not ref
            or not timed
            or timed["status"] != "annotated"
            or pitch["identity_status"] != "verified"
        ):
            raise ValueError(
                "Every pitch in each scoped PA needs verified identity and decision timing"
            )
        if ref["play_id"] != play_id or timed["play_id"] != play_id:
            raise ValueError("Feed, manifest and timing play IDs disagree")
        if any(pitch["pre_state"][role] != ref["reference_ids"][role] for role in ROLES):
            raise ValueError("Manifest and feed reference players disagree")
        opportunities.append(
            {
                **dict(zip(KEYS, key, strict=True)),
                **ref,
                "decision_seconds": timed["decision_seconds"],
            }
        )
    document = {
        "schema": SCHEMA,
        "game_pk": game,
        "input_hashes": hashes,
        "source": timing["source"],
        "protocol": {
            "stale_after_seconds": stale_after_seconds,
            "reference_kind": "feed_final_hindsight_not_live_availability",
            "name_matching": "exact_normalized_full_game_roster_no_expected_role_filter",
            "lineup_order": "visual_metadata_only_never_used_to_infer_ID",
        },
        "roster": build_name_roster(feed),
        "opportunities": sorted(opportunities, key=_key),
        "review": review,
    }
    document["snapshot_sha256"] = canonical_hash(
        {key: document[key] for key in ("roster", "opportunities")}
    )
    document["rows"], document["summary"] = _derive(document)
    return document


def check_player_identity_evalset(document, *, verify_frames=False, root=ROOT):
    """Recompute a frozen snapshot without implying the ignored source feed was reverified."""
    _fields(
        document,
        {
            "schema",
            "game_pk",
            "input_hashes",
            "source",
            "protocol",
            "roster",
            "opportunities",
            "review",
            "snapshot_sha256",
            "rows",
            "summary",
        },
        "identity evalset",
    )
    if document["schema"] != SCHEMA or not _positive(document["game_pk"]):
        raise ValueError("Unsupported player identity evalset")
    _fields(
        document["input_hashes"],
        {"manifest_sha256", "timing_sha256", "feed_sha256", "review_sha256"},
        "input hashes",
    )
    for digest in document["input_hashes"].values():
        _hash(digest)
    if canonical_hash(document["review"]) != document["input_hashes"]["review_sha256"]:
        raise ValueError("Manual review content changed")
    if (
        canonical_hash({key: document[key] for key in ("roster", "opportunities")})
        != document["snapshot_sha256"]
    ):
        raise ValueError("Frozen roster/reference snapshot changed")
    rows, summary = _derive(document, verify_frames=verify_frames, root=root)
    if rows != document["rows"] or summary != document["summary"]:
        raise ValueError("Derived identities or summary do not match frozen evidence")
    return {
        "validation_level": "frozen_snapshot_recomputed",
        "feed_bytes_reverified": False,
        "frame_bytes_reverified": verify_frames,
        **summary,
    }
