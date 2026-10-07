"""Run the local shadow glove observer from an anonymous per-frame working directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.local_glove_observer import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
