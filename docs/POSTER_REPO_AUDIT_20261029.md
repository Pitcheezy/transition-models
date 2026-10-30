# 포스터와 Song 저장소 대조 — 2026-10-29

## 결론과 조사 범위

포스터의 자동 수집·추천 계산·관전 화면 구성은 저장소 코드와 대체로 일치한다. 다만 **263구는 비공개 운영 기록**, **180구는 지원 투수의 185구 중 추천이 기록된 수**, **0.13초는 다른 경기의 라이브 리허설 계산 중앙값**이다. NLL −0.0137은 2025 개발 자료에서 빈도 기준선과 비교한 결과다. +0.09%p는 2026 정책 평가의 효과 경계 상단이며, 입증된 향상이나 효과의 점추정이 아니다.

사용자는 10/29 Song 저장소를 찾아보도록 명시적으로 승인했다. GitHub 연결을 통해 코드·커밋된 집계·협업 댓글만 읽었다. 상대 파일·프로세스·실제 API·배포는 변경하거나 실행하지 않았다. 평가 잠금 경기 **849844는 이미 커밋된 집계 보고서만 대조**했으며 원투구 행·영상은 열지 않았고 재측정하지 않았다.

코드 존재, 기존 측정 기록, 현재 운영 여부를 구분한다. GitHub에 올라온 고정 소스가 최신 로컬 UI나 현재 공개 사이트에 채택됐다는 뜻은 아니다. 댓글에 인용된 로컬 장부와 미커밋 산출물은 직접 검사하지 않았으므로 공급자 운영 보고 수준으로 표시한다.

## 주장별 판정과 전시용 권장 문구

| 포스터 주장 | 판정 | 근거와 한계 | 권장 문구 |
| --- | --- | --- | --- |
| MLB Stats API → Python/FastAPI → 상태·PyTorch 추천 → SQLite/JSON → HTTP 업로드 → 정적 웹·React/TypeScript/Vite | 코드 일치, 운영 조건부 | 자동 HTTP 폴링, ARM-B 계산, 저장·발행, 정적 화면 경로가 있다. HTTP 업로드는 선택 기능이고 확인한 기본 설정은 꺼짐이다. 실제 공개 운영 완료를 의미하지 않는다. | “MLB 기록을 자동 수집해 추천을 계산하고, 발행 파일로 관전 화면에 전달하는 구조” |
| 경기·날짜 선택과 결과, 추천 구종·위치, 추천과 실제 비교, 선수 기록, 구종·구속·위치·타석 기록 | 구현 일치, 자료 범위 조건부 | 해당 화면과 데이터 경로가 있다. 모든 선수 필드·모든 경기 입력이 완비된 것은 아니다. Top 3는 양의 비중을 가진 후보 중 최대 3개다. 위치는 과거 투구 분포에서 얻은 대략 위치이며 목표·의도 정답이 아니다. | “경기 기록과 추천 후보를 함께 살펴보는 AI 관전 분석 화면” |
| 월드시리즈 1차전 263구 | 운영 보고 일치 | 경기 ID는 **849805**. 비공개 무인 운영, 업로드 꺼짐, 공개 관객 0명이다. 전체 263구에 추천이 모두 있었다는 뜻은 아니다. | “월드시리즈 1차전 263구를 비공개 자동 수집·기록” |
| 180구 모두 추천 | 분모 명시 필요 | 전체 263구 중 추천 기록 180구. 지원 투수의 공은 185구이고 그중 180구에 추천이 있다. 미지원 선발 78구는 추천 공백, 나머지 지원 투수 5구의 공백 원인 분해는 미측정이다. | “지원 투수의 185구 중 180구에 추천 기록” |
| 추천 계산 0.13초 | 별도 시험으로 한정 | **10/2 경기 849844 라이브 리허설의 계산 중앙값**이다. WS 1차전 180구의 계산 시간이나 API 수신부터 화면 표시까지의 전체 지연이 아니다. | “별도 라이브 리허설에서 추천 계산 중앙값 0.13초” |
| 단순 통계보다 NLL −0.0137 | 수치 일치, 개발 평가 조건부 | 2025 DEV 311,721구·1,161경기, 동결 G0 대 빈도 기준선. 독립 검증·정책 효용·실전 성과를 입증한 결과는 아니다. | “2025 개발 자료에서 빈도 기준선 대비 NLL 0.0137 감소” |
| 2026 약 18만 타석에서 +0.09%p | 향상으로 표현하면 불일치 | 184,288타석 평가의 효과 경계는 약 **[−0.12, +0.09]%p**. 0을 포함하며 공식 판정은 개선 근거 없음이다. +0.09만 떼어 효과로 쓰지 않는다. | “2026 정책 평가의 효과 경계는 −0.12~+0.09%p로, 개선 근거를 확인하지 못함” |
| MLB 모든 경기에서 최선의 공 추천 | 보편적 지원·최선 입증 근거 없음 | 지원하지 않는 투수·행동·불완전 문맥에서는 추천을 거부한다. 정책 우위도 입증되지 않았다. 경기 목록 제공과 모든 투구 추천 가능은 다른 조건이다. | “지원 가능한 상황에서 구종 후보와 대략 위치를 제시하는 실험용 추천” |

## 수치의 정확한 의미

### 263구와 180구: 월드시리즈 1차전 849805

[10/24 운영 인계 댓글](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6385457013)은 263구 중 추천 180구, 미지원 선발 78구, 업로드 꺼짐·공개 0명을 보고한다. 투구부터 첫 수신까지 p50 21.0초·p90 28.1초·최대 49.9초도 별도로 기록돼 있다. 이는 0.13초의 모델 계산 시간과 다른 측정량이다.

[10/28 포스터·졸업 문서 대조](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6464218359)는 지원 투수 185구 중 추천 180구라는 분모를 명시한다. [10/29 종료 기록](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6488226111)은 지원 투수의 공백 5구 원인과 WS 실경기 공당 계산 시간을 미측정으로 남긴다. 이 문서와 장부는 로컬 미커밋 자료이며, 이번 조사에서 직접 재계산하지 않았다.

### 0.13초: 10/2 별도 라이브 리허설

고정 소스 `7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8`의 [LIVE-rehearsal-849844.json](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/results/checks/LIVE-rehearsal-849844.json#L160)은 한 실행 기록에서 계산 결정 275건, 중앙값 0.13초, p90 0.17초, 최대 6.44초를 보고한다. 전체 경기 기록은 277구이며 추천 불가 결정도 포함돼 있다. **평균·p95·모든 공의 고정 지연으로 바꾸어 쓰지 않는다.** 보고서 자체가 서비스 시간·지원 범위 측정이며 모델·정책 평가가 아니라고 구분한다.

### NLL −0.0137: 2025 개발 자료의 예측 손실 비교

[고정 평가 보고서 L15–26](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/docs/reports/G0-whole-MLB-and-calibration-2026-09-27.md#L15)의 주 비교는 투구 가중 평균의 G0−frequency다.

- 평가 대상: 요청 341,941구 중 적격 311,721구, 1,161경기.
- NLL: G0 1.490408196725, 빈도 기준선 1.504081016265.
- 차이: **−0.013672819540**, 조건부 95% CI **[−0.014415351081, −0.012924306116]**.
- 완전 경기 단위 10,000회 bootstrap, 5/5 seed에서 음의 차이. 고정 예측에 조건부인 결과이며 학습·보정·선택 불확실성을 모두 포함하지 않는다.
- ECE10은 G0 0.008710236256, 빈도 기준선 0.001660086965로 기준선이 더 낮다. NLL 개선을 모든 지표의 우위로 확장하지 않는다.

[보고서의 해석 한계 L50](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/docs/reports/G0-whole-MLB-and-calibration-2026-09-27.md#L50)은 이미 노출된 2025 DEV이며 독립 확인·서비스 채택·정책 효과 근거가 아니라고 명시한다.

### +0.09%p: 효과 경계의 상단이며 95% CI 자체가 아님

고정 연구 소스 `813ce61c0621df2559615c23075bfae08a9df78a`의 [MLB-2026-OPE-v1.json L8–26](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/results/MLB-2026-OPE-v1.json#L8)은 2026-03-25~09-27 동결 자료, 2,429경기·184,288타석을 기록한다. 완료 132,019, 시작 전 제외 34,763, 검열 17,506타석이며 공식 판정은 `NO_EVIDENCE_OF_IMPROVEMENT`다.

[L60–70](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/results/MLB-2026-OPE-v1.json#L60)의 `L1R_delta_bounds`는 [−0.001204616445139576, +0.0009206006143749304], 즉 **[−0.12046, +0.09206]%p**다. 이것은 검열을 반영한 효과 경계다. **이 구간을 95% 신뢰구간이라고 쓰지 않는다.** 경계 양 끝에 대한 95% CI가 따로 있다.

- 아래쪽 끝의 95% CI: 약 [−0.17449, −0.07873]%p.
- 위쪽 끝의 95% CI: 약 [+0.05124, +0.14688]%p.

[L109](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/results/MLB-2026-OPE-v1.json#L109)의 평가 대상은 최초 고정 거부 조건까지 추천 정책을 따르고 이후 기록된 행동으로 복귀하는 방식이다. 추천 정책 전체의 가치 자체를 판정한 결과가 아니다. [L167–168](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/results/MLB-2026-OPE-v1.json#L167)은 가정에 조건부인 평가이며 식별 가정이 성립하지 않으면 인과효과가 아니라고 명시하고 D131을 연결한다. 2025 개발 S6의 11,350타석 결과와도 혼합하지 않는다.

## 기능·자동 경로의 고정 코드 근거

다음 링크는 모두 `7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8` 기준이다.

| 확인한 기능 | 근거 | 해석 범위 |
| --- | --- | --- |
| 일정·라이브 피드 자동 수집 | [live_feed.py L361](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/live_feed.py#L361) | 실제 MLB API 호출은 이번에 하지 않았다. |
| FastAPI와 라이브 ARM-B 연결 | [main.py L291](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/main.py#L291) | 저장소에는 실시간 계산 경로와 replay 경로가 함께 있다. 실제 시연 모드는 실행 설정 확인이 필요하다. |
| 추천 후보 최대 3개 | [demo_precompute.py L376](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/scripts/demo_precompute.py#L376) | 정책 선택 비중은 적중·성공 확률이 아니다. |
| 추천 지원 거부 | [policy_runtime.py L315](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/experiments/pitchmdp/pitchmdp/policy_runtime.py#L315) | 불완전 문맥, 미지원 투수, 지원 행동 부재 등을 거부한다. |
| 저장·발행·선택적 HTTP 전송 | [publisher.py L1](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/backend/observer_app/publisher.py#L1), [publish_config.json L29](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/publish_config.json#L29) | 발행기 구현과 공개 배포·업로드 실행을 구분한다. |
| 정적 웹 빌드 | [web/package.json](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/package.json), [정적 파일 조회 api.ts L341](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/api.ts#L341) | 정적 화면이 자체적으로 모델을 계산하는 구조는 아니다. |
| 날짜·경기 목록·종료 결과 | [WatchList.tsx L165](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/WatchList.tsx#L165) | 발행되거나 수신된 경기 자료 범위다. |
| 선수 시즌·오늘 기록 | [GameScreen.tsx L80](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/GameScreen.tsx#L80) | ERA·AVG·OPS와 오늘 기록 표시가 있다. 모든 시즌 세부 필드가 연결됐다는 뜻은 아니다. |
| 수신 구종·관측 비율·평균 구속 | [LivePanels.tsx L20](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/LivePanels.tsx#L20) | 수신된 기록 중 구종이 확인된 공 기준이며, 구속 결측은 평균에서 제외한다. |
| 타석 선택·추천과 실제 위치 비교 | [Sheets.tsx L54](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/Sheets.tsx#L54) | 추천과 실제를 나란히 표시하는 것이 정답 판정은 아니다. |
| 실험 추천·대략 위치·재생 출처 안내 | [Sheets.tsx L41](https://github.com/SongRoute/pitcheezy/blob/7a460cc0bf93f71ea52d3fc3acc6816b9ff3baf8/apps/observer/web/src/service/Sheets.tsx#L41) | 라이브 기록과 경기 후 as-of 재계산을 구분한다. |

## 현재 사이트 작업에 적용

현재 목표는 **기존 사이트에 Song의 추천·관전 기능을 PC와 모바일에서 공통으로 연결한 뒤 CV를 후속으로 진행하는 것**이다. 기존 Song 모델·발행 계약·관전 화면을 재사용하며, 포스터만을 근거로 새 추천 모델이나 별도 관전 프런트엔드를 복제하지 않는다. 로컬 화면 완성과 최신 Song UI 채택, 공개 배포 완료는 각각 구분한다.

전시 화면에는 추천 지원 여부, 라이브 기록인지 저장 자료 재생인지, 자료 시각과 수신 상태를 남긴다. 보편적 MLB 지원·정책 효과·공개 운영 완료를 암시하는 문구는 위 근거 범위로 좁힌다. 이 조사는 문서 대조이며 새 기능 검증·브라우저 검사·모델 평가 결과를 만들지 않았다.
