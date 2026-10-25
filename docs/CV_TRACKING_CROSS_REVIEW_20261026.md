# CV37 실제 교차 검토와 수리 — 2026-10-26

사용자 CLI 업데이트·정상 한도 초기화 후 전역 Claude Code **2.1.310**에서 `claude-fable-5-1`, effort=max로 고정 소스의 정적 검토를 다시 실행했다. 원본 영상·사람 응답·비밀·상대 소스는 보내지 않았다. 도구/MCP/파일 수정/명령 실행은 허용하지 않았고, 최종 답변과 실제 보고 모델을 확인했다. 이전401·400·429 기록은 [당시 영수증](results/cv_tracking_20261026/review_attempts_v2.json)으로 보존한다.

추적·측정 분할 검토와 수정 재검토의 최종 답변을 모두 수신했다. 확인된 코드2건·보고4건을 수리했고, 추가 fallback 지적1건은 현재 환경에서 미재현으로 보존했다. 이는 **제한된 연구 범위의 검토 완료**이며 전체 런타임 무결함·미트 정확도·운영 준비 PASS가 아니다.

## 추적 코드

[첫 Fable 답변](results/cv_tracking_20261026/fable_tracker_review_v1.json)은 두 파일의 고정 SHA를 검토해 P1 없음·P2 두 건을 반환했다.

1. `seed`가 있으면서 `usable=False`인 입력을 조용히 버리는 오류: 프레임 상태를 바꾸기 전에 명시적으로 거부하도록 수정했다. 같은 프레임의 올바른 재시도를 검사한다.
2. 호출자의 CUDA TF32 설정이 상관계수와 경계 판단에 영향을 주는 오류: 상관 계산에서 TF32·외부 autocast를 끄고 다른 설정과 호출 후 상태를 보존한다. 추가 CPU autocast 문제도 재현했다. cuDNN 설정이 프로세스 전역이므로 **프로세스당 계산 작업자 하나**라는 제한을 명시했다.

합성 회귀 세 개가 수정 전 실패했고, 수정 후 실제 노트북 CUDA를 포함한 관련51검사가 통과했다. 수정 소스는 `938145f0c23559ea0f3b473cbe1b52df70079be9`다. [재실행 영수증](results/cv_tracking_20261026/fix_replay_v2.json), [v2 보고서](results/cv_tracking_20261026/report_v2.json). 같은625프레임의 CPU/CUDA 개별 기록은 각각 v1과 바이트가 같고 입력667파일 SHA도 불변이다. 첫 pilot가 이미 TF32를 껐기 때문에 과거 추적 결과는 유지된다. 이 사실이 모든 입력의 CPU/CUDA 동일성을 증명하지는 않는다.

고정938145f의 [Ubuntu/macOS CI](https://github.com/Pitcheezy/transition-models/actions/runs/40225285644)는 각각2,783passed·10skipped·2deselected로 성공했다. 다른 Codex 에이전트 검토도 추가 P1/P2 없음이지만, 이를 Fable 수정 재검토 대신 사용하지 않는다. [Fable 수정 재검토](results/cv_tracking_20261026/fable_tracker_fix_review_v1.json)는 seed 오류 해소·cuDNN 경로 해소를 확인했고, cuDNN을 끈 cuBLAS 대체 경로의 잔여 TF32 영향을 추가 지적했다.

이 추가 지적은 실제 RTX4070·Torch2.6.0+cu124에서 cuDNN OFF, matmul TF32 OFF/ON × autocast OFF/ON 네 조합으로 확인했다. 기존 경계 fixture(`min_ncc=0.999985`)에서 모두 tracking·점[60,60]·NCC0.9999945163726807로 동일하여 **재현되지 않았다**. [실행 코드·결과 영수증](results/cv_tracking_20261026/fallback_probe_v1.json). 코드를 추측으로 더 수정하지 않았으며, 이 확인을 모든 입력/다른 라이브러리의 무결함 증명으로 삼지 않는다. Fable의 잔여 지적은 미확정으로 보존하고 추적기 지원 범위를 현재 고정 환경·검증한 경로로 제한해 설명한다. 전체 런타임 P1/P2가 모두 없다는 PASS는 선언하지 않는다.

## 측정·보고 코드

[실제 Fable 답변](results/cv_tracking_20261026/fable_pilot_review_v1.json)은 세 파일을 검토해 P1 없음·P2 네 건을 반환했다. 원본 JPEG·시간·seed 결속은 제공 파일 범위에서 검토했고, 정확도 판정은 하지 않았다.

- 전체625행 지연에는 미초기82행·lost420행이 섞인다. 실제 활성 추적123회, seed10회, 계산 없는492회를 나누어 전체 읽기→결과 지연을 추가한다. 첫 지적의502행은 현재 상태가 tracking이 아닌 행의 합이며, 실제 계산한 최초 실패10회도 포함한다. 따라서502를 계산 없는 행으로 쓰지 않고 `prior_state` 기준으로 정정한다.
- lost420행과 최초 중단10회를 구분하고, 행별 `prior_state`와 최초 중단 사유를 기록한다. lost 뒤에는 재추적하지 않는다.
- 기존 AI 점과의 거리54쌍은 정확도가 아니다. seed 적격 규칙과 별도로 사용 가능/불가 판독의 분모를 명시해 분리 집계한다.
- 저장된 pilot·답변의 해시와 CPU/스레드 정보를 보고서에 연결한다. 해시는 파일 식별이며 시각적 정답 증명이 아니다.

기존 report/records v1·v2는 수정하지 않았다. 고정 `611d0c669e7529a5fec688f222408d2ab399a5de`에서 새 [report v3](results/cv_tracking_20261026/report_v3.json)를 실행했다. [영수증](results/cv_tracking_20261026/report_fix_replay_v3.json)의 SHA와 source4파일 해시로 연결한다. 추적 파라미터·입력667파일은 불변이고 새 두 메타데이터 필드를 제외하면 CPU/CUDA625행 모두 각각 v2와 동일하다. 관련55검사(실제 CUDA 포함)와 Ruff를 통과했다.

- 실제 활성123·초기화10·대기492로 합계625행. 첫 실패10회(유사도5/모호3/왕복2), 실패 후 지속410행이며 전체 lost420행이다.
- 기존 AI 비교54쌍은 이번 자료에서 모두 적격 판독이었다. 부적격0쌍의 중앙값/95분위는 null이다. 이번 수치가 바뀌지 않았어도 향후 부적격 판독의 혼합을 알아볼 수 있도록 분모를 남긴다.
- 활성 읽기→결과 중앙값 CPU12.82ms·CUDA11.23ms, 계산만4.78ms·2.41ms. 순서/캐시 영향을 포함하며 서비스 지연 측정이 아니다.
- `saved_pilot_inputs`에 pilot_private SHA, 답변40파일 상대경로 SHA와 정렬 JSON digest, environment에 실제 processor/논리코어/스레드 수를 기록했다. 공개 문서의 장비명은 별도 CIM 조회로 보충했다.

[측정 수정 Fable 최종 답변](results/cv_tracking_20261026/fable_pilot_fix_review_v1.json)은 고정611d0c6의 네 지적 해소·새 구체 P1/P2 없음을 확인했다. 원본 파일 소비 순간의 원자적 스냅샷, 프레임 추출 PTS의 독립 검증, 모든 런타임 지원까지 검토한 것은 아니다. Fable은 도구를 사용하지 않았으며 실제 실행·CUDA 검사는 우리 노트북 증거다.

고정611d0c6의 [최종 코드 CI](https://github.com/Pitcheezy/transition-models/actions/runs/40225993172)는 Ubuntu/macOS 각각2,787passed·10skipped·2deselected로 성공했다. 이후 인계 문서 갱신은 체크리스트8검사·JSON/해시/링크·diff와 Ruff로 확인한다. 원격 CPU CI는 실제 Mac 사용 검수나 CUDA 실기기 검사를 대신하지 않는다.

## 다음 기술 작업과 협업

현재 추적은 고정 패치의 시간순 일관성 검사다. 10구 모두 중단되고 유지 중앙값0.551초이므로 안정적인 미트 추적기가 완성됐다고 말할 수 없다. 다음 CV38은 유효 구간의 후보/현재 위치를 분리하고 잘못된 초기 점·변형·가림에 따른 실패를 구분한다. 사람 정확도·독립 평가·운영 배포는 별도 조건이다.

[노트북·외장 SSD·Colab 판단과 미발신 고지안](CV_COMPUTE_PLAN_20261026.md)을 따른다. 우리 상황판에 상세 계획은 기록돼 있으며, Song에게 새 글을 발신하지 않았다. 이번 수정은 우리 연구 브랜치에만 적용하며 공개 파일 계약·운영 화면·상대 일정은 변경하지 않는다.
