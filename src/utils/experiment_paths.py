"""Portable run references that survive moving an experiment between operating systems."""

from pathlib import Path, PureWindowsPath


def resolve_selected_runs(selection, evaluation_dir, runs_dir=None):
    """Resolve versioned relative run names, with legacy Windows-path compatibility."""
    selected = selection["selected"]
    if "run_names" in selection:
        names = selection["run_names"][selected]
    else:
        names = [PureWindowsPath(value).name for value in selection["groups"][selected]]
    root = (
        Path(runs_dir)
        if runs_dir is not None
        else Path(evaluation_dir) / selection.get("runs_root_relative", "..")
    )
    if not names or any(
        not name or name in (".", "..") or "/" in name or "\\" in name or ":" in name
        for name in names
    ):
        raise ValueError("Invalid selected run directory names")
    paths = [(root / name).resolve() for name in names]
    for path in paths:
        if not (path / "manifest.json").is_file():
            raise FileNotFoundError(f"Missing run {path}. Move the run folders or pass --runs-dir.")
    return paths
