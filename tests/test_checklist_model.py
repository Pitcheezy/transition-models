"""The model tag on a CHECKLIST item decides which Claude model runs that unit."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "checklist_model.py"

SAMPLE = """# list
- [x] A-0. done (`abc1234`)
- [ ] C-1. teammate-owned item, first in file order 〔담당: 팀원〕
- [ ] A-3. untagged open item that is not the next unit
- [ ] A-4. **PA 6** 주석 ← **다음 한 단위**. 이후 계속. 〔모델: Opus 5〕
- [ ] B-1. 규약 정의 `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Fable 5.1〕
- [!] A-x. blocked 〔모델: Opus 5〕
"""


def load_module():
    spec = importlib.util.spec_from_file_location("checklist_model", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_reads_state_and_model_tag():
    mod = load_module()
    items = {i["id"]: i for i in mod.parse_items(SAMPLE)}
    assert items["A-4"]["model"] == "claude-opus-5"
    assert items["A-4"]["state"] == "open"
    assert items["B-1"]["model"] == "claude-fable-5-1"
    assert items["A-3"]["model"] is None
    assert items["A-x"]["state"] == "blocked"
    assert items["A-0"]["state"] == "done"
    assert items["C-1"]["owner"] == "팀원" and items["C-1"]["external"] is True
    assert items["A-4"]["owner"] is None and items["A-4"]["external"] is False


def test_next_unit_prefers_in_progress_then_marked_then_first_open():
    mod = load_module()
    assert mod.next_unit(mod.parse_items(SAMPLE))["id"] == "A-4"
    running = SAMPLE.replace("- [ ] B-1.", "- [~] B-1.")
    assert mod.next_unit(mod.parse_items(running))["id"] == "B-1"
    plain = SAMPLE.replace(" ← **다음 한 단위**", "")
    assert mod.next_unit(mod.parse_items(plain))["id"] == "A-3"  # C-1 is skipped: teammate-owned
    only_external = "- [ ] C-1. teammate 〔담당: 팀원〕\n- [~] C-2. teammate 〔담당: 팀원〕\n"
    assert mod.next_unit(mod.parse_items(only_external)) is None
    assert mod.next_unit(mod.parse_items("- [x] A-0. done\n")) is None


def test_cli_prints_model_and_fails_without_tag(tmp_path):
    checklist = tmp_path / "CHECKLIST.md"
    checklist.write_text(SAMPLE, encoding="utf-8")
    base = [sys.executable, str(SCRIPT), "--checklist", str(checklist)]
    run = subprocess.run(base + ["--next"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and run.stdout.strip() == "claude-opus-5"
    run = subprocess.run(base + ["B-1"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and run.stdout.strip() == "claude-fable-5-1"
    run = subprocess.run(base + ["A-3"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 2 and run.stdout == ""
    run = subprocess.run(base + ["C-1"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 3 and run.stdout == ""  # teammate-owned: not a Claude unit
    run = subprocess.run(base + ["Z-9"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 1
    run = subprocess.run(base, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 2  # argparse usage error: neither item nor --next


def test_real_checklist_next_unit_is_tagged():
    mod = load_module()
    items = mod.parse_items((ROOT / "CHECKLIST.md").read_text(encoding="utf-8-sig"))
    item = mod.next_unit(items)
    actionable = [i for i in items if i["state"] in ("open", "in_progress") and not i["external"]]
    assert (item is None) == (not actionable)
    if item is not None:
        assert item["model"] in mod.MODEL_IDS.values()
        assert item["external"] is False
    untagged = [
        i["id"]
        for i in items
        if i["state"] in ("open", "in_progress") and not i["external"] and not i["model"]
    ]
    assert untagged == [], f"open CHECKLIST items without a model tag: {untagged}"


def test_multi_letter_workstream_is_not_silently_skipped():
    mod = load_module()
    text = """- [ ] E-demo2. external response pending 〔모델: Opus 5〕
- [~] CV-5a4. current CV boundary review 〔모델: Opus 5〕
- [~] F-4a. historical OCR work 〔모델: Fable 5.1〕
"""
    items = mod.parse_items(text)
    assert [item["id"] for item in items] == ["E-demo2", "CV-5a4", "F-4a"]
    assert mod.next_unit(items)["id"] == "CV-5a4"


def test_multiletter_teammate_work_remains_excluded():
    mod = load_module()
    items = mod.parse_items("""- [~] ML-1. external service 〔담당: 팀원〕
- [~] CV-5a4. our boundary review 〔모델: Opus 5〕
""")
    assert items[0]["external"] is True
    assert mod.next_unit(items)["id"] == "CV-5a4"


def test_blocked_and_external_work_do_not_create_an_actionable_unit():
    mod = load_module()
    items = mod.parse_items("""- [x] H-port1. delivered
- [!] I-service2. real source pending 〔모델: Fable 5.1〕
- [!] CV-6. human response pending 〔모델: Opus 5〕
- [ ] C-1. teammate work 〔담당: 팀원〕
""")
    assert mod.next_unit(items) is None
