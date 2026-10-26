# CV-39c — 저장 OCR 관측의 프레임 재생 화면 연결

## 착수 전에 고정한 합격 기준

2026-10-26 사용자 요청의 CV 후속이다. 작성 Claude Fable 5.1(`claude-fable-5-1`), 연구 브랜치 `claude/cv-ocr-view-1026`, 기준 PR72 `360d3c480ce31dda4379c84059e107dbfc6feaab`. PR67→69→70→71→72에 의존하며 main 병합·운영 배포·Song 코드·Cloudflare·공개 계약·IntentEstimate·기존 팩/OCR 원문/사람 응답/M3는 바꾸지 않는다. [착수 기록](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6408517957).

- `pitch_id`·`frame_index`·`frame_seconds`·`image_sha256`를 정확히 결합한다. OCR 보고 SHA→관측 SHA→payload SHA→화면 프레임 JPEG SHA 사슬을 검증하고, 다른 키·SHA 불일치·중복·역순·시각 오류·관측 누락·집계 불일치는 생성 단계에서 거부한다.
- 현재 프레임의 원문/이름·읽음/기권/오류·인접 문자열 같음/변화·비교 프레임만 보여 준다. 이름을 이전 프레임에서 채우지 않고, `VLTNLUS`를 `VIENTOS`로 교정하지 않으며, 변화를 선수 교체로 표시하지 않는다. OCR이 없는 투구는 "관측 자료 없음"으로 기권·엔진 오류와 구별한다.
- 이미지 로딩·실패·뒤로 탐색·투구 전환·늦은 응답에서 OCR 표시도 현재 이미지와 함께 초기화한다. 기존 미트 현재/과거 표시와 재생 조작은 유지한다.
- OCR 문자열은 textContent로만 표시한다. 비공개 경로·원격 URL은 화면과 공개 기록에 넣지 않는다.
- OCR 재호출·새 AI 판독·모델 학습은 하지 않는다. 새 출력 폴더만 만들고 기존 v2/v3 팩과 OCR 원문을 보존한다.

## 구현

- `intent/mitt_ocr_view.py`(새 파일): CV39a v3 팩(영수증 SHA 고정)과 CV39b OCR 실행(보고 SHA 고정)을 읽는다. 보고의 `observations_sha256`·`payload_sha256`으로 관측과 표시 payload를 묶고, 기존 `mitt_frame_ocr._validated_inputs`로 표시되는 모든 투구의 payload·JPEG를 다시 검증한다. 관측 행은 표시 프레임과 같은 수·같은 순서여야 하며 네 키가 정확히 같아야 한다. 역할 행의 형식, 읽음/기권/오류와 이름 유무, `lineup_order`, 인접 판독 비교(0.25초 안의 직전 읽음과 문자열 같음/변화, 기권·오류·간격 뒤 초기화)를 저장 규칙대로 재계산해 대조한다. 보고의 역할별 집계와 (있으면) `comparison_summary`도 행에서 다시 센다. `--ocr-source-receipt`를 주면 OCR이 실제로 읽은 팩(v2) 영수증이 보고의 `receipt_sha256`과 같고 payload·203 JPEG 항목이 표시 팩(v3)과 같은지 확인한다. 출력은 `index.html`·`review.js`·`style.css`·`payload.json`(입력과 동일 바이트)·`ocr.json`·203 JPEG·`receipt.json`이다.
- `web/track-review/index.html`·`review.js`·`style.css`: OCR 패널을 추가했다. `ocrFor`는 네 키로 정확히 한 행만 찾고, 없는 투구는 `none`, 맞지 않는 행·중복·형식 오류는 `mismatch`로 돌려 표시하지 않는다. `ocrView`는 현재 이미지 상태(로딩·오류)와 현재 프레임만으로 문자열을 만들며, 모든 값은 `textContent`로 넣는다. 변화 표시 문구는 "선수 교체 근거 아님"을 포함한다. 기존 Controller·재생·현재/과거 표시는 그대로다.
- `intent/mitt_track_view.py`: 템플릿의 새 자리 `__OCR_VIEW_DATA__`를 `null`로 채운다(이 빌더는 OCR을 싣지 않음). 기존 검사 28개는 그대로 통과한다.

## 결과

기준 폴더의 v3 팩(영수증 `80c6b107…27dd14e`)과 OCR 실행(보고 `6d2ac945…6a931`, 관측 `cea32470…06b4c9b`)으로 비공개 `outputs/cv_ocr_frame_view_20261026_v1/`을 만들었다. 203프레임·3투구 표시, 74행 결합, 관측 없는 투구 2(PA3 2·3구). v2 원 영수증(`7ea09fef…5fd39`)과 payload·203 JPEG 항목 204개 일치, `payload.json` SHA는 입력과 동일(`00c2ff23…5dc223`). 영수증 SHA256 `d281de8ece3d80a4c7f0e541400f627c1895db0c2965622e575b1a186685b1c0`. 집계 재계산은 CV39b 파생 집계와 같다(타자 읽음42=첫비교없음1+같음40+변화1, non-read 32; 투수 non-read 74). [검증 기록](results/cv_ocr_frame_view_20261026/verification_v1.json).

실제 Windows 브라우저(loopback) 확인: 1장 기권/기권 → 33장 `VLTNLUS` 읽음·비교 없음 → 34장 `VIENTOS` 읽음·직전과 문자열 다름(비교 원본 번호 15102)·선수 교체 근거 아님 → 2구 전환 시 "관측 자료 없음"과 빈 역할 → 1구 복귀 시 1장 기권 → 슬라이더 34장 → 두 장 뒤 32장 기권(이전 이름 잔존 없음) → 74장 읽음·같음(비교 15342)·다음 장 비활성. 콘솔 오류 0. Mac/아이폰·원영상 PTS·이름 정확도는 확인하지 않았다.

검사(각 실행 별도, 검토 전): `tests/test_mitt_ocr_view.py` 31 passed(13.28초); `tests/test_mitt_ocr_view.py`+`test_mitt_track_view.py`+`test_mitt_frame_ocr.py` 88 passed(31.50초); `tests/test_ocr_frame_view_ui.cjs` 6 pass; 두 Node 파일 21 pass. 검토 반영 후 같은 3파일 94 passed(35.37초). `scripts/check_project.py --lint-only` 통과(180경로), 체크리스트/인계 검사 26 passed. CI에 새 Node 검사를 추가했다.

## 한계

- OCR은 첫 투구 74장에만 있다. 2·3구의 "관측 자료 없음"은 기권이 아니라 자료 부재다.
- 표시는 저장 문자열의 재생이며 정확도·선수 식별·교체·연속성 판정이 아니다. `VLTNLUS`는 저장된 그대로다.
- 시각은 manifest 기반이며 디코딩 PTS를 독립 검증하지 않았다. 해시 검증은 생성 시점 검사이며 브라우저가 매 프레임 암호학적으로 검증한다는 뜻이 아니다.
- 새 OCR·새 영상·사람 평가·새 경기 독립 정확도는 없다. CV39 전체·CV41 전체·CV35/36·A-y는 그대로다.

## 재현

```sh
python -m intent.mitt_ocr_view --pack <v3 팩> --pack-receipt-sha256 80c6b107c67dd0169a881aa3e60e8ba86048cf85d87d6dd423bb8874927dd14e --ocr-dir <OCR v1 폴더> --ocr-report-sha256 6d2ac945a8609fc5c3e4e4b3dd93eff19c0e744cf70411401427161472a6a931 --ocr-source-receipt <v2 팩>/receipt.json --out <새 폴더>
python -m pytest -q tests/test_mitt_ocr_view.py
node --test tests/test_ocr_frame_view_ui.cjs
python -m http.server 0 --bind 127.0.0.1 --directory <새 폴더>
```

입력 팩과 OCR 폴더는 Git 제외 비공개 자료이며 이미지·캡처는 공개 PR에 올리지 않는다.

## 다른 모델 검토

작성 모델은 Claude Fable 5.1이고, 검토는 이 노트북의 로컬 OpenAI Codex CLI 0.162.0-alpha.2(`claude`가 아닌 `gpt-6-astra`, 읽기 전용 sandbox, 고정 커밋 `e74e187f967ef694939c109500f663580195b18a`)로 받았다. [영수증](results/cv_ocr_frame_view_20261026/codex_review_v1.json)에 시도·명령·결과·원문 SHA를 남겼다.

- 시도 a `exec review --commit`: 명령 실행 호스트가 없어 JS REPL로 읽기 검사만 수행. Node 21검사·산출물 208파일·74행 결합을 확인하고 "actionable 결함 없음". Python 검사는 미실행.
- 시도 b: 명령 실행 불가로 소스를 읽지 못해 검토 차단(미검증으로 기록).
- 시도 c: 커밋 diff와 기존 `mitt_frame_ocr.py`를 stdin으로 제공한 정적 검토. P2 2건을 지적했다. ① `False == 0`이라 프레임 0에서 불리언 키가 결합될 수 있음 → 키 형식(정수·유한 실수·문자열, 불리언 제외) 검사와 프레임 0 회귀 검사 4개 추가. ② 템플릿 자리 순차 치환이 삽입된 JSON 안의 토큰을 다시 치환할 수 있음(`mitt_track_view`도 동일) → 두 빌더가 원본 템플릿을 한 번에 치환하는 `fill_template`로 통일, 데이터 안 토큰 회귀 검사 2개 추가. 검사가 실제 DOM을 mount하지 않는다는 지적은 한계로 남기며 실제 브라우저 확인 기록으로 보완한다.
- 수리 후: 관련 3파일 94 passed, Node 21 pass, 린트 통과. 수정 빌더로 실제 자료를 다시 생성한 `v2` 팩의 영수증은 `v1`과 바이트 동일하다. 수정 커밋과 Codex 재검토 여부는 board 종료 기록을 따른다.
- 이 검토는 연구 범위의 정적·읽기 검토이며 사람 검토·정확도 측정·운영 준비 PASS가 아니다.
