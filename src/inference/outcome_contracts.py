"""Explicit outcome axes and validation; semantic correspondence is not probability conversion.

The teammate axes describe a reviewed source snapshot, not an agreed or live service contract.
This module does not connect a service, alter a model, or enable unsupported UI marginals.
"""

from collections.abc import Mapping, Set
from dataclasses import dataclass
from math import fsum, isfinite
from numbers import Integral, Real
from types import MappingProxyType

LEGACY10_SCHEMA = "transition_models_legacy10_v1"
SERVICE10_SCHEMA = "pitcheezy_pitchmdp10_9d09694_v1"
RESEARCH11_SCHEMA = "pitcheezy_research11_9d09694_v1"
OBSERVATION8_SCHEMA = "pitch_observation_v1"
TEAMMATE_COMMIT = "9d096940b6fe065051979cd7ef4dbfde006e35c6"
PROBABILITY_SUM_TOLERANCE = 1e-5
PITCH_KEYS = ("game_pk", "at_bat_number", "pitch_number")


@dataclass(frozen=True)
class OutcomeContract:
    """Immutable class order, per-class meanings and evidence for one named schema."""

    schema_id: str
    class_names: tuple[str, ...]
    definitions: tuple[str, ...]
    evidence: tuple[str, ...]
    conversion_limits: tuple[str, ...]


def _teammate(path):
    return f"SongRoute/pitcheezy@{TEAMMATE_COMMIT}:{path}"


CONTRACTS = MappingProxyType(
    {
        LEGACY10_SCHEMA: OutcomeContract(
            LEGACY10_SCHEMA,
            (
                "Ball",
                "Strike",
                "Single",
                "Double",
                "Triple",
                "HomeRun",
                "FieldOut",
                "Strikeout",
                "Walk",
                "HitByPitch",
            ),
            (
                "Nonterminal ball descriptions, including automatic_ball; excludes terminal walks.",
                "Nonterminal strikes and fouls/foul bunts/tips; includes automatic_strike.",
                "events=single (event takes precedence over description).",
                "events=double (event takes precedence over description).",
                "events=triple (event takes precedence over description).",
                "events=home_run (event takes precedence over description).",
                "Listed in-play outs, double/triple plays, sacrifices, fielders_choice and field_error.",
                "events=strikeout or strikeout_double_play; underlying pitch subtype is lost.",
                "events=walk, intent_walk or catcher_interf; not solely walks on four balls.",
                "events=hit_by_pitch or the same description when no event is present.",
            ),
            (
                "src/data/features.py:PitchResult10,map_to_10class",
                "src/data/point_data.py:CLASS_NAMES",
            ),
            (
                "Legacy Strike merges nonterminal strike/foul mixtures, which cannot be separated.",
                "Legacy Strikeout includes strikeout_double_play; Walk includes catcher_interf.",
                "Legacy FieldOut includes field_error and fielders_choice, not only actual outs.",
                "Event-first terminal labels and included administrative events differ by schema.",
            ),
        ),
        SERVICE10_SCHEMA: OutcomeContract(
            SERVICE10_SCHEMA,
            (
                "ball",
                "strike",
                "foul",
                "out",
                "single",
                "double",
                "triple",
                "home_run",
                "hbp",
                "double_play",
            ),
            (
                "Ball descriptions, including intent_ball; planner derives a walk at three balls.",
                "Called/swinging strikes, missed bunts and tips; includes foul_bunt at two strikes.",
                "foul or foul_bunt except two-strike foul_bunt; planner retains two-strike fouls.",
                "hit_into_play plus field_out/force_out/fielders_choice_out/sac_fly/sac_bunt.",
                "hit_into_play plus single.",
                "hit_into_play plus double.",
                "hit_into_play plus triple.",
                "hit_into_play plus home_run.",
                "description=hit_by_pitch.",
                "hit_into_play plus double_play/grounded_into_double_play or sacrifice double plays.",
            ),
            (
                _teammate(
                    "experiments/pitchmdp/pitchmdp/model.py:OUTCOMES,outcome_labels,eligible"
                ),
                _teammate("experiments/pitchmdp/pitchmdp/planner.py:OUTCOMES"),
                _teammate("experiments/pitchmdp/scripts/minimal_pitch_service.py:Engine"),
            ),
            (
                "Service ball/strike include terminal pitches; walks/strikeouts are count-derived.",
                "Two-strike foul_bunt maps to strike, while ordinary two-strike foul remains foul.",
                "Service out/double_play cover narrower events; errors, interference and triple plays "
                "cannot be recovered from this ten-class vector.",
                "Outcome-label support and supported_pa/feature eligibility restrict the source population.",
            ),
        ),
        RESEARCH11_SCHEMA: OutcomeContract(
            RESEARCH11_SCHEMA,
            ("ball", "strike", "foul", "K", "BB", "HBP", "1B", "2B", "3B", "HR", "in_play_out"),
            (
                "Nonterminal ball descriptions including automatic_ball and intent_ball.",
                "Nonterminal called/swinging strikes, tips, missed bunts and automatic_strike.",
                "Nonterminal foul/foul_bunt/foul_pitchout after terminal event precedence.",
                "events=strikeout or strikeout_double_play.",
                "events=walk or intent_walk; catcher_interf is not BB.",
                "description=hit_by_pitch after K/BB event precedence.",
                "hit_into_play plus single.",
                "hit_into_play plus double.",
                "hit_into_play plus triple.",
                "hit_into_play plus home_run.",
                "hit_into_play plus every other event, including errors, interference, unknown or missing events.",
            ),
            (_teammate("src/pitcheezy/interfaces/outcomes.py:OUTCOME_NAMES,outcome_id,rule_mask"),),
            (
                "Research in_play_out is a broad fallback, including unknown/missing in-play events.",
                "Research BB excludes catcher_interf; K and in_play_out discard pitch/play subtypes.",
                "Nonterminal labels and terminal count masks differ from the service outcome axis.",
            ),
        ),
        OBSERVATION8_SCHEMA: OutcomeContract(
            OBSERVATION8_SCHEMA,
            (
                "ball",
                "called_strike",
                "swinging_strike",
                "foul",
                "caught_foul_tip",
                "hit",
                "in_play_no_hit",
                "hit_by_pitch",
            ),
            (
                "Physical ball descriptions, including intent_ball; terminal event retained separately.",
                "description=called_strike, including a terminal strikeout pitch.",
                "Swinging strike descriptions or missed_bunt, including a terminal strikeout pitch.",
                "foul/foul_bunt even when foul_bunt ends the plate appearance with a strikeout.",
                "foul_tip/bunt_foul_tip; terminal event retained separately.",
                "hit_into_play plus single/double/triple/home_run, combined into one class.",
                "hit_into_play plus listed non-hit events, including errors and double/triple plays.",
                "description=hit_by_pitch; catcher interference is excluded separately.",
            ),
            ("src/data/pitch_observation.py:OBSERVATION_CLASSES,build_observation_targets",),
            (
                "Observation hit collapses single/double/triple/home_run and cannot recover hit types.",
                "Observation classes do not encode terminal PA events; counts alone do not recover "
                "double plays or the discarded event details.",
                "Administrative pitches and catcher_interf are excluded from observation targets.",
            ),
        ),
    }
)


@dataclass(frozen=True)
class ClassCorrespondence:
    """Related labels for documentation, never an equality or conversion matrix."""

    concept: str
    legacy: tuple[str, ...]
    service: tuple[str, ...]
    research: tuple[str, ...]
    observation: tuple[str, ...]
    caveat: str


CORRESPONDENCES = (
    ClassCorrespondence(
        "ball/walk",
        ("Ball", "Walk"),
        ("ball",),
        ("ball", "BB"),
        ("ball",),
        "Terminal handling, interference and administrative-event support differ.",
    ),
    ClassCorrespondence(
        "strike/foul/strikeout",
        ("Strike", "Strikeout"),
        ("strike", "foul"),
        ("strike", "foul", "K"),
        ("called_strike", "swinging_strike", "foul", "caught_foul_tip"),
        "Legacy loses foul/subtype detail; two-strike foul bunts have different labels.",
    ),
    ClassCorrespondence(
        "recorded hit",
        ("Single", "Double", "Triple", "HomeRun"),
        ("single", "double", "triple", "home_run"),
        ("1B", "2B", "3B", "HR"),
        ("hit",),
        "Hit types collapse in observation8; source populations still differ.",
    ),
    ClassCorrespondence(
        "in-play non-hit",
        ("FieldOut",),
        ("out", "double_play"),
        ("in_play_out",),
        ("in_play_no_hit",),
        "Different support for errors, interference, choices, double and triple plays.",
    ),
    ClassCorrespondence(
        "hit by pitch",
        ("HitByPitch",),
        ("hbp",),
        ("HBP",),
        ("hit_by_pitch",),
        "Related recorded event, but precedence and retained populations differ.",
    ),
)


def get_contract(schema_id):
    """Resolve an explicit schema ID, with no inference from vector length or spelling."""
    if not isinstance(schema_id, str) or schema_id not in CONTRACTS:
        raise ValueError(f"Unknown outcome schema: {schema_id!r}; use an explicit registered ID")
    return CONTRACTS[schema_id]


def validate_probabilities(schema_id, probabilities, *, class_names=None):
    """Return a canonical-order mapping without renormalization; vectors require exact names.

    Mappings carry their own names, so insertion order has no semantic meaning. Duplicate
    names must be rejected before constructing a mapping if the source was a JSON object.
    """
    expected = get_contract(schema_id).class_names
    if class_names is not None:
        if isinstance(class_names, (str, bytes, Mapping, Set)):
            raise ValueError("class_names must be the explicit ordered outcome axis")
        try:
            names = tuple(class_names)
        except TypeError as exc:
            raise ValueError("class_names must be the explicit ordered outcome axis") from exc
        if any(not isinstance(name, str) for name in names) or names != expected:
            raise ValueError(
                "class_names must match the schema exactly, including order and uniqueness"
            )
    if isinstance(probabilities, Mapping):
        if set(probabilities) != set(expected) or len(probabilities) != len(expected):
            raise ValueError("Probability mapping must have exactly the schema's class names")
        values = [probabilities[name] for name in expected]
    else:
        if class_names is None:
            raise ValueError("Probability vectors require explicit class_names in canonical order")
        if isinstance(probabilities, (str, bytes, Set)):
            raise ValueError("Probabilities must be a numeric vector or a named mapping")
        try:
            values = list(probabilities)
        except TypeError as exc:
            raise ValueError("Probabilities must be a numeric vector or a named mapping") from exc
        if len(values) != len(expected):
            raise ValueError("Probability vector length does not match the schema")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Probabilities must be real numbers, not booleans or coerced strings")
        try:
            valid = isfinite(value) and 0 <= value <= 1
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Probabilities must be finite values in [0, 1]")
    if abs(fsum(values) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise ValueError("Probabilities must sum to 1; implicit renormalization is forbidden")
    return {name: float(value) for name, value in zip(expected, values, strict=True)}


def convert_probabilities(source_schema, target_schema, probabilities, *, class_names=None):
    """Validate same-schema identity only; globally unsafe cross-schema conversions fail closed."""
    source, target = get_contract(source_schema), get_contract(target_schema)
    if source_schema != target_schema:
        reasons = " ".join((*source.conversion_limits, *target.conversion_limits))
        raise ValueError(
            f"No exact probability conversion from {source_schema} to {target_schema}. "
            f"Class correspondence is semantic only. {reasons}"
        )
    return validate_probabilities(source_schema, probabilities, class_names=class_names)


def align_pitch_rows(reference, rows):
    """Return rows in reference key order after strict one-to-one key and play-ID checks.

    Each side supplies game_pk/at_bat_number/pitch_number and play_id. Other payload fields
    are retained unchanged; validate probability payloads separately against their schema.
    """

    def indexed(items):
        if isinstance(items, (str, bytes, Mapping, Set)):
            raise ValueError("Pitch batches must be ordered collections of row mappings")
        try:
            iterator = iter(items)
        except TypeError as exc:
            raise ValueError("Pitch batches must be ordered collections of row mappings") from exc
        result, play_ids = {}, set()
        for row in iterator:
            if not isinstance(row, Mapping) or any(k not in row for k in (*PITCH_KEYS, "play_id")):
                raise ValueError("Every row requires all pitch keys and play_id")
            if any(
                isinstance(row[k], bool) or not isinstance(row[k], Integral) or row[k] <= 0
                for k in PITCH_KEYS
            ):
                raise ValueError("Pitch keys must be positive integers without coercion")
            key = tuple(int(row[k]) for k in PITCH_KEYS)
            play_id = row["play_id"]
            if not isinstance(play_id, str) or not play_id.strip():
                raise ValueError("play_id must be a nonempty string")
            if key in result or play_id in play_ids:
                raise ValueError("Duplicate pitch key or play_id prevents one-to-one alignment")
            result[key] = row
            play_ids.add(play_id)
        return result

    expected, received = indexed(reference), indexed(rows)
    if expected.keys() != received.keys():
        missing, extra = (
            sorted(expected.keys() - received.keys()),
            sorted(received.keys() - expected.keys()),
        )
        raise ValueError(f"Pitch roster mismatch: missing={missing}, extra={extra}")
    if any(expected[key]["play_id"] != received[key]["play_id"] for key in expected):
        raise ValueError("play_id mismatch for the same pitch key")
    return tuple(dict(received[key]) for key in expected)
