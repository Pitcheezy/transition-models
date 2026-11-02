"""Verify delivered files without downloading or changing anything."""
import hashlib
import json
from pathlib import Path, PurePosixPath

# Well-known OS metadata only (Finder, AppleDouble on exFAT/FAT, Archive Utility, Explorer). Never a real pack file name.
METADATA_NAMES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
LIST_LIMIT = 8


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


def is_os_metadata(relative, expected):
    """.DS_Store/Thumbs.db/desktop.ini anywhere; ._X only beside an expected file or folder X; __MACOSX/ holds only such names."""
    p = PurePosixPath(relative)
    if p.parts[0] == '__MACOSX':
        return len(p.parts) > 1 and (p.name in METADATA_NAMES or p.name.startswith('._'))
    if p.name in METADATA_NAMES:
        return True
    if p.name.startswith('._') and len(p.name) > 2:
        sibling = p.with_name(p.name[2:]).as_posix()
        return sibling in expected or any(PurePosixPath(e).is_relative_to(sibling) for e in expected)
    return False


def listing(paths):
    names = sorted(paths)
    shown = ', '.join(names[:LIST_LIMIT])
    return f'{len(names)}: {shown}' + (f' … and {len(names) - LIST_LIMIT} more' if len(names) > LIST_LIMIT else '')


def verify(root, warn=None):
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
    expected = seen | {'MANIFEST.json'}
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    metadata = {name for name in actual - expected if is_os_metadata(name, expected)}
    unexpected, missing = actual - expected - metadata, expected - actual
    if unexpected or missing:
        problems = [f'unexpected files ({listing(unexpected)})'] if unexpected else []
        problems += [f'missing files ({listing(missing)})'] if missing else []
        raise ValueError('; '.join(problems) + '. Delete or restore them, then run verify.py again.')
    if metadata and warn:
        warn(f'ignored OS metadata files ({listing(metadata)}). They are not part of the pack and are never served.')
    return len(seen)


if __name__ == '__main__':
    try:
        print('Verified', verify(Path(__file__).resolve().parent, warn=lambda text: print('Warning:', text)), 'files. No network used.')
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error
