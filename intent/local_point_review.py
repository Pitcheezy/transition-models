"""Build a private, read-only CV16 viewer of hash-bound CV15 development points.

This module never imports or calls a model. Original JPEG bytes are embedded unchanged.
The viewer has no annotation, label-saving, server, upload, or seed-selection procedure.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

from PIL import Image

from intent.replay import _inside, _no_links

SCHEMA = "local_point_review_v1"
EXPECTED_COUNTS = {823407: (29, 28), 849845: (57, 56)}
SEEDS = (42, 43, 44)
VALID_RUN_STATUSES = {"completed", "completed_with_errors", "interrupted"}


class ReviewError(ValueError):
    """Reject inconsistent saved evidence before creating a viewer."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ReviewError("A full lowercase SHA-256 is required")
    return value


def _file(path):
    path = Path(path).absolute()
    _no_links(path)
    if not path.is_file():
        raise ReviewError("A regular local input file is required")
    return path.resolve()


def _json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReviewError("Duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ReviewError("Nonfinite JSON value")

    raw = _file(path).read_bytes()
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(result, dict):
        raise ReviewError("Expected a JSON object")
    return result, raw


def _index(rows, name, key="observation_id"):
    if not isinstance(rows, list):
        raise ReviewError(f"{name} must be a list")
    result = {}
    for row in rows:
        identity = row.get(key) if isinstance(row, dict) else None
        if not isinstance(identity, str) or not identity or identity in result:
            raise ReviewError(f"Missing or duplicate {name} identity")
        result[identity] = row
    return result


def _point(value, *, normalized=False):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(v) not in (float, int) or not math.isfinite(v) for v in value)
    ):
        raise ReviewError("A point must have two finite numeric coordinates")
    if normalized and any(not 0 <= v <= 1 for v in value):
        raise ReviewError("Normalized point must lie in the unit crop")
    return [float(v) for v in value]


def _project(point, crop):
    left, top, right, bottom = crop
    return [left + point[0] * (right - left), top + point[1] * (bottom - top)]


def _arms():
    games = list(EXPECTED_COUNTS)
    return [
        {
            "arm_id": f"train_{train}_seed_{seed}",
            "train_game": train,
            "test_game": test,
            "seed": seed,
        }
        for train, test in (games, games[::-1])
        for seed in SEEDS
    ]


def _artifact_documents(report, root):
    mapping = report.get("artifact_sha256")
    if not isinstance(mapping, dict):
        raise ReviewError("Report must bind its saved artifacts by SHA-256")
    names = [
        "plan.json",
        "run_manifest.json",
        "events.json",
        "checkpoint_ledger.json",
        *[f"training/{arm['arm_id']}.json" for arm in _arms()],
        *[f"evaluation/{arm['arm_id']}.json" for arm in _arms()],
    ]
    documents = {}
    for name in names:
        if name not in mapping:
            raise ReviewError(f"Report does not bind {name}")
        document, raw = _json(_inside(root, name))
        if _sha(raw) != _digest(mapping[name]):
            raise ReviewError(f"Saved artifact SHA-256 mismatch: {name}")
        documents[name] = document
    if mapping["plan.json"] != _digest(report.get("plan_sha256")):
        raise ReviewError("Report plan binding differs")
    if mapping["checkpoint_ledger.json"] != _digest(report.get("checkpoint_ledger_sha256")):
        raise ReviewError("Report checkpoint ledger binding differs")
    return documents


def _source_frames(manifest, references):
    frames = _index(manifest.get("frames"), "frame")
    refs = _index(references.get("references"), "reference")
    if frames.keys() != refs.keys():
        raise ReviewError("Manifest/reference ID sets differ")
    cohorts = {game: [] for game in EXPECTED_COUNTS}
    totals, crops, digests, excluded, source_bindings = Counter(), {}, set(), [], set()
    for identity in sorted(frames, key=lambda item: tuple(map(int, item.split(":")))):
        frame, reference = frames[identity], refs[identity]
        if re.fullmatch(r"[1-9]\d*:[1-9]\d*:[1-9]\d*", identity) is None:
            raise ReviewError("Invalid pitch observation ID")
        game = frame.get("game_pk")
        if (
            type(game) is not int
            or game not in EXPECTED_COUNTS
            or reference.get("game_pk") != game
            or int(identity.split(":")[0]) != game
        ):
            raise ReviewError("Frame/reference game identity mismatch")
        totals[game] += 1
        digest = _digest(frame.get("image_sha256"))
        if digest in digests or reference.get("image_sha256") != digest:
            raise ReviewError("Duplicate image or reference image SHA-256 mismatch")
        digests.add(digest)
        width, height = frame.get("width"), frame.get("height")
        if any(type(value) is not int or value <= 0 for value in (width, height)):
            raise ReviewError("Invalid original image dimensions")
        crop = frame.get("legacy_main_crop")
        if (
            not isinstance(crop, list)
            or len(crop) != 4
            or any(type(edge) is not int for edge in crop)
        ):
            raise ReviewError("Four fixed integer crop edges are required")
        left, top, right, bottom = crop
        if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
            raise ReviewError("Crop is outside the original image")
        if game in crops and crops[game] != crop:
            raise ReviewError("Manual camera crop must be fixed within each game")
        crops[game] = crop
        image_path = frame.get("image_path")
        if not isinstance(image_path, str) or not Path(image_path).is_absolute():
            raise ReviewError("An absolute local image path is required")
        image_path = _file(image_path)
        raw = image_path.read_bytes()
        if _sha(raw) != digest:
            raise ReviewError("Original image SHA-256 mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "JPEG" or image.size != (width, height):
                raise ReviewError("Original JPEG format/dimensions differ from the manifest")
            image.verify()
        source_bindings.add((str(image_path), digest, "image"))
        status = reference.get("legacy_mitt_status")
        if status not in ("marked", "hidden", "not_in_setup", "not_centre_field"):
            raise ReviewError("Unknown legacy reference status")
        if status != "marked":
            if reference.get("mitt") is not None:
                raise ReviewError("Unmarked legacy reference must not contain a point")
            excluded.append(
                {
                    "observation_id": identity,
                    "game_pk": game,
                    "legacy_mitt_status": status,
                    "reason": "legacy_nonmarked_is_not_a_negative",
                }
            )
            continue
        human = _point(reference.get("mitt"))
        if not left <= human[0] < right or not top <= human[1] < bottom:
            raise ReviewError("Legacy human point is outside the fixed crop")
        cohorts[game].append(
            {
                "observation_id": identity,
                "game_pk": game,
                "image_sha256": digest,
                "width": width,
                "height": height,
                "crop": crop,
                "human_point": human,
                "human_normalized": [
                    (human[0] - left) / (right - left),
                    (human[1] - top) / (bottom - top),
                ],
                "image_data": "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii"),
                "predictions": {},
            }
        )
    for game, (total, marked) in EXPECTED_COUNTS.items():
        if totals[game] != total or len(cohorts[game]) != marked:
            raise ReviewError("Frozen full/marked cohort counts differ")
    return cohorts, excluded, source_bindings


def _same_arm(row, arm):
    if any(
        type(row.get(key)) is not type(value) or row[key] != value for key, value in arm.items()
    ):
        raise ReviewError("Saved arm identity/train-game/test-game/seed mismatch")


def _attach_predictions(report, documents, cohorts):
    ledger = documents["checkpoint_ledger.json"]
    if (
        ledger.get("schema") != "local_point_checkpoint_ledger_v1"
        or ledger.get("plan_sha256") != report["plan_sha256"]
    ):
        raise ReviewError("Checkpoint ledger schema/plan mismatch")
    entries = _index(ledger.get("checkpoints"), "checkpoint", "arm_id")
    summaries = _index(report.get("arms"), "report arm", "arm_id")
    report_checkpoints = _index(report.get("checkpoints"), "report checkpoint", "arm_id")
    expected_arms = {arm["arm_id"] for arm in _arms()}
    if (
        entries.keys() != expected_arms
        or summaries.keys() != expected_arms
        or report_checkpoints.keys() != expected_arms
    ):
        raise ReviewError("All six fixed cross-game/seed arms must be preserved")
    for arm in _arms():
        key, train, test, seed = arm["arm_id"], arm["train_game"], arm["test_game"], arm["seed"]
        entry, summary = entries[key], summaries[key]
        training = documents[f"training/{key}.json"]
        evaluation = documents[f"evaluation/{key}.json"]
        for row in (entry, summary, training, evaluation, report_checkpoints[key]):
            _same_arm(row, arm)
        checkpoint_sha = _digest(entry.get("sha256"))
        if (
            entry.get("path") != f"checkpoints/{key}.pt"
            or report_checkpoints[key].get("sha256") != checkpoint_sha
        ):
            raise ReviewError("Checkpoint identity/hash differs from report")
        training_ids = training.get("training_observation_ids")
        expected_train = {row["observation_id"] for row in cohorts[train]}
        if (
            training.get("status") != "completed"
            or training.get("checkpoint_sha256") != checkpoint_sha
            or not isinstance(training_ids, list)
            or len(training_ids) != len(expected_train)
            or set(training_ids) != expected_train
        ):
            raise ReviewError("Checkpoint training identities are not the opposite-game cohort")
        if (
            evaluation.get("checkpoint_sha256") != checkpoint_sha
            or evaluation.get("checkpoint_ledger_sha256") != report["checkpoint_ledger_sha256"]
            or evaluation.get("status") not in ("completed", "error", "not_attempted")
        ):
            raise ReviewError("Evaluation is not bound to its sealed checkpoint")
        predictions = _index(evaluation.get("predictions"), "prediction")
        expected_test = {row["observation_id"] for row in cohorts[test]}
        if predictions.keys() != expected_test:
            raise ReviewError("Evaluation must preserve every planned marked frame exactly once")
        mean = [
            statistics.fmean(row["human_normalized"][axis] for row in cohorts[train])
            for axis in (0, 1)
        ]
        baselines = summary.get("baselines_all_marked")
        if not isinstance(baselines, dict):
            raise ReviewError("Usable report must retain both fixed baselines")
        for name, expected in (("crop_center", [0.5, 0.5]), ("training_game_mean", mean)):
            actual = _point(baselines.get(name, {}).get("normalized_point"), normalized=True)
            if any(
                not math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
                for a, b in zip(actual, expected, strict=True)
            ):
                raise ReviewError("Report baseline differs from the training-only reference mean")
        states = Counter()
        for row in cohorts[test]:
            prediction = predictions[row["observation_id"]]
            if prediction.get("image_sha256") != row["image_sha256"]:
                raise ReviewError("Prediction image SHA-256 differs from original frame")
            status = prediction.get("status")
            if status not in ("completed", "error", "not_attempted"):
                raise ReviewError("Unknown prediction status")
            states[status] += 1
            if status == "completed":
                if evaluation["status"] != "completed":
                    raise ReviewError("Failed evaluation cannot contain a completed prediction")
                normalized = _point(prediction.get("normalized_point"), normalized=True)
                model_point = _project(normalized, row["crop"])
            else:
                if prediction.get("normalized_point") is not None:
                    raise ReviewError("Failed or missing prediction cannot contain a point")
                model_point = None
            error_type = prediction.get("error_type") or evaluation.get("error_type")
            if error_type is not None and not isinstance(error_type, str):
                raise ReviewError("Prediction error must be text or null")
            row["predictions"][str(seed)] = {
                "status": status,
                "error_type": error_type,
                "train_game": train,
                "model_point": model_point,
                "crop_center": _project([0.5, 0.5], row["crop"]),
                "training_game_mean": _project(mean, row["crop"]),
            }
        if summary.get("planned_marked") != len(expected_test) or summary.get(
            "prediction_states"
        ) != dict(states):
            raise ReviewError("Report arm denominator/status counts differ from saved predictions")


def collect_review_data(manifest_path, references_path, report_path):
    """Validate the saved evidence and return a JSON-compatible, media-embedded snapshot."""
    manifest_path, references_path, report_path = map(
        _file, (manifest_path, references_path, report_path)
    )
    manifest, raw_manifest = _json(manifest_path)
    references, raw_references = _json(references_path)
    report, raw_report = _json(report_path)
    if (
        report.get("schema") != "local_point_experiment_report_v1"
        or report.get("results_usable") is not True
        or report.get("status") not in VALID_RUN_STATUSES
    ):
        raise ReviewError("Only usable, non-invalidated CV15 saved results can be reviewed")
    manifest_sha, references_sha = _sha(raw_manifest), _sha(raw_references)
    if (
        manifest.get("schema") != "local_glove_frames_v1"
        or references.get("schema") != "local_glove_references_v1"
        or report.get("manifest_sha256") != manifest_sha
        or report.get("references_sha256") != references_sha
        or references.get("manifest_sha256") != manifest_sha
    ):
        raise ReviewError("Report/manifest/reference SHA-256 or schema binding mismatch")
    documents = _artifact_documents(report, report_path.parent)
    plan, run_manifest = documents["plan.json"], documents["run_manifest.json"]
    if (
        plan.get("schema") != "local_point_experiment_plan_v1"
        or plan.get("manifest_sha256") != manifest_sha
        or plan.get("references_sha256") != references_sha
        or _file(plan.get("manifest")) != manifest_path
        or _file(plan.get("references")) != references_path
        or plan.get("seeds") != list(SEEDS)
        or plan.get("input_view") != "legacy_main_crop"
        or run_manifest.get("schema") != "local_point_experiment_run_v1"
        or run_manifest.get("plan_sha256") != report["plan_sha256"]
    ):
        raise ReviewError("Saved plan/run manifest does not bind the supplied inputs")
    cohorts, excluded, image_bindings = _source_frames(manifest, references)
    bindings = run_manifest.get("input_bindings")
    if not isinstance(bindings, list) or any(
        not isinstance(row, list) or len(row) != 3 for row in bindings
    ):
        raise ReviewError("Saved input bindings are missing")
    actual_bindings = {tuple(row) for row in bindings}
    required_bindings = image_bindings | {
        (str(manifest_path), manifest_sha, "manifest"),
        (str(references_path), references_sha, "references"),
    }
    if not required_bindings <= actual_bindings:
        raise ReviewError("Saved run does not bind all supplied source images/references")
    count = sum(marked for _, marked in EXPECTED_COUNTS.values())
    if (
        report.get("unique_marked_frames") != count
        or report.get("unique_original_frames")
        != sum(total for total, _ in EXPECTED_COUNTS.values())
        or report.get("seed_repetitions") != len(SEEDS)
        or report.get("prediction_rows_planned") != count * len(SEEDS)
        or report.get("seed_repetitions_are_independent_samples") is not False
        or report.get("excluded") != excluded
    ):
        raise ReviewError("Report cohort, repetitions, or legacy exclusions differ")
    _attach_predictions(report, documents, cohorts)
    rows = sorted(
        (row for group in cohorts.values() for row in group),
        key=lambda row: tuple(map(int, row["observation_id"].split(":"))),
    )
    for row in rows:
        del row["human_normalized"]
    return {
        "schema": SCHEMA,
        "default_seed": 42,
        "seeds": list(SEEDS),
        "run_status": report["status"],
        "frames": rows,
        "excluded": excluded,
        "provenance": {
            "manifest_sha256": manifest_sha,
            "references_sha256": references_sha,
            "report_sha256": _sha(raw_report),
            "plan_sha256": report["plan_sha256"],
            "checkpoint_ledger_sha256": report["checkpoint_ledger_sha256"],
            "original_images": "unchanged, SHA-256-verified JPEG bytes embedded locally",
            "annotation_editing": False,
            "model_calls": 0,
            "scope": "previously reviewed, legacy single-labeler, conditional development comparison",
            "independent_validation": False,
            "detection_evaluation": False,
        },
    }


VIEWER_JS = """
"use strict";
const data=JSON.parse(document.getElementById("review-data").textContent);
const el=id=>document.getElementById(id);
let currentId=data.frames[0].observation_id;
const game=el("game"), seed=el("seed"), frameSelect=el("frame-select");
for(const value of [...new Set(data.frames.map(row=>row.game_pk))]){
  const option=new Option(String(value),String(value)); game.add(option);
}
for(const value of data.seeds) seed.add(new Option(String(value),String(value)));
seed.value=String(data.default_seed);
function filtered(){return data.frames.filter(row=>game.value==="all"||String(row.game_pk)===game.value);}
function setupFrames(){
  const rows=filtered(); frameSelect.replaceChildren();
  if(!rows.some(row=>row.observation_id===currentId)) currentId=rows[0].observation_id;
  for(const row of rows) frameSelect.add(new Option(row.observation_id,row.observation_id));
  frameSelect.value=currentId; render();
}
const ns="http://www.w3.org/2000/svg";
function shape(tag,attributes){
  const node=document.createElementNS(ns,tag);
  for(const [key,value] of Object.entries(attributes)) node.setAttribute(key,String(value));
  return node;
}
function marker(point,color,kind,radius){
  if(!point)return;
  const [x,y]=point; const group=shape("g",{stroke:color,"stroke-width":radius/3,fill:"none"});
  if(kind==="circle") group.append(shape("circle",{cx:x,cy:y,r:radius}));
  else if(kind==="diamond") group.append(shape("path",{d:`M ${x} ${y-radius} L ${x+radius} ${y} L ${x} ${y+radius} L ${x-radius} ${y} Z`}));
  else {
    const d=kind==="cross"?`M ${x-radius} ${y-radius} L ${x+radius} ${y+radius} M ${x-radius} ${y+radius} L ${x+radius} ${y-radius}`:`M ${x-radius} ${y} L ${x+radius} ${y} M ${x} ${y-radius} L ${x} ${y+radius}`;
    group.append(shape("path",{d}));
  }
  el("overlays").append(group);
}
function pointText(point,human){
  if(!point)return "출력 없음";
  const distance=Math.hypot(point[0]-human[0],point[1]-human[1]);
  return `(${point[0].toFixed(1)}, ${point[1].toFixed(1)}) · 사람 점과 ${distance.toFixed(1)} px`;
}
function render(){
  const rows=filtered(), index=rows.findIndex(row=>row.observation_id===currentId);
  const row=rows[index], prediction=row.predictions[seed.value];
  el("counter").textContent=`${index+1} / ${rows.length} · 전체 ${data.frames.length}개 기존 marked 프레임`;
  el("pitch").textContent=`Pitch ID ${row.observation_id}`;
  el("direction").textContent=`학습 경기 ${prediction.train_game} → 표시 경기 ${row.game_pk} · seed ${seed.value}`;
  el("previous").disabled=index===0; el("next").disabled=index===rows.length-1;
  el("canvas").setAttribute("viewBox",`0 0 ${row.width} ${row.height}`);
  el("original").setAttribute("href",row.image_data);
  el("original").setAttribute("width",row.width); el("original").setAttribute("height",row.height);
  el("overlays").replaceChildren();
  if(!el("original-only").checked){
    const radius=Math.max(row.width,row.height)/90, [left,top,right,bottom]=row.crop;
    if(el("show-crop").checked) el("overlays").append(shape("rect",{x:left,y:top,width:right-left,height:bottom-top,fill:"none",stroke:"#ffffff88","stroke-width":radius/7,"stroke-dasharray":radius}));
    if(el("show-human").checked) marker(row.human_point,"#38dce8","circle",radius);
    if(el("show-model").checked) marker(prediction.model_point,"#ff6565","cross",radius);
    if(el("show-center").checked) marker(prediction.crop_center,"#ffd45a","diamond",radius);
    if(el("show-mean").checked) marker(prediction.training_game_mean,"#df9bff","plus",radius);
  }
  el("human-value").textContent=`(${row.human_point[0].toFixed(1)}, ${row.human_point[1].toFixed(1)})`;
  const statuses={completed:"완료",error:"실패",not_attempted:"미실행"};
  el("state").textContent=`모델 상태: ${statuses[prediction.status]}${prediction.error_type?" · "+prediction.error_type:""}`;
  el("state").className=prediction.status==="completed"?"":"failure";
  el("model-value").textContent=pointText(prediction.model_point,row.human_point);
  el("center-value").textContent=pointText(prediction.crop_center,row.human_point);
  el("mean-value").textContent=pointText(prediction.training_game_mean,row.human_point);
}
function move(delta){
  const rows=filtered(), index=rows.findIndex(row=>row.observation_id===currentId);
  const next=rows[index+delta]; if(next){currentId=next.observation_id;frameSelect.value=currentId;render();}
}
game.addEventListener("change",setupFrames);
seed.addEventListener("change",render);
frameSelect.addEventListener("change",()=>{currentId=frameSelect.value;render();});
el("previous").addEventListener("click",()=>move(-1)); el("next").addEventListener("click",()=>move(1));
for(const input of document.querySelectorAll('input[type="checkbox"]')) input.addEventListener("change",render);
document.addEventListener("keydown",event=>{
  if(event.altKey||event.ctrlKey||event.metaKey||event.shiftKey)return;
  if(["INPUT","SELECT","TEXTAREA"].includes(event.target.tagName))return;
  if(event.key==="ArrowLeft"){event.preventDefault();move(-1);}
  if(event.key==="ArrowRight"){event.preventDefault();move(1);}
});
el("provenance").textContent=JSON.stringify(data.provenance,null,2);
el("excluded").textContent=`기존 미표시 ${data.excluded.length}개는 음성 사례가 아니며 이 점 비교에서 제외됩니다: ${data.excluded.map(row=>row.observation_id+" ("+row.legacy_mitt_status+")").join(", ")}`;
el("run-status").textContent=`저장된 실행 상태: ${data.run_status}. 실패·미출력 프레임도 목록에 남깁니다.`;
setupFrames();
"""


def render_html(data):
    """Render one self-contained page; saved strings are data, never executable markup."""
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for character, escaped in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        encoded = encoded.replace(character, escaped)
    script_hash = base64.b64encode(hashlib.sha256(VIEWER_JS.encode()).digest()).decode()
    prefix = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'sha256-__SCRIPT_HASH__'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>CV16 로컬 점 비교</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#111722;color:#edf1f8;font:15px/1.55 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:24px;margin:0 0 8px}p{margin:8px 0}.notice{color:#c4ccda;max-width:1120px}.controls,.toggles{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin:18px 0}label{display:flex;gap:7px;align-items:center}select,button{background:#253249;color:inherit;border:1px solid #526079;border-radius:6px;padding:8px;font:inherit}button:disabled{opacity:.4}button:not(:disabled),label{cursor:pointer}.canvas-wrap{background:#000;border:1px solid #334158;border-radius:8px;overflow:hidden}svg{display:block;width:100%;max-height:75vh}.details{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0}.card{padding:12px;background:#1c2636;border-radius:7px}.card strong{display:block}.human{color:#38dce8}.model{color:#ff8585}.center{color:#ffd45a}.mean{color:#df9bff}.failure{color:#ffbd79}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer}#counter,#direction,#excluded,#run-status{color:#b7c4d8}input{accent-color:#5eb9f4}#pitch{font-size:18px;margin:8px 0}footer{margin-top:20px;border-top:1px solid #334158;padding-top:12px}
</style></head><body><main>
<h1>CV16 로컬 점 비교 · 읽기 전용</h1>
<p class="notice">이미 검토한 두 경기의 기존 단일 라벨러 점과 AI 좌표 회귀 출력을 비교합니다. 개발 자료이며, 검출 성능·독립 검증·현재 미트 중심 규약의 정답을 뜻하지 않습니다. 라벨을 수정하거나 저장하는 기능은 없습니다.</p>
<div class="controls"><label>경기 <select id="game"><option value="all">전체</option></select></label><label>모델 seed <select id="seed"></select></label><button id="previous" type="button">← 이전</button><button id="next" type="button">다음 →</button><label>프레임 <select id="frame-select"></select></label></div>
<p class="notice">기본 seed는 42입니다. 성능에 따른 자동 seed 선택이나 좋은 사례만의 선별은 없습니다.</p>
<p id="counter"></p><h2 id="pitch"></h2><p id="direction"></p>
<div class="toggles"><label><input id="original-only" type="checkbox">원본만 보기</label><label class="human"><input id="show-human" type="checkbox" checked>○ 사람: 기존 라벨</label><label class="model"><input id="show-model" type="checkbox" checked>× AI: 모델 점</label><label class="center"><input id="show-center" type="checkbox" checked>◇ 기준선: crop 중심</label><label class="mean"><input id="show-mean" type="checkbox" checked>＋ 기준선: 학습 경기 평균</label><label><input id="show-crop" type="checkbox" checked>수동 crop 영역</label></div>
<div class="canvas-wrap"><svg id="canvas" role="img" aria-label="원본 프레임 위의 사람 점, AI 점, 기준선 비교"><image id="original" x="0" y="0"/><g id="overlays" pointer-events="none"/></svg></div>
<p id="state" role="status"></p>
<div class="details"><div class="card"><strong class="human">○ 사람 · 기존 단일 라벨러</strong><span id="human-value"></span></div><div class="card"><strong class="model">× AI · 선택 seed의 모델</strong><span id="model-value"></span></div><div class="card"><strong class="center">◇ 기준선 · crop 중심</strong><span id="center-value"></span></div><div class="card"><strong class="mean">＋ 기준선 · 학습 경기의 점 평균</strong><span id="mean-value"></span></div></div>
<p class="notice">좌표와 거리는 원본 이미지 픽셀 단위입니다. 평균 기준선은 반대쪽 학습 경기의 정규화 점만 사용해 표시 경기의 수동 crop에 옮겼습니다. 모델은 알려진 marked 프레임의 점을 회귀하며, 미트 존재나 기권 확률을 판정하지 않습니다.</p>
<footer><p id="run-status"></p><p id="excluded"></p><p class="notice">원본 JPEG 바이트를 그대로 담은 로컬 파일입니다. 이미지·라벨·모델은 서버로 전송되지 않으며 모델을 호출하지 않습니다.</p><details><summary>자료 결속 확인</summary><pre id="provenance"></pre></details></footer>
</main><script id="review-data" type="application/json">"""
    return (
        prefix.replace("__SCRIPT_HASH__", script_hash)
        + encoded
        + "</script><script>"
        + VIEWER_JS
        + "</script></body></html>\n"
    )


def build_review(manifest_path, references_path, report_path, out):
    """Create only a fresh outputs/cv_local_point_review_*/index.html after validation."""
    out = Path(out).absolute()
    _no_links(out)
    if out.exists():
        raise FileExistsError("A fresh review output directory is required")
    if out.parent.name != "outputs" or not out.name.startswith("cv_local_point_review_"):
        raise ReviewError("Output must be a new outputs/cv_local_point_review_* directory")
    data = collect_review_data(manifest_path, references_path, report_path)
    html = render_html(data)
    out.mkdir(parents=True, exist_ok=False)
    path = out / "index.html"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(html)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    path = build_review(args.manifest, args.references, args.report, args.out)
    print(json.dumps({"index_html": str(path), "model_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
