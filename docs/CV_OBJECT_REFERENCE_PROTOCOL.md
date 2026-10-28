# CV49a 객체 지목 진단 규칙

2026-10-28, 판독 전 고정. 범위는 849843 첫 타석의 기존 대표 프레임3장뿐이다.
새 추출·전체80장 재투표·학습·평가 잠금 열람을 하지 않는다. 원본과 기존 v3 표시를 바꾸지 않는다.

## 질문과 판독

같은 “미트” 라벨을 쓴 두 AI가 실제로 같은 물체를 지목했는지 살핀다.
원본1280×720 프레임과 이미 저장된 포수 문맥 크롭을 함께 본다. 좌표는 항상 원본의
`[left, top, right, bottom)` 픽셀 정수이고 크롭 좌표·정규화 좌표와 섞지 않는다.
크롭의 원점은 원본(450,240)이며 크기는210×230이다.

각 프레임에 `mitt`, `bare_hand`, `protective_gear` 세 종류를 빠짐없이 기록한다.
각 종류는 `located`(보이는 물체를 지목), `unclear`(구별 불가), `not_visible`(보이는 영역에서 못 찾음) 중 하나다.
`located`만1~4개의 상자를 허용한다. 다른 상태는 빈 목록이며 좌표를 추측해 채우지 않는다.
보호대는 가슴·정강이 보호대 같은 포수 장비를 뜻하며 마스크는 제외한다.
둘레의 대략적인 상자이지 정밀 중심·포수 목표·실제 공 위치가 아니다.
각 판단에는 형태·주변 신체와의 연결 등 근거와 혼동 가능한 물체를 짧게 적는다.

두 판독자는 서로의 이번 응답·상자·이전 후보점을 받지 않고 먼저 응답을 고정한다.
Codex는 과거 개발 내용을 이미 알며, Claude는 새 호출의 사진과 규칙만 받는다.
자료3장 자체가 이미 개발에 사용됐으므로 새 독립 평가 또는 사람 정답으로 부르지 않는다.
첫 응답을 보존하며 구문 오류를 고쳐 조용히 덮어쓰거나 합의를 얻을 때까지 반복 호출하지 않는다.
잘못된 응답은 원문과 거부 사유를 기록한다. 재호출이 필요하면 별도 수정 응답으로 구분한다.

## 내부 자료 형식

- 입력 `pitcheezy-object-reference-input-v1`: `source_commit`, `source_review_sha256_lf`, `game_pk`, `frames`.
  각 프레임은 `pitch_key`, `play_id`, `clip_sha256`, `frame_pts`, `time_base`, `image`,
  `image_sha256`, `width`, `height`, `context_crop`을 갖는다.
- 응답 `pitcheezy-object-reference-reading-v1`: `input_sha256`, `reviewer_id`, `model`, `prior_exposure`,
  `coordinate_system="source_raster_xyxy_half_open"`, `frames`.
  각 프레임은 입력의 `pitch_key`, `play_id`, `clip_sha256`, `frame_pts`, `time_base`, `image_sha256`과
  `objects`를 갖는다. 각 객체는 `kind`, `status`, `boxes`, `reason`이다.
- 입력 해시는 생성된 UTF-8 LF JSON 파일의 실제 바이트 SHA다. `source_review_sha256_lf`만
  기존 판독 JSON의 CRLF를 LF로 바꾼 바이트 해시다. 필드 값·목록 순서의 의미 정규화는 하지 않는다.
- 파일 내용의 중복 키·비유한 숫자, 프레임 누락/중복/식별 불일치, 범위 밖 상자, 잘못된 좌표계,
  상태와 상자의 모순을 거부한다. 파일 해시는 식별 근거이며 작성자·모델의 인증은 아니다.

## 비교와 합격 기준

같은 종류를 양쪽 모두 `located`로 지목하면 모든 상자 쌍의 IoU와 최대값을 보고한다.
겹침0은 `located_pair_disjoint`, 양의 겹침은 `located_pair_with_overlap`으로만 기록한다.
한쪽이라도 `unclear`이면 `one_or_both_unresolved`, 양쪽 `not_visible`은 `both_not_visible`,
한쪽만 `not_visible`인 경우도 `one_or_both_unresolved`다.
겹쳤다는 이유로 정답/합의 판정하거나 상자 중심을 미트 좌표로 내보내지 않는다.
임계값을 이3장에 맞춰 선택하지 않는다. 분모는3프레임·9객체종류 비교이며 독립9표본이 아니다.

1. 투구ID·영상SHA·실제PTS·이미지SHA를 묶고 잘못된 연결/상자를 출력 전에 거부한다.
2. 같은 라벨·다른 공간의 거짓 합의를 드러내고 기권을 임의 좌표로 채우지 않는다.
3. 원본3장·응답SHA·실제 작성 모델·분모·미해결 이유와 비공개 겹쳐보기 SVG를 남긴다.
   기존 대표점·v3의2구 기권·사람 평가를 자동 변경하지 않는다.

검사는 합성 입력으로 결속/기하 계산을 확인하고, 실제3장 결과는 AI 개발 진단으로 따로 기록한다.
이 단위는 새 검출기·연속 추적·물리 거리·의도 정확도의 완성이 아니다.

## 재현과 실행 범위

비공개 입력 디렉터리에 `input.json`과 그 상대 경로 PNG, 두 최초 판독 응답을 둔다.
입력 작성은 기존 CV48c audit의 고정 대표 PTS·영상/이미지 SHA를 대조한 뒤 수행한다.
`source_commit`과 `source_review_sha256_lf`는 출처 식별 정보이며 이 비교 CLI가 그 Git 커밋이나
전체 과거 판독을 다시 인증하는 것은 아니다. 실제3장 수신 경로와 해시는 결과 영수증에 별도 기록한다.

```sh
python scripts/79_compare_object_references.py --input <PRIVATE_INPUT>/input.json --reading-a <PRIVATE_INPUT>/codex_reading.json --reading-b <PRIVATE_INPUT>/claude_reading.json --out outputs/<NEW_PRIVATE_COMPARISON>
python -m pytest tests/test_object_reference.py tests/test_object_reference_cli.py tests/test_checklist_model.py -q
python scripts/check_project.py --lint-only
```

출력은 새 비공개 폴더의 `comparison.json`과 원본 PNG 바이트를 포함한 SVG다. 기존 폴더를
덮어쓰지 않는다. SVG의 A는 첫 판독(하늘색), B는 둘째 판독(분홍색), M/H/G는 미트/맨손/보호대다.
필요 환경은 기존 Pillow와 Python이며, Windows junction까지 명시적으로 거부하는 실행 기준은
Python3.12 이상이다. 이전 Python에서는 resolved-path containment가 유지돼도 junction 자체의
전면 거부를 주장하지 않는다. 이것은 기존 재생 실행팩의 Python 요구 버전을 바꾸지 않는다.
모든 입력 검사는 쓰기 전에 완료하지만 디스크 고장·용량 부족까지 원자적 복구하는 도구는 아니다.
판독자 이름과 모델 문자열은 자가 보고이며 서로 다른 사람/모델이라는 인증 수단이 아니다.
