"""Resume long experiments while preserving interrupted outputs and completed results."""

import json
from pathlib import Path
from uuid import uuid4


def prepare_stage(output, marker, required=(), *, resume=False, expected=None, force=False):
    """Return whether to execute; archive incomplete owned outputs without deleting them."""
    output, marker = Path(output), Path(marker)
    expected = expected or {}
    if not output.exists():
        return True
    if not resume:
        raise FileExistsError(f"Output already exists: {output}. Choose a fresh path or --resume.")
    completed = marker.is_file() and all((output / name).is_file() for name in required)
    metadata = None
    if completed and marker.suffix == ".json":
        try:
            metadata = json.loads(marker.read_text(encoding="utf-8"))
            completed = metadata.get("status", "complete") == "complete"
        except (ValueError, OSError):
            completed = False
    if completed and not force:
        if expected and (
            metadata is None or any(metadata.get(k) != v for k, v in expected.items())
        ):
            raise ValueError(f"Completed stage configuration mismatch: {output}. Use a fresh run.")
        print(f"Skipping completed stage: {output}", flush=True)
        return False
    # Only rename the explicit stage output within its verified parent; never delete recursively.
    parent = output.absolute().parent.resolve()
    resolved = output.resolve()
    if output.is_symlink() or resolved.parent != parent:
        raise ValueError(f"Refusing to archive redirected output: {output}")
    reason = "superseded" if completed else "interrupted"
    archived = parent / f"{output.name}.{reason}-{uuid4().hex[:8]}"
    if archived.parent != parent or archived.exists():
        raise ValueError("Invalid interrupted-output archive path")
    resolved.rename(archived)
    print(f"Preserved {reason} stage: {archived}", flush=True)
    return True
