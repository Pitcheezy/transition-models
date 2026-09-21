# MLB P0 — Codex / Claude 인계 기록

현재 범위는 MLB 우선 개발이다. KBO는 최종 확장 목표로 유지한다.
2026-09-22 Codex가 아래 코드를 구현·검증했다. Claude의 첫 호출은 OAuth 만료(401)로
실행되지 않았다. 이후 사용자가 재로그인을 완료했으나, 비공개 코드 외부 전송에 대한
자동 승인 검토가 리뷰 실행을 거부해 구체적인 전송 승인을 기다리고 있다.
이 Codex 작업에서 수신한 Claude 리뷰 결과는 없다.
사용자는 별도 Claude 점검이 5시간 사용 한도로 중단됐다고 보고했다. 그 세션의 파일 변경과
검토 결과는 여기서 확인하지 못했다. 재개할 때 먼저 보존·대조하고,
[새 Claude 재개 프롬프트](CLAUDE_RESUME_PROMPT.md)를 사용한다.
[로컬 검토와 HTTP 수정](MLB_P0_REVIEW_2026-09-22.md)을 참고한다.
2026-09-22 Claude Code가 [재개 프롬프트](CLAUDE_RESUME_PROMPT.md)에 따라 3번 타석 주석을
추가했다(아래 체크포인트 7). 이전 Claude 전체 점검 세션의 파일 변경은 이 저장소에 없었다
(작업 트리 깨끗, HEAD 6a07125 확인 후 시작).

## 교대 원칙

- 한 번에 한 도구만 코드를 수정한다. 다른 도구는 명시한 커밋을 읽고 리뷰한다.
- AGENTS.md, docs/MLB_P0.md, docs/PREPITCH_CONTRACT.md,
  docs/OPERATIONAL_VALIDATION_2026-09-21.md를 먼저 읽는다.
- 브랜치는 `codex/fix-point-label-alignment`. 검증한 단위마다 커밋·푸시한다.
- 원본 영상, 데이터, 모델 캐시, 로그인 정보는 새로 Git에 넣지 않는다.
- 독립 스트라이크·볼·파울 확률과 목표 위치는 현재 미지원이다. 0으로 대체하지 않는다.
- 한도 약 20%에서는 인계 기록을 갱신하고 약 10%에서는 새 대형 작업을 시작하지 않는 것을
  운영 기준으로 삼는다. 서비스의 실제 한도·복구 시각은 별도로 확인한다.
- 두 도구 모두 제한되면 검증된 Python 작업은 별도 터미널에서 로그를 남겨 실행하고,
  영상 주석은 JSON으로 내보낸다. 자동 유료 전환·크레딧 사용은 하지 않는다.

## 완료한 체크포인트

1. `6fe5fbc`: 경기 747139의 322개 투구를 공식 feed와 Statcast ID로 연결했다.
   투수·타자·구종을 대조하며 중복/누락/충돌은 성공으로 처리하지 않는다.
2. `bb4fa75`: 엄격한 투구 전 상태 규약과 CLI/웹 공통 추천 서비스를 구현했다.
   기존 Strike에 파울이 포함되는 의미 문제를 드러내고 지원 범위 밖 추천을 보류한다.
3. 수동 웹 시연: 실제 운영 MLP 앙상블 → 구종 후보별 확률 → 추천 → 화면까지 연결했다.
   예시 SL 추천 / 피안타 약 7.12%. 입력 변경 시 기존 결과를 지운다.
4. 공식 MLB 전체 경기 입력과 첫 투구 클립을 점검했다. Chrome 실제 영상 재생 확인.
   전체 파일은 저장하지 않았으며 Codex 내장 브라우저 영상 재생은 실패했다.
5. 자료 점검 재현 CLI와 별도 8종 투구 관찰 정답 생성기를 추가했다.
   정규시즌 2,142,792행 중 2,135,726행 정답 생성, 자동 판정 6,796행 및 포수 방해
   270행 제외, 알 수 없는 유형 0행. 기존 10종 모델을 수정하거나 재학습한 결과는 아니다.
6. **중계 시각 주석**: `scripts/63_annotate_broadcast.py`와 브라우저 도구 구현.
   실제 SNY 영상 첫 두 타석에서 8개 시각 확인, 1개 판단 화면 확인 불가, 313개 미검토.
   두 번째 타석의 세 투구는 모두 주석 완료. 1/6은 통계 그래픽 때문에 보류했다.
   [결과·재개 명령](MLB_BROADCAST_TIMING.md). 주석 저장·복원·내보내기·출처 불일치 거부를
   Chrome에서 확인했고 CLI로 투구 ID·시각 순서·완전 타석 여부를 검증했다.
7. **3번 타석 시각 주석 (Claude Code, 2026-09-22)**: 데스크톱 앱 내장 브라우저에서
   `http://127.0.0.1:8772` 주석 페이지의 실제 SNY 영상을 재생해 Vientos 타석 3구(3/1, 3/2, 3/3)의
   판단·릴리스 시각을 추가했다. Git 저장 주석을 먼저 불러와 보존했고 기존 9개 항목은 바뀌지 않았다.
   누적 **11개 시각 확인, 1개 확인 불가, 310개 미검토**, 완전 타석 2·3.
   실행한 검사: `63_annotate_broadcast.py check --require-pa 3` 통과(검증 보고서 갱신),
   `--require-pa 2` 통과, `--require-pa 1` 예상대로 실패, `pytest tests/test_broadcast_timing.py`
   23 passed. 코드 변경 없음(JSON·검증 보고서·문서만)이라 전체 check_project는 재실행하지 않았다.
   내장 브라우저 제약: 탐색 직후 스크린샷 타임아웃이 잦고 zoom 크롭 미지원, 입력 포커스 시
   페이지가 스크롤돼 프레임마다 상단으로 되돌려 캡처했다. 8772는 이미 실행 중이던 같은
   주석 페이지 서버를 재사용했다.

이 문서와 함께 추가되는 후속 커밋의 해시는 `git log -6 --oneline`으로 확인한다.
전체 Windows CPU 검사: **264 passed, 2 deselected**, Ruff 47개 경로 통과.
JavaScript 구문 검사 및 Chrome 수동 입력·실제 추론·9회 이후 추천 보류 확인.
GitHub CI 결과는 해당 커밋의 validation 워크플로에서 따로 확인한다.
주석 모듈을 먼저 import한 새 프로세스에서도 Torch→Pandas 문자열 생성이 성공하는지
회귀 검사한다. 조기 hashlib/urllib.request 초기화로 Windows Arrow가 멈추는 조건을
재현해 주석 모듈의 관련 import를 실제 검증 함수 호출 시점으로 늦췄다.
기존 직접 임베딩 경로의 모든 초기화 문제가 해결됐다는 뜻은 아니다.

전체 경기 322개 상태의 실제 서비스 점검도 완료했다. 188개 추천, 94개는 과거 구종 지원 부족,
40개는 9회 이후 범위 제외로 보류한다. `scripts/62_check_game_service.py`로 재현한다.
기존 고정 2022 프로필은 신규 투수에 대응하지 못하므로 시점 이전 자료만 사용하는 갱신이 필요하다.
62번은 실행 중인 59번 서버를 호출하는 표준 라이브러리 기반 HTTP 검사다.
모델을 별도 새 프로세스에 직접 임베딩한 진단 중 첫 Arrow 문자열 변환 멈춤을 관찰했다.
선행 pandas 초기화로 정상 완료한 실행도 있으나 근본 원인은 미확정이다.
정상인 59번 서버와 HTTP 경로를 유지하고 직접 임베딩 경로는 별도로 조사한다.

## 바로 실행하기

기존 운영 아티팩트가 있는 저장소 루트에서:

```bash
uv run --frozen python scripts/59_serve_manual_demo.py --with-example-video
uv run --frozen python scripts/check_project.py --cpu-only
node --check src/web/static/app.js
```

Chrome에서 `http://127.0.0.1:8770`을 연다. 포트 충돌 시 `--port 8771`.
필수 모델/데이터 경로와 Mac 이관은 docs/MLB_P0.md를 따른다.

## Claude 재로그인 후 첫 작업

아래는 이전 읽기 전용 리뷰 요청이다. **사용자가 5시간 제한 이후 최신 구현을 이어가려는
경우에는 [CLAUDE_RESUME_PROMPT.md](CLAUDE_RESUME_PROMPT.md)를 우선한다.**

우선 읽기 전용 리뷰를 맡긴다. 기존 입력 규약을 새로 만들라는 오래된 지시는 사용하지 않는다.
아래 내용을 Claude Code에 전달할 수 있다.

> 현재 브랜치의 6fe5fbc부터 HEAD까지 MLB P0 변경을 읽기 전용으로 리뷰해라.
> AGENTS.md와 docs/MLB_P0_HANDOFF.md, docs/PREPITCH_CONTRACT.md부터 읽어라.
> 투구 ID 대응, 미래 정보 누수, 레거시 확률 의미, 추천 지원 범위,
> HTTP 입력 검증과 UI의 오래된 결과 표시, 새 8종 정답의 타석 종료 사건 구분을 집중 점검해라.
> src/data/mlb_video.py, mlb_sources.py, pitch_observation.py,
> src/inference/prepitch_contract.py, recommendation.py, src/web 및 관련 tests가 범위다.
> 파일을 수정하거나 커밋하지 말고, 재현 가능한 결함을 경로·행·영향과 함께 보고해라.
> 실제 결함이 없다면 없다고 쓰고 검토 한계를 밝혀라. 이후 Codex가 확인하고 수정한다.

## 남은 순서

1. **영상 시간 주석 확대**: 2·3번 타석을 완료했다. 저장된 JSON을 불러와
   네 번째 타석부터 계속한다. feed UTC 시각을 재생 시간으로 쓰지 않는다.
   `63_annotate_broadcast.py check --annotations docs/results/mlb_p0/game_747139_timing.json
   --require-pa 3`로 기존 주석을 먼저 확인한다. 이후 점수판 인식 평가셋으로 연결한다.

   다음 첫 실행 명령(저장소 루트, 모델·원본 Statcast 불필요):

   ```bash
   uv run --frozen python scripts/63_annotate_broadcast.py check --annotations docs/results/mlb_p0/game_747139_timing.json --require-pa 3
   uv run --frozen python scripts/63_annotate_broadcast.py prepare
   uv run --frozen python -m http.server 8772 --bind 127.0.0.1 --directory outputs/annotation
   ```

   페이지에서 Git 저장 JSON을 불러온 뒤 4번 타석(투구 4/1부터)을 확인하고, 내보낸 JSON을
   같은 경로에 저장해 `--require-pa 4 --output docs/results/mlb_p0/game_747139_timing_validation.json`
   으로 검증 보고서를 갱신한다.
2. **기존 영상 재검증**: 옛 오타니 수집기는 CSV `iloc[i]`를 사용했다.
   기존 영상 파일명은 재확인 전 정답이 아니다. 원본 확보 후 playId로 재대조한다.
3. **새 확률 모델**: 8종 정답을 기존 특징에 투구 ID로 연결하고 시간 분할을 유지한다.
   학습·독립 보정·CE/Brier 검증을 거친 뒤에만 UI의 미지원 확률을 활성화한다.
4. **위치/인식**: 목표 위치와 제구 오차, 타자 특성, 점수판 OCR, 선수·상태 추적을 순차 구현한다.
5. **효용 검증**: 기존 정책 실점 차이 CI는 0을 포함한다. 실제 실점 개선 입증으로 발표하지 않는다.

경기 747139는 이미 기존 test cohort에 포함되어 있다. 개발·시연용이며,
이 경기를 보고 튜닝한 뒤 새로운 독립 검증 성능으로 보고하지 않는다.
