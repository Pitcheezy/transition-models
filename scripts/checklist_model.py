"""Print the Claude model assigned to a CHECKLIST.md item or to the next open unit.

Every open CHECKLIST item ends with a ``〔모델: Opus 5〕`` or ``〔모델: Fable 5.1〕`` tag.
The tag only decides which Claude model a Claude Code session should run for that item;
Codex ignores it. A session cannot switch its own model, so the caller compares the
printed id with its current model and hands the unit off (task chip / model menu) on a
mismatch instead of starting the work.

Items tagged ``〔담당: 팀원〕`` (or any owner other than Claude/Codex) belong to another
teammate: they carry no model tag, ``--next`` skips them, and asking for one directly
exits with code 3.

Usage::

    uv run --frozen python scripts/checklist_model.py A-4
    uv run --frozen python scripts/checklist_model.py --next
    uv run --frozen python scripts/checklist_model.py --next --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_IDS = {"Opus 5": "claude-opus-5", "Fable 5.1": "claude-fable-5-1"}
ITEM = re.compile(r"^- \[(?P<state>[ x~!])\] (?P<id>[A-Z]+-[a-z0-9]+)\. (?P<text>.*)$")
TAG = re.compile(r"〔모델: (?P<label>[^〕]+)〕")
OWNER = re.compile(r"〔담당: (?P<owner>[^〕]+)〕")
INTERNAL_OWNERS = {"Claude", "Codex", "Claude/Codex", "Claude Code"}
STATES = {" ": "open", "~": "in_progress", "x": "done", "!": "blocked"}


def parse_items(text):
    """Return checklist items in file order with their state and model tag."""
    items = []
    for line in text.splitlines():
        match = ITEM.match(line)
        if not match:
            continue
        tag = TAG.search(match["text"])
        label = tag["label"].strip() if tag else None
        owner_tag = OWNER.search(match["text"])
        owner = owner_tag["owner"].strip() if owner_tag else None
        items.append(
            {
                "id": match["id"],
                "state": STATES[match["state"]],
                "label": label,
                "model": MODEL_IDS.get(label) if label else None,
                "owner": owner,
                "external": owner is not None and owner not in INTERNAL_OWNERS,
                "next_unit": "다음 한 단위" in match["text"],
            }
        )
    return items


def next_unit(items):
    """In-progress item first, then the item marked as the next unit, then the first open one.

    Teammate-owned (external) items are never a Claude/Codex unit and are skipped.
    """
    ours = [item for item in items if not item["external"]]
    for item in ours:
        if item["state"] == "in_progress":
            return item
    for item in ours:
        if item["state"] == "open" and item["next_unit"]:
            return item
    for item in ours:
        if item["state"] == "open":
            return item
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("item", nargs="?", help="checklist item id such as A-4")
    parser.add_argument("--next", action="store_true", help="resolve the next open unit instead")
    parser.add_argument("--checklist", type=Path, default=ROOT / "CHECKLIST.md")
    parser.add_argument("--json", action="store_true", help="print the item as a JSON object")
    args = parser.parse_args(argv)
    if bool(args.item) == args.next:
        parser.error("give exactly one of an item id or --next")
    items = parse_items(args.checklist.read_text(encoding="utf-8-sig"))
    if args.next:
        item = next_unit(items)
    else:
        item = next((i for i in items if i["id"] == args.item), None)
    if item is None:
        print("no such checklist item", file=sys.stderr)
        return 1
    if item["external"]:
        print(f"{item['id']} is owned by {item['owner']}, not a Claude/Codex unit", file=sys.stderr)
        return 3
    if item["model"] is None:
        print(f"{item['id']} has no model tag", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(item, ensure_ascii=False))
    else:
        print(item["model"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
