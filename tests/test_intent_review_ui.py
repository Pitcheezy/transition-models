"""Offline review schema, geometry and synthetic event checks (not browser rendering)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from intent import reviewer_ui

HASH = "a" * 64
UI_SCRIPT = Path(__file__).resolve().parents[1] / "intent/review_ui.js"


def _fixture():
    frames = [
        {
            "observation_id": f"review_{i}",
            "image_sha256": str(i) * 64,
            "path": f"images/review_{i}.jpg",
            "width": 1280,
            "height": 720,
        }
        for i in (1, 2)
    ]
    manifest = {
        "schema": "intent_source_review_pack_v1",
        "protocol_version": "cv_observation_v1",
        "scope": "development_source_only_recheck",
        "frames": frames,
    }
    response = {
        "schema": "intent_source_review_response_v1",
        "protocol_version": "cv_observation_v1",
        "manifest_sha256": HASH,
        "reviewer_id": "",
        "rows": [
            {
                "observation_id": f["observation_id"],
                "image_sha256": f["image_sha256"],
                "status": "unreviewed",
                "mitt": None,
                "visibility": "unknown",
                "pose": "unknown",
                "reason": "",
            }
            for f in frames
        ],
    }
    return manifest, response


def _node(source):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-independent JavaScript checks")
    manifest, response = _fixture()
    script = (
        "const assert = require('node:assert/strict');\n"
        + "const modulePath = "
        + json.dumps(str(UI_SCRIPT))
        + ";\nconst ui = require(modulePath);\nconst manifest = "
        + json.dumps(manifest)
        + ";\nconst response = "
        + json.dumps(response)
        + ";\nconst hash = "
        + json.dumps(HASH)
        + ";\nconst copy = x => JSON.parse(JSON.stringify(x));\n"
        + source
    )
    result = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=20
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_inert_json_and_escaped_instructions():
    manifest, response = _fixture()
    response["reviewer_id"] = '__COUNT__</script><script src="attack.js">'
    page = reviewer_ui.render_review_page(manifest, response, "<img onerror=attack> & resting")
    assert '<script src="attack.js">' not in page
    assert "\\u003c/script>" in page
    assert "&lt;img onerror=attack&gt; &amp; resting" in page
    assert "default-src 'none'" in page and "script-src 'self'" in page
    assert '<script src="review_ui.js" defer>' in page
    embedded = page.split('id="review-data">')[1].split("</script>")[0]
    assert json.loads(embedded)["response"] == response
    assert "자동 저장하지 않습니다" in page


def test_render_rejects_nonfinite_json():
    manifest, response = _fixture()
    response["rows"][0]["mitt"] = [float("nan"), 2]
    with pytest.raises(ValueError):
        reviewer_ui.render_review_page(manifest, response, "instructions")


def test_blank_state_roundtrip_export_requires_reviewer():
    _node("""
assert.deepEqual(ui.parseResponse(JSON.stringify(response), manifest, hash), response);
assert.throws(() => ui.exportResponse(response, manifest, hash));
response.reviewer_id = 'person';
const saved = ui.exportResponse(response, manifest, hash);
assert.deepEqual(JSON.parse(saved), response);
assert(response.rows.every(row => row.status === 'unreviewed' && row.mitt === null));
""")


@pytest.mark.parametrize(
    "mutation",
    [
        "r.manifest_sha256 = 'b'.repeat(64)",
        "r.rows[0].image_sha256 = 'a'.repeat(64)",
        "r.rows[1] = copy(r.rows[0])",
        "r.rows.pop()",
        "r.rows[0].extra = true",
        "r.schema = 'other'",
    ],
)
def test_import_rejects_wrong_binding_without_mutation(mutation):
    _node(f"""
const original = copy(response), r = copy(response);
{mutation};
assert.throws(() => ui.parseResponse(JSON.stringify(r), manifest, hash));
assert.deepEqual(response, original);
""")


def test_marked_bounds_types_visibility_and_reason():
    _node("""
response.reviewer_id = 'person';
const marked = {...response.rows[0], status:'marked', mitt:[1279.9,719.9],
  visibility:'partial', reason:'synthetic occlusion'};
response.rows[0] = marked;
ui.validateResponse(manifest, hash, response);
for (const point of [[1280,2],[-1,2],[3,720],[NaN,2],[true,2],[Infinity,2],[2]]) {
  const r=copy(response); r.rows[0].mitt=point;
  assert.throws(() => ui.validateResponse(manifest, hash, r));
}
response.rows[0].visibility='unknown';
assert.throws(() => ui.validateResponse(manifest, hash, response));
response.rows[0] = ui.setStatus(marked, 'unavailable');
response.rows[0].reason='';
assert.throws(() => ui.validateResponse(manifest, hash, response));
response.rows[0].reason='occluded'; ui.validateResponse(manifest, hash, response);
response.rows[0].status='unknown'; ui.validateResponse(manifest, hash, response);
response.reviewer_id=' '; assert.throws(() => ui.validateResponse(manifest, hash, response));
""")


@pytest.mark.parametrize("reason", ["", " \t\n "])
def test_partial_requires_nonblank_reason_on_import_and_export(reason):
    _node(f"""
response.reviewer_id='person';
Object.assign(response.rows[1], {{status:'marked',mitt:[100,200],visibility:'partial',
  pose:'resting',reason:{json.dumps(reason)}}});
response.rows.reverse();
const original=copy(response);
const message=/프레임 2 \\(review_2\\).*partial/;
assert.throws(() => ui.exportResponse(response,manifest,hash),message);
assert.throws(() => ui.parseResponse(JSON.stringify(response),manifest,hash),message);
assert.deepEqual(response,original);
""")


def test_full_resting_blank_reason_and_partial_with_reason_are_allowed():
    _node("""
response.reviewer_id='person';
Object.assign(response.rows[0],{status:'marked',mitt:[100,200],visibility:'full',
  pose:'resting',reason:''});
Object.assign(response.rows[1],{status:'marked',mitt:[300,400],visibility:'partial',
  pose:'resting',reason:'synthetic visible body partly occluded'});
const saved=JSON.parse(ui.exportResponse(response,manifest,hash));
assert.equal(saved.rows[0].reason,'');
assert.equal(saved.rows[0].pose,'resting');
assert.equal(saved.rows[1].visibility,'partial');
assert.deepEqual(saved.rows[1].mitt,[300,400]);
""")


def test_invalid_marked_visibility_names_manifest_frame_after_response_reorder():
    _node("""
response.reviewer_id='person';
Object.assign(response.rows[1],{status:'marked',mitt:[100,200],visibility:'unknown'});
response.rows.reverse();
assert.throws(() => ui.exportResponse(response,manifest,hash),
  /프레임 2 \\(review_2\\).*full.*partial/);
""")


def test_coordinate_scaling_and_outside_rejection():
    _node("""
const rect={left:10,top:20,width:640,height:360}, frame=manifest.frames[0];
assert.deepEqual(ui.imagePoint(330,200,rect,frame),[640,360]);
assert.deepEqual(ui.imagePoint(10,20,rect,frame),[0,0]);
for (const point of [[650,20],[10,380],[9,20],[10,19],[NaN,20]])
  assert.throws(() => ui.imagePoint(...point,rect,frame));
assert.throws(() => ui.imagePoint(20,30,{...rect,width:0},frame));
""")


def test_status_reset_and_reordered_import():
    _node("""
const marked={...response.rows[0],status:'marked',mitt:[1,2],visibility:'full',pose:'resting',reason:'note'};
assert.deepEqual(ui.setStatus(marked,'unreviewed'), response.rows[0]);
assert.equal(ui.setStatus(marked,'unknown').mitt,null);
assert.deepEqual(marked.mitt,[1,2]);
response.rows.reverse();
assert.deepEqual(ui.parseResponse(JSON.stringify(response),manifest,hash),response);
const m=copy(manifest); m.frames[0].path='https://example.test/image.jpg';
assert.throws(() => ui.validateResponse(m,hash,response));
""")


def test_synthetic_dom_click_export_and_failed_import():
    _node("""
(async () => {
 const fs=require('node:fs'), vm=require('node:vm'), els={};
 const ids=['review-data','message','reviewer','index','total','prev','next','caption','frame',
 'marker','coordinates','status','visibility','pose','reason','export','import'];
 for (const id of ids) els[id]={value:'',textContent:'',style:{},files:[]};
 els['review-data'].textContent=JSON.stringify({manifest,response});
 Object.assign(els.frame,{complete:true,naturalWidth:1280,naturalHeight:720,
 getBoundingClientRect:()=>({left:10,top:20,width:640,height:360})});
 let blob=null, clicked=false;
 const context={document:{getElementById:id=>els[id],body:{appendChild(){}},
 createElement:()=>({click(){clicked=true;},remove(){}})},
 window:{confirm:()=>true,addEventListener(){}}, Blob,
 URL:{createObjectURL:b=>{blob=b;return 'blob:synthetic';},revokeObjectURL(){}},setTimeout:()=>0};
 vm.runInNewContext(fs.readFileSync(modulePath,'utf8'),context);
 assert.equal(els.status.value,'unreviewed');
 els.frame.complete=false; els.frame.onclick({clientX:330,clientY:200});
 assert.equal(els.status.value,'unreviewed');
 els.frame.complete=true; els.frame.naturalWidth=100;
 els.frame.onclick({clientX:330,clientY:200}); assert.equal(els.status.value,'unreviewed');
 els.frame.naturalWidth=1280; els.frame.onclick({clientX:330,clientY:200});
 assert.equal(els.status.value,'marked'); assert.equal(els.visibility.value,'unknown');
 els.reviewer.value='person'; els.reviewer.oninput();
 els.export.onclick(); assert.equal(clicked,false);
 els.visibility.value='full'; els.visibility.oninput(); els.export.onclick();
 assert.equal(clicked,true); let saved=JSON.parse(await blob.text());
 assert.deepEqual(saved.rows[0].mitt,[640,360]); assert.equal(saved.rows[1].status,'unreviewed');
 const invalid=copy(response); invalid.manifest_sha256='b'.repeat(64);
 els.import.files=[{text:async()=>JSON.stringify(invalid)}]; await els.import.onchange();
 assert.match(els.message.textContent,/현재 입력을 유지/);
 els.export.onclick(); saved=JSON.parse(await blob.text());
 assert.deepEqual(saved.rows[0].mitt,[640,360]);
 els.next.onclick(); assert.equal(els.index.value,2); assert.equal(els.status.value,'unreviewed');
 els.prev.onclick(); assert.equal(els.index.value,1); assert.equal(els.status.value,'marked');
})().catch(error=>{console.error(error);process.exitCode=1;});
""")


def test_js_export_passes_python_image_bound_checker(tmp_path):
    import hashlib

    from PIL import Image

    from intent.review_queue import check_response

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for cross-language export validation")
    manifest, response = _fixture()
    reviewer = tmp_path / "reviewer"
    (reviewer / "images").mkdir(parents=True)
    for frame, row in zip(manifest["frames"], response["rows"], strict=True):
        image = reviewer / frame["path"]
        Image.new("RGB", (frame["width"], frame["height"]), "white").save(image)
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        frame["image_sha256"] = row["image_sha256"] = digest
    raw = json.dumps(manifest).encode()
    (reviewer / "manifest.json").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    response["manifest_sha256"] = digest
    (tmp_path / "private_selection.json").write_text(
        json.dumps({"reviewer_manifest_sha256": digest}), encoding="utf-8"
    )
    source = (
        "const ui=require("
        + json.dumps(str(UI_SCRIPT))
        + "); const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));"
        + "const r=input.response;r.reviewer_id='synthetic-test-only';"
        + "Object.assign(r.rows[0],{status:'marked',mitt:[640,360],visibility:'full',pose:'resting'});"
        + "r.rows[1]=ui.setStatus(r.rows[1],'unknown');r.rows[1].reason='synthetic uncertainty';"
        + "process.stdout.write(ui.exportResponse(r,input.manifest,r.manifest_sha256));"
    )
    result = subprocess.run(
        [node, "-e", source],
        input=json.dumps({"manifest": manifest, "response": response}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=True,
    )
    output = tmp_path / "synthetic_only.json"
    output.write_text(result.stdout, encoding="utf-8")
    assert check_response(tmp_path, output) == {"completed": 1, "unknown": 1, "unreviewed": 0}
    (reviewer / manifest["frames"][0]["path"]).write_bytes(b"changed image")
    with pytest.raises(ValueError, match="SHA256"):
        check_response(tmp_path, output)


IMPORT_SCENARIOS = {
    "latest_selected_response_wins_reverse_completion": """
const old = beginImport('older.json'), latest = beginImport('latest.json');
await finish(latest, saved('latest-person', 20));
await finish(old, saved('older-person', 10));
const actual = await exported();
assert.equal(actual.reviewer_id, 'latest-person');
assert.deepEqual(actual.rows[0].mitt, [20,30]);
assert.equal(confirmations, 0);
""",
    "stale_invalid_response_does_not_replace_success_notice": """
const old = beginImport('older.json'), latest = beginImport('latest.json');
await finish(latest, saved('latest-person', 20));
const notice = els.message.textContent;
const invalid = saved('older-person', 10); invalid.manifest_sha256 = 'b'.repeat(64);
await finish(old, invalid);
assert.equal(els.message.textContent, notice);
assert.equal((await exported()).reviewer_id, 'latest-person');
""",
    "stale_read_error_cannot_clear_latest_pending_selection": """
const old = beginImport('older.json'), latest = beginImport('latest.json');
const notice = els.message.textContent;
old.reject(new Error('synthetic old read error')); await old.done;
assert.equal(els.import.value, 'latest.json');
assert.equal(els.message.textContent, notice);
await finish(latest, saved('latest-person', 20));
assert.equal((await exported()).reviewer_id, 'latest-person');
""",
    "edit_during_read_then_decline_preserves_unsaved_input": """
const latest = beginImport('latest.json');
edit(); acceptReplacement = false;
await finish(latest, saved('file-person', 20));
const actual = await exported();
assert.equal(actual.reviewer_id, 'edited-person');
assert.deepEqual(actual.rows[0].mitt, [640,360]);
assert.equal(actual.rows[0].reason, 'synthetic unsaved note');
assert.equal(confirmations, 1);
assert.equal(unloadBlocked(), true);
assert.equal(els.import.value, '');
""",
    "edit_during_read_then_accept_restores_exact_partial_response": """
const latest = beginImport('latest.json');
edit();
const imported = saved('file-person', 20);
imported.rows.reverse();
await finish(latest, imported);
assert.deepEqual(await exported(), imported);
assert.equal(confirmations, 1);
assert.equal(unloadBlocked(), false);
els.next.onclick(); assert.equal(els.status.value, 'unreviewed');
els.prev.onclick(); assert.equal(els.status.value, 'marked');
assert.equal(els.pose.value, 'unknown');
""",
    "failed_latest_import_does_not_fall_back_to_older_response": """
edit();
const old = beginImport('older.json'), latest = beginImport('latest.json');
latest.reject(new Error('synthetic latest read error')); await latest.done;
const notice = els.message.textContent;
assert.match(notice, /synthetic latest read error/);
await finish(old, saved('older-person', 10));
assert.equal(els.message.textContent, notice);
assert.equal((await exported()).reviewer_id, 'edited-person');
assert.equal(confirmations, 0);
assert.equal(unloadBlocked(), true);
""",
}


@pytest.mark.parametrize("scenario", IMPORT_SCENARIOS)
def test_import_request_order_and_edits(scenario):
    _node(
        """
(async () => {
 const fs=require('node:fs'), vm=require('node:vm'), els={};
 const ids=['review-data','message','reviewer','index','total','prev','next','caption','frame',
 'marker','coordinates','status','visibility','pose','reason','export','import'];
 for (const id of ids) els[id]={value:'',textContent:'',style:{},files:[]};
 els['review-data'].textContent=JSON.stringify({manifest,response});
 Object.assign(els.frame,{complete:true,naturalWidth:1280,naturalHeight:720,
 getBoundingClientRect:()=>({left:0,top:0,width:1280,height:720})});
 let blob=null, confirmations=0, acceptReplacement=true, beforeUnload;
 const context={document:{getElementById:id=>els[id],body:{appendChild(){}},
 createElement:()=>({click(){},remove(){}})},
 window:{confirm:()=>{confirmations++;return acceptReplacement;},
 addEventListener:(name, handler)=>{if(name==='beforeunload') beforeUnload=handler;}}, Blob,
 URL:{createObjectURL:b=>{blob=b;return 'blob:synthetic';},revokeObjectURL(){}},setTimeout:()=>0};
 vm.runInNewContext(fs.readFileSync(modulePath,'utf8'),context);
 const beginImport = name => {
   const read = {};
   const pending = new Promise((resolve,reject)=>Object.assign(read,{resolve,reject}));
   els.import.files=[{text:()=>pending}]; els.import.value=name;
   read.done=els.import.onchange(); return read;
 };
 const finish = async (read, document) => {
   read.resolve(JSON.stringify(document)); await read.done;
 };
 const saved = (id, x) => {
   const document=copy(response); document.reviewer_id=id;
   Object.assign(document.rows[0],{status:'marked',mitt:[x,30],visibility:'full',pose:'unknown'});
   return document;
 };
 const edit = () => {
   els.reviewer.value='edited-person'; els.reviewer.oninput();
   els.frame.onclick({clientX:640,clientY:360});
   els.visibility.value='full'; els.visibility.oninput();
   els.reason.value='synthetic unsaved note'; els.reason.oninput();
 };
 const exported = async () => {
   blob=null; els.export.onclick(); assert.ok(blob, els.message.textContent);
   return JSON.parse(await blob.text());
 };
 const unloadBlocked = () => {
   let blocked=false;
   beforeUnload({preventDefault(){blocked=true;}}); return blocked;
 };
"""
        + IMPORT_SCENARIOS[scenario]
        + """
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )
