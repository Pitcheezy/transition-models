"""Verify delivered files without downloading or changing anything."""
import hashlib
import json
from pathlib import Path, PurePosixPath


def safe_file(root, relative):
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or any(x in ('', '.', '..') for x in relative.split('/')) or '\\' in relative or ':' in relative:
        raise ValueError('unsafe relative path')
    result = root.joinpath(*p.parts)
    if not result.resolve().is_relative_to(root.resolve()) or result.is_symlink():
        raise ValueError('path escapes package')
    return result


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    seen = set()
    for row in manifest['files']:
        name = row['path']
        if name in seen:
            raise ValueError('duplicate manifest path')
        seen.add(name)
        path = safe_file(root, name)
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('file verification failed: ' + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != seen | {'MANIFEST.json'}:
        raise ValueError('unexpected or missing files')
    return len(seen)


if __name__ == '__main__':
    try:
        print('Verified', verify(Path(__file__).resolve().parent), 'files. No network used.')
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error
