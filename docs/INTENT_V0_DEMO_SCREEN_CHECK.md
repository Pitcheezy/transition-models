# 10/6 시연 화면 대조표 — 849843

2026-10-05. **39개 투구 키 / 좌표 27개 / 기권 12개**의 파일 대조를 마쳤다. 아래 표는 화면에서 보여야 할 값이며 **Song 화면 확인 결과는 전부 미확인**이다. 직접 화면·영상 대응과 공개 전후 표시를 확인한 사람만 아래 리허설 칸을 기록한다.

자료 기준: `feature/intent-v0`의 `fac3a93` 인계에서 보존한 [JSONL](results/mlb_p0/game_849843_intent_v0.jsonl). 확정 화면 제목은 **포수 미트 위치 추정**이다. 기존 서비스 JSONL 재전달·축약 JSON·zone9 참고값 생성은 필요 없다.

## 좌표와 표시 규칙

- `statcast_plate_x_catcher_view`: **음수=포수 시점 왼쪽(3루 쪽), 양수=오른쪽(1루 쪽)**. 타자 손에 따라 뒤집지 않는다. 중견수 중계 카메라는 반대쪽을 바라보므로 원본 영상의 좌우와 동일하다고 가정하지 않는다.
- `x(in)=원본 x(ft)×12`. 두 칸을 각각 소수 둘째 자리까지 표시했다(셋째 자리에서 반올림). 방향은 반올림 전 원본 부호로 정한다. 이 값은 같은 좌표 변환의 표시값이며 물리 정확도 검증값이 아니다.
- 실제 투구 공개 전에는 숨기고, 공개 후 해당 키의 x만 표시한다. 높이·9구역·투수 의도는 미표시한다. 기권과 이 목록에 없는 투구는 0·직전 값·보간으로 채우지 않는다.
- 표의 순서는 열람 편의를 위한 것이다. 영상·서비스는 배열 순서가 아닌 `pitch_id`로 연결한다. `evidence.frame_time/frame_index`는 판독 근거이며 서비스 공개 시각을 대신하지 않는다.

방향 근거: 우리 [plate_feet.py](../intent/plate_feet.py)의 x 정의와 [schema.py](../intent/schema.py)의 `x_convention` 검사; 팀원 [intent-spec.md@8771c06](https://github.com/SongRoute/pitcheezy/blob/8771c06/docs/intent-spec.md) §1, [CONTRACT.md](https://github.com/SongRoute/pitcheezy/blob/8771c06/apps/observer/CONTRACT.md)의 `GET /api/zones`, [domain.py](https://github.com/SongRoute/pitcheezy/blob/8771c06/apps/observer/backend/observer_app/domain.py)의 `target_point`(column0→음수, column2→양수). 구역 API는 부호 규약 확인에만 참고했으며 시연용 9구역을 만들지 않았다. 읽기 조회한 main의 스펙도 같은 바이트였다(SHA256 `d5e37ec59d77e0e4bb1e3e869d421d0d1b75a12946fe183ba65a968efd0b5689`). 실제 Song 화면의 방향 적용은 별도 확인 대상이다.

## 투구별 기대 표시

| pitch_id | status | unavailable_reason | x(ft) | x(in) | 포수 시점 좌우 | 공개 전(기대) | 공개 후(기대) |
|---|---|---|---:|---:|---|---|---|
| 849843:1:3 | estimated | — | -0.05 | -0.62 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:2:5 | unavailable | readers_disagree_on_mitt | — | — | — | 숨김 | 표시 안 함 |
| 849843:3:3 | unavailable | readers_disagree_on_mitt | — | — | — | 숨김 | 표시 안 함 |
| 849843:4:1 | estimated | — | -0.13 | -1.52 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:6:2 | estimated | — | +0.31 | +3.69 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:9:5 | unavailable | readers_disagree_on_mitt | — | — | — | 숨김 | 표시 안 함 |
| 849843:10:3 | unavailable | glove_not_distinguishable | — | — | — | 숨김 | 표시 안 함 |
| 849843:11:3 | unavailable | glove_not_distinguishable | — | — | — | 숨김 | 표시 안 함 |
| 849843:12:2 | unavailable | glove_not_distinguishable | — | — | — | 숨김 | 표시 안 함 |
| 849843:19:1 | estimated | — | -0.08 | -1.00 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:19:4 | unavailable | only_one_reader_found_a_setup_frame | — | — | — | 숨김 | 표시 안 함 |
| 849843:22:3 | estimated | — | -0.30 | -3.54 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:23:3 | estimated | — | -0.06 | -0.71 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:27:2 | unavailable | only_one_reader_found_a_setup_frame | — | — | — | 숨김 | 표시 안 함 |
| 849843:28:2 | unavailable | only_one_reader_found_a_setup_frame | — | — | — | 숨김 | 표시 안 함 |
| 849843:31:8 | estimated | — | -0.45 | -5.41 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:33:4 | estimated | — | -0.41 | -4.95 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:34:2 | estimated | — | +0.38 | +4.62 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:35:4 | estimated | — | +0.30 | +3.57 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:36:3 | estimated | — | +0.41 | +4.94 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:37:5 | estimated | — | -1.03 | -12.35 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:39:4 | estimated | — | +0.10 | +1.15 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:40:2 | estimated | — | -0.79 | -9.48 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:41:3 | estimated | — | -0.66 | -7.86 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:42:1 | estimated | — | -0.80 | -9.56 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:43:4 | estimated | — | -0.94 | -11.23 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:44:5 | estimated | — | +0.66 | +7.97 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:46:6 | estimated | — | -0.13 | -1.56 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:51:3 | estimated | — | +0.70 | +8.35 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:52:5 | estimated | — | -0.57 | -6.87 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:53:5 | unavailable | readers_disagree_on_mitt | — | — | — | 숨김 | 표시 안 함 |
| 849843:54:5 | estimated | — | +0.04 | +0.43 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:55:4 | estimated | — | -0.99 | -11.86 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:60:5 | estimated | — | -0.32 | -3.82 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:66:3 | estimated | — | -0.10 | -1.23 | 왼쪽(3루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:67:2 | estimated | — | +0.29 | +3.45 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:68:5 | unavailable | glove_hidden_by_catcher_body | — | — | — | 숨김 | 표시 안 함 |
| 849843:69:2 | estimated | — | +0.51 | +6.10 | 오른쪽(1루 쪽) | 숨김 | 해당 투구 x 표시 |
| 849843:71:6 | unavailable | only_one_reader_found_a_setup_frame | — | — | — | 숨김 | 표시 안 함 |

## 파일 검사 결과와 해시

- JSONL 키 중복 0개. 좌표 27개 모두 유한 x/z와 고정 좌표 규약을 가지며 `plate_feet`에서 멈춘다. 기권 12개 모두 점이 비어 있고 사유가 있다.
- [창 목록](results/mlb_p0/game_849843_condensed_windows_v0.json) 39키 및 [스캔](results/mlb_p0/game_849843_condensed_scan_v0.json)에서 match가 있는 39키와 집합이 일치한다. 세 파일 간 누락·추가 키 0개이며, 스캔의 match 없는 1건은 비교 대상에서 제외했다.
- 이는 **동일 파이프라인 산출물의 키 일관성 검사**다. 실제 영상 대응을 새로 독립 검증한 것이 아니다. 경기 전체 262구 중 39구만 포함한다. 나머지 223구를 이번 자료의 누락 오류나 표시 대상으로 취급하지 않는다.
- 기권 사유: 판독자 미트 위치 불일치 4 / 한 판독자만 셋업 확인 4 / 글러브 구분 불가 3 / 포수 몸에 가림 1. 파일의 사유를 요약했으며 새 원인 판정은 아니다.

| 바이트 기준 | 크기 | SHA256 |
|---|---:|---|
| Windows 작업 파일 CRLF | 457,107 | `5ad0c28847c12dcea3d6c8589e966553a44d1d8f5829381b87ec6d0b7e2d27dc` |
| HEAD와 1687c1e Git blob LF | 457,068 | `12c11e1d2976992d39a1c4e126ba192291cd6f90edd7d82c6a9be3412dd17d0b` |

39개 줄바꿈만 다르다. 팀원의 서비스 파일 일치 확인은 기존 팀원 답변에 근거한다. 이번에 원격 서비스의 실제 적재 파일이나 UI를 직접 검사한 것은 아니다.

## 장표·대본 일관성 검사

2026-10-05: 기존 PPTX의 `ppt/slides/slide1.xml`에서 텍스트를 추출해 보고서·리허설 문서·이 대조표·발표 대본과 비교했다. PPTX는 1장이고, 확정 검증 문구와 **전체 86장 중 AI 출력 58장 / 기권 28장**이 원문 그대로 들어 있다. 숫자나 설명 범위의 모순은 발견하지 않았다.

| 확인 항목 | 보고서 원값과 근거 | 대본·장표 표시 |
|---|---|---|
| 시연 출력 / 좌표 / 기권 | `development_games[1].pitches_in_output`, `.assistant.estimated`, `.assistant.unavailable` | 39 / 27 / 12; 장표는 39/27, 대조표는 12기권도 별도 표시 |
| 평가 출력 / AI 좌표 / 기권 | `evaluation_pooled.lines_in_output`, `.assistant.estimated`, `.assistant.unavailable` | 86 / 58 / 28 |
| 사람 판단 / 표시 / 기권 | `evaluation_pooled.frames_decided_by_person`, `.person_marked`, `.person_abstained` | 86 / 84 / 2; 대본 보충 수치, AI 분모와 구분 |
| 양쪽 표시 미트 점 거리 중앙값 | `evaluation_pooled.mitt_reading_pixels.distance`: n=58, median=2.5298221281347035 px | 58구 / 2.5px |
| 같은 변환 기준 x·z 거리 중앙값 | `evaluation_pooled.output_vs_person_feet.distance`: n=58, median=0.09236584866713454 ft; ×12=1.1083901840056145 in | 약 1.1인치; 물리 정확도나 x만의 오차가 아님 |

근거 보고서: [intent_accuracy_report_v0.json](results/mlb_p0/intent_accuracy_report_v0.json), `code_commit=6245038`. 기존 PNG도 직접 열어 숫자·문구가 보이고 잘리지 않는지 확인했다. PowerPoint 앱에서 PPTX를 직접 재생한 검사는 아니다. 기존 PPTX·PNG·M3·JSONL은 재생성하거나 수정하지 않았다.

검사: 기존 `tests/test_intent_*.py` **251 passed**(55.44초), 체크리스트 가드 **4 passed**. 시연 JSONL의 로컬 schema 검사 **39/39 통과**. 기존 동결 자료 186개 바이트 SHA 불변, 리허설 문서는 새 대조표·대본 링크 한 줄만 추가했다. 실제 서비스의 화면·적재·공개 시점 검사는 포함하지 않는다.

## 리허설 6단계 — 직접 확인 후 기록

| 순서 | Song 화면에서 맞춰 볼 것 | 기록 |
|---|---|---|
| 1 | 서비스 키와 영상의 해당 투구를 대조한다. 첫 출력 `849843:1:3`부터 시작해 키 이동과 목록 밖 투구 처리를 확인한다. 문서 정렬 순서로 연결하지 않는다. | 미확인: 확인자 / 시각 / 결과 |
| 2 | estimated 행의 원본 부호·단위를 비교한다. 예: `849843:1:3`은 x<0, 포수 시점 왼쪽이다. `849843:6:2`는 x>0, 포수 시점 오른쪽이다. 양쪽 방향과 높이·9구역·의도 미표시를 확인한다. | 미확인: 확인자 / 시각 / 결과 |
| 3 | 같은 투구를 공개 전→공개 후로 넘겨 숨김/표시를 확인하고, 다음 투구 이동·되감기에서도 이전 좌표가 남지 않는지 본다. | 미확인: 확인자 / 시각 / 결과 |
| 4 | `849843:2:5` 등 unavailable 행에서 좌표가 사라지는지 확인한다. 아래 사유 12행 전체를 대조하고 0·보간·이전 값이 나오면 실패로 기록한다. | 미확인: 확인자 / 시각 / 결과 |
| 5 | 제목, 확정 검증 문구, 같은 장표의 86/58/28을 맞춘다. 물리 정확도·투수 의도 검증 완료로 표시되지 않는지 확인한다. | 미확인: 확인자 / 시각 / 결과 |
| 6 | 별도 로컬 비교 자료의 대표 `849845:10:4`를 열어 pitch_id·선정 기준·범례를 확인한다. 평가 849845/823407 예시는 시연 849843의 타임라인에 넣지 않는다. | 미확인: 확인자 / 시각 / 결과 |

6단계는 [기존 리허설 안내](INTENT_V0_DEMO_REHEARSAL.md)의 미완료 6항목과 같은 순서다. 스키마 검사나 이 문서 작성만으로 완료 체크하지 않는다. 실제 결과를 받으면 확인자·시각·실패 키와 조치를 기록한다.

## 표 재현

저장소 루트에서 아래 Python 코드를 임시 `render_screen_table.py`로 저장하고 `python render_screen_table.py`로 실행한다. Windows의 기존 환경은 `.venv\Scripts\python.exe render_screen_table.py`, Mac 환경은 `.venv/bin/python render_screen_table.py`다. 표를 표준 출력으로만 내보내고 JSONL은 수정하지 않는다. 별도 의존성은 없다.

```python
import json
from pathlib import Path

source = Path("docs/results/mlb_p0/game_849843_intent_v0.jsonl")
rows = [json.loads(s) for s in source.read_text(encoding="utf-8").splitlines()]
keys = [r["pitch_id"] for r in rows]
assert len(keys) == len(set(keys)) == 39
print("| pitch_id | status | unavailable_reason | x(ft) | x(in) | 포수 시점 좌우 | 공개 전(기대) | 공개 후(기대) |")
print("|---|---|---|---:|---:|---|---|---|")
for r in sorted(rows, key=lambda v: tuple(map(int, v["pitch_id"].split(":")))):
    if r["status"] == "estimated":
        x = r["points"]["plate_feet"]["x"]
        side = "왼쪽(3루 쪽)" if x < 0 else "오른쪽(1루 쪽)" if x > 0 else "중앙"
        ft, inch, after = f"{x:+.2f}", f"{x*12:+.2f}", "해당 투구 x 표시"
    else:
        ft, inch, side, after = "—", "—", "—", "표시 안 함"
    print(f"| {r['pitch_id']} | {r['status']} | {r['unavailable_reason'] or '—'} | {ft} | {inch} | {side} | 숨김 | {after} |")
```

판독 결과·해시 검증 기록은 새 성능 평가가 아니다. 설명용 대본은 [1분 발표와 질문 대응](INTENT_V0_DEMO_SCRIPT.md)을 사용한다.
