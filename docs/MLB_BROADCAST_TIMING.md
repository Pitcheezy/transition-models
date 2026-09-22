# MLB 중계 시각 주석

전체 경기 영상에서 투구 전 판단용 화면과 릴리스 시각을 직접 확인해 투구 ID와 연결한다.
자동 OCR·자동 투구 감지 결과가 아니다. 기록된 상태는 화면 대조용이다.

## 확인한 범위

2026-09-22 Chrome에서 경기 747139의 SNY 전체 경기 첫 두 타석을 확인했고(Codex),
같은 날 Claude Code가 데스크톱 앱 내장 브라우저로 세 번째(Vientos)·네 번째(Harris II)·
다섯 번째(Albies) 타석을 확인했다.
**19개 투구 시각 확인, 1개 판단 화면 확인 불가, 302개 미검토**다.
두 번째~다섯 번째 타석의 투구가 모두 주석을 갖는다.

| 타석/투구 | 판단용 재생 초 | 릴리스 재생 초 | 수동 시각 오차 |
|---|---:|---:|---:|
| 1/1 | 76.0 | 78.70 | ±0.15초 |
| 1/2 | 88.0 | 91.10 | ±0.25초 |
| 1/3 | 102.8 | 104.45 | ±0.20초 |
| 1/4 | 119.0 | 122.70 | ±0.25초 |
| 1/5 | 134.5 | 136.20 | ±0.25초 |
| 1/6 | 확인 불가 | 저장하지 않음 | — |
| 2/1 | 182.0 | 185.50 | ±0.25초 |
| 2/2 | 198.0 | 200.40 | ±0.25초 |
| 2/3 | 220.0 | 224.00 | ±0.25초 |
| 3/1 | 253.5 | 256.10 | ±0.25초 |
| 3/2 | 274.0 | 276.80 | ±0.25초 |
| 3/3 | 290.0 | 293.10 | ±0.25초 |
| 4/1 | 328.0 | 331.40 | ±0.25초 |
| 4/2 | 345.0 | 348.20 | ±0.25초 |
| 5/1 | 356.5 | 358.60 | ±0.25초 |
| 5/2 | 370.0 | 373.20 | ±0.25초 |
| 5/3 | 390.0 | 393.00 | ±0.25초 |
| 5/4 | 410.0 | 413.00 | ±0.25초 |
| 5/5 | 430.5 | 431.65 | ±0.25초 |
| 5/6 | 450.0 | 453.00 | ±0.25초 |

1/6은 영상이 없는 투구가 아니다. 150.0·151.8초의 투수 구종 사용률 그래픽이
점수판과 마운드를 가리고, 152.4초에는 화면 전환 중이며, 152.8초에는 이미 투구 동작 중이다.
따라서 이 검토에서는 투구 동작 전 판단용 화면을 확정하지 않았다.
향후 상태 추적은 그래픽·리플레이 중에도 과거 확인 상태를 유지하되 신선도를 표시해야 한다.

3번 타석(Vientos vs Schwellenbach, 1회초 2아웃 주자 없음)은 Claude Code가 내장 브라우저에서
253.5·274.0·290.0초의 세트 자세와 점수판(카운트 0-0/0-1/0-2, 아웃 2, 주자 없음, 0:0)과
하단 투수/타자 배너를 확인해 판단 시각으로 기록했다. 릴리스는 팔 코킹·앞발 착지 프레임과
팔로스루 프레임(0.4초 간격 샘플)으로 브래킷한 중간값 256.1·276.8·293.1초, ±0.25초다.

5번 타석(Albies vs Megill, 1회말 1아웃 주자 없음)은 Claude Code가 브라우저 canvas 프레임 추출
(video.crossOrigin=anonymous 재로드 후 drawImage, 640px 전체 프레임을 로컬 수신 서버로 저장)로
356.5·370.0·390.0·410.0·430.5·450.0초의 세트 자세와 점수판(카운트 0-0/1-0/1-1/2-1/2-2/3-2, 아웃 1,
주자 없음, 0:0, 배너 MEGILL P:2~P:7 / 2. ALBIES .247)을 확인해 판단 시각으로 기록했다.
릴리스는 358.6·373.2·393.0·413.0·431.65·453.0초, ±0.25초. 5/1은 Harris II 컷어웨이 뒤 356.0초 디졸브
직후, 5/5는 428~430초 투수 글러브 클로즈업 뒤 430.5초에 와이드샷이 돌아와 판단-릴리스 간격이
각각 약 2.1초·1.2초로 짧다. 6구 뒤 458초에는 점수판이 0-0·1루 주자로 바뀌어 볼넷을 확인했다.
feed UTC 외삽은 이 타석에서도 맞지 않았다(6구 예상 약 475초 vs 실제 453.0초).

릴리스는 전후 샘플 장면 사이의 수동 추정치다. 프레임 단위 정답으로 사용하지 않는다.
판단 시각은 최초 인식 가능 시각이나 투구 동작 시작 시각을 뜻하지 않는다.
`decision + uncertainty < release - uncertainty`가 필요하지만,
이 수식만으로 투구 동작 전 장면인지 또는 선수 인식이 가능한지 보장되지 않는다.
사람의 시각 검토와 note를 함께 확인한다. 현재 오차는 통계적 신뢰구간이 아니다.

## 실행과 중단 후 재개

저장소에 작은 출처 스냅샷·ID manifest·주석을 보관했다. 모델과 원본 Statcast 없이 준비와
검증이 가능하며, 영상 재생에만 인터넷이 필요하다. 전체 MP4를 내려받지 않는다.

```bash
uv run --frozen python scripts/63_annotate_broadcast.py prepare
uv run --frozen python -m http.server 8772 --bind 127.0.0.1 --directory outputs/annotation
```

Chrome에서 `http://127.0.0.1:8772`를 연다. 이 서버는 생성된 주석 페이지 폴더만 제공한다.
현재 모델 시연용 8770 서버와 독립적이다. 서버 종료는 실행 터미널에서 Ctrl+C.

1. Git에 저장된 `docs/results/mlb_p0/game_747139_timing.json` 내용을 화면 아래 JSON 칸에
   붙여넣고 **아래 JSON 불러오기**를 누른다. 기존 브라우저 임시 주석을 바꾸므로 먼저 내보낸다.
2. 미검토 투구를 선택하고 영상 재생 초를 이동한다. **영상 탐색 중…**이 끝난 뒤 장면을 확인한다.
3. 판단·릴리스 시각, 양의 오차 범위, 확인 근거를 기록하고 **이 투구 저장**을 누른다.
   이 버튼을 누르기 전 입력은 저장되지 않는다. 불명확하면 **이 영상에서 확인 불가**를 선택한다.
4. **JSON 내보내기**로 파일을 저장한다. 브라우저 임시 저장은 같은 브라우저·origin에서만
   복원된다. 맥미니·다른 브라우저·다른 포트로 이동할 때에는 JSON 파일을 사용한다.
5. 아래 CLI 검증을 통과한 JSON과 검증 보고서를 함께 커밋한다. 생성 HTML은 Git에서 제외한다.

```bash
uv run --frozen python scripts/63_annotate_broadcast.py check --annotations docs/results/mlb_p0/game_747139_timing.json --require-pa 5 --output docs/results/mlb_p0/game_747139_timing_validation.json
```

검증 보고서를 갱신할 때 `--require-pa`는 방금 완료한 타석 번호로 지정한다.
`--require-pa`를 생략하면 부분 주석도 검증한다. 미검토·확인 불가 투구가 있으면 해당 타석을
완전 주석 타석으로 세지 않는다. 현재 파일에 `--require-pa 1`을 지정하면 실패해야 정상이다.

## 출처와 검증 규칙

- `game_pk + at_bat_number + pitch_number`와 MLB `play_id`가 모두 일치해야 한다.
- 주석을 정확한 manifest SHA-256, 영상 페이지·MP4 URL·길이에 묶는다.
  다른 방송사 클립이나 편집본에 같은 초를 적용하지 않는다.
- ID 중복·불일치, 음수·NaN·무한대·숫자 문자열, 영상 범위 초과, 시각 역전·겹침을 거부한다.
- feed UTC 시각은 탐색 참고만 가능하며 주석 초로 변환하거나 보간하지 않는다.
  2026-09-22 실제로 깨지는 것을 확인했다. PA 3 마지막 투구(17:15:15 = 영상 293.1초)에서
  PA 4 첫 투구(17:17:41)까지 wall-clock 146초가 영상에서는 약 35초였다. 이닝 교대 구간이
  편집돼 재생 시간이 실시간보다 느리게 간다. 선형 변환으로 찍으면 다른 타석에 도달한다.
- MP4 자체의 콘텐츠 해시는 없다. 동일 URL의 원본이 교체되면 장면을 다시 확인해야 한다.
- 경기 747139는 기존 test cohort에 포함된 개발·시연 자료다. 이를 보고 튜닝한 결과를
  새로운 독립 성능으로 보고하지 않는다.

점수판 인식 평가셋은 아래 절의 규약으로 이 시각에 한정해 만든다. 확인 불가 사례를 삭제해
인식률을 높이지 말고 coverage와 오류율을 함께 보고한다.

## 점수판 인식 평가셋 (B, 2026-09-22 판정 기준 보완)

입력 세 가지와 역할을 섞지 않는다.

- **manifest `pre_state`** = 기록 메타데이터(Statcast/MLB feed) 라벨. OCR 결과가 아니다.
- **timing** (`mlb_broadcast_timing_v1`) = 사람이 확인한 판단 프레임(재생 초).
- **scoreboard review** (`mlb_scoreboard_review_v1`, `docs/results/mlb_p0/game_747139_scoreboard_review.json`)
  = 그 판단 프레임에서 **사람이 점수판 bug를 읽은 값**. 필드별로 `observed` 값을 적고(`null` = 그 프레임에서
  판독 불가), `readability`(readable / partial / unreadable)·검토자·방법을 함께 적는다. note 문자열에
  "scoreboard"가 있는지로 판정하지 않는다. manifest 값을 베껴 넣지 않고, 영상으로 읽지 않은 값은 넣지 않는다.

`scripts/64_build_scoreboard_evalset.py review-check | build | check | score`
(`src/data/scoreboard_evalset.py`, 스키마 `mlb_scoreboard_evalset_v2`).

- 필드 상태: `confirmed`(읽은 값 = 라벨) / `mismatch`(읽은 값 ≠ 라벨 → `label_conflicts`에 보고, 평가 제외) /
  `unreadable`. **confirmed 필드만 평가 대상**이다. 필드마다 평가 가능 투구 수가 다르므로 분모도 필드별이다.
- 제외 목록 `excluded`: `occluded`(timing 확인 불가) / `scoreboard_unreviewed`(시각은 있으나 필드별 리뷰 없음) /
  `no_confirmed_field`. 제외 투구와 미확인 필드에 대한 예측은 `non_evaluable_attempts`로만 세고 정답·오답에 넣지 않는다.
- 분모(코드 docstring·이 문서·`score` 출력의 `denominators`가 같은 문자열이어야 하며 테스트가 확인한다):

```
coverage = evaluable / total_pitches
attempt_rate = attempted / evaluable
correct_rate = correct / evaluable
error_rate = wrong / evaluable
abstain_rate = abstained / evaluable
accuracy = correct / attempted
```

  `evaluable`은 필드별 confirmed 투구 수(`all_fields`는 모든 필드가 confirmed인 투구 수), `abstained = evaluable − attempted`,
  따라서 `correct_rate + error_rate + abstain_rate = 1`. `accuracy`만 시도 수가 분모이며 시도가 없으면 `null`이다.
- 2026-09-22 현황(경기 747139): timing 20구 중 19구를 Claude Code가 캔버스 프레임으로 다시 읽어 10개 필드 모두
  `confirmed`(라벨 충돌 0), 1구(PA 1/6)는 `occluded`. 미검토 302구는 `total_pitches`에만 들어간다.

검증: 주석 관련 23개를 포함한 Windows CPU **264 passed, 2 deselected**(38.20초),
Ruff 47개 경로와 JavaScript 구문 검사 통과. Chrome에서 저장·새로고침 복원·JSON 내보내기,
출처 불일치 불러오기 거부·정상 불러오기를 확인했다. 단일 검토자의 수동 주석으로,
다른 검토자와의 일치도는 아직 측정하지 않았다.

2026-09-22 PA 3 추가 후(Claude Code): `check --require-pa 3` 통과(11 확인 / 1 확인 불가 /
310 미검토, 완전 타석 2·3), `--require-pa 2` 통과, `--require-pa 1` 실패(정상),
tests/test_broadcast_timing.py 23 passed. 코드 변경은 없다. 내장 브라우저에서
`http://127.0.0.1:8772` 페이지와 원본 MP4 스트리밍은 동작했으나, 탐색 직후 스크린샷이
자주 타임아웃되고 zoom 크롭이 지원되지 않으며 입력 포커스 시 페이지가 스크롤되어
프레임마다 상단으로 되돌린 뒤 캡처했다. 1/6은 그대로 확인 불가로 남긴다.

2026-09-22 PA 4 추가 후(Claude Code): `check --require-pa 4` 통과(13 확인 / 1 확인 불가 /
308 미검토, 완전 타석 2·3·4), `--require-pa 3`·`2` 통과, `--require-pa 1` 실패(정상),
tests/test_broadcast_timing.py 23 passed. 코드 변경은 없다.
1280x720 원본에서는 카운트·아웃·타자 배너를 육안으로 읽기 어려워, 브라우저에서 점수판 영역을
canvas로 3배 확대해 판독했다(`drawImage`로 crop+scale, 저장소의 페이지 자체는 수정하지 않았다).
이 방법으로 4/1은 `0-0 / 아웃 0 / MEGILL P:0`, 4/2는 `0-1 / 아웃 0 / 1. HARRIS II .266`을 확인했다.
확대 보조 뷰를 주석 페이지의 정식 기능으로 넣을지는 미정이다.
내보낸 JSON과 저장 파일이 모든 항목의 ID·상태·시각 해시까지 일치하는지 대조했다.

2026-09-22 PA 5 추가 후(Claude Code): `check --require-pa 5` 통과(19 확인 / 1 확인 불가 /
302 미검토, 완전 타석 2·3·4·5), `--require-pa 4` 통과, `--require-pa 1` 실패(정상),
tests/test_broadcast_timing.py 23 passed. 코드 변경은 없다. 브라우저 localStorage 복원본의 4/1 note가
커밋본과 달라(초안 잔존) 기존 14개 항목은 Git 커밋본을 그대로 쓰고 5/1~5/6만 덧붙였다.
내장 브라우저 스크린샷은 타일·크롭 렌더링 오류가 잦아 canvas 추출로 대체했다.
