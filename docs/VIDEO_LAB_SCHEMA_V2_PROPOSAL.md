# Video Lab 스키마 v2 제안 (transition-models P0 → pitcheezy Video Lab)

- 날짜: **2026-09-23**
- 대상 레포: `SongRoute/pitcheezy` `main` @ **`804f523be5f2c12b2adbbd74a8740dc5dcc96a76`** (2026-09-22 02:58 UTC, 문서 커밋). 9d09694→804f523 차이는 `CLAUDE.md`·`docs/decisions.md`·`docs/plan.md`·`docs/roadmap.md` 4개 문서뿐이라 아래 코드 사실은 그대로다(GitHub compare API 확인).
- 상태: **초안. 아직 보내지 않았다.** 사용자 검토 후 전송 여부를 정한다.
- 우리 표기: **transition-models P0**. 읽기 전용으로 GitHub raw/API로만 읽었고 팀원 레포를 클론·수정·실행하지 않았다.
- 범위 밖: 우리 legacy 10종 결과 클래스 ↔ 팀원 10/11종 대응(CHECKLIST I-6에서 따로 다룬다). 이 문서는 **투구 식별 + 중계 시각** 접점만 다룬다.

---

## 0. 한 줄 요청

Video Lab 주석 스키마를 `schema_version: 2`로 올려 (a) `pitch_id`를 `"{game_pk}:{at_bat_number}:{pitch_number}"`로 실제로 채우고, (b) `play_id`·`decision_seconds`·`uncertainty_seconds`·`note`·`manifest_sha256`·미디어 바인딩을 추가하고, (c) `release_time`(추적 배제 경계)과 우리 `release_seconds`(불확실성을 가진 릴리스 사건 추정)를 **구분해서** 저장하고, (d) `usable_for_tracking`과 macOS SSD 경로 하드코딩을 설정값으로 빼 달라는 것이다. 조인표(투구 키 + play_id + 시각)는 **우리가 JSON으로 제공**한다.

---

## 1. 지금 코드에서 확인한 사실

모두 위 커밋의 파일을 직접 읽은 것이다.

| 사실 | 근거 |
|---|---|
| 주석 필수 필드 14개: `schema_version, clip_id, clip_sha256, source_url, pitch_id, seed_time, end_time, release_time, roi, image_dimensions, label_source, review_status, annotation_version, annotated_at` | `apps/observer/backend/observer_app/video_lab.py:50-52` |
| `pitch_id`는 `null` 또는 비어있지 않은 문자열만 허용 — 형식 규약 없음 | `video_lab.py:65-66` |
| **웹 UI는 `pitch_id`를 언제나 `null`로 보낸다.** 입력 칸도 없다 | `apps/observer/web/src/videoAnnotation.ts:58` (`annotationPayload`), `apps/observer/web/src/VideoLab.tsx`에 `pitch_id` 참조 0건 |
| 테스트 픽스처도 `pitch_id: None` | `apps/observer/backend/tests/test_video_lab.py:15`, `backend/tests/test_video_annotations.py:17` |
| `validate_annotation`은 **필수 목록에 없는 키를 조용히 버린다**(`result = {key: raw[key] for key in required}`). 예외는 `clip_path`와 `calibration_corners` | `video_lab.py:95-98` |
| `schema_version != 1`은 거부 | `video_lab.py:55-56` |
| 시간 규칙: `0 <= seed_time < end_time < release_time`, `end-seed <= 3초`, 프레임 600개 이하 | `video_lab.py:20-21, 79-81` |
| **`release_time`은 배제 경계다**: 추적 프레임은 `timestamp >= release_time`이면 예외를 던진다 | `video_lab.py:165-166` |
| `release_time >= clip_duration`이면 거부 | `video_lab.py:256-257`, API 층에서도 `video_annotations.py:63-64` |
| `clip_sha256`은 소문자 64 hex **필수**, 실제 파일 해시와 일치해야 추적 | `video_lab.py:63-64, 239-244` |
| `usable_for_tracking`은 **하드코딩**: `usable = entry['key'] == 'seven_strikeouts'` (제목·사유 문구도 같은 `usable` 조건을 쓰는 삼항식) | `apps/observer/backend/observer_app/media_registry.py:41-48` |
| 추적 불가 클립은 저장 자체가 거부된다 | `video_annotations.py:56-58` |
| 승인 미디어가 모듈 상수로 1개 고정 | `video_lab.py:18-19` (`ALLOWED_MEDIA = (LAB_ROOT/'media/seven_strikeouts.mp4',)`) |
| macOS SSD 경로 하드코딩 4곳 | `observer_app/settings.py:7, 15`, `apps/observer/scripts/prepare_video_lab.py:29`, `apps/observer/scripts/build_catalog.py:201` (그 외 `apps/observer/README.md:54-55, 91`) |
| **카탈로그 투구 id는 이미 우리가 원하는 형식이다**: `f'{game_id}:{pa_id}:{int(row.pitch_number)}'`. `game_id`는 `game_pk` 그룹키, `pa_id`는 `at_bat_number` 그룹키 | `build_catalog.py:159`(생성), `:83`(`groupby('game_pk')`), `:114`(`groupby('at_bat_number')`), `:72-73`(`game_pk, at_bat_number, pitch_number` 정렬·중복 거부) |
| `play_id`는 우리가 읽은 Video Lab·미디어·카탈로그 어디에도 없다 | `video_lab.py`, `media_registry.py`, `videoAnnotation.ts`, `build_catalog.py` 전수 확인. (레포 전체 부재는 2026-09-22 감사 `docs/TEAMMATE_PITCHEEZY_2026-09-22.md` §6.1 기준이며, 그 뒤 코드 변경은 없다) |
| `/api/video-lab/*` 핸들러 6개(경로 4개: `catalog`, `clips/{clip_id}`, `annotations` GET/POST, `annotations/{id}`, `annotations/{id}/track`; `main.py:149-189`)가 **계약 문서에 없다** | `apps/observer/CONTRACT.md:5-14`의 `## Routes` 절에 `/api/health`, `/api/catalog`, `/api/sessions*`, `/api/zones`, `/api/runtime`만 있고 video-lab 항목 0건 |

우리 쪽 대응 사실: 우리 주석은 `mlb_broadcast_timing_v1`이고 검증기는 `src/data/broadcast_timing.py`다. 투구 키는 `KEYS = ("game_pk", "at_bat_number", "pitch_number")`(`broadcast_timing.py:8`), 즉 **팀원 카탈로그 id와 같은 3요소**다.

---

## 2. 요청 (1) — `pitch_id` 채우기

**형식**: `"{game_pk}:{at_bat_number}:{pitch_number}"` (10진수, 접두 0 없음, 구분자 `:`).
예: `"747139:6:1"`.

근거: 팀원 카탈로그가 이미 같은 문자열을 투구 id로 쓴다(`build_catalog.py:159`). 새 규약이 아니라 **이미 있는 규약을 Video Lab에도 적용**하는 것이다. 이러면 Video Lab 주석 ↔ 카탈로그 투구 ↔ 우리 manifest가 문자열 하나로 붙는다.

요청 사항:
1. `video_lab.py:65-66`의 검사를 정규식 `^[0-9]+:[0-9]+:[0-9]+$` (또는 `null`)로 좁힌다.
2. `videoAnnotation.ts:58`의 `pitch_id: null` 하드코딩을 UI 입력/선택값으로 바꾼다. 사람이 손으로 적게 하지 말고 **아래 §6 조인표에서 고른 값**을 넣는 것을 권한다.
3. `pitch_id`가 있으면 `game_pk`는 접두에서 파싱 가능하지만, 검증·조인 편의를 위해 `game_pk`를 정수 필드로도 같이 저장하기를 제안한다(중복이지만 불일치를 즉시 잡는다).

---

## 3. 요청 (2) — 추가 필드

`validate_annotation`이 필수 목록 밖 키를 버리므로(`video_lab.py:95-98`), 아래는 **팀원 쪽에서 `required`(또는 새 `optional_v2` 집합)에 넣어 주셔야** 저장된다. 우리가 클라이언트에서 넣는 것만으로는 사라진다.

| 필드 | 형식 | 뜻 | 우리 쪽 출처 |
|---|---|---|---|
| `play_id` | `str` (UUID) 또는 `null` | MLB Statcast play id. 투구 키와 1:1 | manifest `pitches[].video.play_id` |
| `decision_seconds` | `float >= 0` | 사람이 확인한 **투구 전 판단 프레임**의 소스 미디어 재생 초 | timing `decision_seconds` |
| `uncertainty_seconds` | `float > 0` | 수동 시각의 양쪽 여유(통계적 신뢰구간 아님) | timing `uncertainty_seconds` |
| `note` | 비어있지 않은 `str` | 그 프레임에서 실제로 본 것(세트 자세·bug 판독값·컷어웨이·견제 등) | timing `note` |
| `manifest_sha256` | 소문자 64 hex | 우리 식별 manifest의 정확한 버전 바인딩 | timing `manifest_sha256` |
| `source_media` | 객체 | 미디어 바인딩(아래) | timing `source` |
| `release_seconds` | `float >= 0` 또는 `null` | 우리 릴리스 **사건 추정**(§4) | timing `release_seconds` |
| `release_time_basis` | enum | `release_time`을 어떻게 만들었는지 | 파생 |

`source_media` 객체:

```json
{
  "page_url": "https://www.mlb.com/video/9-30-24-mets-win-epic-game-in-playoff-clincher",
  "media_url": "https://mlb-cuts-diamond.mlb.com/FORGE/2024/2024-09/30/0371d6a1-835956e4-13ff0140-csvm-diamondgcp-asset_1280x720_59_4000K.mp4",
  "duration_seconds": 9340.748083,
  "clip_start_seconds": null
}
```

`clip_start_seconds`가 **핵심**이다. 우리 초는 전체 경기 MP4 기준이고(길이 9340.748083 s), Video Lab의 `seed/end/release_time`은 클립 기준이다. 클립을 잘라 쓰면 `clip_time = source_time - clip_start_seconds`로 변환한다. 이 필드가 없으면 두 시간축이 말없이 섞인다. `clip_start_seconds: null`은 "클립이 곧 소스"를 뜻한다.

**해결되지 않은 충돌 하나**: Video Lab은 `clip_sha256`(소문자 64 hex)을 필수로 요구하고 실제 로컬 파일 해시와 대조한다(`video_lab.py:63-64, 239-244`; `media_registry.py:26-30`). 우리 소스는 원격 스트리밍 MP4이고 **콘텐츠 해시가 없다**(`docs/MLB_BROADCAST_TIMING.md` "MP4 자체의 콘텐츠 해시는 없다"). 따라서 둘 중 하나가 필요하다 — (a) 그쪽이 그 구간을 로컬 클립으로 잘라 해시하고 우리가 `clip_start_seconds`를 제공, (b) v2에서 `media_kind: "remote_stream"`일 때 `clip_sha256`을 `null` 허용하고 대신 `media_url + duration_seconds + manifest_sha256`로 바인딩. **우리는 (a)를 선호**한다(그쪽 불변성 규칙을 깨지 않는다). §8 Q3.

마이그레이션 주의: 저장 id가 주석 전체의 sha256이므로(`video_annotations.py:22-23, 83`) 필드가 늘면 기존 주석의 id가 바뀌지 않게 **`schema_version: 2`를 새 분기로** 두고 v1 레코드는 그대로 두는 편이 안전해 보인다(`video_lab.py:55-56`도 함께 수정 필요).

---

## 4. 요청 (3) — `release_time` ≠ `release_seconds`

이 둘은 **다른 것**이고, 같다고 적으면 안 된다.

| | 팀원 `release_time` | 우리 `release_seconds` |
|---|---|---|
| 뜻 | **추적 배제 경계**. 이 시각 이상의 프레임은 추적에 넣으면 예외 | 사람이 본 **릴리스 사건의 점추정** |
| 근거 | `video_lab.py:165-166` (`timestamp >= release_time` → `ValueError`), `:79-81` | `src/data/broadcast_timing.py:113-122`, `docs/MLB_BROADCAST_TIMING.md` "릴리스는 전후 샘플 장면 사이의 수동 추정치다" |
| 오차 | 없음(정의상 경계) | `uncertainty_seconds` (현재 ±0.15~±0.25초; 릴리스 브래킷 샘플 간격은 PA 6가 0.05~0.10초, PA 1~5는 0.2~0.6초) |
| 안전 방향 | **이르게** 잡을수록 안전(릴리스 후 프레임 유입 방지) | 양방향 오차 |

브래킷 간격 근거(`docs/results/mlb_p0/game_747139_timing.json`의 `annotations[].note`): PA 6은 `483.75 s`/`483.80 s`(0.05 s), `672.25 s`/`672.30 s`(0.05 s), `535.50 s`/`535.60 s`(0.10 s)처럼 0.05~0.10초 간격이지만, PA 1/1은 `78.6 s`/`78.8 s`(0.2 s), PA 1/2는 `90.9–91.3 s`(0.4 s), PA 4/2는 `347.9–348.5 s`(0.6 s)다. **PA 1~5의 정밀도를 PA 6 수준으로 말하면 안 된다.**

**파생 규칙(제안)** — `release_seconds`에서 `release_time`을 만들되, 같다고 주장하지 않는다:

```
release_time = release_seconds - uncertainty_seconds - (1 / fps)
end_time     = release_time - (1 / fps)
seed_time    = max(decision_seconds + uncertainty_seconds, end_time - 3.0)
조건: 0 <= seed_time < end_time < release_time  (video_lab.py:79-81 만족)
```

`- uncertainty_seconds`로 릴리스 추정의 **이른 쪽 끝**을 취하고, 프레임 1개(`1/fps`)를 더 빼서 경계 프레임 자체를 배제한다. `seed_time`은 우리 판단 프레임의 **늦은 쪽 끝** 이후로 잡아 "판단 이전 화면"이 섞이지 않게 한다.

`release_time_basis` 값 제안: `"derived_from_partner_release_seconds_minus_uncertainty_minus_one_frame"` (사람이 영상에서 직접 릴리스를 찍었다면 `"user_marked_in_clip"`). 이 필드가 있으면 나중에 누가 봐도 그 숫자가 측정값이 아니라 파생 경계임을 안다.

**실제 여유가 얼마나 남는지**(중요): 우리 판단→릴리스 리드는 PA 6 6구에서 1.05~1.28초다(`docs/MLB_BROADCAST_TIMING.md` "리드 시간 규약" 절, `63 check` 보고서의 `short_lead_pitches`·`lead_seconds_min`, 임계 1.5초는 `broadcast_timing.py:11`). 위 규칙을 PA 6/1(판단 482.5, 릴리스 483.78, ±0.15)에 적용하면 — **소스 probe의 `r_frame_rate = "60000/1001"` ≈ 59.94 fps를 가정하고**(`docs/results/mlb_p0/game_747139_sources.json`, `sources.full_game.inspection.probe.streams[0]`) — `release_time ≈ 483.613`, `end_time ≈ 483.597`, `seed_time = 482.65`가 되어 **실제 추적 구간(seed→end)은 약 0.95초**다. Video Lab의 3초 상한(`video_lab.py:20`)보다 훨씬 짧다. **짧은 창이 정상**이며 주석 오류가 아니다. fps가 달라지면 이 값도 달라지므로 `fps`의 출처를 명시해서 계산해야 한다(§8 Q4). 그리고 우리 리드 자체가 판단 프레임 규약에 따라 약 1초 달라진다는 것도 우리 쪽에 기록돼 있다(같은 절, A-v2로 규약 통일 예정).

---

## 5. 요청 (4) — 하드코딩 해제

### (a) `usable_for_tracking`

지금: `media_registry.py:41` `usable = entry['key'] == 'seven_strikeouts'`. 제목과 사유 문구도 같은 조건(`usable`)을 쓰는 삼항식(`:43`, `:47-48`)이다. 클립이 늘면 새 클립은 무조건 추적 불가가 되고, 저장 API가 거부한다(`video_annotations.py:56-58`).

요청: `MediaRegistry`가 이미 읽는 `media_sources.json`(`media_registry.py:13-16`)의 각 항목에서 읽는다.

```json
{"key": "...", "local_file": "...", "sha256": "...", "source_page": "...",
 "ffprobe": {...},
 "title": "...", "usable_for_tracking": true, "reason": "..."}
```

키가 없으면 `usable_for_tracking: false` + 기본 사유로 **닫힌 기본값**을 유지하면 지금의 안전성은 그대로다. 코드 변경은 `media_registry.py:41-48` 한 블록이다.

### (b) macOS SSD 경로

지금 4곳이 `/Volumes/T7 Shield`에 묶여 있어 다른 기기(우리 Windows 포함)에서 실행 자체가 불가하다.

| 위치 | 지금 | 요청 |
|---|---|---|
| `settings.py:7` | `ARTIFACT_ROOT = Path('/Volumes/T7 Shield/pitcheezy/pitchmdp')` | `os.environ.get('PITCHEEZY_ARTIFACT_ROOT', <지금 값>)` — 기본값을 지금 값으로 두면 맥미니 동작은 불변 |
| `settings.py:15` | `Path('/Volumes/T7 Shield').is_mount()` | `ARTIFACT_ROOT.is_dir()` (+ 기존 `RUN`이 `ARTIFACT_ROOT/'runs'` 아래인지 검사는 유지) |
| `prepare_video_lab.py:29` | 같은 `is_mount()` | 동일 |
| `build_catalog.py:201` | 같은 `is_mount()` | 동일 |
| `video_lab.py:18-19` | `LAB_ROOT`·`ALLOWED_MEDIA` 모듈 상수 1개 클립 | 승인 목록을 `MediaRegistry`(= `media_sources.json`)에서 받도록. `resolve_annotation_clip`(`:130-137`)은 그대로 쓰되 상수 대신 레지스트리 조회 |

`PITCHEEZY_OBSERVER_RUN` 환경변수 선례가 이미 있다(`settings.py:8`). 같은 방식이면 된다. 우리는 팀원 레포를 수정하지 않으므로 **요청만** 드린다.

---

## 6. 우리가 제공하는 조인표 (JSON)

**우리가 만든다.** 팀원 쪽은 읽기만 하면 된다. 파일 1개 = 경기 1개.
실제 파일: `docs/results/mlb_p0/game_747139_pitch_timing_join.json` (2026-09-23 기준 아직 커밋되지 않음 — `git status --short` → `??`). 아래는 그 파일의 최상위 키를 그대로 옮긴 것이고, 예시 행도 그 파일의 실제 행이다.

스키마 `transition_models_p0_pitch_timing_join_v1`:

```json
{
  "schema": "transition_models_p0_pitch_timing_join_v1",
  "game_pk": 747139,
  "manifest_sha256": "4d036f94f5b5bddc682e846960dbc40de5ae35c4e023581efa12167475e062da",
  "timing_schema": "mlb_broadcast_timing_v1",
  "source": {
    "page_url": "https://www.mlb.com/video/9-30-24-mets-win-epic-game-in-playoff-clincher",
    "media_url": "https://mlb-cuts-diamond.mlb.com/FORGE/2024/2024-09/30/0371d6a1-835956e4-13ff0140-csvm-diamondgcp-asset_1280x720_59_4000K.mp4",
    "duration_seconds": 9340.748083
  },
  "annotator": "Codex visual review PA1-2 + Claude Code visual review PA3-5, 2026-09-22 + Claude Code workflow (Opus 5 annotator, Fable 5.1 verification, ffmpeg frame grabs) PA6, 2026-09-23",
  "counts": {"manifest_verified": 322, "timing_rows": 26, "annotated": 25, "unavailable": 1, "unreviewed": 296},
  "rules": [
    "times are playback seconds of source.media_url; never apply them to another clip",
    "unavailable rows have null decision/release/uncertainty; unreviewed pitches are absent",
    "feed UTC is not playback time; pitch identity is the key plus play_id"
  ],
  "rows": [
    {
      "pitch_id": "747139:6:1",
      "game_pk": 747139,
      "at_bat_number": 6,
      "pitch_number": 1,
      "play_id": "fb9e321e-1c40-4fec-994b-7e6ece2b9936",
      "play_page_url": "https://baseballsavant.mlb.com/sporty-videos?playId=fb9e321e-1c40-4fec-994b-7e6ece2b9936",
      "status": "annotated",
      "decision_seconds": 482.5,
      "release_seconds": 483.78,
      "uncertainty_seconds": 0.15,
      "lead_seconds": 1.28,
      "note": "SNY full game. Bottom 1, Megill vs Ozuna; 0-0 count, runner on first, one out. The JULY 27 flashback graphic covers 476.0-480.0 s and the live centre-field shot is back by 481.0 s, so a pre-delivery live frame does exist: at 482.5 s Megill is set from the stretch on the rubber, hands together at his chest and body still, Ozuna is in the box, and the bug is fully readable (0-0, one out, runner on first, MEGILL :04 P:8); the leg lift has not started (it begins by 483.0 s). Release bracketed by sampled frames 483.75 s (arm still cocked above the head, front foot landing) and 483.80 s (arm extended toward the plate, ball gone), with 483.85 s already showing the arm dropping past the body. ffmpeg frame grabs. Manual timing, not frame-exact."
    }
  ]
}
```

`rules` 3개는 파일에 실제로 들어 있는 배열이며 **예시에서 빼면 안 된다**(§7 검증 #6·#11이 이 규칙을 전제한다). 위 예시 행은 가공이 아니라 그 파일 `rows[]`의 PA 6 1구 행이고, 시각 3개는 `docs/results/mlb_p0/game_747139_timing.json`, `play_id`·`play_page_url`은 `docs/results/mlb_p0/game_747139_manifest.json` → `pitches[].video`에서 온다. `lead_seconds = release_seconds - decision_seconds`(우리가 계산해 넣는다).

행 규칙:
- `status: "unavailable"`인 행은 `decision_seconds`·`release_seconds`·`uncertainty_seconds`가 **모두 `null`**이다(`broadcast_timing.py:123-128`). 현재 1건(PA 1/6, 그래픽으로 판단 프레임 가림). **지어내지 않는다.**
- 미검토 투구(현재 296)는 조인표에 넣지 않는다. 그 투구는 식별은 되지만 시각이 없다.
- 시각은 `source.media_url` 기준이다. **다른 방송사 클립·편집본에 같은 초를 쓰면 안 된다.**
- feed UTC(`manifest.pitches[].video.event_start_utc`)는 **재생 초가 아니다**. 탐색 출발점으로만 쓴다. 실제로 깨지는 것을 확인했다: PA 3 마지막 투구 → PA 4 첫 투구의 wall-clock 146초가 영상에서는 약 35초였다(`docs/MLB_BROADCAST_TIMING.md` "출처와 검증 규칙").

---

## 7. 양쪽이 돌릴 수 있는 검증 체크리스트

| # | 검사 | 통과 기준 | 근거/도구 |
|---|---|---|---|
| 1 | `game_pk` 일치 | 조인표 `game_pk` == 각 행 `game_pk` == `pitch_id` 접두 == 팀원 카탈로그 게임 id | `build_catalog.py:83`, 우리 `broadcast_timing.py:34-36` |
| 2 | `pitch_id` 형식·유일성 | `^[0-9]+:[0-9]+:[0-9]+$`, 파일 내 중복 0 | §2 |
| 3 | 투구 키 존재 | 각 행의 (game_pk, at_bat_number, pitch_number)가 manifest의 `identity_status: "verified"` 투구에 있다 | `broadcast_timing.py:41-53` |
| 4 | `play_id` 1:1 | 행의 `play_id` == manifest의 같은 키 `video.play_id`, 파일 내 중복 0 | `broadcast_timing.py:47-53, 106-107` |
| 5 | manifest 해시 | 조인표 `manifest_sha256` == manifest 정규 직렬화의 sha256 (`json.dumps(manifest, sort_keys=True, ensure_ascii=False, allow_nan=False)` → utf-8 → sha256). 2026-09-23 기준 `4d036f94…e062da` | `broadcast_timing.py:63-67` |
| 6 | 미디어 바인딩 | `page_url`·`media_url`·`duration_seconds`가 양쪽에서 같다. 클립을 쓰면 `clip_start_seconds`가 있고 `0 <= clip_start < duration`. 조인표 `rules[0]`("times are playback seconds of source.media_url")을 어기지 않는다 | §3, §6 |
| 7 | 시간 단조성(우리 규칙) | `0 <= decision - u < decision + u < release - u` 이고 `release + u <= duration_seconds` | `broadcast_timing.py:117-120` |
| 8 | 구간 비중첩 | 정렬한 `[decision-u, release+u]` 구간들이 겹치지 않고 투구 순서와 모순되지 않는다 | `broadcast_timing.py:132-134` |
| 9 | 시간 단조성(그쪽 규칙) | 파생한 `0 <= seed_time < end_time < release_time`, `end-seed <= 3.0`, 프레임 수 ≤ 600, `release_time < clip_duration` | `video_lab.py:79-81, 258-261, 256-257` |
| 10 | 파생 표시 | `release_time != release_seconds`이고 `release_time_basis`가 채워져 있다 | §4 |
| 11 | `unavailable` 행 | 세 시각 필드가 모두 `null` (조인표 `rules[1]`) | `broadcast_timing.py:123-128`, §6 |
| 12 | 클립 무결성 | (로컬 클립을 쓰면) `clip_sha256`이 실제 파일 해시와 일치 | `video_lab.py:239-244` |

우리 쪽 실행 명령(참고):

```bash
uv run --frozen python scripts/63_annotate_broadcast.py check \
  --annotations docs/results/mlb_p0/game_747139_timing.json --require-pa 6 \
  --output docs/results/mlb_p0/game_747139_timing_validation.json
```

보고서에는 `total_pitches`, `annotated`, `unavailable`, `unreviewed`, `complete_plate_appearances`, `short_lead_threshold_seconds`(1.5), `short_lead_pitches`, `lead_seconds_min`이 들어간다(`broadcast_timing.py:139-158`).

한 가지 더: `/api/video-lab/*` 핸들러 6개(경로 4개: `catalog`, `clips/{clip_id}`, `annotations` GET/POST, `annotations/{id}`, `annotations/{id}/track`; `main.py:149-189`)가 `CONTRACT.md:5-14`의 `## Routes` 절에 없다. v2와 함께 계약 문서에도 넣어 주시면 양쪽 회귀 테스트를 같은 문서에 고정할 수 있다.

---

## 8. 팀원에게 묻는 것 (답이 필요한 순서)

1. **Q1.** `pitch_id`를 `"{game_pk}:{at_bat_number}:{pitch_number}"`로 고정하는 데 동의하는가? (`build_catalog.py:159`와 같은 형식이라 새 규약은 아니다.)
2. **Q2.** §3의 추가 필드를 `validate_annotation`의 보존 집합에 넣어 줄 수 있는가? 지금은 필수 목록 밖 키가 조용히 버려진다(`video_lab.py:95-98`). `schema_version: 2`로 분기하는 방식이 맞는가, 아니면 v1에 선택 필드로 붙이는 편을 선호하는가?
3. **Q3.** 원격 스트리밍 소스의 `clip_sha256` 문제(§3 말미) — (a) 그쪽이 구간을 로컬 클립으로 잘라 해시하고 우리가 `clip_start_seconds`를 제공 / (b) v2에서 `media_kind: "remote_stream"`일 때 `clip_sha256`을 `null` 허용, 어느 쪽인가?
4. **Q4.** `release_time`을 §4의 파생 규칙으로 만드는 데 동의하는가? `fps`를 어디서 취하는가(레지스트리가 `r_frame_rate`를 나눠 `fps`로 노출한다, `media_registry.py:40, 45`)? 가변 프레임률 소스에서도 그 가정이 성립하는가? (우리 소스는 `60000/1001` ≈ 59.94이고, §4의 0.95초는 이 값을 쓴 결과다.) 덧붙여 PA 1~5는 브래킷 간격이 0.2~0.6초로 PA 6(0.05~0.10초)보다 거칠다 — 그쪽 추적이 요구하는 최소 정밀도가 있으면 알려 달라.
5. **Q5.** `usable_for_tracking`·`title`·`reason`을 `media_sources.json`으로 옮기는 데 동의하는가(`media_registry.py:41-48`)? 닫힌 기본값 유지에 동의하는가?
6. **Q6.** `PITCHEEZY_ARTIFACT_ROOT` 환경변수 + `is_dir()` 검사로 SSD 하드코딩 4곳을 푸는 데 동의하는가? 그쪽에서 직접 하실 일이며 우리는 수정하지 않는다.
7. **Q7.** 조인표를 어떤 경로/방식으로 받기를 원하는가(레포 커밋된 JSON 파일 / 우리가 보내는 파일 / 엔드포인트)? 경기 1개당 파일 1개 가정이 맞는가? (현재 우리 파일은 아직 커밋 전이다.)
8. **Q8.** Video Lab이 우리 경기 747139(2024-09-30)를 다루게 되는가, 아니면 코호트 경기(2025-08-16~09-30)에만 쓰는가? 후자면 우리가 그 경기용 manifest·timing을 새로 만들어야 하고, 이 스키마는 그대로 쓰되 **내용은 그 경기 것**이 된다(CHECKLIST I-5와 연결).
9. **Q9.** 검토 이력을 어디에 적는가. `annotation_version`은 UI가 정한다(`VideoLab.tsx:94`: 불러온 라벨을 고쳐 저장하면 `+1`, 새 라벨은 `1`; 백엔드는 `>= 1`만 검사 `video_lab.py:71-72`). 그러나 `review_status`를 `user_reviewed`로 올리는 경로는 UI·API 어디에도 없다(`videoAnnotation.ts:61`이 `'unreviewed'` 고정, `VideoLab.tsx`에 `review_status`·`user_reviewed` 참조 0건). v2에서 독립 검토를 어떻게 기록할지 알려 달라. 덧붙여 우리 `annotator` 문자열(누가·어떤 도구로 확인했는지)은 어디에 넣어야 하는가 — 기존 `label_source` 2값(`user_manual`/`assistant_visual_estimate`, `video_lab.py:67-68`)으로는 우리 워크플로(주석 에이전트 + 독립 검증 2인 + 사람 재확인)를 표현할 수 없다.

---

## 9. 우리가 주장하지 않는 것

- 우리 시각은 **수동 시각 추정**이다. 자동 동기화·자동 투구 감지·OCR 결과가 아니다(`docs/MLB_BROADCAST_TIMING.md`). `uncertainty_seconds`는 통계적 신뢰구간이 아니다.
- 정밀도가 균일하다고 주장하지 않는다. PA 6은 0.05~0.10초 간격 프레임으로 브래킷했지만 PA 1~5는 0.2~0.6초 간격이다(§4).
- `decision_seconds`는 "최초 인식 가능 시각"이나 "투구 동작 시작 시각"이 아니다. 현재 PA 1~5와 PA 6의 판단 프레임 규약이 약 1초 다르며 통일 작업(A-v2)이 남아 있다.
- 경기 747139는 우리 test cohort에 포함된 **개발·시연 자료**다. 이를 보고 조정한 결과를 새 독립 성능으로 보고하지 않는다.
- 이 문서는 결과 클래스 대응(우리 10종 ↔ 그쪽 10/11종)을 제안하지 않는다. 별건이다.
- Video Lab의 추적 결과는 그쪽 스스로 적어 둔 대로 독립 정답이 아니며(`video_lab.py:224-229`의 `claims`/`limitations`), 우리도 그것을 의도 라벨로 쓰지 않는다.

---

## 부록 A. 조인표 실제 파일 (2026-09-23 추가)

§6의 조인표는 제안이 아니라 **이미 만들어 둔 파일**이다: `docs/results/mlb_p0/game_747139_pitch_timing_join.json`
(`scripts/68_export_pitch_timing_join.py`로 timing JSON에서 재생성, `tests/test_pitch_timing_join.py`가 manifest·timing과 대조).
2026-09-23 기준 30행(29 확인, 1 `unavailable`, 미검토 292는 없음). §6의 예시 JSON `counts`(26행)는 PA 6까지의 값이며,
주석이 늘 때마다 파일의 `counts`가 갱신된다. 검증 체크리스트(§7)의 1~5·7·8·11은 `63 check`와 이 테스트가 이미 돌린다.

부록 B. 검증 이력: 이 문서는 Opus 5 에이전트가 초안을 쓰고, 검증 에이전트가 파일 경로·필드명·행 번호·예시값을 두 레포에서
직접 읽어 대조했다(1차 72건 중 5건 반박 → 수리, 2차 78건 중 3건 반박 → 수리). 3차 자동 검증은 하지 않았고, 2차 반박 3건
(video-lab 라우트 수, PA 1~5 릴리스 브래킷 정밀도, 조인표 실제 파일 부재)의 수정은 Fable 5.1 세션이 확인했다.
팀원에게는 **보내지 않았다**.
