# 실제 AI 미트 관측 호출·계측 v1

2026-10-05. CV-5a의 **실제 한 프레임 관측 경로**를 연결했다. 전체 한 타석 자동 리플레이는 아직 미완료다.
저장된 좌표를 읽지 않고, 서로의 응답·기존 라벨·릴리스 시각을 전달받지 않은 새 Codex 에이전트가 각각 원본 이미지 한 장을 실제 판독했다. 사람 라벨이나 독립 정확도 평가가 아니다.

## 실제 실행

기존 747139 개발 경기에서 순서상 첫 완전 시각 주석 타석인 PA2를 골랐다. 판독 전에 고정한 175·180·185초 프레임을 공식 전체 영상에서 추출하고 URL·재생 시각·바이트 SHA 영수증을 검사했다. 175~230초 후보 클립도 로컬에 확보했다(약 28MB). remux된 클립의 시간축과 전체 타석 범위는 아직 검증하지 않았다. 이번 판독 프레임은 그 클립이 아닌 원본 URL에서 직접 추출했다.

| 원본 재생 초 | AI 판정 | 미트 원본 픽셀 | 요청→응답 수신 초 |
|---:|---|---|---:|
| 175 | unavailable | None | 63.125 |
| 180 | unavailable | None | 45.297 |
| 185 | marked | [680, 273] | 54.390 |

175·180초는 덕아웃 화면으로 판독되어 기권했다. 185초에는 partial/resting 미트 좌표를 출력했다. 같은 프레임의 독립 사람 정답으로 맞는지를 검증하지 않았으므로 정확도 수치는 없다.
시간에는 에이전트 생성·도구 호출·컨트롤러 대기와 응답 파일 기록이 포함된다. **모델 단독 추론 시간, 실제 방송 지연, 투구 전 가용률이 아니다.** 실시간 속도로 프레임을 공급한 실험도 아니다.

## 도구와 재현

`intent/observation_session.py`의 begin은 원본 JPEG와 `broadcast_frame_cache_v1` 영수증을 확인해 새 `outputs/cv_observation_*` 폴더에 요청을 만든다. 관측기에는 `request/`의 이미지와 JSON만 준다. private `session.json`에는 원본 경로·시계·호스트가 있으므로 전달하거나 공개하지 않는다.

```bash
python -m intent.observation_session begin --frame path/to/frame.jpg --receipt path/to/frame.jpg.json --source-seconds 185 --out outputs/cv_observation_new
# 실제 관측기가 request/만 읽고 응답 JSON을 별도 파일로 반환해야 한다.
python -m intent.observation_session finish --session outputs/cv_observation_new --response path/to/actual_response.json
```

finish는 이미지·요청·영수증·코드 해시와 같은 호스트의 단조 시계/UTC 경과를 대조한다. 다른 이미지·잘못된 좌표·시계 불일치·기존 결과 덮어쓰기를 거절한다. `marked / unavailable / unknown` 픽셀 관측만 다루며 투구 ID·피트 좌표·IntentEstimate 서비스 출력은 생성하지 않는다.
원본 코드가 바뀌거나 다른 호스트로 옮기면 새 세션으로 시작한다. 파일 검사는 신뢰하는 로컬 실행의 일관성 검사이며 보안 격리·독립성 인증은 아니다. 실패/미완료 요청은 폴더를 그대로 보존하고 새 세션에서 재시도한다.

이번 모델 호출은 Codex의 begin→새 에이전트→finish 조율로 수행했다. CLI만 실행해서 AI가 자동 호출되지는 않는다. 코드 검사는 재현 가능하지만 같은 모델·같은 좌표 출력을 보장하지 않는다.
영상·원본 이미지·private 세션은 로컬에만 있다. [공유 실행 기록](results/cv_followup_20261005/observation_smoke_v1.json)은 개인 호스트명·로컬 경로·중계 이미지를 포함하지 않는다.

후속 검사: [클립 시간축 대조](CV_CLIP_CLOCK_AUDIT_V1.md)에서 한 프레임 불일치를 발견했다. 단순 175초 차감 매핑은 미검증이며, 아래 다음 단계 전에 PTS 대응을 확인한다.

## 다음 한 단위

확보한 후보 클립의 원본 시간축·타석 범위를 확인하고, 고정 간격 프레임 공급과 실제 모델 어댑터 호출을 하나의 자동 실행 루프로 연결한다. 다음에는 입력 도착과 결과 발행까지 계측한다. 현재 세 번의 호출을 전체 타석·실시간 관측 완료로 표시하지 않는다.
기존 M3 사람 검토 86장과 시연 자료는 유지하며 CV-6 추가 재검토는 이 구현의 필수 선행 조건이 아니다.

검사: 새 모듈 27 tests, 전체 **834 passed / 5 skipped / 2 deselected**, Ruff 100경로. 검사 목록 파일의 포맷을 수정한 뒤 통과했다. 기존 Pillow 경고 2건. frozen 186개 SHA 불변.
