"""Synthetic contract tests; no live teammate response or new model result is represented."""

from copy import deepcopy
from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

from src.data.features import PitchResult10, map_to_10class
from src.data.pitch_observation import OBSERVATION_CLASSES, build_observation_targets
from src.inference.outcome_contracts import (
    CONTRACTS,
    CORRESPONDENCES,
    LEGACY10_SCHEMA,
    OBSERVATION8_SCHEMA,
    RESEARCH11_SCHEMA,
    SERVICE10_SCHEMA,
    TEAMMATE_COMMIT,
    align_pitch_rows,
    convert_probabilities,
    get_contract,
    validate_probabilities,
)
from src.inference.prepitch_contract import present_legacy_probabilities


def onehot(schema, name):
    return {label: float(label == name) for label in get_contract(schema).class_names}


def test_contracts_preserve_local_axes_and_snapshot_evidence():
    assert get_contract(LEGACY10_SCHEMA).class_names == tuple(PitchResult10.NAMES.values())
    assert get_contract(OBSERVATION8_SCHEMA).class_names == tuple(OBSERVATION_CLASSES)
    assert get_contract(SERVICE10_SCHEMA).class_names == (
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
    )
    assert get_contract(RESEARCH11_SCHEMA).class_names == (
        "ball",
        "strike",
        "foul",
        "K",
        "BB",
        "HBP",
        "1B",
        "2B",
        "3B",
        "HR",
        "in_play_out",
    )
    for schema, contract in CONTRACTS.items():
        assert contract.schema_id == schema
        assert (
            len(contract.class_names) == len(set(contract.class_names)) == len(contract.definitions)
        )
        assert all(contract.definitions) and contract.conversion_limits
        if schema in (SERVICE10_SCHEMA, RESEARCH11_SCHEMA):
            assert all(TEAMMATE_COMMIT in path for path in contract.evidence)
    with pytest.raises(FrozenInstanceError):
        get_contract(LEGACY10_SCHEMA).schema_id = "changed"
    with pytest.raises(TypeError):
        CONTRACTS[LEGACY10_SCHEMA] = get_contract(SERVICE10_SCHEMA)
    for correspondence in CORRESPONDENCES:
        for field, schema in (
            ("legacy", LEGACY10_SCHEMA),
            ("service", SERVICE10_SCHEMA),
            ("research", RESEARCH11_SCHEMA),
            ("observation", OBSERVATION8_SCHEMA),
        ):
            assert set(getattr(correspondence, field)) <= set(get_contract(schema).class_names)
        assert correspondence.caveat


@pytest.mark.parametrize("schema", list(CONTRACTS))
def test_named_mapping_order_is_irrelevant_but_vector_axis_is_explicit(schema):
    names = get_contract(schema).class_names
    named = onehot(schema, names[-1])
    reversed_mapping = dict(reversed(list(named.items())))
    actual = validate_probabilities(schema, reversed_mapping)
    assert tuple(actual) == names and actual == named
    array = np.array(list(named.values()), dtype=np.float32)
    assert validate_probabilities(schema, array, class_names=np.array(names)) == named
    with pytest.raises(ValueError, match="explicit class_names"):
        validate_probabilities(schema, array)
    with pytest.raises(ValueError, match="order and uniqueness"):
        validate_probabilities(schema, array[::-1], class_names=names[::-1])
    assert convert_probabilities(schema, schema, named) == named


@pytest.mark.parametrize("names_kind", ["duplicate", "missing", "extra", "string", "set"])
def test_invalid_class_names_are_rejected(names_kind):
    names = get_contract(SERVICE10_SCHEMA).class_names
    bad = {
        "duplicate": names[:-1] + (names[0],),
        "missing": names[:-1],
        "extra": names + ("unknown",),
        "string": ",".join(names),
        "set": set(names),
    }[names_kind]
    with pytest.raises(ValueError, match="class_names"):
        validate_probabilities(SERVICE10_SCHEMA, [0.1] * 10, class_names=bad)


def test_schema_identity_is_never_inferred_from_equal_vector_lengths():
    with pytest.raises(ValueError, match="Unknown outcome schema"):
        validate_probabilities("10-class", [0.1] * 10)
    with pytest.raises(ValueError, match="class_names"):
        validate_probabilities(
            SERVICE10_SCHEMA, [0.1] * 10, class_names=get_contract(LEGACY10_SCHEMA).class_names
        )
    with pytest.raises(ValueError, match="exactly"):
        validate_probabilities(SERVICE10_SCHEMA, onehot(LEGACY10_SCHEMA, "Strike"))


@pytest.mark.parametrize(
    "bad", [True, np.bool_(False), float("nan"), float("inf"), -0.1, 1.1, "0.1", None, 1j, 10**1000]
)
def test_invalid_probability_values_are_not_coerced(bad):
    values = onehot(SERVICE10_SCHEMA, "ball")
    values["ball"] = bad
    with pytest.raises(ValueError, match="Probabilities"):
        validate_probabilities(SERVICE10_SCHEMA, values)


@pytest.mark.parametrize("change", ["missing", "extra", "length", "nested", "unordered", "sum"])
def test_malformed_probability_payloads_are_rejected(change):
    names = get_contract(SERVICE10_SCHEMA).class_names
    values = onehot(SERVICE10_SCHEMA, "ball")
    if change == "missing":
        values.pop("foul")
    elif change == "extra":
        values["walk"] = 0.0
    elif change == "length":
        values = [0.1] * 9
    elif change == "nested":
        values = np.zeros((10, 1))
    elif change == "unordered":
        values = {0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.64}
    else:
        values["ball"] = 0.9
    with pytest.raises(ValueError):
        validate_probabilities(SERVICE10_SCHEMA, values, class_names=names)


@pytest.mark.parametrize("kind", [set, frozenset, lambda values: dict.fromkeys(values).keys()])
def test_unordered_probability_containers_cannot_assign_arbitrary_labels(kind):
    values = [0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.64]
    names = get_contract(SERVICE10_SCHEMA).class_names
    assert len(values) == len(names) and sum(values) == 1.0
    with pytest.raises(ValueError, match="numeric vector"):
        validate_probabilities(SERVICE10_SCHEMA, kind(values), class_names=names)
    with pytest.raises(ValueError, match="ordered outcome axis"):
        validate_probabilities(SERVICE10_SCHEMA, values, class_names=kind(names))
    expected = dict(zip(names, values, strict=True))
    for ordered in (values, tuple(values), np.array(values), iter(values)):
        assert validate_probabilities(SERVICE10_SCHEMA, ordered, class_names=names) == expected


def test_sum_tolerance_does_not_renormalize_values():
    values = onehot(SERVICE10_SCHEMA, "ball")
    values["ball"], values["foul"] = 0.5, 0.500005
    actual = validate_probabilities(SERVICE10_SCHEMA, values)
    assert actual == values and sum(actual.values()) != 1.0
    values["foul"] = 0.51
    with pytest.raises(ValueError, match="renormalization"):
        validate_probabilities(SERVICE10_SCHEMA, values)


@pytest.mark.parametrize("source", list(CONTRACTS))
@pytest.mark.parametrize("target", list(CONTRACTS))
def test_only_same_schema_identity_is_globally_supported(source, target):
    values = onehot(source, get_contract(source).class_names[0])
    if source == target:
        assert convert_probabilities(source, target, values) == values
    else:
        with pytest.raises(ValueError, match="No exact probability conversion") as error:
            convert_probabilities(source, target, values)
        assert get_contract(source).conversion_limits[0] in str(error.value)


def test_different_foul_mixtures_are_indistinguishable_in_legacy_strike():
    """Two synthetic worlds have the same legacy vector and different foul probabilities."""

    def collapsed(called_strike, foul):
        result = dict.fromkeys(get_contract(LEGACY10_SCHEMA).class_names, 0.0)
        for description, probability in (("called_strike", called_strike), ("foul", foul)):
            result[PitchResult10.NAMES[map_to_10class(description, None)]] += probability
        return result

    assert collapsed(0.8, 0.2) == collapsed(0.2, 0.8) == onehot(LEGACY10_SCHEMA, "Strike")
    with pytest.raises(ValueError, match="strike/foul mixtures"):
        convert_probabilities(LEGACY10_SCHEMA, SERVICE10_SCHEMA, collapsed(0.8, 0.2))
    displayed = present_legacy_probabilities(collapsed(0.8, 0.2))["display_probabilities"]
    assert displayed["strike"] is displayed["ball"] is displayed["foul"] is None


def test_terminal_and_nonhit_collapses_require_original_event_detail():
    assert map_to_10class("ball", "walk") == map_to_10class("hit_into_play", "catcher_interf")
    assert map_to_10class("called_strike", "strikeout") == map_to_10class(
        "called_strike", "strikeout_double_play"
    )
    assert (
        map_to_10class("hit_into_play", "field_out")
        == map_to_10class("hit_into_play", "field_error")
        == map_to_10class("hit_into_play", "triple_play")
    )
    for label, ambiguity in (
        ("Walk", "catcher_interf"),
        ("Strikeout", "strikeout_double_play"),
        ("FieldOut", "field_error"),
    ):
        with pytest.raises(ValueError, match=ambiguity):
            convert_probabilities(LEGACY10_SCHEMA, SERVICE10_SCHEMA, onehot(LEGACY10_SCHEMA, label))


def test_observation_targets_retain_different_information_from_transitions():
    pairs = [
        ("hit_into_play", "single"),
        ("hit_into_play", "home_run"),
        ("foul_bunt", "strikeout"),
        ("hit_into_play", "catcher_interf"),
        ("automatic_ball", None),
    ]
    source = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": i + 1, "pitch_number": 1, "description": d, "events": e}
            for i, (d, e) in enumerate(pairs)
        ]
    )
    actual = build_observation_targets(source)
    assert actual["observation"].iloc[:3].tolist() == ["hit", "hit", "foul"]
    assert actual["target"].iloc[3:].tolist() == [-1, -1]
    assert map_to_10class(*pairs[0]) != map_to_10class(*pairs[1])
    assert map_to_10class(*pairs[2]) == PitchResult10.STRIKEOUT
    with pytest.raises(ValueError, match="cannot recover hit types"):
        convert_probabilities(
            OBSERVATION8_SCHEMA, SERVICE10_SCHEMA, onehot(OBSERVATION8_SCHEMA, "hit")
        )


def pitch(pitch_number, **values):
    return {
        "game_pk": 7,
        "at_bat_number": 1,
        "pitch_number": pitch_number,
        "play_id": f"play-{pitch_number}",
        **values,
    }


def test_batch_alignment_uses_keys_and_preserves_payloads_without_mutation():
    reference = [pitch(2), pitch(1)]
    rows = [pitch(1, probability=0.2), pitch(2, probability=0.7)]
    before = deepcopy(rows)
    aligned = align_pitch_rows(reference, rows)
    assert [row["probability"] for row in aligned] == [0.7, 0.2]
    assert rows == before
    assert aligned[0] is not rows[1]


@pytest.mark.parametrize(
    "change", ["duplicate-key", "duplicate-play", "missing", "extra", "wrong-play"]
)
def test_batch_alignment_rejects_ambiguous_rosters(change):
    reference, rows = [pitch(1), pitch(2)], [pitch(1), pitch(2)]
    if change == "duplicate-key":
        rows.append(pitch(1, play_id="another"))
    elif change == "duplicate-play":
        rows[1]["play_id"] = rows[0]["play_id"]
    elif change == "missing":
        rows.pop()
    elif change == "extra":
        rows.append(pitch(3))
    else:
        rows[1]["play_id"] = "unrelated"
    with pytest.raises(ValueError):
        align_pitch_rows(reference, rows)
    with pytest.raises(ValueError):
        align_pitch_rows(rows, reference)


@pytest.mark.parametrize("invalid", [True, 1.0, 0, -1, "1", None, float("nan")])
def test_pitch_key_validation_is_strict(invalid):
    with pytest.raises(ValueError, match="positive integers"):
        align_pitch_rows([pitch(1)], [pitch(invalid)])
    assert align_pitch_rows([pitch(1)], [pitch(np.int64(1))])[0]["pitch_number"] == 1


@pytest.mark.parametrize("invalid", [None, object(), "rows", 42, {}, {1}])
def test_malformed_batch_containers_raise_actionable_errors(invalid):
    with pytest.raises(ValueError, match="ordered collections of row mappings"):
        align_pitch_rows([pitch(1)], invalid)
    with pytest.raises(ValueError, match="ordered collections of row mappings"):
        align_pitch_rows(invalid, [pitch(1)])
