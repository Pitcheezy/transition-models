"""Build a private, portable 849843 clip-chain pack. Never modifies input files."""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import sqlite3
import zipfile
from pathlib import Path

EXPECTED_BUNDLE_SHA = 'af10293d5134219b7f750d00786366b93b0134c895519b939fd99a356d77a4bc'
EXPECTED_COMMIT = 'fba6b2ff846dcfa9afad9ea5df4204007e0604c1'
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(__file__).resolve().parent / 'clip_pack_runtime'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_write(path, value, *, exclusive=False):
    with path.open('x' if exclusive else 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def unique(rows, field):
    out = {}
    for row in rows:
        key = row[field]
        if key in out:
            raise ValueError('duplicate ' + field + ': ' + str(key))
        out[key] = row
    return out


def read_game(bundle):
    if sha(bundle) != EXPECTED_BUNDLE_SHA:
        raise ValueError('received bundle SHA mismatch')
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('invalid or duplicate ZIP member')
        game_names = [n for n in names if n.endswith('/site/v1/game/849843.json') or n == 'site/v1/game/849843.json']
        manifest_names = [n for n in names if n.endswith('/site/v1/manifest.json') or n == 'site/v1/manifest.json']
        if len(game_names) != 1 or len(manifest_names) != 1:
            raise ValueError('expected one game and manifest')
        raw = archive.read(game_names[0])
        manifest = json.loads(archive.read(manifest_names[0]))
        if manifest.get('commit') != EXPECTED_COMMIT:
            raise ValueError('publisher commit mismatch')
        return json.loads(raw), hashlib.sha256(raw).hexdigest()


def read_clip_rows(database):
    connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in connection.execute('SELECT p.*, o.pitch_type, c.status, c.file_path, c.file_sha256, c.bytes, c.duration_s, c.media_url FROM pitches p JOIN outcomes o USING(play_id) JOIN clips c USING(play_id) WHERE p.game_pk=849843')]
    finally:
        connection.close()


def bind_registry(game, media, database_rows, clip_root):
    if game.get('schema') != 'pitcheezy-service-game-v2' or game.get('game', {}).get('game_pk') != 849843 or media.get('game_pk') != 849843:
        raise ValueError('wrong game/schema')
    source = unique(game['pitches'], 'key')
    records = unique(media['records'], 'pitch_id')
    excluded = unique(media['excluded'], 'pitch_id')
    clips = unique(database_rows, 'play_id')
    if records.keys() & excluded.keys() or records.keys() | excluded.keys() != source.keys():
        raise ValueError('missing/extra/overlapping media pitch IDs')
    ordered = sorted(source.values(), key=lambda p: p['index'])
    if [p['index'] for p in ordered] != list(range(len(ordered))):
        raise ValueError('non-contiguous source pitch index')
    pitches, copies, filenames = [], [], set()
    for p in ordered:
        key = p['key']
        pa, pitch_number = p['at_bat_number'], p['pitch_number']
        if key != f'849843:{pa}:{pitch_number}':
            raise ValueError('pitch key identity mismatch')
        row = {'pitch_key': key, 'game_pitch_number': p['index'] + 1, 'pa_index': pa, 'pitch_number': pitch_number,
               'inning': p['inning'], 'half': p['half'], 'batter': p['batter']['name'], 'pitcher': p['pitcher']['name'],
               'status': 'excluded', 'reason': None, 'src': None, 'bytes': None, 'sha256': None, 'duration_s': None}
        if key in excluded:
            e = excluded[key]
            matching = [d for d in database_rows if d['at_bat_number'] == pa and d['pitch_number'] == pitch_number]
            if e.get('reason') != 'pitch_type_mismatch' or len(matching) != 1 or e.get('registry_pitch_type') != matching[0]['pitch_type'] or e.get('received_pitch_type') != p['actual']['pitch_type'] or e['registry_pitch_type'] == e['received_pitch_type']:
                raise ValueError('unsubstantiated exclusion')
            row['reason'] = e['reason']
        else:
            m = records[key]
            d = clips.get(m['play_id'])
            if not d or d['status'] != 'downloaded':
                raise ValueError('clip not downloaded: ' + key)
            for field, expected in [('at_bat_number', pa), ('pitch_number', pitch_number), ('pitcher_id', p['pitcher']['id']), ('batter_id', p['batter']['id']), ('pitch_type', p['actual']['pitch_type'])]:
                if m[field] != expected or d[field] != expected:
                    raise ValueError('semantic mismatch ' + key + ' ' + field)
            play_id = m['play_id']
            if not re.fullmatch(r'[0-9a-f-]{36}', play_id):
                raise ValueError('invalid play ID')
            filename = f'{pa:03d}_{pitch_number:02d}_{play_id}.mp4'
            if d['file_path'].replace('\\', '/') != 'clips/849843/' + filename:
                raise ValueError('unexpected registry clip path')
            if filename in filenames:
                raise ValueError('duplicate destination filename')
            filenames.add(filename)
            path = clip_root / filename
            if path.is_symlink() or not path.resolve().is_relative_to(clip_root.resolve()) or not path.is_file():
                raise ValueError('unsafe or missing source clip')
            if d['file_sha256'] != m['video_sha256'] or d['bytes'] != m['bytes'] or d['media_url'] != m['video'] or not re.fullmatch('[0-9a-f]{64}', m['video_sha256']):
                raise ValueError('registry/source media mismatch: ' + key)
            duration = m['duration_seconds']
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0 or abs(d['duration_s'] - duration) > 0.000001:
                raise ValueError('invalid duration')
            if path.stat().st_size != m['bytes'] or sha(path) != m['video_sha256']:
                raise ValueError('clip bytes/SHA mismatch: ' + key)
            row.update(status='available', src='clips/' + filename, bytes=m['bytes'], sha256=m['video_sha256'], duration_s=duration)
            copies.append((path, row['src']))
        pitches.append(row)
    return pitches, copies


def build(args):
    output, zip_path = args.output.resolve(), args.zip.resolve()
    if args.source_commit and not re.fullmatch('[0-9a-f]{40}', args.source_commit):
        raise ValueError('source-commit must be a full base commit')
    receipt_path = zip_path.with_suffix('.receipt.json')
    if output.exists() or zip_path.exists() or receipt_path.exists():
        raise ValueError('refusing to overwrite an existing output, ZIP or receipt')
    if zip_path.is_relative_to(output):
        raise ValueError('ZIP must be outside output folder')
    media_bytes = args.media.read_bytes()
    media = json.loads(media_bytes)
    db_before = sha(args.database)
    if db_before != media['registry_sha256']:
        raise ValueError('registry snapshot SHA mismatch')
    game, game_sha = read_game(args.bundle)
    pitches, copies = bind_registry(game, media, read_clip_rows(args.database), args.clips)
    if len(pitches) != 262 or len(copies) != 261 or {p['pitch_key'] for p in pitches if p['status'] == 'excluded'} != {'849843:69:2'}:
        raise ValueError('expected 262 pitches, 261 clips and the documented exclusion')
    player_files = ['index.html', 'player.css', 'core.js', 'player.js']
    for name in player_files:
        if not (args.player / name).is_file():
            raise ValueError('missing player source: ' + name)
    output.mkdir(parents=True)
    (output / 'clips').mkdir()
    (output / 'provenance').mkdir()
    for path, target in copies:
        shutil.copyfile(path, output / target)
    for name in player_files:
        shutil.copyfile(args.player / name, output / name)
    for name in ['serve.py', 'verify.py', 'README.md']:
        shutil.copyfile(RUNTIME / name, output / name)
    (output / 'provenance' / 'source-media.json').write_bytes(media_bytes)
    registry = {'schema': 'clip-chain-v1', 'game_pk': 849843, 'pitch_count': 262, 'available_count': 261,
                'excluded_count': 1, 'source_commit': EXPECTED_COMMIT, 'source_game_sha256': game_sha,
                'source_bundle_sha256': EXPECTED_BUNDLE_SHA, 'source_media_sha256': hashlib.sha256(media_bytes).hexdigest(),
                'source_registry_sha256': db_before, 'pitches': pitches,
                'notes': ['Pitch clips, not continuous broadcast.', 'Manual same-pitch alignment; no automatic cross-monitor sync.']}
    json_write(output / 'registry.json', registry)
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    for p in pitches:
        if p['src']:
            item = next(f for f in files if f['path'] == p['src'])
            if item['bytes'] != p['bytes'] or item['sha256'] != p['sha256']:
                raise ValueError('copied clip mismatch')
    json_write(output / 'MANIFEST.json', {'schema': 'clip-pack-manifest-v1', 'source_commit': EXPECTED_COMMIT,
                                        'private_transfer_only': True, 'builder_base_commit': args.source_commit,
                                        'builder_source_status': 'working_tree_files_identified_by_manifest_hashes', 'files': files})
    spec = importlib.util.spec_from_file_location('clip_pack_verify', RUNTIME / 'verify.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verified = verifier.verify(output)
    if sha(args.database) != db_before:
        raise ValueError('input registry changed during packaging')
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(output).as_posix(), date_time=(2026, 11, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                with path.open('rb') as stream, archive.open(info, 'w', force_zip64=True) as writer:
                    shutil.copyfileobj(stream, writer, 1024 * 1024)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(files) + 1:
            raise ValueError('ZIP CRC/count failure')
    receipt = {'schema': 'clip-pack-receipt-v1', 'source_commit': EXPECTED_COMMIT, 'zip_name': zip_path.name,
               'zip_bytes': zip_path.stat().st_size, 'zip_sha256': sha(zip_path), 'files_verified': verified,
               'pitch_count': 262, 'clips': 261, 'excluded': ['849843:69:2'],
               'video_bytes': sum(p['bytes'] or 0 for p in pitches), 'video_seconds': sum(p['duration_s'] or 0 for p in pitches),
               'builder_base_commit': args.source_commit, 'builder_source_status': 'working_tree_files_identified_by_manifest_hashes',
               'registry_unchanged': True, 'source_bundle_unchanged': sha(args.bundle) == EXPECTED_BUNDLE_SHA,
               'public_deployment': False, 'actual_device_test': 'not_measured'}
    json_write(receipt_path, receipt, exclusive=True)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ['bundle', 'media', 'database', 'clips', 'output', 'zip']:
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--player', type=Path, default=ROOT / 'web' / 'clip-chain')
    parser.add_argument('--source-commit', help='Base commit only; working files are separately identified by SHA')
    args = parser.parse_args()
    try:
        build(args)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error


if __name__ == '__main__':
    main()
