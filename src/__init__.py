"""SmartPitch transition-models package.

Windows import-order guard (docs/H1_ARROW_CRASH_2026-09-23.md): pyarrow 24's arrow.dll carries a
mimalloc that reads TLS slot 63 before allocating its own slots. If eight TLS slots are already
taken (``import hashlib`` / ``urllib.request`` do that through OpenSSL) when ``import torch``
loads its DLLs, a torch DLL lands on slot 63 and the first Arrow allocation dies with an access
violation after a ~25 s stall. Loading pyarrow before torch avoids it, so this package does that
on Windows; entry points that import torch first were never affected.
"""

import sys

if sys.platform == "win32":
    try:
        import pyarrow  # noqa: F401
    except ImportError:  # pyarrow is optional for pure-annotation helpers
        pass
