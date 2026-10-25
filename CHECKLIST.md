# 남은 작업 체크리스트

## 전시 CV 집중 개발 — 2026-10-26

사용자 요청으로 일정을 앞당긴 우리 연구 계획이다. Song 마감·계약·운영 동결은 변경하지 않는다. [합격 기준·일정](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6401534435). CV37 개발 시험 완료·수정 권한 반납: 우리 Codex / `codex/cv-track-pilot-1026` / PR69 고정 `c41eb74782d585cce47d2f1d99b4417ea2f4623e`. 원래 Claude 작업 폴더와 자료는 보존한다. [실제 결과·한계](docs/CV_TRACKING_PILOT_20261026.md), [고정 소스·해시](docs/results/cv_tracking_20261026/audit_v1.json). Claude 교차 검토는 인증 만료401로 미실행이며 연구 PR 검토 조건으로 남긴다.

- [x] CV-37. 초기 AI 점 기반 시간순 국소 추적·실패 감지와 고정 개발 시험 완료(10/26, 목표10/28). 원본 첫10구625프레임·기존 sequence315판독, tracking123행(초기10+연속113)·미초기82·lost420, 최초 중단10구(유사도5/모호3/왕복2), 유지 중앙값0.551초. CPU/CUDA 상태·좌표 일치625/625·원본667 SHA 불변. 활성 계산 중앙값4.85→2.29ms, 전체 읽기→결과 속도 향상은 미확인. 관련48검사·Ruff 통과. 구현 `cd23d78`, 안정적 미트 식별/사람 정확도/실시간/배포 완료가 아니다. Claude 실제 검토는 로그인 만료로 미완료. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-26 · Codex]`
- [ ] CV-38. 유효 추적 구간에서만 멈춤 후보 선택, 현재 추적과 과거 후보 분리, 원관측 보존. CV37 결과 후 목표11/1. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-26 · Codex]`
- [ ] CV-39. 프레임 PTS/투구 키 근거 통합·OCR 시간 연속성·로컬 한 타석 연결. 기존 F-4i 독립 평가 보류는 유지. 목표11/5. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-26 · Codex]`
- [!] CV-40. 고정 버전 새 경기 평가, 목표11/9~12. 새 영상·기준 검토·판독 비용 조건 필요. CV35/36을 대체하거나 AI 합의를 사람 정답으로 쓰지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-26 · Codex]`
- [ ] CV-41. 연구 시연/재현 팩·실패 사례 정리,11/15 기능 동결 목표·11/16~23 리허설·11/24 전시. 기존11/20 최종 동결선은 여유로 유지. 배포·공동시험·11월 실제 부하는 별도 조건. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-26 · Codex]`

## 검토 도구 결함 수정 — 2026-10-26

- [x] CV-34a. 잘못된 좌표 행 오류 격리·검토팩 전체 릴리스 기준 격자 보존 완료. 관련 51검사·UTF-8 체크리스트 8 재확인·Ruff 통과, 기존 325판독 재평가 바이트 동일. 새 10구 625프레임/39구 2,366프레임·모든 이미지 SHA·원본 격자 일치·문제 투구 후보/구간 시작 포함·기존 응답 재사용 거부 확인. 원본/기존 팩 등 46파일 SHA 불변. [기록](docs/CV_REVIEW_REPAIR_20261026.md)·[영수증](docs/results/cv_review_repair_20261026/verification.json). 사람 응답·새 모델 호출 없이 완료한 연구 수리이며 정확도 향상/운영 배포는 아니다. 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-26 · Codex]`

검증 완료·수정 권한 반납: 우리 Codex / `codex/cv-review-repair-1026` / PR67 기준 `5e90c19343785cea917c94bc5aaf9374406f1581`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6401045906). 별도 작업 폴더에서 연구 결함만 수정했고 원래 Claude 폴더·브랜치·운영 배포는 변경하지 않았다. 기존 CV-35 사람 검토는 별도이며 이 작업의 선행 조건이 아니다. PR67에 의존하는 수정 PR로 검토하며 main 병합/배포하지 않는다.

## 미트 영상 분석 고도화 — 2026-10-25

**CV-32~34 완료·수정 권한 반납: Claude Opus 5.5(`claude-opus-5-5`), 연구 브랜치 `claude/cv-mitt-temporal-1025`, 기준 main `4e6aba7`, [PR #67](https://github.com/Pitcheezy/transition-models/pull/67) 초안(병합·배포 안 함). 다른 모델 검토: Fable 5.1 워크플로(검토 34·재검증 24·마지막 확인 1) 지적 반영. CV-35는 사용자 응답, CV-36은 사람 결정 대기.** 운영 동결·PR #66과 분리한 연구 작업이다. Song 코드·우리 Cloudflare·공개 사이트·실경기·접근 권한·공개 파일 계약·IntentEstimate 필드는 바꾸지 않는다. 기존 M3(86장·AI 출력58·기권28·사람 표시84)·원본 라벨·JSONL은 덮어쓰지 않는다. 747139·849843·849845·823407·849849는 개발 자료다. A-y 보류·요금제/동시접속 11월 보류를 유지한다.

- [x] CV-32. 실제 파일 기준 자료 현황·기권 원인 분리·연속 개발 묶음. 결과: [기록](docs/CV_MITT_DEV_20261025.md), `docs/results/cv_mitt_20261025/{inventory_v1,dev_bundle_v1}.json`. ① 5경기 형태·보유 파일 digest·문서 경로 대 실제 보유(747139 판단 프레임은 기본 체크아웃에만 있음, SHA 297/297), 재검토 26장 파일·SHA 26/26, 판독자 릴리스 0.00–0.30초 전 ② 저장 결정 재현 후 6범주 분리: M3 기권 28건 미분류 0, 849843 미분류 4(판독자 원본 행 없음), 747139 64건은 D 프레임 1장의 저장 판독 사유 C5 36·C2 26·C1 2(저장 주장, 화면 미확인; 62건은 저장 기준 D 시점 선택에서 생긴 기권) ③ 사전 규칙 40구 → 추출 39·제외 1·실패 0, 2,596프레임, 창 안 번호 공백 0, 재시도 3구 ④ 기존 v0: estimated 38·unavailable 1·출력 없음 1, v0 판단 이미지는 기록 번호와 20장 일치·19장 +1프레임(올림 규칙 39/39), 10:3·10:6은 기록 번호가 다른 화면 ⑤ 검사 12개. 주요 병목: 압축 판독은 릴리스 직전(중앙값 0.05초 전)을 사후 선택하고 생중계 중앙 화면이 릴리스 전 0.55–0.80초뿐이다. 개발 자료이며 독립 평가가 아니다. 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-25 · Claude]`
- [x] CV-33. 시간순 목표 제시 후보 개발. 결과: [기록](docs/CV_MITT_DEV_20261025.md) CV-33절, `docs/results/cv_mitt_20261025/pilot_v1.json`. ① A/B/C 분리 개발 스키마·`PARAMS_DEV_V1` SHA `01c82c45…` ② 처리기는 릴리스·결과·미래 프레임을 받지 않고 접두 불변 검사 통과, 투구 동작 시작 전/릴리스 전 별도 기준 ③ 사전 규칙 10구·325프레임을 v0와 같은 Fable 5.1·같은 crop으로 무상태 판독(형식 시험 1회 포함 40호출, 형식 거부 0, 실행기 보고 3.20M 토큰·21분) ④ 같은 10구: v0 D 1장 픽셀 10/10(시간 근거 없음) 대 시간 규칙 후보 투구 동작 전 9/10·릴리스 전 10/10, 앞변 단위 7/9; 같은 이미지 재판독 중앙값 3.8 px·90% 21.9 px; 연속 프레임 30 px 초과 도약 22%; 임계값 6칸에서 후보 시각 중앙값 0.6–3.4초로 흔들림 ⑤ 검사. 사람 기준 정확도는 미측정이며 후보 시각은 아직 신뢰하지 않는다. 투구 동작 시작은 작성 세션의 사후 AI 표시다. 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-25 · Claude]`
- [x] CV-34. 독립 평가 계획과 연속 구간 사람 검토 준비. 결과: [평가 계획 초안](docs/CV_MITT_EVAL_PLAN_20261025.md), `intent/sequence_review.{py,js}`, 비공개 검토 팩 39구·10구. 합격 기준(작업 중 같은 세션에서 도구 초안을 먼저 만든 뒤 기록함 — 착수 전 기록 원칙과 다름): ① 경기 단위 분할·메타데이터 사전 선정·투구 단위 분모·연속 영상 우선·압축 편향·지표·군집 부트스트랩·비용·사람 결정 목록 ② 기존 검토 화면 방식을 따르는 연속 검토 도구(재생·한 장 이동·초안 저장/불러오기, 시점·상태와 중심점 분리 입력, AI 정보·투구 ID 비노출) ③ 시드 25% 두 사람 표본 사전 배정·원 응답과 합의본 분리 규칙 ④ 브라우저 동작 확인과 단위 검사. 사람 응답·두 번째 검토자는 없음(사람 간 일치도 미완료). 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-25 · Claude]`
- [ ] CV-35. 사용자 개발 검토: CV-34a 수정 작업 폴더의 `outputs/cv_review_repair_20261026_v2/pilot10_pack`(10구) 응답 1개를 받아 `sequence_review check`로 검사하고, 소형 시험 후보의 적절한 기권·잘못된 출력·잘못된 순간과 같은 프레임 중심 차이를 개발 자료로 계산한다. 옛 trim 팩은 보존하고 응답을 자동 이식하지 않는다. 그 뒤에만 A 안정화·B 임계값을 사람 기준 개발 자료 안에서 다시 정하고 SHA로 고정. **사람 응답 필요.** AI-only 개발 교차 검토는 사람 정확도와 별도로 기록한다. 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-26 · Claude]`
- [ ] CV-36. 독립 평가 실행: 평가 계획 10절의 사람 결정(새 경기 영상 출처·이용 조건, 판독 호출 규모·비용, 검토자 1–2명, 공개 범위) 뒤 착수. 결정 전에는 메타데이터 후보 목록만 작성. **사람 결정 대기.** 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-26 · Claude]`

## PR63 병합·운영 증거 PR64 검토 — 2026-10-25

- [x] H-main3. 사용자 승인으로 PR63 고정 `e09c9d2`의 코드 불변·최종CI8/8을 재확인하고 main `06aa6d0f3ad24a7e9f0649491f9887283d8f77d8`에 병합했다. [PR63](https://github.com/Pitcheezy/transition-models/pull/63). 실제 배포는 변경하지 않았다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`
- [x] WS-evidence1. PR64 고정 `abddb24`의 다른 모델 검토에서 P1/P2 없음. 발행3요청/로그3건·안내13요청/로그12건·지연4값·고정client SHA3개·영수증2개 불변·현재 상대링크128·이력3구역·체크리스트8을 검증하고 최신 main 문서3곳 충돌을 해소했다. 새 head CI는 PR64에서 별도 확인한다. PR64 병합·실제 재시험은 포함하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

검증 완료·수정 권한 반납 준비: 우리 Codex / `codex/ws-publisher-revoke-1025` / 기존 PR64 `abddb24`, 통합 main `06aa6d0`. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6393493153). 요금제·요청량은11월 보류, 팀원 코드·Cloudflare 변경 없음.

## PR65 병합·설정 검사 PR63 충돌 해소 — 2026-10-25

- [x] H-main2. 사용자 승인으로 PR65 고정 `059c8cc`를 다른 모델 재검토·CI8/8 성공 뒤 main `e12ac008bebc55fcfc62dea9fa0b36eddb1571d8`에 병합했다. [검토 기록](https://github.com/Pitcheezy/transition-models/pull/65#issuecomment-6393306159). 독립 Node9/Python107 통과, 새 부하·배포 없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`
- [x] WS-config2. PR63에 main `e12ac00`을 합쳐 문서2곳 충돌을 해소했다. 기존 설정 코드/테스트 blob 불변·관련287+체크리스트8=295검사·Ruff·현재 상대링크128·Git 영수증2개/이력4구역 보존·별도 문서검토 통과. PR63/64 main 병합과 실제 배포는 포함하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

검증 완료·수정 권한 반납 준비: 우리 Codex / `codex/ws-log-config-1025` / 기존 PR63 `1d6bfd1`, 통합 기준 main `e12ac00`. 새 head의 원격 CI는 PR63에서 별도 확인한다. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6393310734). 전시회 요금제·요청량은11월 보류, 팀원 코드·Cloudflare 변경 없음.

## 로그 보존 설정 검사 — 2026-10-25

- [x] WS-config1. 기존 Logs100%저장 보존 검사/후보·dry-run 준비, 관련287검사 통과. gpt-5.6-sol 고정 e8b015a 검토·독립287검사 통과. [근거](docs/WS_LOG_CONFIG_20261025.md). 실제 배포·발행 회수는 별도 WS-publish4다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`
- [!] WS-exhibit1. 동시30~50명 목표는 WS-capacity1의 로컬 결과로 준비했고, 전시회 요금제·요청량/추가 부하 준비는 사용자 지시로11월 보류(WS-capacity2)다. 실제 서비스 용량 합격·공개 확대·유료 변경은 미승인/미측정이다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

기존 검사 기준 `6262afb`, [WS-config1 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6387190685). 당시 관리 자격 대기는 PR64의 본인 시험으로 후속 해소되었으며 새 공동시험 자격/GO와 구별한다. PR63은 main `06aa6d0`에 후속 병합됐다.

## 협업 현재 상태 정정·11월 우선순위 반영 — 2026-10-25

- [x] H-collab5. 사용자 지시로 전시회 요금제·요청량 결정을11월로 보류하고, 배포/회수/로그·새최종본·사람 결정과 다음 인수 기준을 정합화했다. 기존 증거/ZIP·공동시험 유한 요청 원장을 보존했다. 체크리스트8·상대링크455·고정근거13·영수증2SHA/역사본문 보존·별도 문서 검토 통과. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

수정 권한 반납: 우리 Codex / `codex/ws-exhibition-local-1025` / 기준 `757409f`, 최신 main `24fea70`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6388687726). 문서만 변경, 팀원 코드/프로세스/배포 및 우리 Cloudflare 변경 없음.

## 현재 협업 우선순위 — 2026-10-25

- 본인 호스트 배포·접속·관람/발행 회수 완료와 실제 공동시험을 구별한다. [현재 순서·본인 결정](docs/WS_COLLAB_V1_ACTIONS.md)을 따른다. 새 전달본 → 로컬 인수 → 새 시험 창/권한/GO → 공동시험 순서이며 전시회 용량은11월 보류다.
- [x] WS-publish4. 고정 runtime 배포·원격 바이트 일치·동일 발행 bearer HEAD404→회수401→업로드OFF503과 저장 로그3건을 대조했다. [PR64 고정 근거](https://github.com/Pitcheezy/transition-models/blob/abddb240a698e91923d14ef413e36081a4af5315/docs/WS_PUBLISHER_REVOCATION_20261025.md). 실제 파일 PUT/DELETE·만료 경계·Song 공동시험은 포함하지 않는다. PR64는 main 미병합이다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`
- [!] WS-notice3. 본인 안내ON/OFF·같은세션/본문복구·안내시험자격 회수 기능13요청 통과, 저장 로그12/13. OFF PUT1건은 재조회도 미확인으로 전체 증거 합격 대기다. [고정 기록](https://github.com/Pitcheezy/transition-models/blob/abddb240a698e91923d14ef413e36081a4af5315/docs/WS_NOTICE_TRIAL_20261025.md)·[재조회](docs/results/ops/ws_notice_log_recheck_20261025.json). 원래 요청 재실행으로 대체하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

PR64 기존 착수 근거: [발행 시험](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6387400853), [안내 시험](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6387602964). 중복 태스크를 새로 만들지 않고 위 WS-publish4·WS-notice3가 현재 상태를 유지한다.

아래 날짜별 미완료·다음 작업 문구는 당시 이력이다. PR65는 main `e12ac00`, PR63은 main `06aa6d0`에 병합했고 PR64는 main 미병합이며, 증거 링크의 고정 커밋과 실제 배포 소스를 구별한다.

## 전시회 30/50명 로컬 준비 · 로그 재조회 — 2026-10-25

- [x] WS-capacity1. 접근 문 ON·고유 세션30/50의 유한 loopback GET360/600 전부 성공, p95 121.42/196.77ms·누락0·정리완료. Free 일일 예산·377Node/132Python/8checklist·다른 모델 고정검토 통과. 로그 재조회도12/13으로 OFF PUT1건 미확인 유지. [근거](docs/WS_EXHIBITION_CAPACITY_20261025.md). 실제 서비스50명 검증이 아니다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`
- [!] WS-capacity2. 사용자10/25 지시로 전시회 요금제·요청량 결정은11월 최종발표 준비로 보류한다. 지금 가격/부하 후속을 진행하지 않는다. 재개 시 최종UI/폴링/크기와 실제30/50명 시험 범위·요청 상한·접속/비용을 고정한다. 공동시험의 유한 요청 원장과 GO 조건은 별개로 유지한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

수정 권한 반납 준비: 우리 Codex / `codex/ws-exhibition-local-1025` / main `24fea70`, 코드/검토 `f7e65bb98990feae7d423bbaf9f32855e61db363`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6388196522). 기존 PR64 main 미병합·WS-notice3 로그12/13 미완료/전달 ZIP 보존, 팀원 코드·프로세스·배포 미접근.

## 관람 자격 회수 증거 정리 — 2026-10-25

- [x] WS-access4. 실제 본인 로그인200·홈200→같은 세션 회수401과 최초 실패401을 서버 로그4건에 대조했다. [근거](docs/WS_VIEWER_REVOCATION_20261025.md). 발행 자격·최신본 일치·공동시험은 미완료다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

검증·반납 준비: 우리 Codex / `codex/ws-viewer-revoke-1025` / 기준 `6262afb`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6387091829).

## 저장 로그 원본 확보 — 2026-10-25

- [x] WS-log1. 저장 로그 원본20,587bytes/SHA 확보·4건401/version대조·허용목록 공유 영수증·현재 인계를 갱신했다. [근거](docs/results/ops/ws_host_log_export_20261025.json). 실제 권한 회수·공동시험은 미실행이다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

검증·반납 준비: 우리 Codex / `codex/ws-log-export-1025` / 기준 `e9b362b75d6d4768c552740bfc6e0124872805e1`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6386816143).

## 형 요청 우선·Cloudflare 로그 기반 확보 — 2026-10-25

- [x] WS-partner8. Song D181/추가2차단을 상대 보고로 반영하고, 이 채팅의 실제 Cloudflare 조회·사용자 승인 Logs100%저장·무인증홈401과저장4이벤트를 확인했다. [실제근거](docs/WS_HOST_PREFLIGHT_20261025.md). runtime/source·scope/expiry·회수/공동시험은미완료, 팀원코드변경없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-25 · Codex]`

검증·반납 준비: 우리 Codex / `codex/ws-readiness-1025` / 기준 `af95d956c13012fa115cdbde51c2b738d083429a`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6386251355).

## 회신 발신·출시 잔여 상태 정리 — 2026-10-23

- [x] WS-partner7. 사용자 승인 #38 회신 게시·본문 재조회/SHA 대조와 출시 잔여8묶음을 정리했다. [실행 계획](docs/WS_COLLAB_V1_ACTIONS.md)·[발신 기록](docs/results/ops/ws_host_reply_sent_20261023.json). 체크리스트8·상대링크102·본문대조/diff 통과. Cloudflare 보안 선택·실제설정/로그와 새ZIP/시험/배포 승인은 대기다. 운영 코드·설정·팀원 코드 변경 없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-23 · Codex]`

검증·반납 준비: 우리 Codex / `codex/ws-reply-status-1023` / 기준 `aa3dc69`, 선점 `18f6c56`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6357826887).


## 네 질문 답안·새 최종본 수신 준비 — 2026-10-23

- [x] WS-partner6. #38 네 질문의 고정 소스·기존 합성36검사·미발신 답안과 새 v7/v4.5 수신 절차, GATE-06의 상대 동의/우리 검토안/미승인을 정리했다. [근거](docs/WS_HOST_ANSWERS_20261023.md). 실제 Cloudflare 설정/로그는 보안 선택 안내로 미확인, 새 파일/시험/배포 승인은 대기다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-23 · Codex]`

검증·반납 준비: 우리 Codex / `codex/ws-host-answers-1023` / 기준 `ecc9d7b`, 선점 `dae4b3d`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6357395623). 우리 문서·합성 검증만, 팀원 코드/새 발신/배포/설정 변경 없음.


## 반환팩 수신·공동시험 추가 조건 — 2026-10-22

- [x] WS-partner5. 반환팩 v2 상대 수신 보고와 세 결함의 미수정/절차 제안을 확인하고, 우리 GATE-06 증거 조건·판정 한계를 정리한다. [후속 기록](docs/WS_PARTNER_FOLLOWUP_20261022.md): 상대 무결성검사13파일 확인, 자체요청로그 없음/실제로그 미확인, GATE-06 합의전보완안과 미발신 초안 완료. Cloudflare 탭 연결 대기로 실제설정은 미확인, 절차수용·실행GO는 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-22 · Codex]`

검토·반납 준비: 우리 Codex / `codex/ws-trial-conditions-1022` / 기준 `d9d4864`, 선점 `fb410c1`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6342964859). 우리 문서만 변경한다.


## 최종 전달본 수신·공동시험 준비 — 2026-10-21

- [x] WS-partner4. 최종2종 ZIP·등록핀 대조/예제6개/로컬34기능 검사·비공개후보 준비 완료. 열린 화면의 과거추천 잔존·Windows 발행기 제약·실제배포/공동시험 대기는 유지한다. [근거](docs/WS_FINAL_DELIVERY_20261021.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-21 · Codex]`

수정 권한 반납 준비: 우리 Codex / `codex/ws-final-delivery-1021` / 기준 `9ed7135`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6312118763). 팀원 코드·Mac·실제 배포/권한/발신 변경 없음.

## 배포 자료 JSON 실패 처리 — 2026-10-20

- [x] WS-release1. 큰 정수 JSON 오류를 안전하게 거부하도록 수정했다. 신규4개 선행실패→집중5·관련238·Ruff 통과. 고정499b185의 gpt-5.6-sol 검토PASS·독립5검사 완료. [근거](docs/WS_RELEASE_JSON_20261020.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-20 · Codex]`

수정 권한 반납 준비: 우리 Codex / `codex/ws-release-json-1020` / 기준 `172d3490722a5edcf9186ce8beb592468b649f59`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6284264075). 로컬 합성만, 팀원·원본 전달팩·배포·계약·발신 변경 없음.

## 공개 보고서 비공개 정보 보호 — 2026-10-20

- [x] WS-report5. 공개 초안에 이메일·IP·개인 절대경로가 포함되는 입력을 거부하고 정상 근거 문구를 보존한다. 집중36·전체Node368·체크리스트8 통과. 고정61bb00c의 gpt-5.6-sol 검토PASS·독립36 통과. [근거](docs/WS_REPORT_PRIVACY_20261020.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-20 · Codex]`

PR #54 CI6 통과·main `172d349` 병합·우리 board 수정 권한 반납 완료. 기준 `008e14a827a21515d4e8b75f936b5d721a842006`. 로컬 합성만 수행하며 팀원 코드·배포·발신·공개 계약은 변경하지 않는다.

## 최종 실행본 회신 접수·수신 준비 — 2026-10-19

- [x] WS-partner3. #38 회신·mail 라벨 적용 확인과 최종 실행본 수신 절차 준비 완료. 상대 보고14검사와 우리 검증을 구분하고 N23·검토 모델·날짜/동결 확인 사항 및 미발신 초안을 보존한다. 최종 파일/실제 실행 승인은 대기다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

[근거·수신 절차](docs/WS_FINAL_RUNNER_INTAKE_20261019.md). 체크리스트8·현재 구역 상대 경로26개·원문 해시3개·별도 문서 검토 통과. 수정 권한 반납 준비: 우리 Codex / `codex/collab001-runner-intake-1019` / 기준 `b7feebf6620f279d30803e45a707522005852db0`, 선점 `0dde60a`. CI/병합 뒤 우리 board에 반납한다. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6270197582). 우리 문서만 변경하며 최종 파일 미수신·실제 공동시험/배포 승인 대기를 유지한다.

## 협업 실행계획 현재 상태 정리 — 2026-10-19

- [x] H-collab4. 협업 실행계획의 현재 상태/다음 입력과 초기 이력을 구분했다. 상대 링크82·과거 본문 보존·체크리스트8·별도 문서 대조 통과. 승인된 범위와 새 사람 결정 대기는 유지한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

[현재 실행계획](docs/WS_COLLAB_V1_ACTIONS.md). PR #52 CI2 통과·main `b7feebf` 병합·우리 board 수정 권한 반납 완료. 기준 `595415270cad6f976043341bccd7cce94b0be37d`, 선점 `d379f8c`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6264093517). 문서만 수정하며 팀원·배포·발신·승인 범위를 변경하지 않는다.

## 현재 운영 소스 검토 근거 — 2026-10-19

- [x] WS-review3. 현재35파일의 검토 근거와 Git blob 일치 확인: 기존32파일 연결·배포묶음2파일/감시CLI1파일 gpt-5.6-sol 집중 검토PASS·관련73검사 통과. 과거 작성 모델 미확인·실제 출시 조건은 유지한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

[파일별 근거·한계](docs/WS_REVIEW_COVERAGE_20261019.md). PR #51 CI2 통과·`5954152` 병합·우리 board 수정 권한 반납 완료. 검토 기준 `0497b2b862fed7288b803ab14bd4c3de1ed8c6ef`, 선점 `dcf1dc5`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6263886050). 합격은 현재 파일의 근거 구분·다른 모델 집중 검토·관련 검사이며, 사람 결정이나 팀원 자료 대기를 임의로 해제하지 않는다.

## 알림 시각 경계 — 2026-10-19

- [x] WS-alert4. 표현할 수 없는 이벤트 시각이 정상 알림을 중단하지 않도록 하고, 존재하지 않는 저장 날짜를 거부한다. 정상 이전 상태·확장 연도·큰 카운터 호환과 모의 전달·상태쓰기 전 거부를 검증한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

완료: 집중53(새8)·Node346·체크리스트8·문법 통과, 고정 `1b10ed6`의 gpt-5.6-sol 검토PASS/독립53검사. [근거](docs/WS_ALERT_TIME_20261019.md). PR #50 CI6 통과·`0497b2b`에 병합·우리 board 권한 반납 완료. 작업 기준 `d2ff7bd`, 선점 `2202675`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6263661558). 노트북 합성 검사만 수행하며 팀원·Mac·실배포·실제 발송·공개 계약은 변경하지 않는다.

## 운영 보고서 입력 검증 — 2026-10-19

- [x] WS-report4. 불가능한 UTC 시각·잘못된 알림 행의 조용한 누락을 거부하고 정상 날짜 정밀도와 기존 버전 입력을 보존한다. 출력 전 거부·집중/전체 검사·다른 모델 검토를 완료한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

완료: 집중46·전체Node338·체크리스트8·문법 통과, 고정 `a4b9384`의 gpt-5.6-sol 검토PASS/독립11검사. [근거](docs/WS_REPORT_INPUT_20261019.md). 수정 권한 반납 준비: `codex/ws-report-input-1019`, 선점 `769a94d`. CI/병합 후 우리 board에 반납한다. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6262949761). 공개 계약·팀원 코드·실배포/발송은 변경하지 않는다.

## 테스트 임시 자료 정리 — 2026-10-19

- [x] WS-test1. 알림/보고서 계열 테스트의 임시폴더 잔존을 해결하고 정상·실패 종료 정리 및 인접 자료 보존을 검증한다. 운영 코드·계약·기존 전달팩은 변경하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-19 · Codex]`

완료: 관련70검사 두 번·전체Node327·체크리스트8·문법 통과, 테스트 잔존0·인접 자료 보존. [근거](docs/WS_TEST_TEMP_CLEANUP_20261019.md). 수정 권한 반납 준비: 우리 Codex / `codex/ws-test-cleanup-1019` / 선점 `e89c615`. PR/CI 종료 뒤 board에 반납한다.

## 비공개 배포 후보·연결 점검 준비 — 2026-10-18

- [x] WS-stage5. 받은 v4.2 화면+고정 우리 호스트의 비공개 후보·설정/dry-run·로컬 합성 연결·중단/회수 실행안을 준비한다. 실제 계정/배포/접속 확대는 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`

완료: 후보507,750bytes·설정/dry-run·실제Worker+받은화면22항목/105요청·관련Python209 통과. 원본22/후보19파일 불변. 요청 부분합20회·notice/실패정리 추가원장·두 종류 자격회수 조건을 명시했다. [근거](docs/WS_STAGE5_READINESS_20261018.md). 운영코드/배포/발신/팀원/Mac 변경 없음.

수정 권한 반납 준비: 우리 Codex / `codex/ws-stage5-readiness-1018` / 기준 `9e405aa`, 선점 `03ae493`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6247513227).

## 비공개 v4.2 수신·감시 호환 — 2026-10-18

- [x] WS-partner2. 비공개 전달팩 원본/manifest·offline 실행·health/game_checks·reason 호환·우리 runtime/요청 한도와 로컬 화면을 확인하고 필요한 우리 변경 및 회신 자료를 준비한다. 실제 공동 연결/배포는 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`

완료: 원본21파일·스키마5예제·원문전송5·static browser15·우리Node322/Python21·고정5effc7a 다른모델검토PASS. 제공runner는 Windows fcntl/WSL 가상화 제약으로 실행불가를 보존. 우리99소스 반환팩·미발신 회신·시험조건 초안 준비. [근거](docs/WS_PARTNER_V42_20261018.md).

수정 권한 반납 준비: 우리 Codex / `codex/ws-partner-v42-1018` / 기준 `ac8b6c7`. [합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6247213943). Song ZIP·소스·빌드는 비공개 원본으로 보존하며 팀원 레포·Mac·기존 서버는 건드리지 않는다.

## 공개 전달·실제 만료 경계 — 2026-10-18

- [x] WS-handoff4. 사용자 요청으로 고정 우리 ZIP을 GitHub 검토용 asset으로 게시·익명 다운로드102항목/SHA 확인·[#18 링크 안내](https://github.com/Pitcheezy/transition-models/issues/18#issuecomment-6245327702) 완료. 팀원 비공개 자료 공개 승인은 아님. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`
- [x] WS-publish3. 같은 runtime 실제 만료 경계18HTTP/20.261초·거부/보존/정리 확인. 전체Node310·체크리스트8·고정a2bb75b의 gpt-5.6-sol 검토PASS. [근거](docs/WS_LIVE_EXPIRY_20261018.md). 한 키/본문2KiB/전체18요청/정리포함120초 이내와 거부·보존·실패를 기록. 운영 runtime 변경 없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`

수정 권한 반납 준비: `codex/ws-public-handoff-expiry-1018` / 선점 `d0023c6`. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6245302206). PR/CI 종료 후 우리 board에 반납한다. 팀원·Mac·기존 서버·실제 배포 변경 없음.


## 상호 전달팩 준비 — 2026-10-18

- [x] WS-handoff3. 고정 소스 ZIP·안내·해시·압축해제 Node304/CLI29회/CRC·SHA 검증 완료. #18 안내 1회 게시·원문 SHA 대조 완료. 실제 ZIP 전달/상대 수신·공동 시험은 별도. [근거](docs/WS_PEER_HANDOFF_20261018.md). 운영 코드·계약·배포·Mac·팀원 코드 변경 없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`

수정 권한 반납 준비: `codex/ws-peer-handoff-1018` / 선점 `2758712`. PR/CI 종료 후 우리 board에 반납한다. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6244974720). 실제 ZIP 송수신과 이슈 안내 게시, 로컬 검사와 실제 공동 연결을 구분한다.


## 협업 표본 감사·노트북 운영 리허설 — 2026-10-18

- [x] H-collab3. 대표 PR28/40/41/42 표본 감사·현재/이력 인계 정리 완료(나머지 PR 전수 대조 아님). 절차 편차1건과 과거 모델/일일조회 미확인을 보존. [감사](docs/COLLABORATION_AUDIT_20261018.md). 상대링크17·체크리스트8 통과, WS-laptop1은 아래 별도 기록. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`
- [x] WS-laptop1. 노트북 실제 CLI29회 연결·철회/복원·감시/안내/범위/만료 거부·자체 정리 통과. 집중8/전체Node304·체크리스트8·문법 통과, 고정7deeac5의 gpt-5.6-sol 검토PASS. [근거·한계](docs/WS_LAPTOP_OPS_20261018.md). 기존 서버·Mac·팀원·배포 변경 없음. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-18 · Codex]`

작업 브랜치 `codex/ws-laptop-ops-1018`, 선점 `62dd0f0`; CI/병합·현재 수정 권한은 우리 board의 최신 기록을 따른다. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6244814626). 사용량 약50% 잔여에서 마무리하며, 외부 입력 대기를 임의로 완료하지 않는다.

## 제한된 연결 시험 보호 — 2026-10-17

- [x] WS-publish2. 정확한 발행 키 하나·UTC 만료 제한과 옛 runtime 번들 거부 완료. Node296·Python209·고정 ZIP loopback12요청 통과, 고정834f838 다른 모델 검토PASS. [근거](docs/WS_PUBLISH_SCOPE_20261017.md). 실제 배포/접속 확대/발신 없음, 수정 권한 반납. 〔모델: Fable 5.1〕

## 운영 도구와 Song 시험 준비 — 2026-10-17

- [x] WS-notice2. 안내 CLI 구현·집중17/전체Node284 통과. 조건부 전환·응답 유실/감사누락 구별·비밀 ENV. 고정5083b1a 다른 모델 재검토PASS. [근거](docs/WS_OPERATOR_TOOLS_20261017.md). 실제 계정 전환/배포 없음. 〔모델: Fable 5.1〕
- [x] WS-monitor3. 유한 감시 실행기 구현·집중24/전체Node284 통과. 중첩/중단/재시작·누적 실패·모의 알림 검증, 고정5083b1a 다른 모델 재검토PASS. [근거](docs/WS_OPERATOR_TOOLS_20261017.md). 실제 스케줄/발송 없음. 〔모델: Fable 5.1〕
- [x] WS-partner1. 새 요청 수신·기존 토큰 범위/만료 한계·비공개 전달 준비 및 별도 승인 회신1회 게시/원문 SHA대조 완료. [기록](docs/WS_PARTNER_TRIAL_PREPARATION_20261017.md). Song 소스/빌드 미수신·접속 허용 미결정. 〔모델: Fable 5.1〕

## 본인 전용 실자원 합성 시험 — 2026-10-16

- [x] WS-stage3. 전용 실자원 실행안·최소 제품 권한 초안·합성 후보 준비 완료. 고정 host `c07dc94`의 gpt-5.6-sol 전체 검토 P1/P2 없음, Node79·JS7·패키지/설정·격리 dry-run1회 통과, 원본16파일 SHA 보존. [실행안](docs/WS_STAGE3_EXECUTION_PLAN_20261015.md)·[영수증](docs/results/ops/ws_stage3_20261015.json). API 토큰 발급·자원/비밀/배포/DNS는 미실행이며 아래 WS-stage4로 분리. 선점 `93d4c7b`, 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`
- [x] WS-stage4. 사용자 구체 승인 범위의 신규 Worker/private R2/D1·접근 제한 시험 주소 생성 및 실제 합성 HTTPS 시험 완료. 초기17·진단7·수정 후36·최종OFF16요청 통과, 초기12요청 실패는 CDN weak ETag로 원인 확인·보완. 전체Node243·집중61·다른 모델검토 P1/P2 없음. 자료읽기/업로드/수집/피드백OFF·gateON으로 복귀, D1수집0행. CPU/집계사용량·실제1시간만료·cron·실경기는 미측정. [결과](docs/WS_STAGE4_CLOUD_TRIAL_20261016.md)·[영수증](docs/results/ops/ws_stage4_20261016.json). 선점 `e9a8fa1`, 배포 host `87168d7`, 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 실계정 읽기·시험 실행안 — 2026-10-15

- [x] WS-stage2. 로그인 계정의 Free 플랜·전체 관리자·zone Active·D1 DB0개 확인. R2만 후속 명시 승인으로 활성화·버킷0/사용료0 확인. Wrangler4.151.0 분리 고정·npm audit0·합성 패키지/설정/dry-run 통과·원본16파일 SHA 보존. [실행안](docs/WS_ACCOUNT_READINESS_20261015.md)·[영수증](docs/results/ops/ws_stage2_20261015.json). R2 가입 외 자원/유료전환/배포/발송·팀원 접근 없음. 체크리스트8·문서 링크76·독립 문서 지적2건 수정. 선점 `6daf0d4`; 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 비공개 시험 준비·승인 회신 — 2026-10-15

- [x] WS-stage1. 승인된 mail #18 회신 본문 한 건 게시·원격 SHA 대조 완료(댓글6190443556, mail OPEN). 본인 Cloudflare·본인 시험·월 $10 이내 준비·수집/피드백 OFF 결정과 [비공개 시험안](docs/WS_PRIVATE_STAGE_PLAN_20261015.md)을 기록했다. 기존 비용 산정1회(가정 $5/$9.90, 실제 청구 미측정)·체크리스트8·로컬 링크59·독립 문서 검토2건 수정. [영수증](docs/results/ops/ws_stage1_20261015.json). 실제 가입/자원/배포/메일 발송 없음. 선점 `11bfa701`, 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 실제 연결 결정·회신 준비 — 2026-10-15

- [x] WS-handoff2. 최신 업로드/API 회신과 [운영 결정서](docs/WS_HUMAN_DECISIONS.md)를 준비했다. 본인 Cloudflare·본인 시험만 확정, 이메일 희망·예산/수집/발신/배포는 미정. 링크44·체크리스트8·독립 문서 대조 통과. 당시 미발송·미배포(후속 사용자 결정·게시 완료는 상단 WS-stage1). [근거](docs/results/ops/ws_handoff2_20261015.json). 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 알림 저장 실패 정리 — 2026-10-15

- [x] WS-io1. 알림 저장 오류의 임시파일 정리·실패후재시도와 보고서 helper 공유 완료. 새8·보고서10·전체Node243·체크리스트8·문법 통과. 고정 `c19e1c5`의 gpt-5.6-sol 검토 PASS. 단일작성자 전제와 마지막 검사/unlink 경합 한계를 공개했다. [근거](docs/WS_IO1_20261015.md). 실제발송/배포 없음. 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 원시 저장소 복구 점검 — 2026-10-15

- [x] WS-recovery2. 합성 R2 raw 복원9사례를 실제 격리 Miniflare에서 재현했다. 철회/옛ETag/안내OFF 되감김과 외부토글의 정적화면 한계를 기록. 집중3·전체Node235·체크리스트8·문법 통과, 고정 코드 `b74c001`의 gpt-5.6-sol 검토 PASS(독립3/9사례). [근거](docs/WS_R2_RECOVERY_20261015.md). 실제계정 복구/공개 재개는 미실행. 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 알림 입력 오류 보호 — 2026-10-15

- [x] WS-alert3. 잘못된 감시 incident 입력은 잠금·전송·저장 전에 거부하며 대기를 보존한다. 정상 복구·재시도·개별 이벤트 skip 유지. 새9·기존36·전체Node232·체크리스트8·문법 통과, 고정 코드 `a4932bb`의 gpt-5.6-sol 검토 PASS(집중9). [근거](docs/WS_ALERT3_20261015.md). 합성/모의검증이며 실제발송 없음. 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

## 보고서 저장 실패 복구 — 2026-10-15

- [x] WS-report3. 보고서 저장 실패 시 자기 출력만 롤백·출력쌍 잠금·외부 파일 보존·재시도 복구 완료. 집중24·전체Node223·체크리스트8·문법 통과, 고정 코드 `8373678`의 gpt-5.6-sol 검토 PASS. [근거](docs/WS_REPORT3_20261015.md). 합성 IO 검사이며 강제 종료 원자성/실제 배포는 별도. 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`


## 독립 복구 점검 완료 — 2026-10-15

- [x] WS-recovery1. 합성 SQLite 과거 복구점 점검 완료: 구조·인덱스·ID·만료 행·budget 되감김/근거 없음의 10사례, 읽기 전용·원본 SHA 불변·외부 입력/덮어쓰기 거부 4검사. 전체 Node213·체크리스트8·문법 통과. 고정 코드 `4503c2d`의 gpt-5.6-sol 독립 검토 PASS(집중4검사). [실행·근거](docs/WS_D1_RECOVERY_20261015.md). 실제 복구·수집 재개·배포는 미실행이며 WS-ops4e 준비 보완이다. 수정 권한 반납. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`


## WS-report2 내보내기·보고서 연결 — 2026-10-15

- [x] WS-report2a. 읽기 전용 SQLite 스냅샷 → UTC 일별 비공개 집계 포장 CLI를 구현했다. 기존 D1 SQL 재사용·원본 SHA 불변·스키마/TTL/경로/덮어쓰기 가드, 전체Node197·체크리스트8 통과. `gpt-5.6-sol`의 지적2건 수정 후 고정 코드 `d60d45b` 재검토 PASS(독립 합성4검사). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`
- [x] WS-report2. 사용자 명시 승인 후 전체 스냅샷 포장 입력을 보고서에 연결했다. 빈 자료 null/보존 행 partial_data/OFF 채널 null·UTC 날짜 한계·운영자 JSON 출처 보존. 전체Node209·체크리스트8 통과, 고정 코드 `70f62e6`의 gpt-5.6-sol 검토 PASS(독립25+3검사). 실제 DB 취득·공개 배포·발신은 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-15 · Codex]`

[구현·검토·한계](docs/WS_REPORT2_20261015.md) · [커밋/파일 SHA/명령 영수증](docs/results/ops/ws_report2_snapshot_20261015.json) · [연결 검증 영수증](docs/results/ops/ws_report2_connection_20261015.json) · [남은 우선순위](docs/WS_OPERATIONS_HANDOFF.md).
**우리 구현 수정 권한 반납.** 브랜치 `codex/ws-report-snapshot`, 선점 `6197660`; [PR #30](https://github.com/Pitcheezy/transition-models/pull/30)의 CI/병합 상태를 별도 확인한다.
공개 계약·Song 코드·실제 DB·프로세스·배포·발신은 변경하지 않았다. A-y/F-4i 보류 유지.

## WS-review2 교차검토·수정 main 반영 — 2026-10-14

사용자 직접 지시로 기준 main `b40e8a6`에서 작업했다. [PR #28](https://github.com/Pitcheezy/transition-models/pull/28)은 2026-10-14 main `b140b3616a955b4875844bde683863647dec49b9`에 병합됐다. 최종 코드 `2ce3a70a142c592d1db06d242616669766e1a6f7`의 재현 결함 11건과 로컬 검사 의존성 패치가 main에 포함된다.
Node 186·관련 Python 172·Chromium/WebKit 각19 및 감시·알림·보고서 리허설 통과. 외부 첫 연결 자료가 필요한 브라우저3개는 각 엔진에서 건너뛰었다.
작성 GPT-6 계열과 다른 `gpt-5.6-sol`이 최종 고정 코드를 검토해 PASS로 판정했다. [범위·재현·해시·한계](docs/WS_CODEX_REVIEW2_20261013.md).
PR 병합·현재 문서 동기화와 로컬 모델 근거 조사를 마치고 수정 권한을 반납한다. 과거 작성 모델 직접 연결은 0/16으로 미확인이며, 별도 다른 모델 검토를 완료했다고 소급하지 않는다. WS-human1·WS-ops4 실제 운영 결정과 Song 후속 자료 수신은 남아 있다.
아래 원래 완료 기록의 ‘교차 검토 대기’는 WS-review2 이전 상태이며, 현재 상태는 이 절과 WS-review2 기록을 따른다. A-y/F-4i 보류와 실제 배포·발송·상대 코드 변경 제한은 유지한다.

## 협업 v1 반영 — 2026-10-12

WS-safe1·WS-access1·WS-alert1·WS-report1·WS-ops2·WS-review1·WS-access2·WS-access3·WS-monitor2·WS-alert2는 구현·로컬/CI 검증을 마쳤다.
Claude 작성 코드의 Codex 교차검토와 후속 수정의 독립 검토는 PR #28에 반영됐다. 아래 작업별 수치는 각 작업 완료 당시 기록이며,
현재 호환성은 접근 쿠키 v3·알림 상태 v3을 설명하는 [WS-review2 기록](docs/WS_CODEX_REVIEW2_20261013.md)을 따른다.
이전 Codex 묶음 모델 근거 확인, WS-human1·WS-ops4 실제 운영 결정, Song 후속 전달물은 별도 조건이다.
[협업 규약](docs/COLLABORATION_PROTOCOL.md) · [실행 계획](docs/WS_COLLAB_V1_ACTIONS.md) · [현재 인계](docs/WS_OPERATIONS_HANDOFF.md).

- [x] H-collab2. 사용자 채택 협업 v1의 역할/파일 경계/사람 결정/우편/다른 모델 검토/일정/비상 대응/경기별 증거를 지침에 반영했다. 일일 읽기 예약 등록, mail #18 첫 연결 안내 수신 반영. 체크리스트7·YAML·현재 상대 링크24·별도 Codex 문서 대조 통과. 기능 완료/실제 실행 성공과 구별한다. 〔모델: Fable 5.1〕
- [x] WS-safe1. 긴급 안내 스위치를 로컬 구현·합성 검증했다: 운영자 토큰 digest(`NOTICE_TOKEN_SHA256`, 발행기 토큰과 분리)로 `/_notice/v1/state`를 조건부 변경하면 화면·asset·공개 JSON·수집이 503 안내(no-store, `X-Pitcheezy-Notice`)로 바뀌고 업로드·운영자 경로는 유지, 변경마다 private R2 감사 기록. 신규 Node 7(단위·메모·감시 구별·실제 로컬 Worker/R2)·전체 Node 102, Chromium 호스트 브라우저 11(열린 화면 다음 읽기·새로고침·직접 파일·뒤로가기·복구), Python 설정 검사 67(관련 132)·checklist 7 통과. loopback 실측 PUT 후 첫 안내 응답 11.71 ms(단일 isolate; 다중 colo 미측정). 실제 공개 문구·전환·토큰 전달·Song 화면 안내 표시(요청 초안만)는 남는다. 코드 검토는 WS-review2를 따른다. 내려받은 자료 회수 기능 아님. [기록](ops/public-host/NOTICE.md) · [영수증](docs/results/ops/ws_notice_rehearsal_20261013.json). 선점 `51958c1`; 구현은 완료 커밋(PR #20). 〔모델: Fable 5.1〕
- [x] WS-access1. 관람 접근 문을 로컬 구현·합성 검증했다: `ACCESS_GATE_ENABLED`(기본 false)·코드 digest 비밀·세션 비밀로 화면·asset·공개 JSON·수집을 세션 없이는 401(HTML 입력 화면/JSON)로 막고, 무상태 HttpOnly·SameSite=Strict 쿠키(https `__Host-`)를 발급하며 업로드·안내 인증과 분리했다. 만료·코드 삭제 철회·비밀 회전·로그아웃·same-origin 검사·요청자별 제한·잘못된 설정의 닫힌 실패·안내 우선·감시 구별(`access_gate_active`)을 검사했다. 신규 Node 9·전체 Node 111, Chromium 호스트 브라우저 13(신규 2: 입력 화면 로그인·쿠키 속성·직접 파일·로그아웃·1초 세션 만료), Python 설정/패키지 검사 130(다섯 토글·세션 길이·같은 출처 규칙·비밀 inline 거부)·checklist 7 통과. 로컬 JSON 로그인 3.39 ms. 화면은 호스트와 같은 출처여야 하고 `credentials: "omit"` fetch는 401이 됨을 재현(Song 요청 초안). 접근 제한은 MLB 이용 허가가 아니며 세션은 개인 식별이 아님. 실제 코드·대상·활성화·https/Safari/CDN은 남는다. 코드 검토는 WS-review2를 따른다. [기록](ops/public-host/ACCESS.md) · [영수증](docs/results/ops/ws_access_rehearsal_20261013.json). 선점 `b593542`; 구현은 완료 커밋(PR #21). 〔모델: Fable 5.1〕
- [x] WS-alert1. 감시 이벤트를 발행 중단(`publish_stalled`, Song 우선)·호스팅 오류(`host_error`, 우리 우선)·혼합/미지(양쪽)·안내/접근 문/복구(정보)로 분류해 두 수신자에게 mock transport로 전달하는 단발 CLI(`alerts-cli.mjs`)와 상태 파일을 구현했다. (장애 id·종류·수신자)별 중복 억제, 재알림 창(복구 뒤 중단), 전송 실패 재시도·소진 후 `undelivered` 보존, 예외 문구 비기록, 주소/토큰/연락처 비포함, `delivery_confirmed:false` 상시 기록을 검사했다. 신규 Node 8(실제 감시 상태 기계 연동·CLI 포함)·전체 Node 119·checklist 7 통과, 합성 시퀀스 5개 리허설 영수증 passed. 지원 transport는 mock뿐이며 실제 채널·연락처·발송 승인은 WS-human1, 모의 성공은 전달 성공이 아니다. [기록](ops/public-host/ALERTS.md) · [영수증](docs/results/ops/ws_alert_rehearsal_20261013.json). 선점 `bcdbcd8`; 구현은 완료 커밋(PR #22). 〔모델: Fable 5.1〕
- [x] WS-report1. 경기별 운영 기록 초안 생성기(`report.mjs`·`report-cli.mjs`)를 구현했다: 경기 ID·집계 기간(UTC, ≤14일)·증거 라벨(합성/오프라인 재생/실경기)·동의/누락·수집 OFF·감시 이벤트/안내 전환/모의 알림 결과·조치·호스트/화면 커밋·계약 버전·manifest 해시·실행 명령·미측정을 Markdown 초안+JSON으로 쓰며 자동 게시 없음·덮어쓰기 없음. 이용 기록은 `collection_off`/`no_data`(미측정, 0명 아님)·`zero_rows`(0세션)·`counted`(opt-in 세션 수·활성 시간, 사람 수 아님)로 구별. 주소/토큰 모양 입력 거부. 신규 Node 5(검증·상태 구별·문제 집계·초안 섹션·CLI)·checklist 7 통과; 실제 로컬 D1 요약(합성 세션 2·활성 90,000 ms)+실제 감시 상태 기계(2이벤트)+합성 안내 감사 2건으로 네 상태 초안을 생성한 리허설 영수증 passed. D1 내보내기 CLI 없음·실경기 수치 미측정·게시는 사람 승인. [기록](ops/public-host/REPORT.md) · [영수증](docs/results/ops/ws_report_rehearsal_20261013.json). 선점 `02893ba`; 구현은 완료 커밋(PR #23). 〔모델: Fable 5.1〕
- [x] WS-review1. 운영 후보 고정 커밋(main `70aa241`)을 네 관점 발견 + 지적별 반박 2명의 Workflow(`wf_72b94abf-12b`, 검토 모델 `claude-fable-5-1`)로 검토해 지적 24건 → 확정 12건(preflight `If-None-Match`, 안내 감사 목록 페이지, 기록 초안의 OFF 채널 0세션 오기·주소/토큰 검사 범위·알림 집계 기간, 재알림 재시도·CLI 잠금·상태 정리, 첫 연결 `--output` 선검사, 배포 스크립트 경로 노출, 계약 검증기 bool·이중 읽기)을 검사와 함께 수정하고, 기각 12건은 사유를 남기며 9건(loopback 외 http 거부, 세션 길이 축소 반영, 감사 쓰기 실패 응답, 요약 범위 검사, 초안 고아 파일, 스키마 평가 실패 행, `--no-replace-objects`, 링크 검사 순서, `fullmatch`)을 추가 보강·3건 유지. 작성 모델을 커밋 trailer로 묶음 분리(Codex 2026-10-12 / Claude 2026-10-13). 재검사: ops Node 130·Python 147·ruff·브라우저 35(+첫 연결 3)·리허설 5종 통과. 당시 규약 5절 조건의 미충족 항목은 아래 WS-review2의 최신 판정을 따른다. [기록](docs/WS_REVIEW1_20261013.md) · [영수증](docs/results/ops/ws_review1_recheck_20261013.json). 선점 `ca22f48`; 수정은 완료 커밋(PR #25). 〔모델: Fable 5.1〕
- [x] WS-access2. 세션 길이 축소 뒤 기존 쿠키 부활 결함을 고쳤다. 재현(main `9c99a5d`): 2시간→30분 축소 시 같은 쿠키가 10~89분 거부 후 **90~119분 다시 유효**(남은 수명만 비교). 수정: 쿠키 v2에 발급 시각을 넣어 서명하고 유효 = 서명·코드 ∧ 현재<만료 ∧ (만료−발급)≤현재 설정 ∧ 발급≤현재+60초; 수명·만료·코드·서명 거부는 설정이 같으면 영구, 연장은 기존 세션 유지, v1 거부. 검사: 0~180분 1분 격자·연장·같은 길이·v1·수명 초과·만료≤발급·시계차·목록 밖 코드 단위, 실제 로컬 Worker 6초→3초 재시작 후 부활 구간(약 3.8초)에서도 401(main 규칙 변형에서 실패 확인). 한계(설정 되돌리면 원래 만료 안 세션 복귀, 확정 종료는 비밀 회전)는 ACCESS.md. [기록](docs/WS_ACCESS2_20261013.md). 선점 `ca01258`; 구현은 완료 커밋(PR #26). 작성 `claude-opus-5-5`, **Codex 교차검토·후속 수정은 PR #28/main 반영 완료.** 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-13 · Claude]`
- [x] WS-access3. 접근 문×수집 충돌을 고쳤다. 재현(main `9c99a5d`, 로컬 https Worker·실제 D1·Chromium): 로그인·동의 후 통계/의견이 `omit`으로 쿠키 없이 401, D1 0행, 위젯 "지연" 오표시. 수정: 공개 수집 설정 `accessGate`(설정 검사가 ACCESS_GATE_ENABLED와 일치 강제)일 때만 `same-origin`, 아니면 `omit`; 401+접근 헤더는 참여 종료(동의 해제·체크 해제, 재시도 없음, 경기·날짜 변경으로 재개 없음), 의견은 첫 거절이면 미저장 확정·앞선 시도 불확실이면 같은 id로만 재시도; 게이트 우회·수집 예외·동의 완화 없음, 서버 쿠키 미저장. 실제 로컬 조합 6(세션 없는 직접 전송·로그인 미동의/의견/동의/갱신/철회·로그아웃·재로그인 동의 미승계·4초 만료·게이트 OFF omit·설정 불일치) Chromium 통과, [영수증](docs/results/ops/ws_access_collection_20261013.json). WebKit은 CI(로컬 미설치). [기록](docs/WS_ACCESS2_20261013.md). 작성 `claude-opus-5-5`, **Codex 교차검토·후속 수정은 PR #28/main 반영 완료.** 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-13 · Claude]`
- [x] WS-monitor2. 접근 문 ON 상태 발행 감시를 보완했다: 감시 설정 선택 키 `access_code_env`(환경 변수 이름)의 감시 전용 코드로 매 실행 관람자와 같은 로그인 경로에서 세션을 받아 page/health를 읽는다(우회·새 자격 증명 없음). 코드·쿠키는 report·state·출력에 없음; 로그인 실패 `access_login_*`(읽기 skipped)·세션 거부 `*_access_session_rejected`·404 뒤 게이트 `*_access_gate_without_login`은 host_error; `access_gate_active`는 게이트 응답을 본 경우만. 실제 로컬 Worker: 게이트 ON 신선→available, 오래된 health 2회→incident→모의 알림 publish_stalled(Song 우선), 복구, 틀린 코드→host_error, 코드 없음→access_required, 안내 ON에서 notice_active; CLI 환경 변수 경로. [리허설 영수증](docs/results/ops/ws_monitor_gate_rehearsal_20261013.json). 함께 고침: 경기별 기록이 감시 미관측 기간을 "이벤트 없음"으로 쓰던 결함(`monitor_coverage`). [기록](docs/WS_ACCESS2_20261013.md). 작성 `claude-opus-5-5`, **Codex 교차검토·후속 수정은 PR #28/main 반영 완료.** 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-13 · Claude]`
- [x] WS-alert2. 열린 장애의 원인 범주가 바뀔 때 재분류 알림을 더했다(main에도 있던 고정 분류 문제; WS-access2 검토에서 재현). 알림 CLI가 감시 최신 report(마지막 기록 실행, 실행당 1회)로 원인을 따라가며 두 번 연속 규칙(감시와 같음), 알린 범주 기억(상태 v2 `incidents`), 번호 붙은 재분류(`reclassified:<n>:<범주>`, 원래 원인 복귀도 알림), 정보성에서 두 번 연속 조치 필요 시 올림, 재알림은 마지막으로 알린 범주(낮추지 않음), 새 재분류가 이전 미전달분 대체, 최신 재분류 재시도·장애 종료 시 `abandoned` 정리, opened 재시도 중 순서 대기, 형식 오류 건너뜀(종료 1). 함께 고침: 30일 정리가 감시 목록의 opened/recovered를 지워 다시 보내던 WS-review1 결함, 경기별 기록 집계 라벨. 상태 v1→v2 자동 올림, 되돌리기는 `--downgrade-to-v1`. 같은 모델 자체 검토 2회(`wf_9fc85390-ca8` 첫 판 결함 → 재설계, `wf_8e661cda-61b` 퍼징 약 1,600 수열·확정 3 수정). 검사 alerts+report 29·ops 163·리허설 7 시나리오 [영수증](docs/results/ops/ws_alert2_rehearsal_20261013.json). [기록](docs/WS_ALERT2_20261013.md). 선점 `f0a2311`; 구현은 완료 커밋(PR). 작성 `claude-opus-5-5`, **Codex 교차검토·후속 수정은 PR #28/main 반영 완료.** 〔모델: Opus 5.5〕 `[추가되었음 · 2026-10-13 · Claude]`
- [!] WS-review2. 전체 출시 검토의 남은 조건: 이전 Codex 작성 묶음의 정확한 모델 id를 세션 근거로 확인한다. Claude 운영 코드 교차검토와 이번 GPT-6 계열 수정분의 다른 모델 검토는 PR #28에서 완료했다(`2ce3a70`, `gpt-5.6-sol` PASS). 이 결과를 이전 전체 묶음의 출시 검토 완료로 소급하지 않는다. [범위·근거](docs/WS_CODEX_REVIEW2_20261013.md). 〔모델: Fable 5.1〕
- [!] WS-human1. 본인 Cloudflare·본인 시험·월 $10 이내 준비·수집/피드백 OFF와 지정 회신 1회 게시 완료(WS-stage1). 본인 전용 합성 시험 승인/배포는 WS-stage4 완료. 남은 것은 공개/실경기 연결 승인·양쪽 연락/응답 시간·안내 문구/합의된 긴급 내림의 조작 경로·운영자 권한/복구·실경기/추가 발신 범위다. 10/20 연락 결정. 10/21 이후 고장 수리만, 10/23~31 경기별 기록. 〔모델: Fable 5.1〕


## 월드시리즈 공개 운영 착수 — 2026-10-12

**H-ops1 구현 완료·수정 권한 반납.** 기준 `f312b87`, 선점 `58edf8a`. 현재 안내는 [운영 인계](docs/WS_OPERATIONS_HANDOFF.md), 과거 WS 원문은 연결된 history에 보존했다.

**WS-ops3d 구현 완료·수정 권한 반납.** 기준 `84974cd`, 선점 `96912af`. 잘못된 제한 응답13종을 양쪽 수집 경로에서 차단한다.

**WS-ops4f 완료·수정 권한 반납.** 기준 `5b1d1d7`, 선점 `97e1d9d`.

**WS-ops1c 완료·수정 권한 반납.** 기준 `6891966`, 선점 `dcd606d`.

**WS-ops4e 완료·수정 권한 반납.** 기준 `2c9c7ae`, 선점 `08dde16`.

**WS-ops4d 완료·수정 권한 반납.** 기준 `c2d1d0d`, 선점 `e075c51`.

**WS-ops3c 완료·수정 권한 반납.** 기준 `e76b53b`, 브랜치 `codex/ws-collection-settings`.

**WS-ops1b 완료·수정 권한 반납.** 기준 `ce37caf`, 선점 `cf6870a`.


- [x] WS-ops1. 공개 JSON 호스팅 후보(Cloudflare Worker/R2)의 제한된 업로드·GET/HEAD·삭제·캐시/Date/Age·실제404 처리와 CI를 구현했다. 단위28·실제 로컬 workerd/R2 통합1 검사 통과. 공개 배포·실제 스키마 연결은 별도다. 사용자 직접 요청으로 Codex가 수행하며 Claude 교대 태그는 후속 세션용이다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops1b. 인증 업로드 공통 요청 제한·limiter 장애 시 저장소 차단을 구현했다. Node71·체크리스트7·별도 Codex 관련39통과. 실제 Cloudflare 분산/과금 상한이나 발행 주기 확정은 아니다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops3c. 통계/피드백 독립 토글과 실제 보관일 안내, 미설정 시 양쪽 차단을 연결했다. Node73·체크리스트7·Chrome/WebKit 각7·별도 Codex client10통과. 서버설정/실제배포 일치 확인은 별도. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops2. mail #18 첫 연결 자료를 실제로 검증했다: 예시 13·스키마 6을 `svc/ws-publisher@d5a1dd9`에서 받아 문서 SHA 19/19 일치, JSON Schema 오류 0, 호스트 경로/크기 제약 통과(`scripts/verify_publish_contract.py`, 영수증 `docs/results/ops/collab001_contract_verification_20261013.json`). 문서 절차대로 로컬 Worker에 업로드·6단계 교체·철회/복원·404·CORS·no-store를 확인하고 공개 GET `If-None-Match`→304를 구현했다(영수증 `ws_first_connection_rehearsal_20261013.json`). `svc/ws-static-web@ef4e4df` 공개 빌드(Windows는 셸 `VITE_PUBLISH_BASE=.` 필요)를 같은 Worker에서 Chromium으로 열어 목록·경기 전·추천·확인 중·연결 끊김·공수 교대·종료·발행 중단(갱신 지연 28 s)·철회를 구별, `/api/**` 0건, setup 미요청(영수증 `ws_first_connection_screen_20261013.json`). `unsupported` 예시 없음(Song 후속)·추천 후보 스키마 2곳 미반영·실제 발행기 업로드/실계정/CDN/Safari는 미확인. 회신 초안 `docs/mail_drafts/COLLAB-001-reply-draft-20261013.md`(미발송). [기록](docs/WS_OPS2_FIRST_CONNECTION_20261013.md). 선점 `dca5339`; 구현은 완료 커밋(PR #24). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops3a. 전용 D1 이용 기록·선택형 피드백 저장, 원자적 일별 상한, 중복/역순 방지, UTC 집계·만료 정리를 구현했다. 신규9·전체Node38검사 통과. 실제 수집 비활성. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops3b. 동의·철회·활성 시간 측정·선택형 피드백 독립 UI와 브라우저 회귀를 구현했다. Node46·Chrome/WebKit 각5 통과. Windows WebKit의 omit 지정에도 쿠키 전송되는 현상은 미해결 한계로 기록했다. 실제 Song 화면 삽입·수집 활성화·Safari 기기는 별도다. CI에서 드러난 가상시계의 실제 시간 혼입을 pauseAt으로 고정했다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4a. 고정 호스트 커밋·공급자 화면/계약 메타데이터·파일 해시의 결정적 ZIP 생성/검사를 구현했다. 관련58검사·체크리스트7검사 통과, 합성 빌드2회 SHA 일치. 출처/권리/배포 승인이 아니며 deployable=false 유지. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4b. 단발 읽기 감시·발행 시각 별도 판정·2회 장애/복구 기록·잠금/원자적 상태 보존을 구현했다. 신규15·전체Node61검사 통과. 실제 스키마/도메인/상시 실행/외부 알림은 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4c. 로컬 Worker 합성 조회120/120·실제최대동시6·충돌/철회/복원/감시복구와 Chrome/WebKit 각2검사를 통과했다. 전체Node66, 별도Codex 신규5통과. Windows WebKit 종료의 WSARecv64 진단은 남아 있다. 공개 CDN/Song 성능이 아니다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4d. 오프라인 후보 설정 검사: 목록 바이트/공개 폴더 추가 파일/경로/Worker 우선/binding·namespace/수집 안내·정리 cron 대조를 구현했다. 신규66·기존58통과, 별도 Codex64 및 수정 경계6확인. 실제 계정·권리·배포는 별도. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4e. 운영 장애/철회/코드롤백/DB복구 절차와 공식 가격 날짜·가정별 트래픽/비용 산정기를 작성했다. 신규25·별도 Codex25통과. 실제 가격 재확인/배포·복구 성공·승인된 예산과 구별한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops1c. 단일 파일 전송 후보·기본 dry-run·고정 조건/바이트 재시도·불확실성 영수증을 구현했다. 신규17·별도 Codex17통과. Windows workerd 취소/종료 WSARecv64 진단은 미해결로 기록. 실제 발행기/다중 파일/스키마 검증은 별도. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops4f. 로컬 영속 R2/D1의 4회 시작·3회 재시작, 키 교체·중복 budget·수집 OFF 실제 scheduled 만료 정리를 검증했다. 신규/독립 각3·전체 Node93통과. 정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 별도. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] WS-ops3d. boolean true만 수집 허용, false는429, 잘못된 제한 응답은503으로 구분했다. 신규2·전체 Node95·독립11·체크리스트7통과; 실제 Cloudflare 장애 관찰이 아닌 방어 회귀다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [x] H-ops1. 운영 안내를 한 곳에 모으고4개 시작 문서의 과거 WS 원문을 보존했다. PR/main 자동 CI·수동 실행을 유지하며 작업 브랜치 push 중복을 제거했다. 4개 나머지 본문·workflow 검사 명령/범위 불변, 현재 링크16개·체크리스트7·독립 문서/CI 검토 통과. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`
- [!] WS-ops4. 본인 계정·월 $10 준비·수집/피드백 OFF 결정 및 본인 전용 합성 배포는 WS-stage4에서 완료. 남은 것은 Song 후속 고정 자료·공동 시험 접속/시간/운영자 결정, 실제 알림·실경기/실기기 검증이다. 새 일반 공개·수집 ON은 별도 사람 결정이며 상세는 현재 운영 인계 참조. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-12 · Codex]`

브라우저 실행 폴더에서 Worker 모듈 경로 실패를 재현해 modulesRoot를 명시했다. 원격 Chromium/WebKit 각29·전체 CPU Linux/macOS·Node66 CI 통과(PR #9).

**WS-ops4c 구현 완료·수정 권한 반납.** 기준 `3898083`, 선점 `a648376`. [리허설 결과·한계](ops/public-host/REHEARSAL.md).

**WS-ops4b 구현 완료·수정 권한 반납.** 기준 `b00ec71`, 선점 `55598a5`. [감시 범위·실행·한계](ops/public-host/MONITORING.md).

**WS-ops4a 구현 완료·수정 권한 반납.** 선점 `09b28ca`, 기준 `c8a6865`. [패키지 형식·재현·한계](ops/public-host/RELEASE.md). 당시 Song 파일 수신 전 이력이다. 첫 팩은 WS-ops2에서 수신·검증했고 후속 팩/실배포는 별도다.

**WS-ops3a/b 구현 완료·수정 권한 반납.** 브랜치 `codex/ws-telemetry`, 선점 `1fb7360`, 서버 `5da2f2a`. 로컬 검증 완료, CI·병합은 우리 board 기록을 확인한다.

**WS-ops1 완료·수정 권한 반납.** 구현 브랜치 `codex/ws-host-foundation`, 기준 main `7128cd3`, 선점 `c932219`. 원격 검사·병합 기록은 우리 board에 남긴다.
[구현·검증·남은 범위](docs/WS_PUBLIC_HOST_20261012.md) · [운영 코드·재현](ops/public-host/README.md).
협업 문서 `collab/ws-2026@ed3a51c`의 추가 호스팅 조건을 반영한다. 초기 착수 때는 열린 mail 0건이었으나, 현재 #18과 첫 연결 경로 안내 댓글을 수신했다.
실제 파일 검증은 WS-ops2로 남는다. 이 단위는 우리 운영 기반이며 Song 코드 변경·모델 실행·공개 배포가 아니다.
기존 I-run1 모델 이식과 A-y 사람 검토는 이 파일 발행 구조의 선행 조건으로 삼지 않는다. 기존 미완료/보류는 유지한다.


## GitHub 상황판·우편 협업 도입 — 2026-10-11

- [x] H-collab1. 우리 고정 상황판 #3(board)·mail/needs-human 라벨·우편 양식과 AGENTS/CLAUDE/Cloud/재개 세션 규칙을 반영했다. Song #35/#36은 읽기만 했으며 정본·계약·실행 권한 합의와 구분했다. 체크리스트7검사·YAML/문서 링크·별도 Codex 검토 통과. 종료 기록은 우리 board 댓글에 남긴다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-11 · Codex]`

**수정 권한 반납.** 구현 브랜치 `codex/collaboration-board`; 협업 문서와 우리 GitHub 이슈 설정만 변경했다.
[우리 상황판 #3](https://github.com/Pitcheezy/transition-models/issues/3) · [협업 규약](docs/COLLABORATION_PROTOCOL.md).
A-y·F-4i 보류, 기존 영상·모델·사람 응답·서버·공개 배포 상태는 유지한다.

## main 통합·Codex Cloud 인계 완료 — 2026-10-11

- [x] H-main1. 우리 feature/intent-v0·codex/fix-point-label-alignment·codex/cv-m3-oct05-deliverables 이력을 PR #2로 main에 병합했다(39ffcd0). Linux/macOS 전체 CPU 각2283passed/8skipped/2deselected, Chrome/WebKit 각22passed, Node70passed. 운영 구조·Cloud 설치/LFS·실행·프롬프트를 문서화했다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-11 · Codex]`

**수정 권한 반납.** 다음 작업은 최신 main에서 짧은 새 작업 브랜치로 시작한다. 기존 작업 폴더·미커밋/비공개 자료·서버·원본 브랜치를 보존했고, SongRoute/pitcheezy에는 접근/변경하지 않았다. A-y·F-4i 보류와 외부 입력 조건은 유지한다.

[통합 범위·검증·원격 반영 기록](docs/MAIN_INTEGRATION_20261011.md) · [Codex Cloud 운영 설명과 복사 프롬프트](docs/CODEX_CLOUD_HANDOFF.md).
통합 후 새 작업의 기준은 최신 main이며, 원본 브랜치와 미커밋/비공개 자료는 보존한다.



## 노트북 후속 CV-31 완료 — 2026-10-11

- [x] CV-31. 구간 끝 기본 영상 재생/키보드 재시작과 WebKit 최초 탐색·반복 이동을 수정했다. 합성 Chrome/WebKit 각22검사(신규9+기존13), 실제 개발 영상 Chrome16, Node26, 관련 Python58 통과. 발행/마감 기준·원본 관측은 동일하다. [수정·재현·한계](docs/CV_PLAYBACK_BROWSER_REGRESSION_20261011.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-11 · Codex]`

현재 노트북 화면은 `http://127.0.0.1:59158/`, 새 관측팩은 `outputs/cv_replay_view_20261011_v9`다. 기존 팩을 보존했다.
[팀원 수신 ZIP/우리 소스 ZIP/영상 ZIP의 차이와 전달 문안](docs/handoff/FILE_GUIDE_20261011.md)을 정리했으며 전송하지 않았다.
Mac I-device2는 해당 기기 사용 시 별도 재개한다. 노트북 작업의 선행 조건이 아니다. A-y 보류·독립 사람/새 영상/모델 실행 자료 대기를 유지한다.
선점 `c8f9fe8`; 구현·검증은 같은 완료 커밋. **수정 권한 반납.** 팀원 저장소·공개 Site·사람 응답 변경 없음.

## I-device2 Mac 환경 확인 · 영상팩 전송 대기 — 2026-10-11

- [!] I-device2. 실제 Mac에서 Darwin/arm64·macOS27.0(26A428), 우리 origin과 `feature/intent-v0`의 `06a3110`을 확인했다. 변경31개가 있는 기존 main은 보존하고 별도 작업트리에서 fetch·pull --ff-only 완료(이미 최신). 비공개 `service_review_video_20261010_v5.zip`은 조사한 로컬 경로에서 미발견이다. 영상팩 전송 전에는 재생·결과 공개·투구/타석 전환·미트 가로 표시를 검사할 수 없어 모두 미실행으로 남긴다. [실제 확인·전송·재개](docs/MAC_DEVICE_REVIEW_20261011.md). hosted macOS CI를 실기기 검사로 대체하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-11 · Codex]`

Mac 연결 대기는 해소됐으며 현재 차단 사유는 영상팩 부재다. 기본 `python3`는3.9.6이므로
기존 프로젝트에서 확인한 Python3.12.13 실행 파일을 사용한다. 아래 CV-30 검사 수치는 이전 Windows 기록이다.
이번 Mac의 서비스 UI 검사 통과 수는0이며 I-device2·I-release1은 미완료, CV-30 완료·A-y 보류를 유지한다.
기록 검증: checklist7passed, JSON/기대 ZIP 식별값/문서 링크/diff 검사 통과. 서비스 동작 검사와 구분한다.
**수정 권한 반납 — 영상팩 도착 후 I-device2 재개.**
- [x] CV-30. 기존 CV24 자동 관측14개를 제한 중계 구간의 영상 시계·발행 시각·투구 참조에 연결한 비공개 뷰어를 만들었다. 발행 전/뒤로 탐색 시 숨김·다른 투구의 과거 관측 구분·Range 영상 재생·입력 이미지 교체를 검증했다. 구간 안 입력10개/구간 앞4개·확정 미트0개·보수적 투구 전 시각 충족0/3구. 새 모델 실행·전체 타석·독립 평가가 아니다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-11 · Codex]`

사용자 “4번 6번 진행해봐” 승인으로 등록한 단위다. Python80passed·Node26cases·Chrome154 브라우저15항목 통과.
전체 CPU2254passed/8skipped/2deselected(406.51초); 이후 추가한 Range 서버22검사는 관련80검사에 포함해 별도 통과했다. 기존 Pillow 테스트의 폐기 예정 API 경고2개가 있다.
[구현·재현](docs/CV_OBSERVATION_PLAYBACK_20261011.md) · [검증 영수증](docs/results/cv_followup_20261011/observation_playback_v1.json).
로컬 화면 `http://127.0.0.1:59158/`; 최종 비공개 팩 `outputs/cv_replay_view_20261011_v4`(21파일,52899890bytes).
기존 엄격한 CV-5a4/CV-5a·I-release1 완료 조건은 유지한다. 팀원 저장소 접근/변경·공개 배포·사람 판정 대행 없음.
A-y는 계속 보류한다. 사용량 시작 잔여41%→완료 전 확인33%; 약10% 하한 유지. **수정 권한 반납.** 선점 `2d8a95c`; 구현은 같은 완료 커밋.

## 독립 서비스 작업·v5 이관 완료 — 2026-10-10

- [x] H-browser1. 새 S 합성 자료의 실제 브라우저 파일 교체·공개 순서·오류 복구 검사 13개와 Chromium/WebKit CI를 추가·실행했다. 이전 로컬 임시 스크립트를 반복 실행하는 것과 구분한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

- [x] I-service7. 키보드 투구 선택 후 포커스 유실을 수정하고 Enter/Space 및 외부 컨트롤 포커스 보존을 실제 브라우저로 확인했다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`
- [x] I-service8. CLI의 5MiB 초과 출력·브라우저 단위/비중 합/중복 구종 수용 불일치를 수정했다. 기존 수신262구 검토팩의 원문·정규화 바이트와 부분 비중/null 의미는 유지한다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

- [x] H-port8. v5 소스64파일 ZIP 및 별도 영상16파일 ZIP의 압축 해제·CRC/SHA·실행을 확인했다. 소스 Python458passed/1skipped·Node112passed; 영상3구 재생/공개 및 타석 전환4항목 통과. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

H-browser1/I-service7/I-service8 구현·로컬 검사 완료. Windows CPU2225passed/8skipped/2deselected·Node44passed·Chrome/WebKit 각각13passed. [수정과 재현](docs/SERVICE_REVIEW_REGRESSION_20261010.md). 원격 Chromium/WebKit 각13passed(CI38056890881); 같은 소스 Linux/macOS CPU 각2225passed/8skipped/2deselected(CI38056890856).

소스 `fafc9c6`의 v5 전달 기록: [영수증](docs/handoff/delivery_v5.json) · [사용 안내](docs/handoff/README.md).
현재 영상 화면 `http://127.0.0.1:59154/`는 이 컴퓨터의 실행 세션 주소다. 공개 Site는 변경하지 않았다.
팀원 저장소 접근·변경·팀원 전송·사람 판정 대행 없음. 기존 팩·응답·영상·라벨 보존. **수정 권한 반납.**
사용량은 시작 잔여53%, 마지막 작업 단위 확인44%다. 10% 하한에 닿지는 않았으며, 현재 등록된 독립 실행 단위를 완료했다.
남은 조건을 AI 자료로 대신 채우거나 같은 표본/검사를 되풀이해 완료로 만들지 않는다.

### 지금 남은 조건별 재개

| 남은 작업 묶음 | 재개에 필요한 것 |
|---|---|
| I-0 / I-5 최종 통합 기준·지원 범위 | 팀원의 소스/배포 버전 대응, 전체 지원 목록, 공동 기준 합의 |
| I-run1 모델/API 실제 기동 | 합의된 실행 번들·가중치·데이터 manifest·lock·경로 설정 |
| I-1 / I-2 / I-4 모델·프로필·타자 연결 | 실제 사건확률/프로필/as-of 공급 계약과 자료 |
| I-release1 / E-site5 / E-demo2 실사용·배포 확인 | 실제 Mac/아이폰과 사용자/Song 확인 기록·운영 조건 |
| CV-6 가용성 판단 대조 | 별도 독립 사람이 판정한26장 응답 |
| CV-5a4 → CV-5a 연속 타석 리플레이 | 시작 정의 결정 또는 엄격 조건을 만족하는 새 원본 |
| CV-7 독립 영상 평가 | 미열람 영상·독립 라벨러·고정 평가 manifest |
| F-1 / G-1 / G-3 의도·제구·정책 효용 | 대리값/좌표 평면/보상 단위/공동 평가 규약 합의 |

A-y44구 사람 검토는 사용자 요청으로 보류다. 팀원 C/D, OCR 확대, 옛 영상 정리, KBO 확장은 현재 독립 필수 작업으로 재배정하지 않는다.
위 목록은 관련 항목을 묶은 것이며 모든 미체크 행이 같은 크기의 개발 작업이라는 뜻은 아니다.

### 이전 H-port7 전달 기록

- [x] H-port7. 기존54→64파일로 최신 S 수신·검토 화면·단독 실행기·검사를 포함했다. 소스 `73cf059` ZIP 실제 압축 해제→Python456passed/1skipped·Node104passed·브라우저3항목·65파일 CRC/SHA 확인 완료. 받은262구 정규화 바이트는 기존 v4와 동일하다. 원문·영상·가중치·사람 응답은 새 소스 ZIP에 넣지 않았다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

[소스 사용 안내](docs/handoff/README.md) · [전달 영수증](docs/handoff/delivery_v4.json). 선점 `0f165b9`; 구현 `73cf059`.
소스 ZIP: `outputs/service_review_source_20261010_v4.zip`(265852bytes). 별도 영상 검토팩 v4와 구분한다.
Codex 수정 권한 반납. A-y 사람 검토 보류·I-0/I-run1/I-release1 대기는 유지한다. 팀원 저장소·공개 Site 변경 및 팀원 전송 없음.

## 현재 우선순위 — 수동 검토 보류·서비스 오류 복구 — 2026-10-10

사용자가 A-y44구 수동 검토를 명시적으로 보류했다. 해당 화면·부분 응답·고정 규약을 보존하고 서비스 마무리를 진행한다.
A-y를 다음 필수 작업으로 다시 배정하거나 AI 검토로 완료 처리하지 않는다. 독립 사람 일치도는 미측정으로 남긴다.

- [x] I-service6. Windows 영상 요청 중단 예외 처리 완료. 새20검사 수정 전16실패→후20통과,관련 Python115·Node36·브라우저7시나리오·v4 ZIP16파일 이관 검사 통과. 선점 `cbc6f29`; 구현은 이 기록과 같은 커밋. [복구 검사·현재 팩](docs/SERVICE_REVIEW_RECOVERY_20261010.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

수정 권한 반납. 현재 전달본은 `outputs/service_review_video_20261010_v4.zip`이며 이전 팩·사람 입력·모델·팀원 저장소는 보존한다.


## A-y 실제 사람 부분 응답 수신 — 2026-10-10

44구 중1구 annotated·43구 unreviewed인 첫 응답을 원본 그대로 비공개 보존하고 scripts72 형식 검사를 통과했다.
전체 완료 검사는 미검토43구로 예상대로 실패한다. 파일명 ay_v1은 고정 study ID이며 내부 schema는 올바른 v2다.
저장 키는 `747139:1:3`(첫 타석3구)이지만 사용자가 실제로 본 것은 경기 초구였다고 확인했다.
이1행은 투구 식별 불일치로 비교 대상에서 제외한다. 형식상1입력/43미검토와 구분해 유효 비교0구·완료에 필요한44구로 기록한다.
[사용자 정정 기록](docs/results/mlb_p0/game_747139_ay_followup_20261010_v1.json). 원본·최초 수신 영수증은 보존하며 초구로 자동 재배정하지 않는다.
아직 기준 정답과 비교하거나 영상 판정·일치도·정확도를 계산하지 않았다. 입력값·기존 주석·검토팩은 변경하지 않는다.
[수신 기록](docs/results/mlb_p0/game_747139_ay_receipt_20261010_v1.json). A-y는 부분 진행이며 미완료다.
아래 “응답 미수신”은 이전 상태다. CV-6의 추가 독립 검토자는 계속 대기한다. 수정 권한 반납.


## 좌표 표시 이해도 개선 I-service5 완료 — 2026-10-10

- [x] I-service5. 실제 공 위치·가로 방향·높이·원 실수 기반 cm 환산 설명 완료. ft 눈금·미트 가로 추정·공개 순서는 유지한다. Node36·관련 Python95·Chrome9시나리오·화면 확인·v3 ZIP16파일 이관 검사 통과. 선점 `6ecedbf`; 구현은 이 기록과 같은 커밋. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

[좌표 안내·현재 v3 팩](docs/SERVICE_REVIEW_COORDINATES_20261010.md). v2와 데이터·영상은 동일하다.
수정 권한 반납. 아래 I-device1 사용자 확인은 v2에 대한 기록이며 v3 사용자/실기기 검수로 확대하지 않는다.
독립 사람 응답·새 영상·실제 Mac/아이폰·모델 실행 합의·공개 운영 조건은 유지한다.

## Windows 노트북 실제 사용자 확인 — 2026-10-10

- [x] I-device1. 사용자가 현재 Windows 노트북의 v2 로컬 화면에서 첫 타석3구 재생, 종료 후 결과 공개, 투구 전환 초기화,3구 미트 가로 표시, 실제 파일 선택 취소의5항목을 모두 정상으로 보고했다. 자동 재관찰이 아닌 실제 사용자 보고이며 새 ZIP 설치·Mac·아이폰 검수로 확대하지 않는다. [확인 기록](docs/results/service_integration_20261010/windows_user_review_v1.json). 실행 소스 `24ca998`; 이 기록과 같은 커밋. 〔모델: Opus 5〕 `[추가되었음 · 2026-10-10 · Codex]`

2번 기기 검수 중 Windows의 위5개 사용자 동작만 완료했다. Mac·아이폰·별도 기기 설치는 미완료이며 I-release1 전체도 유지한다.
3번 CV-6의 추가 독립 검토자와4번 A-y의 실제 응답은 아직 미수신이다. 사용자가 사람 검토 화면에 입력할 내용은 대신 작성하지 않았다.
문서 기록만 변경; 수정 권한 반납. 사용자 보고의 기기/브라우저 정확한 버전은 제공되지 않았다.


## I-service4 브라우저 파일 교체 검수·식별자 수정 완료 — 2026-10-10

- [x] I-service4. 실제 Chrome 파일 선택에서 99구 표시/1구 영상 불일치 재현 후 경기·타석·투구 식별 검사 수정. 새7검사 수정 전 실패→Node36통과, 관련 Python95통과, 실제 브라우저21시나리오·화면 캡처·v2 ZIP16파일 이관 검사 완료. 전용 도구 오류를 별도 Chrome headless로 대체했으며 OS 파일 대화상자/실제 Mac·아이폰은 미검증. 기존 원본·v1 ZIP 보존. 선점 `9b400cc`, 구현은 이 완료 기록과 같은 커밋. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`

수정 권한 반납. 이후 전달은 `outputs/service_review_video_20261010_v2.zip`을 사용한다.
[검수·실행 안내](docs/SERVICE_REVIEW_BROWSER_QA_20261010.md). 아래 파일 선택 오류/최종 캡처 미완료 기록은 당시 상태다.
남은 실제 기기·독립 사람 검토·새 영상·모델 실행·공개 운영 조건은 유지한다.

## I-service3 · H-port6 완료 — 2026-10-10

사용자가 승인한 독립 두 단위다. 팀원 저장소를 참조하거나 수정하지 않고 이미 받은 응답과 우리 영상만 사용한다.
- [x] I-service3. 새 S 검토 화면에 기존 849843 첫 타석 3구 영상을 투구 키·기존 play ID 근거·SHA로 연결 완료. 새 S 자체에는 play ID가 없다. 영상 재생·결과 공개·전환 초기화·미지원·실패 처리를 검증한다. 별도 미트 정지 장면의 시각을 공식 클립에 추정 대응하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`
- [x] H-port6. 새 검토팩의 stdlib 실행 도우미·자료 검사·빈 포트·허용 파일 제공·비공개 ZIP 및 압축 해제 실행 검증. 실제 Mac/아이폰 사용 검증과 공개 배포는 별도다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-10 · Codex]`



검사: Windows CPU2202passed/8skipped/2deselected·Node29passed·Ruff167경로. ZIP16파일 실제 압축 해제/격리 실행 및 영상3구 브라우저 공개 확인.
파일 선택기 오류 검수·최종 캡처는 도구 중단으로 미완료, 실제 Mac/아이폰은 미검증. 선점 `b44b401`, 구현은 이 완료 기록과 같은 커밋.
[실행 안내](docs/SERVICE_REVIEW_VIDEO_PACKAGE_20261010.md) · [검증 기록](docs/results/service_integration_20261010/video_package_verification_v1.json).
팀원 저장소 조회/수정·공개 Site 배포 없음. I-0/I-run1/I-release1 및 독립 사람/영상 평가의 대기는 유지한다.

## I-service2 실제 S 원문 수신·로컬 연결 완료 — 2026-10-09

사용자 제공 ZIP의 원본·CRC·manifest 5파일 SHA/크기를 검사하고, 경기 849843의 262투구/71타석을 새
`teammate_export_20261009_v1` 프로필로 대조했다. ready 246·unsupported 16·missing 0,
셋업 estimated 27·unavailable 12·null 223이다. missing 실제 사례는 미수신이며 합성 검사와 구분한다.
`web/service-review`의 비공개 로컬 화면(`http://127.0.0.1:8794/`)에 추천 → 실제 결과 공개 →
조건을 만족하는 가로 셋업 표시를 연결했다. 원문과 정규화 데이터는 Git 제외 경로에 보존한다.

cutoff 객체의 투구 키/경계, `game.date_kst`, 셋업 상태/좌표를 명시적으로 검사한다. 기존 잠정 프로필과
저장 결과는 유지한다. 선택 비중은 사건확률로 변환하지 않는다. 이 자료는 경기 후 as-of 재생이며,
사전 가용성·누출 없음·정책 효용·전체 경기 완전성·실시간 연결·런타임 커밋은 검증하지 않았다.
SHA 일치는 파일 식별이며 출처 인증이 아니다. 셋업은 검토 전 가로 추정치이고 투수 의도가 아니다.

검사: 전체 Windows CPU 2120 passed/8 skipped/2 deselected(최종 크기 제한 검사 추가 전, 549.41초); 최종 관련 Python208 passed/1 skipped(25.96초)·Node16 passed; 실제262구 공개 전후 대조 및 로컬 브라우저 확인 완료. 선점 `2b11c06`; 구현·완료는 이 갱신과 같은 커밋이다.
I-service2의 로컬 수신/표시 범위만 완료했다. **I-0·I-run1·I-release1은 미완료**이며 수정 권한을 반납한다.
다음 조건은 모델/API 실행 번들과 정본·버전 합의, 추가 사람 검토(CV-6/A-y), 새 기기 실행 기록,
미열람 영상·독립 라벨러(CV-7)다. CV-5a4의 시작 정의 등 기존 미완료 조건도 자동 해제하지 않는다.
H-port5의 기존54파일 ZIP은 이번 새 수신 프로필·로컬 화면 코드를 포함하지 않는다.
팀원 저장소/API·공개 배포·기존 M3/JSONL/사람 응답은 변경하지 않았다.

[수신·연결 기록](docs/SERVICE_GAME_V2_RECEIVED_20261009.md) · [수신 영수증](docs/results/service_integration_20261009/s_export_receipt_v1.json).
아래의 S 원문 미수신·I-service2 대기·다음 작업 지시는 당시 범위의 이력이며 현재 상태는 이 절을 따른다.


## 독립 투구·프레임 결속 수정 H-13 — 2026-10-09

사용자 재개 지시로 체크리스트 밖의 실제 결함을 확인했다. 아래 추가 작업 없음은 당시 등록 범위에 대한 이력이다.

- [x] H-13. 중복 timing 투구와 비유한/음수/비숫자 시각을 변환 전에 거부한다. 새21검사 전20실패/1통과→관련57통과. 정상5경기10경우950행 동일·43원자료 SHA 불변. 전체 Windows CPU 2060 passed, 8 skipped, 2 deselected, 3 warnings in 577.39s (0:09:37). [보고](docs/INTENT_FRAME_BINDING_20261009.md). 선점 `83b7d4c`; 구현 `47ddc8f`. `[추가되었음 · 2026-10-09 · Codex]`

- [x] H-port5. 최신 소스 이관에 누락된 보정 JSON5개를 포함한54파일 ZIP v3 생성·검사 완료. 독립 사본의 기존5실패를 해소했으며 실제 압축 해제 Python276passed/1skipped·Node68passed·전후55파일 바이트/SHA 일치. 기존 v1/v2 ZIP 보존. 구현 `47ddc8f`, 소스 CI Linux/mac CPU 각각2060passed. [전달 기록](docs/handoff/delivery_v3.json). `[추가되었음 · 2026-10-09 · Codex]`

`--next`의 없음은 등록 항목 선택 결과다. 새로 재현한 우리 결함/구체 작업은 별도 등록할 수 있다. 같은 탐색·실험을 반복해 대기를 해제하지 않는다.

새 S 원문(I-service2), CV-6 추가 사람 검토, A-y 별도 timing 검토, CV-7 독립 영상/라벨러, 실제 Mac 확인은 계속 대기한다. 기존 자료를 새 검증 자료로 바꾸지 않는다.

## 독립 결함 탐색 — 2026-10-09 (Claude, Fable 5.1)

조건 ①–④(새 S 원문·추가 사람 응답·새 기기·새 영상/독립 라벨러)가 모두 미충족임을 다운로드·외장 SSD·응답 폴더·팀원 공개 브랜치·`--next`로 확인했다.
경로 ⑤로 최근 변경 `plate_feet`(H-12)와 `service_game` 정규화기를 구체 입력으로 탐색했다. **재현되는 결함은 없었다.**
H-12의 `applied_depth_parallax_correction`은 커밋된 5경기 보정·무보정·합성 5건 모두 행렬 이동항과 1e-9 이내 일치했다.
S 정규화기 16경계 입력은 전부 거부되거나, 수용된 경우에도 미공개 뷰에 사후 필드가 새지 않았다. 행 형제 키 생략은 문서화된 설계다.
[탐색 기록](docs/results/cv_independent_20261009/defect_probe_v1.json). 코드·모델·사람 응답·M3·JSONL 변경 없음. 팀원 레포 미수정.
같은 탐색을 반복하지 않는다. 재개는 조건 ①–④ 충족 시 해당 단위부터다. 수정 권한 반납.

## 독립 좌표 근거 정정 — 2026-10-09

- [x] H-12. 고정된 “약0.01ft, 적용하지 않음”을 실제 적용 보정량/잔여 깊이 민감도로 정정. 5경기 수정 전후 좌표·상태·오차 동일,26원자료 SHA 불변. [보고](docs/COORDINATE_EVIDENCE_CORRECTION_20261009.md). 선점 `1d787e3`; 구현/완료는 같은 커밋. `[추가되었음 · 2026-10-09 · Codex]`


## 독립 사용성 개선 CV-29 · H-11 완료 — 2026-10-08

사용자 재개 지시로 실제 개인 검토 흐름의 미완성 작업을 추가한다. 아래 추가 구현 없음은 이전 범위 점검의 이력이다.

- [x] CV-29. 별도 미완성 초안 저장·복원·현재 프레임 복귀 완료. 최종 응답 엄격 검사와 최신 파일 선택 보존. 합성 브라우저 저장/복원/최종 제출 확인, 새27검사 포함 관련145passed. 초안은 제출용이 아니며 자동 저장·판독 없음. 선점 `7b1888d`, 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`
- [x] H-11. stdlib 실행 도우미·사전 검사·빈 포트·현재 컴퓨터 주소 안내·고정 reviewer 자료만 제공 완료. 새 ui_v3 팩/비공개 ZIP 생성·압축 해제 바이트/독립 실행 검사, 기존65파일 보존. 기존26응답 재검사 통과. 실제 Mac 확인은 미수행. [검증 기록](docs/results/cv_independent_20261008/review_draft_launcher_v1.json). 선점 `7b1888d`, 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

## 독립 수정 H-8–10 · CV-28 · H-port4 완료 — 2026-10-08

사용자 지시로 팀원 응답 없이 가능한 독립 작업을 계속한다. 기존 사람 응답과 검토 팩은 고정한다.

- [x] H-8. 검토 응답 불러오기의 최신 선택 보존 완료. 이전 읽기 성공/오류/정리가 최신 응답·편집을 덮어쓰지 않는다. 새6검사 수정 전4실패/2통과→후6통과; 관련55passed. 새 팩 `outputs/cv_review_20261008_ui_v2`는 JS만 다르고 고정31파일·원응답 보존, 기존26응답 검사 통과. [안내](docs/CV_REVIEW_UI_V1.md). 선점 `9df8fe6`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

- [x] H-9. 좌표 생성기의 timing·points·calibration 경기 결속 검사 완료. 다른 경기 보정/식별자 누락을 출력 전에 거부한다. 신규12검사 전부 수정 전 실패→후 통과, 관련94passed. 정상4경기178행은 보정 사용/미사용 모두 기존 함수와 전체JSON 같고16원자료SHA 불변. [기록](docs/results/cv_independent_20261008/calibration_game_binding_v1.json). 선점 `c220ba3`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`
- [x] CV-28. 새 AI marked/partial 응답의 비어 있지 않은 이유를 요청·수신 검사에 반영. 옛/새 요청 계약을 구분해 저장 보고서16개와 결과/요청278파일을 보존했고 옛 빈 이유5건을 소급 수정하지 않았다. 정본 관련314passed·Ruff161경로·독립 코드 검토 통과. [보고](docs/CV_PARTIAL_REASON_ACCEPTANCE_20261008.md). 선점 `c220ba3`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

- [x] H-10. 명시 보정 파일 부재/디렉터리 입력을 출력 전에 거부하고 반복 판독 RMS 0과 미측정을 구분한다. 새7시나리오 전5실패/2통과→관련31통과. 전체 CPU1971passed/8skipped/2deselected·Ruff161경로, 기존5경기 입력/통계 불변. [기록](docs/results/cv_independent_20261008/calibration_missing_and_zero_v1.json). 선점 `5fc8e27`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

- [x] H-port4. 최신 소스49개 이관 v2 생성·압축 해제 검증 완료. 기준 `bf1fb5d`,154,924bytes, SHA `9387621a3850dc5109ca8fe5d770504c01761dc01c4db9db3f3520b640c7f2bd`. 독립폴더Python244passed/1skipped·Node68passed·50파일 바이트/CRC/전후SHA 통과. 기준소스 Linux/macOS 전체CPU각1971passed. 기존 v1/운영 ZIP 보존·전송/공개 없음. [안내](docs/handoff/README.md) · [전달 기록](docs/handoff/delivery_v2.json). 선점 `e669ed4`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

현재 체크리스트의 우리 독립 구현 단위를 다시 확인했다. 다음은 새 S 원문/합의→I-service2, 독립 사람 응답→CV-6/A-y, 새 영상/독립 라벨러→CV-7, 새 기기 실행 기록이다. 준비된 저장·검사·집계·이관 도구를 중복 개발하거나 같은 표본 실험으로 이 조건을 대신하지 않는다. 추가 자료가 오면 해당 단위부터 재개한다. 파일 수정 권한 반납.

## H-7 · CV-6b 완료 — 2026-10-08

H-7 날짜 검사 수정·검증(`4111eed`), CV-6b 저장된 기권 처리 경로 감사 완료. 우리 저장소만 수정했다.

- [x] CV-6b. 고정26장·A/B52행·사람 응답26개 연결, 기존 합의 함수의 상태/사유/프레임/메모26건 재현 완료. 처리 경로7/2/2/3/6/3/3, 좌표변환 기준점 부재와 미트 결측·프레임 선택을 구분했다. [보고서](docs/CV_SAVED_PROCESSING_ROUTES_20261008.md). 관련69tests·Ruff161경로·원자료SHA/공개집계 검사 통과. 새 시각 판정·자세 재분류·정확도 측정·학습 없음. 선점 `562fcce`; 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

## CV6 첫 사람 응답 처리 완료 — 2026-10-08

실제 응답1개·26장 모두 marked/full, 미검토0. 출처·좌표 범위 검사와 CV26 원본 연결을 통과했다.
자세는 원문 resting18/moving5/presented_target2/unknown1을 보존했다. 사용자가 지적한 낮은 준비 자세와
휴식/움직임의 모호함은 전역 피드백으로 별도 기록했다. 자세를 임의 재분류하거나 목표/의도 정답으로 쓰지 않는다.
원본9,035bytes·SHA 및 검토 팩31파일 불변, 새 점26개 준비·학습 선택0. 사람 간 일치도·독립 정확도 미측정.
CV-6a 수신과 CV-6b 저장된 처리 경로 감사, H-7 날짜 검사 수정은 완료했다. CV-6의 시각적 원인 확정·합의는 미완료다.
원응답은 `outputs/cv_review_response_20261008_v1/`에 비공개 보존했다. 아래 응답0 기록은 수신 이전 이력이다.

- [x] CV-6a. 실제 첫 응답1개/26장 검사·원본 보존·개발 집계·점 자료 준비 완료. 미검토0, 자세18/5/2/1 원문 유지·전역 모호함 별도 기록. 학습/원인 확정/합의 미수행. [수신 보고](docs/CV_FIRST_HUMAN_REVIEW_20261008.md). 선점 `61fe8c6`, 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

## H-6 완료 — 수동 시연에서 최신 입력 보존 (2026-10-08)

예시를 불러오는 동안 바꾼 볼카운트가 늦은 응답에 덮어써지는 오류를 재현해 수정했다.
초기 연결·예시·예측의 지연/역순 응답과 오류는 최신 입력 및 요청의 상태를 덮어쓰지 않는다.
검사: 관련 34 passed(11.96초)·Ruff159경로·JS구문 통과; 새 14시나리오는 수정 전 12실패/2통과 → 수정 후 14통과. 모델 재학습·정확도 측정·공개 Site 배포는 하지 않았다.
사용자는 외출 중이므로 CV6 실제 사람 응답0·미검토26을 유지한다. 검토 화면의 입력을 대신하지 않았다.
다음 독립 단위는 H-7(공개 화면 수신기의 존재하지 않는 날짜 허용 오류)이다.
팀원 새 S 원문·CV6 실제 응답이 오면 각각 I-service2·CV-6으로 재개한다.

- [x] H-6. 수동 시연 예시/추론의 지연·역순 응답 처리 수정. 최신 수동 입력과 요청 상태를 보존하고 이전 응답·오류·버튼 잠금 해제의 간섭을 차단했다. 선점 `080cd62`; 완료는 같은 커밋. 실제 모델 호출/공개 배포와 구분. `[추가되었음 · 2026-10-08 · Codex]`
- [x] H-7. 수신기의 존재하지 않는 생성 날짜 거부 완료. 윤년·세기·월별 일수 검사, 정상 시간대·정밀도·원문 표기 유지. 수정 전 관련58검사 중2실패 → 수정 후 사이트81검사 통과, 미디어SHA·JS구문·체크리스트7검사 통과. 선점 `562fcce`; 완료 `4111eed`. 공개 배포 미수행. `[추가되었음 · 2026-10-08 · Codex]`

## CV27 완료 — 본인이 시작할 사람 검토 (2026-10-08)

CV6의26장 재검토는 본인 영상 파트이며 팀원 모델/API 답변이 선행 조건이 아니다.
한 사람의 응답은 개발 자료로 사용하고, 두 사람 가용성 합의와 CV7 새 영상 독립 평가는 구분한다.
[사용자 순서 안내](docs/CV_HUMAN_REVIEW_START_HERE.md)와 새 한글 UI 팩 `outputs/cv_review_20261008_ko_v1`를 준비했다.
로컬 주소 `http://127.0.0.1:8792/`는 reviewer 폴더만 제공한다. 실제 사람 판정은0·미검토26이다.
원래 부분 가림 이유 필수 규약을 JS/Python 검사가 누락하던 오류를 고치고 오류 프레임 번호를 표시한다.
기존 팩31파일·26이미지·manifest·빈 응답 양식 불변, 응답 schema 동일. 관련75tests 통과.
본인의 새 JSON이 오면 검사→집계→CV26 연결로 진행한다. 팀원 코드/API·M3·기존 라벨은 변경하지 않았다.

- [x] CV-27. 본인용26장 상세 안내·한글 입력 화면·부분 가림 이유 필수 JS/Python 검사·오류 프레임 번호 완료. 새 UI 팩은 기존 이미지/manifest/빈 응답과 동일, 구팩31파일 불변. 브라우저 빈 상태 확인·관련75tests 통과. 실제 응답0/미검토26 유지. [사용 안내](docs/CV_HUMAN_REVIEW_START_HERE.md). 선점 `7c4bd4c`, 완료는 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

## 독립 작업 CV25–26·H-port2–3 완료 — 2026-10-08

사용자 지시로 팀원 응답 없이 가능한 우리 작업 네 단위를 완료했다. 팀원 코드/API·공개 사이트·
기존 M3/JSONL은 고정했다. 소스/결과 `d452b1c`, ZIP 도구 `8fda709`; 마지막 전달 검증은 이 기록과 같은 커밋이다.

- CV25: 같은 14관측·3구에 판단 시작/릴리스 오차를 적용하면 보수적 시간 조건은 CV23/24 모두 0/3이다.
  CV24의 5초 이내 14/14는 처리 속도다. AI 23프레임 확인은 전체 타석/사람 검증이 아니며 시각 주석은 보존했다.
- CV26: 기존 86장→재검토 26장의 원본·키·SHA 연결을 실제 확인했다. 새 규약의 사람 응답0·점0·미검토26.
  학습 표본을 만들지 않았다. 실제 응답을 받으면 준비 도구에 입력한다.
- H-port2: 우리 운영 파일14개·8,986,954bytes를 새 경로로 옮겨 양쪽 CLI 각1회 실행했다.
  전체 JSON/출력 바이트 일치·확률차0. 같은 Windows·기존 환경·예제1개 범위다.
- H-port3: 운영 파일14개+안내/manifest2개를 5,138,558bytes ZIP으로 포장했다. stdlib 검사·CRC·실제 압축 해제
  16파일 바이트/14자료 SHA 대조 통과. 기준 전체 소스 `8fda709bbfc534d0f8d377234f487aacbb640a5f`.
  로컬에만 준비했으며 자동 전송·모델 재학습·공개 배포는 하지 않았다.

검사: CV25–26 전체 CPU **1879 passed, 8 skipped, 2 deselected, 2 warnings / 508.41초**.
그 뒤 H-port3 새21검사 포함 관련45 passed·Ruff158경로 통과. 전체 CPU 결과를 ZIP 도구 추가 뒤 재실행한 것으로 쓰지 않는다.
ZIP 도구 포함 소스 `8fda709`의 Linux/macOS GitHub 전체 검사는 **각1900 passed, 8 skipped, 2 deselected**로 성공했다.
Linux61.18초·경고4개, macOS139.00초·경고2개, Ruff158·JS구문 통과(CI37726869630). 실제 Mac 모델 실행과 구분한다.

[시간 진단](docs/CV_REPLAY_PITCH_DEADLINES_V1.md) · [사람 점 자료](docs/CV_REVIEW_POINT_DATA_V1.md) ·
[운영 모델 이관](docs/HANDOFF_OPERATIONAL_RELOCATION_V1.md) · [전달 ZIP](docs/HANDOFF_OPERATIONAL_BUNDLE_V1.md)

**다음 조건별 재개:** 팀원 새 S 원문→I-service2, 기준/역할 합의→I-0. 우리 쪽은 실제 추가 사람 응답→CV-6,
미열람 영상·독립 라벨러→CV-7, 새 기기에서 받은 묶음 실행 확인이다. CV5a4의 엄격한 전체 타석 조건은 미완료다.
저장 자료의 같은 속도 실험이나 새 학습을 반복해 이 조건을 대신하지 않는다. 자동 `--next`는 조건 충족 전에는 없음(종료1).
Codex 수정 권한 반납. 팀원 응답이나 실제 사람 검토를 만들어 대기를 해제하지 않는다.

## STATUS 비교 후 계획 정리 — 2026-10-07

- [x] I-plan1. 양쪽 STATUS의 계층별 재사용안·현재 병목·대기 조건을 반영해 계획 수정 완료. 완료 이력과 팀원 담당 유지, 비활성 진행 항목을 보류/대기로 정정, 자동 선택기를 H-port1에 맞춤. 선점 `dbbaa40`, 결과는 이 체크리스트와 같은 커밋. 코드·모델 변경 없음. `[추가되었음 · 2026-10-07 · Codex]`

### 판단 근거와 계층별 기본안

우리 [STATUS](STATUS.md)(조사 `050740e`, 문서 `62121c0`)와 I-service1 `d3db232`,
사용자가 제공한 팀원 STATUS(2026-10-07; R=`f7e8f47`, S=`5488c93`)를 비교했다.
팀원 문서는 **팀원 자체 점검 보고**이며 최신 S 코드·서버·번들을 우리 환경에서 재현한 결과가 아니다.
첨부 원문 SHA256: `ea1388544c81fd711549aafbde73bedad87875e1d2a4524e549acddd941ebec0`.
아래는 우리 작업 우선순위와 통합 제안이다. 최종 공용 브랜치·UI/백엔드 정본은 I-0에서 합의한다.
팀원 저장소에는 수정·커밋·푸시하지 않는다. 팀원 측 변경은 제안·전달 자료 요청으로만 남기며 이 계획이 수정 권한을 부여하지 않는다.

| 계층 | 보존·재사용할 것 | 바뀌는 작업 방향과 확인 조건 |
|---|---|---|
| 경기 상태·기록 | 팀원 S의 StatsAPI/기록 재생 경로를 우선 후보로 검토 | MLB 상태를 OCR로 다시 만드는 일을 필수 경로에서 제외. 피드 시각과 방송 시각은 달라 투구 키·영상 동기화 검증은 유지 |
| 결과 모델·추천 | 팀원 G0/ARM-B 서빙을 통합 후보로, 우리 운영 모델·평가를 비교 기준으로 보존 | 양쪽 NLL/CE·CI의 과제/클래스/기간/단위가 달라 숫자만으로 승자를 고르지 않음. G15 연구 개선을 S 배포 모델 성능으로 옮기지 않음. 새 8종 학습을 우리가 중복 수행하지 않음 |
| 미트·영상 | 우리 IntentEstimate, 사람 검토, PTS/SHA, 기권·공개 시점 제어 | CV24 속도 개선은 보존하되 확정 미트 0. 추가 동일 표본 속도 반복보다 CV6 실제 재검토·판독 품질을 우선. M3 일치도와 새 루프 속도를 합쳐 실시간 정확도로 발표하지 않음 |
| 화면 | 우리 홈·브랜딩·영상 비교·검증 리포트와 팀원 S 경기/타석 화면의 장점 | 두 화면을 병렬로 계속 확장하지 않고 한 타석으로 연결 경계부터 검증. 최종 화면 기술/정본은 아직 미결정. R 사건 분석은 S에 이미 연결된 기능으로 취급하지 않음 |
| 계약·품질·배포 | 우리 키/단위/해시·테스트·CI, 팀원 출처/미지원 표시 | S의 누락 의존성·T7 경로·미푸시 버전은 전달/기동 확인 조건. 우리 쪽 이식·회귀 검사를 재사용하며 팀원 코드를 여기서 고치지 않음 |

**완료 이력의 의미:** 주석·OCR·운영 모델 검증·CV1–24·M3·시연 화면은 재사용 자산으로 남는다.
실험을 마친 것과 채택 모델/운영 서비스를 완성한 것은 다르다. 기존 완료를 취소하거나,
보류 항목을 완료로 바꾸어 진척률을 높이지 않는다. 양쪽 모두 추천 개선은 아직 입증되지 않았다.

### 2026-10-07 실행 계획 이력 (현재 완료·대기 상태는 상단과 각 항목)

1. **H-port1 완료:** 48개 소스 파일과 해시·외부 31항목·실행 안내를 ZIP으로 고정하고 압축 해제 환경에서 검사했다. [이관 안내](docs/handoff/README.md) · [전달 식별자](docs/handoff/delivery_v1.json).
2. **I-0 / I-5 자료 확인:** S의 기준 revision·공급 방식·지원 경기와 표시할 필드를 합의한다.
   기존 849843 watch/reveal 3구 수신과 새 service-game-v2 수신을 구분한다.
3. **I-service2:** 실제 원문 검사 → 로컬 한 타석 추천/실제 결과/미지원/공개 순서 확인.
   셋업 형태가 미합의면 미트는 null로 남기고 나머지 필드부터 연결한다. 모델 재학습은 선행 조건이 아니다.
4. **I-run1 → I-release1:** 합의한 버전을 새 실행 환경에서 재현하고 실제 사용자 경로를 측정한 뒤 공개 연결을 판단한다.
   로컬 저장 응답 재생 성공을 live 검증으로 세지 않는다.

- [x] H-port1. 우리 최소 소스 이관 ZIP 완료. 기준 `441f5e5`, 소스48개·외부목록31항목(실파일29SHA), 148,178bytes. 압축 해제 사본 표준 라이브러리 검사·합성 S 검사 통과, Python213 passed/1 skipped·Node64 passed. 영상/가중치/사람응답/비공개 비교자료 제외, 공개/비공개와 별도 전달 조건 명시. [안내](docs/handoff/README.md) · [파일별 SHA](docs/handoff/source_manifest_v1.json) · [검증 기록](docs/handoff/delivery_v1.json). 전체검사 결과는 인계 기록 참조. 선점 `e1f3dab`; 완료 기록은 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-07 · Codex]`
- [!] I-run1. **I-0 합의·번들 수신·I-service2 뒤:** 합의한 서비스 소스/가중치/데이터 manifest·lock·경로 설정으로 독립 환경의 기동/health/한 경기 응답/웹 검사를 수행한다. 기록 재생만 확인되면 그 범위로 기록한다. 팀원 경로·의존성 수리는 요청 사항이며 우리 담당으로 일방 전환하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-07 · Codex]`
- [!] I-release1. **I-run1 완료·실기기 접근 가능 뒤:** 합의한 사용자 경로(S 채택 시 새 S 경로)에서 추천 계산/피드 수신/영상 공개 시점·지연·지원률·미지원/오류 복구와 표시 수치 의미를 대조한다. 맥북/아이폰 등 실제 기기·롤백 확인, 영상 공유 범위·배포 권한 확인 후 공개 연결. 기존 지연 0 스냅샷과 옛 /api/live 리허설을 혼용하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-07 · Codex]`

**2026-10-07 당시 자동 다음 작업 없음:** H-port1 직후의 기록이다. 10/8 사용자 지시로 상단 독립 CV 작업을 재개했으며 현재 순서는 상단을 따른다. 새 S 원문은 I-service2, 실제 사람 응답은 CV-6으로 연결한다.

**당분간 추가하지 않을 개발:** 새 모델 대규모 학습, 같은 CV 표본 속도 반복, 다중 방송 OCR 확대,
별도 공용 백엔드 재작성, 감독 교체/타자 책임의 수치화, KBO 확장. 필요한 근거·합의가 생기면 해당 항목을 재개한다.
S 선택 비중은 사건확률이 아니며 S 위치는 과거 투구 분포의 근사다. 실제 모델/API에 없는 값은 예시 또는 미지원으로 둔다.

## 최신 S 응답 통합 준비 — 2026-10-07

- [x] I-service1. S STATUS 기반 로컬 service-game-v2 검사·정규화, 사전/후 표시 분리, 합성 3상태 예제 완료 (`d3db232`). 원본 SHA·투구 키·선택 비중 보존, 미트 원자료 해석 보류. 전체 CPU 1812 passed·8 skipped·2 deselected, 기존 사이트 검사와 원격 Linux/macOS CI 통과. [안내](docs/SERVICE_GAME_V2_INTEGRATION.md). 실제 S 호환성·라이브 완료와 구분. `[추가되었음 · 2026-10-07 · Codex]`
- [x] I-service2. **2026-10-09 실제 S 원문 수신·로컬 한 타석 연결 완료.** 262투구/71타석의 키·경계·날짜·셋업 계약을 새 `teammate_export_20261009_v1`로 대조하고 비공개 화면의 추천/실제/셋업 공개 순서를 연결했다. ready246/unsupported16/missing0; missing은 실제 사례 미수신. 셋업27추정/12불가/null223. 경기 후 as-of 재생·정책 미검증 범위를 유지하며 I-0/I-run1/I-release1은 미완료다. [기록](docs/SERVICE_GAME_V2_RECEIVED_20261009.md). 선점 `2b11c06`; 완료는 같은 커밋. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-07 · Codex]`

## 통합 비교용 저장소 현황 — 2026-10-07

- [x] I-status1. `feature/intent-v0@050740e`의 데이터·모델·서빙·화면·배포를 읽고 루트 [STATUS.md](STATUS.md)에 요청한 9개 목차로 정리. 실제 CLI/API·공개 브라우저·웹 검사 확인, 운영 번들 누락과 우리 브랜치 간 미통합 OCR 변경 명시. 코드/모델/팀원 저장소/배포 변경 없음. 결과 문서는 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-07 · Codex]`

## 공개 홈·최종 서비스 콘셉트 — 사용자 추가 요청

- [x] E-site6. 홈 영상 4투구·23.83초 하이라이트로 확장, 대표 미트 정지 장면 구분·출처/원본 보존·77 Node 검증·브라우저 재생 확인·Site v9 배포. 기존 오프라인 v4 보존, 향후 패키지 허용 목록 갱신. `[추가되었음 · 2026-10-06 · Codex]`

- [x] E-site1. 독립 발표 사이트39구 탐색·공개 전후·기권·M3 리포트·프로젝트 방향, 반응형 확인·공개 배포·소스 보존 완료. (`c211425`) `[추가되었음 · 2026-10-05 · Codex]`
- [x] E-site2. pitcheezy.com A 2건/TXT 2건 등록, 도메인·SSL active 및 HTTPS 200·홈 화면 확인 완료(2026-10-06). `[추가되었음 · 2026-10-05 · Codex]`

- [x] E-site3. 야구 홈·별도 서비스·실제 관측 리포트, 공개 승인 MLB 리플레이, 경기명·날짜·선수명, 네 상황 예시·네 분석 단계 구현·모바일 검수·배포·계약 명세 보존. 실제 모델 연결은 미완료. (`6ea6260`) `[추가되었음 · 2026-10-05 · Codex]`

- [x] E-site4. 우리 사이트의 한 타석 로컬 응답 수신·검증·공개 후 CV 대조 도구 준비, 34 Node 회귀 검사·브라우저 검수·배포. 실제 응답 미수신. (`e3bc870`) `[추가되었음 · 2026-10-05 · Codex]`
- [!] E-site5. **Song 최종 확인·실기기 기록 대기.** **부분 완료(2026-10-06):** 실제 첫 타석 응답 3구와 공식 영상 3/3구 연결·투구 키/playId/해시 대조. 영상 종료 공개·전환 초기화·3구 별도 판독 정지 장면·미검토 AI x 표시, Site v8 배포 및 오프라인 v4 준비. 사이트 77 Node·체크리스트 4 passed·Windows 1280/390px 검수. 우리 연결 완료, Song 최종 확인/실기기 리허설 대기. 연속 중계·실시간 자동 동기화는 미완료. 팀원 개발 제외. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-05 · Codex]`

- [x] E-demo4. (`9c39c46`) 재생 복구·정상/기권 바로가기·브라우저 정상 폭/390px 검수·Site v4 배포·비공개 오프라인 v3·발표 안내 완료. 40 Node·4 checklist·원본/ZIP 검사 통과. 실제 기기/낭독/Song 리허설은 E-demo2로 유지. `[추가되었음 · 2026-10-06 · Codex]`

[사이트 실행·검증·유지보수](docs/INTENT_DEMO_SITE.md). Song UI 리허설 완료나 제구 오차 검증으로 처리하지 않는다.

## 10/6 시연 — 발표 종료 보고, 세부 확인 대기

10/6 당시 발표 종료 후 CV 개발을 재개했다. 현재는 STATUS 비교 후 통합을 우선하며 E-demo2/E-site5는 실제 확인 기록을 기다린다.

- [x] E-demo1. 39구 기대 화면 대조표·60–90초 대본·5개 Q&A·장표 수치 대조·재현 절차 준비. 실제 UI는 미확인. (`3cfc014`) `[추가되었음 · 2026-10-05 · Codex]`
- [!] E-demo2. **실제 확인 기록 대기; 발표를 다시 준비하는 항목이 아님.** 사용자/Song의 실제 화면 6항목 결과와 낭독 시간을 받아 기록 — 실제 세부 증거 대기(발표 종료 보고와 구분). 〔모델: Opus 5〕 `[추가되었음 · 2026-10-05 · Codex]`

- [x] E-demo3. 우리 사이트·기존 장표·비공개 대표 비교자료의 오프라인 ZIP v2 및 2분 목표 발표 안내 준비. 파일·해시·ZIP·링크 검증 완료, file URL 직접 실행·실기기·낭독 시간 미확인. (`3e58e92`) `[추가되었음 · 2026-10-05 · Codex]`

[화면 대조표](docs/INTENT_V0_DEMO_SCREEN_CHECK.md) · [발표 대본](docs/INTENT_V0_DEMO_SCRIPT.md). 39고유키/27좌표/12기권, 창·스캔 키 집합 일치, 로컬 schema 39/39. 기존 intent 회귀 검사 251 passed, 체크리스트 가드 4 passed. PPTX·보고서·문구 일치, 고정 자료 186개 SHA 불변, 리허설은 링크 한 줄만 추가. 실제 화면 연결은 완료 처리하지 않았다. 10/6 당시에는 발표 후 CV-5a를 재개했다. 현재 실행 순서는 이 문서 상단을 따른다.


## CV-5a의 10/6 진행 기록 — 현재 우선순위는 문서 상단

[순차 실행·실제 호출](docs/CV_OBSERVATION_LOOP_V1.md) 이후 CV-5a4 재개. [화면 경계 근거](docs/CV_PA_BOUNDARY_REVIEW_V1.md)와 10개 후보 시각을 저장했다. 연속 전체 검토·타석 경계 확정·실행 계획 고정은 별도 유지한다. CV-11을 완료했으며 이전 사용량 하한은 해제됐다. 아래 10/5 상태는 역사 기록이다.

### 이전 상태 — 2026-10-05

[실제 AI 관측 호출 기록](docs/CV_OBSERVATION_SESSION_V1.md): 원본 프레임 3장 실제 판독(2기권·1좌표), 요청→응답 경과 기록 완료. 자동 전체 타석 리플레이·정확도·실시간 가용률은 미완료다. [클립 시간축 대조](docs/CV_CLIP_CLOCK_AUDIT_V1.md)에서 3개 시각 중 1개의 한 프레임 불일치를 확인했다. 다음은 디코딩 프레임 PTS 대응을 검증한 뒤 실제 모델 어댑터 자동 실행을 연결하는 것이다. 최종 전체 검사 834 passed / 5 skipped / 2 deselected, Ruff 100경로. 수정 권한 반납. 최신 사용자 지시에 따라 잔여 사용량 하한은 10%다.

## 사람 검토 상태 구분 — 2026-10-05

기존 M3 사람 검토는 86장 완료(84표시·2기권)다. 이 수치는 기존 인계 기록에 이미 포함된 결과다. 아래의 CV-6 “응답 0 / 미검토 26”은 새 관측 규약으로 하는 추가 재검토만 뜻한다. 기존 사람 라벨이 없는 상태가 아니다. 10/6 시연을 위해 기존 86장을 다시 검토할 필요는 없다.

10/5 당시 구현 계획은 CV-5a였다(현재 순서 아님): 개발용 연속 한 타석의 영상·출처 확인, 실제 관측기 연결, 입력 도착·출력 발행 시각 측정 순서다. 저장 주석 변환기 intent.run을 자동 검출기로 취급하지 않는다. CV-6 추가 도구 개발은 마치고 실제 추가 응답이 있을 때 재개한다. CV-6 재검토는 CV-5a의 필수 선행 조건이 아니다. 기존 M3·시연 산출물 및 팀원 영역은 고정한다.


이 파일은 **"지금 무엇이 남았는가"의 단일 목록**이다. 배경·근거는 아래 문서에 있고,
여기에는 상태와 다음 행동만 둔다.

- 프로젝트 지침·확정 결과: [AGENTS.md](AGENTS.md)
- MLB P0 실행 범위: [docs/MLB_P0.md](docs/MLB_P0.md)
- 도구 교대 기록: [docs/MLB_P0_HANDOFF.md](docs/MLB_P0_HANDOFF.md)
- 실행 경로·재개·이관: [docs/MAINTENANCE.md](docs/MAINTENANCE.md)

## 이 파일을 갱신하는 규칙

1. **새로 생긴 작업을 추가하면 항목 끝에 `[추가되었음 · YYYY-MM-DD · 도구]`를 반드시 붙인다.**
   원래 계획에 있던 항목에는 붙이지 않는다. 그래야 "처음부터 있던 일"과 "하다 보니 생긴 일"이 구분된다.
2. 완료 항목은 지우지 말고 `[x]`로 바꾸고 `(커밋 해시)`를 적는다. 기록을 삭제해 진척을 좋아 보이게 하지 않는다.
3. 재현하지 못한 결과를 완료로 적지 않는다. 막혔으면 `[!]`와 막힌 이유를 적는다.
4. 한 작업 단위를 커밋·푸시할 때마다 이 파일도 같은 커밋에 포함한다.
5. 미완료 항목 **첫 줄 끝**의 `〔모델: Opus 5〕` / `〔모델: Fable 5.1〕` 태그는 **Claude Code가 그 항목을 수행할 때
   쓸 모델**이다. 새 항목을 추가하면 태그도 같이 붙인다(기본: 주석·문서·집계·결정 = Opus 5,
   코드·학습·데이터 정합·디버깅·병합 = Fable 5.1). Codex에는 적용되지 않는다.
6. `〔담당: 팀원〕` 태그가 붙은 절·항목은 다른 팀원이 수행한다. Claude/Codex는 착수하지 않고
   `scripts/checklist_model.py --next`도 건너뛴다. 모델 태그는 붙이지 않는다. 산출물이 오면
   I절(팀원 산출물 통합)의 항목으로 받아 검증한다.

기호: `[ ]` 미착수 · `[~]` 진행 중 · `[x]` 완료 · `[!]` 막힘/보류

## CV 후속 작업 — 2026-10-05

- [x] CV-25. 저장 CV23/24 투구별 발행 시간 평가 완료. 입력 14개·3구 유지, 양쪽 시각 오차 적용 0/3·명목 시작 보조 0→1/3·확정 미트 0. AI 23프레임 경계 확인은 별도 진단이며 기존 timing 불변. 새 29tests·기존 checklist7 통과. [보고](docs/CV_REPLAY_PITCH_DEADLINES_V1.md). 완료는 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`
- [x] CV-26. 새 관측 규약 사람 점 자료 연결 준비 완료. CV12 86장→CV6 26장 출처·키·SHA 결속, 검토자별 점/기권/불확실 보존·AI/구형 라벨 대체 차단. 실제 CLI 응답0·점0·미검토26; 학습미수행. 새20tests·관련53tests 통과. [안내](docs/CV_REVIEW_POINT_DATA_V1.md). 완료는 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`
- [x] H-port2. 우리 운영 모델 명명14파일·8,986,954bytes의 경로 이관 실행 확인. 기존 CLI 양쪽1회·전체 JSON/출력 바이트 동일·확률최대차0·원본/사본/소스 불변. 같은 Windows·기존환경·예제1개 범위. [보고](docs/HANDOFF_OPERATIONAL_RELOCATION_V1.md). 완료는 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`
- [x] H-port3. 운영14파일+안내/manifest2개 ZIP 생성·실제 압축 해제 검증 완료. 5,138,558bytes, 소스 `8fda709`, SHA `d51fa7671ec8d753dbc263469a872d2fba9cb327ffcc183861e9b495f9614d4e`. 새21tests·관련45passed·Ruff158. 전체16파일/14자료 SHA·H-port2 실행 소스27개·H-port1 원본 ZIP 불변. [안내](docs/HANDOFF_OPERATIONAL_BUNDLE_V1.md) · [전달 기록](docs/handoff/operational_bundle_delivery_v1.json). 전송/공개/새 기기 실행은 하지 않았다. 완료는 이 체크리스트와 같은 커밋. `[추가되었음 · 2026-10-08 · Codex]`

- [x] CV-24. 정확한PTS탐색·실패보존·구형기록호환. 같은14장JPEG/MD5불변·추출중앙2.185→0.848초. 모델루프1회 14/14≤5초·확정미트0 유지. 관련140tests·전체CPU통과. [실측](docs/CV_EXACT_FRAME_SEEK_V1.md). 사전등록 `d1e2c4f`, 결과는같은커밋. `[추가되었음 · 2026-10-07 · Codex]`
- [x] CV-23. 연속 방송66.81675초·4,005장 누락0 검증 및14개고정시각실행. 수락14·오류0·확정미트0·5초이내5/14. 구간누락 CLI·보고서표본수문구 수정, 관련58tests·전체검사통과. [실측](docs/CV_BROADCAST_INTERVAL_REPLAY_V1.md). 사전등록 `e5a1c58`, 결과는같은커밋. `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-22. 사전등록 `cf355ec` 후 같은10장·새프로세스3회/30관측 완료. 5초이내29/30·전체10개성공실행2/3·오류0·출력동일30/30·확정미트0. 고유10장 개발반복. [결과](docs/CV_LOCAL_REPEATABILITY_V1.md). `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-21. 기기별 새계획 CLI·비덮어쓰기 receipt·입력변경 거절 완료. 관련99tests·실제10cutoff 준비통과·모델/decoder호출0·기존계획불변·Ruff142. [사용법](docs/CV_LOCAL_MACHINE_PLAN_V1.md). (`cf355ec`). `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-20. 사전등록 `3fdef88` 후 동일10시각1회 실행. 발행중앙4.227초·최대4.703초·≤5초10/10·오류0·확정미트0. 출력10/10동일, 준비19.266초·명령전체73.227초. Windows1588tests/Ruff140·Linux/mac CI성공. [결과](docs/CV_CLOCK_CACHE_V1.md). `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-19. 원격Linux/macOS17실패 원인인 정상venv실행파일 링크 거절 수정. 원래venv유지·대상/설정SHA·linkretarget검증, 데이터symlink보호유지. Windows36tests/Ruff통과. 수정 `5b108f2`의 실제Linux/macOS CI 각각1542 passed·6 skipped·2 deselected, 기존180초 이내 성공. [기록](docs/CV_VENV_LAUNCHER_FIX.md). 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-18. 사전등록 `7d75ed0` 후 준비20.015초·전체명령76.115초·warm루프51.547초. 발행중앙4.9845초·≤5초5/10, 10수락·오류0·확정미트0·출력3방식10/10동일·worker정상종료. 모든입력5초/정확도/live는 미충족. [결과](docs/CV_LOCAL_READY_V1.md). `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-17. 동일10시각 단일 worker/engine 재사용9회·10수락·오류0·종료확인. 총72.766초(vs233.562), 발행중앙26.664초·≤5초0/10 유지. 확정미트0·채택보류. 사전 등록 `0f292da`, 결과 `2a560a7`. [결과](docs/CV_LOCAL_WORKER_V1.md). `[추가되었음 · 2026-10-07 · Codex]`

- [x] CV-14. 기존 10시각 로컬 shadow 연결 완료: 10수락·4단일/2복수/4후보없음·오류0, 확정미트0. 233.562초·발행≤5초0/10, 모델 초기화 중앙15.041초. 입력10SHA/코드/응답 결속 통과·179tests/Ruff. 사전 등록 `1d8fffc`, 결과 `7f5aaa1`. [결과](docs/CV_LOCAL_OBSERVER_V1.md). `[추가되었음 · 2026-10-07 · Codex]`
- [x] CV-15. 기존84점·양방향 경기 분리·3seed 고정 실험 완료. 6학습/252예측 오류0, 후보 기준0/6 실패→채택하지 않음. 합친 median59.59–63.51px vs 학습평균50.97px. 사전 등록 `de45beb`, 결과 `0f292da`. [결과](docs/CV_LOCAL_POINT_MODEL_V1.md). `[추가되었음 · 2026-10-07 · Codex]`
- [x] CV-16. 기존84장 전체 원본·사람점·3seed 모델/두 기준선 로컬 비교 화면 생성. 입력/결과SHA 결속·28synthetic tests·브라우저 필터/원본/이동 확인. 새 사람 라벨/공개 사이트 아님. [사용법](docs/CV_LOCAL_POINT_REVIEW_V1.md). `[추가되었음 · 2026-10-07 · Codex]`
- [x] CV-13. 2모델·2입력 GPU 및 crop CPU 고정 비교 완료: 1,118회 처리 오류0, 첫회 86장씩 품질 집계. SSD 후보0/86, Faster 전체16/86·crop5/86; 기존 점 차이 중앙151.93/64.61px. 범용 모델 채택 보류. 사전 등록 `8ac36f7`, 결과 `f6cc67e`. [결과](docs/CV_LOCAL_DETECTOR_RESULTS_V1.md). `[추가되었음 · 2026-10-07 · Codex]`
- [x] CV-12. 로컬 후보2개·선택 의존성·86/86원본SHA/라벨 정합 확인,84기준점/2과거기권의 한계 분리. 입력/기준점 분리·엄격 검출/평가·고정 비교 규약 준비. 전체1331 passed·5 skipped·2 deselected. 준비 커밋 `8ac36f7`, 실제86장 실행은 CV-13. [기록](docs/CV_LOCAL_DETECTOR_V1.md). `[추가되었음 · 2026-10-06 · Codex]`

- [x] CV-11. 구간별 지연·주 모델 일치 검증, 고정10장 Opus/Haiku 각10수락·형식오류0. 총234.500/267.437초, 발행≤5초 각0/10. 좌표7쌍 차이 중앙249.9px(정확도 아님), 새 모델 운영 적용 보류. 전체1119 passed·5 skipped·2 deselected. 사전 등록 `61ddfcb`, 결과 (`63d662b`). [결과](docs/CV_LATENCY_MODEL_COMPARISON_V1.md). `[추가되었음 · 2026-10-06 · Codex]`

- [x] CV-10. 구조화 v1 API 비호환 실패3건 보존, 호환 수정 v2 3/3수락·좌표3/기권0/오류0, 발행≤5초 0/3. 실패 선정 개발 진단, 91tests/Ruff. [기록](docs/CV_STRUCTURED_OUTPUT_V1.md). `f14bc1d`. `[추가되었음 · 2026-10-06 · Codex]`

- [x] CV-9. 고정 10시각 지연 진단 완료: 4좌표·3기권·3계약 오류, 발행≤5초 0/10, 총 160.938초. 명시 모델·계획 분모·실패 보존·74 tests/Ruff. 원본 이미지/제공자 세션 로그/기기별 실행 계획은 Git 제외. [보고서](docs/CV_BOUNDED_LATENCY_V1.md). 사전 등록 `ac5fc7f`. `[추가되었음 · 2026-10-06 · Codex]`

- [x] CV-8. 다음 작업 선택기가 CV처럼 두 글자인 작업군을 누락하던 오류 수정. 이전 F-4a 선택 대신 CV-5a4 선택, 회귀 검사 6 passed·Ruff 통과. (`74aa473`) `[추가되었음 · 2026-10-06 · Codex]`

사용자 승인(2026-10-06): 발표 후 우리 CV 개발 재개. 팀원 영역 제외, 잔여 사용량 하한 해제. 기존 시연·M3 결과는 고정한다.
작업 브랜치는 `feature/intent-v0`, **CV24까지 완료 후 Codex가 수정 권한을 반납**했다(2026-10-07). CV-6 도구는 준비 완료다. 실제 사람 응답은 대기한다. CV-5는 `5934b01`로 완료했다. CV-1–4 통합은 `436ef80`로 완료했다. 하위 작업은 별도
임시 폴더에서 작성하고 root만 이 작업 폴더에 통합한다. 팀원 저장소는 읽기 전용이다.
아래는 10/6 시연 산출물과 분리한 개발 진단이다. M3·기존 JSONL·발표 자료는 고정한다.
이 브랜치의 아래쪽 OCR 이력은 분기 당시 기록이며 새 CV 작업의 다음 행동으로 쓰지 않는다.

- [x] CV-1. 영상 근거·결과 사용 가능 시점 감사와 미래 정보 차단 검사. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-05 · Codex]` (`436ef80`)
- [x] CV-2. 기존 평가 자료의 기권 정의·좌표 민감도 개발 진단. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-05 · Codex]` (`436ef80`)
- [x] CV-3. 입력·코드 해시에 묶인 로컬 작업 재개·실패·처리시간 기록 기반. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-05 · Codex]` (`436ef80`)
- [x] CV-4. 다음 미트 판독 기준·독립 평가 규약 및 담당별 후속 정리. 〔모델: Opus 5〕 `[추가되었음 · 2026-10-05 · Codex]` (`436ef80`)


결과: [CV 후속 보고서](docs/CV_FOLLOWUP_2026-10-05.md), [관측 규약](docs/CV_OBSERVATION_PROTOCOL_V1.md).
기존 자료 186개 SHA 불변. 실제 진단 배치 2건 성공·resume 재실행 0건. 최종 전체 CPU 검사 834 passed / 5 skipped / 2 deselected; lint/format 100경로 통과.

- [x] CV-5. 기존 849845 PA43의 두 압축 투구 창 122장 출처 검증·익명화·시점 제한 공급 준비. 전체 타석/관측기/실시간 계측은 미완료이며 CV-5a로 분리. (`5934b01`) `[추가되었음 · 2026-10-05 · Codex]`
      [실행 기록](docs/CV_PREFIX_REPLAY_V1.md): cutoff 620/621/634/636/639초 → 누적 0/10/61/76/122장, 역행 거절. 관련 108 tests 통과.
- [x] CV-5a1. 원본/클립 디코딩 해시·실제 PTS 대응 도구와 새 캡처 재현 완료: 3,298장 고유 매칭·누락 1구간·185초 미래 프레임 거절. [보고서](docs/CV_CLIP_CLOCK_V1.md). (`183ec0c`) `[추가되었음 · 2026-10-06 · Codex]`
- [x] CV-5a2. 원본 PTS 이전 프레임 추출·새 영수증·v2 관측 요청 연결, 실제 세 응답(1표시·2기권) 수신 완료. [보고서](docs/CV_MAPPED_OBSERVATION_V1.md). 정확도·실시간 전체 루프는 미검증. (`2b4e15b`) `[추가되었음 · 2026-10-06 · Codex]`
- [x] CV-5a3. 고정 시각 순차 실행기·Claude 실제 호출·적체/검증 후 발행 기록 완료. 첫 2/3 및 형식 수정 후 새 3/3 수락. [보고서](docs/CV_OBSERVATION_LOOP_V1.md). 전체 타석/실시간 정확도는 미검증. (`dd16262`) `[추가되었음 · 2026-10-06 · Codex]`
- [!] CV-5a4. **전체 구간 확인 완료(2026-10-09) — 엄격한 전체 타석 조건은 미충족이며 이 원본으로는 충족 불가.** 빈 프레임 없는 144.160683~230.013117초를 0.5초 표본 174장·전 프레임 차이 스캔·하드 컷 9개 인접 프레임·기준 미만 구간 18장으로 확인했다. PA1 6구(스트라이드 이후)·스윙·1루 플레이·복귀·160.68초 점수판 1아웃, PA2 3구·헛스윙 삼진·227.56초 2아웃·퇴장은 모두 자료 안에 있다. 그러나 중계가 168.068~180.230초 더그아웃만 비추고 180.246733초 중앙 카메라 컷 시 Iglesias는 이미 타석(피치클록 :11)이라 물리적 입장은 원본에 없다. PA1 6구 세트는 그래픽에 가려지고 1루 포구·아웃 신호는 0.5초 표본에서 식별 불가, PA2 2구는 컷 직후 0.27초 안에 투구 동작이 시작돼 중앙 카메라 투구 전 프레임이 사실상 없다. 연속 재생·사람 검토·독립 평가·timing 재계측 아님. 리플레이 시작 정의(중계 사건 vs 직전 타석 완료)는 소유자 결정 대기. [기록](docs/CV_PA2_DENSE_REVIEW_V1.md) · [근거](docs/results/cv_followup_20261009/pa2_dense_review_v1.json). 원본 주석 고정. [시간 진단](docs/CV_REPLAY_PITCH_DEADLINES_V1.md). 〔모델: Opus 5〕 `[추가되었음 · 2026-10-06 · Codex]`
      2026-10-09 워크플로 = 태그 모델: Opus 5(`claude-opus-5`) 검토 에이전트 1명이 시트 40장을 보고 구조화 기록, 반박 에이전트 2명(경계 57건 중 11건·연속성 27건 중 18건의 세부 타일 판독 정정, 핵심 결론 반박 없음). Fable 5.1 세션이 41장 전부와 확대 크롭을 직접 보고 정정을 반영해 통합했다.
      CV23에서 새 연속 방송구간66.81675초·4,005장·고정14개실행을 완료했다. 물리적입장/전체연속시각검토를확인한것은아니므로본항목의완료로대체하지않는다.
- [!] CV-5a. **통합 우선으로 보류; CV-5a4와 판독 품질 기준을 확인한 뒤 재개.** 실제 관측기와 입력 도착·출력 발행 시각 계측을 연결해 연속 영상의 한 타석 개발 리플레이 검증. 기존 두 창만으로 전체 타석·실시간 완료를 주장하지 않는다. 〔모델: Fable 5.1〕 `[추가되었음 · 2026-10-05 · Codex]`
      2026-10-09: CV-5a4 결과, 물리적 타자 입장은 이 중계 원본에 없다. 리플레이 시작 정의(첫 중앙 카메라 프레임 180.246733초로 표기 vs 직전 타석 완료)를 소유자가 정한 뒤 재개한다. PA2 2구는 중앙 카메라 투구 전 프레임이 사실상 없음을 계획에 반영해야 한다.
      2026-10-05 Claude 세션의 독립 계산(커밋된 도구·보고서 없음, **재현 필요**): 후보 클립과 원본의 디코딩 프레임 해시(ffmpeg framemd5)를 대조했다.
      - 클립 표시 프레임 3,298장이 모두 원본 프레임 번호 `클립 pts + 10490`과 일치했다(시간 단위 1001/60000). 해시가 모두 서로 달라 정적 장면 중복으로 맞은 것이 아니다.
      - 클립 0 = 원본 175.008167초, 클립 끝 = 원본 230.0298초다. 클립 pts 3297 한 장이 빠져 있다(끝 부분 B-프레임 절단으로 추정, 미확인).
      - 185↔10 불일치는 seek가 '요청 시각 이후 첫 프레임'을 고르는데 클립 0이 175.008167초라서 생긴다. 원본 185.0015초 프레임은 클립 9.9933초 위치다.
      - 해시 원본: 로컬 `outputs/cv_followup_20261005/clip_timeline_claude_check/`(git 제외). 원본 창 명령은 `-ss 172 -t 62 -i URL -copyts`다(`-t`를 출력 옵션으로 두면 0프레임). 클립 명령은 `-i CLIP`이다. 둘 다 `-map 0:v:0 -f framemd5`.
      - 시작한 Fable 단위 1 실행은 파일을 쓰기 전에 사용자 결정(Codex 인계)으로 중단했다.
- [!] CV-6. **첫 사람 재검토26장과 저장 처리 경로 감사 완료. 시각적 원인 확정·합의 판정은 미완료.** 2026-10-08 실제 응답1개·26 marked/full, 미검토0. 자세 필드의 모호함을 보존한 단일 검토자 개발 자료이며 AI 기권 오류26건으로 확정하지 않는다. 가용성 합의에는 별도 독립 판단이 필요하다. 기존 M3 86장 검토는 보존한다. 아래 응답0은 과거 준비 기록이다. 〔모델: Opus 5〕 `[추가되었음 · 2026-10-05 · Codex]`
      2026-10-05: [검토 자료 준비](docs/CV_REVIEW_QUEUE_V1.md) 완료 (`9652644`). 두 경기 각 13장, 완료 응답 0 / 미검토 26. 원본 SHA·파일 연결·빈 양식 검증, 새 테스트 20건 통과. 실제 사람 판정/오류율은 미측정이다.
      [클릭 입력·JSON 저장/재개 UI](docs/CV_REVIEW_UI_V1.md) 준비 완료 (`a46f346`). 새 로컬 패키지 `outputs/cv_review_20261005_ui_v1`, 실제 응답은 여전히 0건이다.
      [응답 검증·집계 도구](docs/CV_REVIEW_SUMMARY_V1.md) 완료 (`15c6798`). 실제 실행은 제출 0 / 미검토 26의 대기 보고서이며 사람 검토 완료가 아니다.
- [!] CV-7. **새 영상·독립 검토자 확보 대기.** 미열람 연속 영상·독립 사람 라벨러·평가 manifest 확보 후 새 검증. 기존 4경기와 이미 처리한 849849는 새 unseen 자료로 쓰지 않는다. 〔모델: Opus 5〕 `[추가되었음 · 2026-10-05 · Codex]`

확률·프로필·정책 평가·경기 피드·서비스/API·관전 UI는 팀원 담당이다.
실제 독립 사람 검토, 미열람 영상의 새 판독 성능, 전체 영상 처리량은 이번 코드 작성만으로
완료 처리하지 않는다. F-4i 이름 OCR 보류는 유지한다.

## 과거 M3 전달 요청 보존 — 2026-10-03 요청 / 2026-10-11 병합

[10/5 제출 요청](docs/INTENT_V0_OCT05_DELIVERABLES.md)은 당시의 CV-M3-1005 요청을 보존한다.
이후 2026-10-04 사람 표시를 반영한 [M3 평가](docs/INTENT_V0_M3_EVAL.md)와
[시연 리허설 안내](docs/INTENT_V0_DEMO_REHEARSAL.md)가 현재 결과·범위 기준이다.
과거 요청의 미체크 목록을 새 미완료 작업이나 새 재측정 지시로 취급하지 않는다.
자료 작성과 실제 전달·수신 확인은 구별한다.

## 분야별 기록 요약 — 각 행의 확인 날짜 기준

현재 작업·선점은 이 파일 상단과 우리 상황판을 따른다. 아래 과거 검사·장비·모델 수치는 날짜가 다른 증거이며 현재 실행 상태가 아니다.

| 항목 | 값 | 갱신 |
|---|---|---|
| 브랜치 | 정본 main. 현재 연구 단위 `claude/cv-mitt-temporal-1025`(CV-32~34 완료); 다른 단위의 브랜치·선점은 상단과 우리 board 참조; 기존 작업 폴더·원본 브랜치 보존 | 2026-10-25 |
| 검토 시작 기준 | PR #42 병합 main `48ec406`; 이후 완료 단위는 상단과 우리 board의 고정 커밋 참조 | 2026-10-18 |
| 파일 수정 권한 | 반납 — Claude Opus 5.5 CV-32~34 완료(`claude/cv-mitt-temporal-1025`, PR #67 초안). CV-35 사용자 응답·CV-36 사람 결정 대기. 과거 모델 근거 미확인·WS-human1·공동 시험·Song 후속 입력 조건 유지 | 2026-10-25 |
| Mac 실기기 I-device2 | 환경 확인 완료·v5 영상 ZIP 전송 대기. 재생/결과 공개/투구 전환/타석 전환/미트 가로 표시 모두 미실행 | 2026-10-11 |
| 저장 공간 운영 | 내부 용량 부족 시 연결된 외장 SSD의 실제 경로·여유를 확인해 사용. 확인 장치 `D:` T7 Shield (exFAT), 여유 3,723.1 GiB; 재확인·이관 원칙은 [MAINTENANCE](docs/MAINTENANCE.md). 기존 데이터 이동 없음 | 2026-10-04 |
| 중계 시각 주석 | **297 확인 / 25 확인 불가 / 0 미검토** — 전 경기 322구 검토 완료. 완전 타석 2~4·6~15·18~19·21·23~28·30~32·34·36~38·40~46·49~51·53~55·57~63·65~69·71·74~79·81. 불가 목록·반이닝 집계·리드 분포는 [전 경기 요약](docs/MLB_BROADCAST_TIMING.md). 규약 v2, 수동 시각 | 2026-09-27 |
| 점수판 평가셋 | timing 322 / 리뷰 297(292구 10필드 confirmed, PA 8/1·16/1·33/1·41/1·44/1 partial) / 라벨 충돌 0 / 판단 화면 불가 25 / 미검토 0 | 2026-09-27 |
| 점수판 OCR | **현행 v2 유지**. A-15 새 17구: 새 판단 프레임 17구의 필드 정답·기권·오답: v1 119·51·0 / v2 119·51·0 / v3 117·53·0 / v4 119·51·0. unavailable 2구는 예측 대상이 아니다. 공유 280행 변화 0·반복 297행 일치·음성 거짓 판독 0. 이전 오판독은 [알려진 목록](docs/results/mlb_p0/game_747139_scoreboard_known_misreads.json)에 유지. v3 무회귀·v4 사전 등록 기준 실패 유지. 747139는 전 경기 개발 자료; 새 버전 독립 검증은 새 미검토 영상 필요 | 2026-09-27 |
| 전체 검사 (Windows CPU) | `fafc9c6`: 2225passed/8skipped/2deselected,419.00초,기존 Pillow 경고2개,Ruff167. 압축 해제 소스458passed/1skipped·Node112 | 2026-10-10 |
| 원격 검사 (Linux/mac CPU) | `fafc9c6`: 각2225passed/8skipped/2deselected, Linux72.40초/macOS145.68초(CI38056890856). 새 브라우저 Chromium/WebKit 각13passed(CI38056890881). 실제 Mac/아이폰 검수 아님 | 2026-10-10 |
| 정책 효용 | **미입증** — delta −0.0862 runs/100, 95% CI [−0.4046, +0.2304] | 2026-09-21 |
| Claude 모델 배정 | 항목 태그 참조 — `uv run --frozen python scripts/checklist_model.py --next` | 2026-09-22 |
| 담당 구분 | **C·D = 팀원(외부)**, 그 외 = Claude/Codex. 통합 검증은 I절 | 2026-09-22 |
| 팀원 레포 | SongRoute/pitcheezy `main` 9d09694 대조 완료, 804f523(문서만 3커밋) 재확인 — 요약 [docs/TEAMMATE_PITCHEEZY_2026-09-22.md](docs/TEAMMATE_PITCHEEZY_2026-09-22.md). 우리 쪽 참조 0건, 별도 병렬 트랙. **지원 투수는 `/metadata` 확정 전 잠정**, 요청 문안 §9 말미(미전송) | 2026-09-22 |

---

## 이전 진행 순서 — 2026-09-22 기록 (현재 실행 순서는 문서 상단)

C(새 8종 확률 모델)·D(투수 프로필/추천 지원 범위)는 다른 팀원이 맡는다. Claude/Codex는 아래 순서로
진행하고, 한 번에 한 도구만 파일을 수정하는 규칙은 그대로다.

| 순서 | 단위 | 완료 기준 | 모델 |
|---|---|---|---|
| 1 | A-4 ✅ A-5 ✅ | 1회말 주석 완료 2026-09-23 — 누적 30구(A-v2 후 28 확인 + PA 1/6 가림 + PA 5/5 카메라 늦은 복귀로 unavailable), 완전 타석 2·3·4·6·7 | Opus 5 |
| 2 | B-1 → B-5 | ✅ 2026-09-22 완료(timing 20구·리뷰 19구). 주석이 늘면 리뷰 행을 같이 추가하고 `64 review-check` → `64 build`로 재생성(B-6) | Fable 5.1 |
| 3 | A-w ✅ | 2026-09-23 완료 — 페이지 뷰 대신 `scripts/65_grab_broadcast_frames.py`(ffmpeg 프레임 + 점수판 확대 몽타주) | Fable 5.1 |
| 4 | A-6 ✅ (PA 8–10, 2회초) ↔ F-3 ✅ v0/v1/v2 | 2026-09-24 2회초 완료(12구). OCR은 주석이 늘 때마다 `66 predict/score` 재실행(F-3a) | Opus 5 / Fable 5.1 |
| 5 | A-7 ✅ (PA 11–26, 2회말~3회) | 2026-09-25 완료 — 3회 종료 누적 101구(95 확인·6 불가) | Opus 5 |
| 5a | A-8 ✅ (PA 27–32, 4회) → F-3c ✅ | 2026-09-25 A-8 완료(120구), F-3c v3 사전 등록·평가(무회귀 기준 실패, 기록 보존) | Opus 5 / Fable 5.1 |
| 5b | A-9 ✅ (PA 33–40, 5회) → F-3d ✅ | 2026-09-25 A-9 완료(153구), F-3d v4 사전 등록 커밋(v4 성능 주장 없음) | Opus 5 / Fable 5.1 |
| 5c | A-10 ✅ (PA 41–49, 6회) | 2026-09-25 완료(187구). v4 첫 blind 채점 → 사전 등록 기준 (1) 실패로 기록 | Opus 5 |
| 5d | A-11 ✅ (PA 50–55, 7회 18구) | 2026-09-26 완료(205구) | Opus 5 |
| 5e | A-12 ✅ (8회초 PA 56–65, 44구) → A-13 ✅ (8회말 PA 66–73, 33구) | 2026-09-26 8회 완료(282구). 8회는 77구라 반이닝씩 나눴다. OCR 새 버전(F-3e)은 해당 주석 전에 사전 등록해야 그 프레임이 blind | Opus 5 |
| 5f | A-14 ✅ (9회초 21구) → A-15 ✅ (9회말 19구) | 2026-09-27 전 경기 322구 검토·요약 완료(297 확인·25 불가). 순서 6의 A-z·A-y 준비 완료; 실제 재검토 응답 대기 | Opus 5 |
| 6 | E-1, H-1, A-y, A-z, A-v | 사이사이 독립 단위 | 태그 참조 |
| 7 | I-0 → I-1 → I-2 | 팀원 C·D 산출물 인터페이스 합의·수신·통합 검증 | Opus 5 / Fable 5.1 |
| ※ | I-0·I-5·I-6·G-3 | I-0·I-5는 **준비 완료, 동료 답변 대기**(TEAMMATE 문서 §9). 첫 통합 완료 기준 = 한 타석 영상 → 투구 전 상태 → 동료 서비스 → 확률 표시 | Opus 5 / Fable 5.1 |
| 8 | G-1 | I-1·I-2 통과 후에만 | Fable 5.1 |

반이닝별 규모(manifest 기준): 1회초 PA 1–3(12구) · 1회말 PA 4–7(18구) · 2회초 PA 8–10(12구) ·
2회말 PA 11–15(20구) · 3회초 PA 16–19(10구) · 3회말 PA 20–26(29구) · … · 9회말 PA 79–82(19구), 총 322구.

## A. 중계 시각 주석 — 전 경기 검토·A-z 완료, A-y 후속 남음

수동 시각 주석이다. 자동 OCR·자동 동기화가 아니다. feed UTC를 재생 초로 변환·보간하지 않는다.

- [x] A-0. 도구·검증 CLI 구현, PA 1–2 주석 (`d5920d0`)
- [x] A-1. **PA 3** (Vientos) 3구 주석 — 11 확인 / 1 확인 불가 / 310 미검토 (`17133e1`)
- [x] A-2. **PA 4** (Harris II) 2구 주석 — 13 확인 / 1 확인 불가 / 308 미검토 (`4d14634`)
- [x] A-3. **PA 5** (Albies) 6구 주석 — 19 확인 / 1 확인 불가 / 302 미검토 (`d80d358`)
- [x] A-4. **PA 6** (Ozuna, 6구, 1회말 1아웃, 주자 1루) 주석 — 25 확인 / 1 확인 불가 / 296 미검토, 완전 타석 2~6 (`9ff2181`)
      2026-09-23 Workflow: Opus 5 주석 에이전트(`claude-opus-5`) 1명이 ffmpeg 프레임(`65` 방식)으로 6구를 찍고, 투구마다 시각 렌즈·점수판/식별
      렌즈 검증 에이전트 2명이 반박을 시도(12건 모두 반박 없음, high). Fable 5.1 세션이 판단·릴리스 프레임 12장을 다시 뽑아 확인한 뒤 통합.
      판단 482.5 / 534.5 / 556.2 / 577.3 / 616.2 / 671.0 s, 릴리스 483.78 / 535.55 / 557.33 / 578.35 / 617.25 / 672.28 s(±0.15).
      특이: 476–480 s "JULY 27" 회상 그래픽 뒤 1구 판단 창이 약 2.5초뿐, 4구 전 572–576 s는 3루측 광각, 4구→5구 사이 601–603 s 견제(P:12 유지).
      리뷰 파일에도 6구 필드별 판독 행 추가(B-6 이행). 다음 한 단위는 **A-5 PA 7**.
- [x] A-5. **PA 7** (Olson, 4구, 2아웃 주자 1루) 주석 → **1회말 완료**(누적 30구, 완전 타석 2~7) (`9271231`) `[추가되었음 · 2026-09-22 · Claude]`
      Workflow: Opus 5 주석 에이전트 + 투구별 2렌즈 반박 검증(4구 릴리스는 시각 렌즈가 763.43→763.31로 반박·수리 후 재검증 통과, 총 10판정 반박 없음).
      판단 700.2 / 718.5 / 740.0 / 762.0 s, 릴리스 701.23 / 719.63 / 740.83 / 763.31 s(±0.15). Fable 5.1 세션이 8프레임을 다시 뽑아 확인.
      관찰: 삼진 뒤 bug는 3아웃을 표시하지 않고 767 s에 "END 1" 카드로 바뀜; 732 s 타 카메라 광각·736 s 덕아웃·755 s 회상 등 컷어웨이 다수.
      리뷰 파일에 4구 필드별 판독 행 추가. 이 4구도 "동작 직전 마지막 set 프레임" 규약이라 리드 0.8~1.3 s(A-v2 대상).
      A-4와 같은 방식(Workflow: Opus 5 주석 에이전트 + 투구별 2렌즈 반박 검증) 또는 Opus 5 세션 직접 수행. 리뷰 행 동반(B-6).
      (2026-09-22) 공통 시연 경기(I-5)가 정해지기 전에는 한 타석 단위로만 진행하고 범위를 크게 늘리지 않는다.
- [x] A-6. **2회초 PA 8–10** (12구) 주석 (`0bb442e`, `15c67cf`; 규약 v2 재검토는 A-v3) `[추가되었음 · 2026-09-22 · Claude]`
      (2026-09-23 착수) Workflow: PA별 Opus 5 주석 에이전트 3명 병렬 + 투구별 2렌즈 반박 검증, Fable 5.1 세션 통합.
      **PA 8·9 통합** (`0bb442e`, 2026-09-24): PA 8(Nimmo 4구) 판단 777.5 / 792.0 / 809.5 / 825.0, 릴리스 780.45 / 795.4 / 811.25 /
      828.65 s; PA 9(Alonso 2구) 판단 854.4 / 867.8, 릴리스 855.68 / 869.03 s(±0.15). 12판정 모두 반박 없음(high). **PA 8/1은 이닝 교대 직후
      라인스코어 그래픽(TOP 2ND R H E)이 count bug를 대체**해 판독 partial(이닝·초말·득점만, 카운트·아웃·주자 null) — 리뷰 파일에 그대로 기록,
      평가셋에서는 해당 필드만 제외. 이닝 휴식은 영상에서 수 초로 편집됨(771~774 s END 1ST, 777 s 블랙 컷).
      **PA 10 통합 → A-6 완료** (`15c67cf`): Martinez 6구 판단 901.35 / 916.1 / 936.8 / 956.8 / 972.8 / 995.1, 릴리스 902.62 / 917.35 /
      938.18 / 958.13 / 973.95 / 996.45 s(±0.15). 1·3·4·6구는 첫 판정에서 "이미 레그 킥 시작" 반박 → 수리 후 재검증 통과, 12판정 최종 반박 없음.
      워크플로가 한도로 세 번 끊겨 `resumeFromRunId`로 이어갔다. 2회초 12구 완료, 누적 42구(40 확인 + 2 확인 불가).
- [x] A-v3. PA 8~10의 판단 프레임을 규약 v2로 재검토 (`692bd07`) `[추가되었음 · 2026-09-24 · Claude]`
      Workflow(PA별 Opus 5 에이전트 + 투구별 검증 1명, 한도로 한 번 재개): 12구 중 9구 이동(PA 8/4 −0.75, PA 9 −5.25/−2.5,
      PA 10 −4.75/−2.25/−3.75/−4.5/−0.25/−0.75 s), 3구 유지(PA 8/1~3 — 직전 프레임이 블랙 전환·타자 클로즈업). 12판정 반박 없음.
      세션이 이동한 판단 프레임 8장을 다시 뽑아 확인. 리뷰 판독값도 새 프레임에서 갱신(충돌 0). 이제 PA 1~10 전부 규약 v2.
      리드 최소 1.15 / 중앙값 4.4 / 최대 10.05 s, 1.5 s 미만 2구(PA 2/2 1.15, PA 10/5 1.40). OCR v1 held-out 29구 오답 0·25 정답·4 기권.
- [x] A-7. **2회말~3회 PA 11–26** (59구) 주석 → 3회 종료(누적 101구). `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Opus 5〕
      PA 11~15 20구(A-7a)와 PA 16~19 10구(A-7b)는 검토·병합 완료. PA 20~26 29구는 2026-09-25 Claude Code가 완료(아래).
      (2026-09-25 Claude Code 착수) PA 20~26 후보 → 직접 검증 → 타석별 병합 → OCR 재채점, 타석 단위 커밋.
      (`5f69f26`) **PA 22·23·25 7구 병합**(6 확인 + PA 22/1 unavailable). Opus 5 주석 → 두 검증 렌즈 모두 통과 → 세션이 투구별
      리뷰 시트(경계·연속성·bug·릴리스 크롭)를 직접 확인. PA 22/1은 홈런 리플레이→SNY 로고 와이프 아래에서 이미 레그 킥, 세 시각 null;
      세션이 note의 릴리스 서술(2197.70~.80→약 2197.50)과 비판단 프레임 observed를 정정. PA 23/1은 반박→수리로 릴리스 2255.95·동작 시작 2254.72.
      PA 20~26 증거는 `game_747139_timing_verification_pa20_26.json`.
      (`ca76e65`) **PA 21·24·26 15구 병합**(모두 annotated). 반박→수리: 21/1·21/4·26/2 동작 시작, 21/3 d2077.25→2071.75(홈 뒤 라이브 항공 샷, 타자가 화면 하단에 들어온 첫 격자; 한계적),
      26/1 d2584.25→2586.00(타자가 장갑을 보며 투수를 향하지 않음, PA 3/1 선례). 세션 정정: 24/4 d2460.50→2460.25(양발이 러버에 놓인 첫 격자;
      이후 창 안의 회전은 모든 렌즈가 허용했으므로 같은 기준 적용, 엄격한 대안 2460.50은 note에 기록), 26/4 note의 타자 배너 시각(2674.00→2675.50).
      (`2887a52`) **PA 20 7구 병합 → A-7 완료**(6 확인 + 20/6 unavailable: 클로즈업 중 이미 와인드업, 1985.00 복귀 때 레그 킥).
      20/1·2·3·5·7은 릴리스가 팔 스윙 단계로 약 0.2초 이르게 적혀 시각 렌즈가 반박→수리(세션 확대 크롭으로 새 값 확인).
      세션 정정: 20/4 d1949.25→**1947.75**(24/4와 같은 '양발이 러버에 놓인 첫 격자' 기준; 워크플로의 엄격한 자세 기준 대안은 note),
      20/6 note 릴리스 서술(→약 1986.00)과 비판단 프레임 observed/readability null. PA 20~26 합계 27 확인·2 불가, 세션 정정 5행(20/4·20/6·22/1·24/4·26/4).
      판단 기준 해석(러버 도착 경계)은 A-y의 다른 검토자 확인 대상으로 남긴다.
      한 타석씩 후보 작성 → 직접 프레임 검증 → `scripts/69` 병합한다. 규약 v2·필드별 직접 판독·불가/미검증 구분은 [재개 지시문](docs/CODEX_RESUME_PROMPT.md) §1 참조.
- [x] A-7a. **PA 11~15 후보 20구 직접 검증·병합** (`06abd0c`) `[추가되었음 · 2026-09-24 · Codex]`
      Claude의 미검증 후보(양 렌즈 2구·한 렌즈 3구·미검증 15구)를 실제 JPEG/확대 프레임으로 다시 확인했다. 과거 통과 문구는 검증 증거로 사용하지 않았다.
      PA 11/1 d1034→1038: 중간 흰 점수판 전환으로 연속성이 깨졌고 1038에 전 필드가 읽힘(partial→readable).
      릴리스 6구 소폭 정정: 11/2 1060.80→1060.85, 11/5 1121.53→1121.58, 12/1 1162.45→1162.50,
      12/2 1177.50→1177.55, 15/1 1468.44→1468.50, 15/2 1490.82→1490.90 s. 모두 수동 오차 ±0.15 s 유지.
      PA 14/1 리드 15.65 s·14/5 9.15 s는 표본 프레임에서 견제/스텝오프/컷어웨이를 찾지 못해 유지. 실제 타자 표시는 PA 14 Urshela, PA 15 Arcia.
      69 dry-run 및 PA별 write로 timing·리뷰·검증·평가셋·조인표 갱신, 후보 rows는 비웠다. 이전 후보는 `1573268`, 새 검증 근거는
      `game_747139_timing_verification_pa11_15.json`. 연속성은 선택 프레임 검사(일부 최대 2.25초 간격)이며 연속 재생·사람 간 일치도 검증은 아니다.
- [x] A-7b. **3회초 PA 16~19 10구 직접 검증·병합** (`eb1cdf6`) `[추가되었음 · 2026-09-24 · Codex]`
      8구 시각 확인 + 2구 unavailable. PA 16/2는 1605.50 타자 클로즈업 → 1605.75 이미 레그 킥,
      PA 17/1은 1654.25까지 리플레이 → 로고 가림 → 1655.00 이미 팔로스루여서 세 시각을 null로 남겼다.
      PA 16/1 d1590.50은 디졸브가 끝난 라이브/라인스코어: 이닝·초말·득점만 직접 판독, 나머지 6필드 null.
      PA 18/1 d1706.25와 PA 19/4 d1817.50은 라이브 광각을 사용. PA 19/3은 타임 이후 새 판단 창 d1803.00.
      누적 68 확인·4 불가·250 미검토. 후보 rows 0, 직접 본 프레임·릴리스 브래킷·해시는 `game_747139_timing_verification_pa16_19.json`.
      PA 16은 세션 직접 확인+별도 에이전트 교차검토, PA 17~19는 에이전트 확인+세션 이미지 점검. 최대 1초 간격의 표본 검토이며 사람 간 일치도 검증은 아니다.
      다음 PA 20이 실제 병합돼도 단위시험이 충돌하지 않도록 합성 테스트 fixture를 분리했고, 모든 후보 파일을 중복·ID 검사 대상으로 바꿨다.
- [x] A-12. **8회초 PA 56–65 (44구)** 주석 → 누적 249구. `[추가되었음 · 2026-09-26 · Claude]` 〔모델: Opus 5〕
      (`4c6e3c7`) **완료**: 39 확인 + 56/1·56/2·56/8·64/2·64/3 unavailable(투수 클로즈업·덕아웃 컷어웨이·SNY 로고가 동작 시작까지 투수를 가림; 세션이 경계 프레임 확대로 확인).
      워크플로 v4 세 개(PA 56–58, 59–61, 62–65), 투구별 예상 상태 지원 추가(PA 62 1구 뒤 주자 2루 진루). 투수 교체 3회(Jimenez·Raisel Iglesias·Bummer, P:0부터).
      경계: 59/1 5784.25(보수적 대안 5785.25), 61/3 매우 높은 상공 라이브 광각 6077.50(대안 6080.00), 63/3 반투명 SNY 윤곽만 남은 6369.25(대안 6369.50), 59/3 홈 뒤 상단 광각.
      짧은 리드 60/1 1.35 s. 58/2·58/3은 실제 릴리스가 기록보다 약 0.05 s 뒤(±0.15 안). 8회초 리드 최소 1.35 / 중앙값 4.30 / 최대 7.55 s.
      OCR(`scripts/70 --reference 10250bc`): v1~v3 초말 오판독 15건을 [알려진 오판독 목록](docs/results/mlb_p0/game_747139_scoreboard_known_misreads.json)에 원인과 함께 기록(판독기 불변). v4는 39구 초말 전부 정답.
      디스크: 사용자가 2026-09-26 정리해 C: 여유 약 35 GB(outputs/frames 11.4 GB 캐시 중 검증 기록·평가셋 참조 2.6 GB, 나머지는 재추출 가능한 중간 프레임).
- [x] A-15. **9회말 PA 79–82 (19구)** 주석 → 전 경기 322구 검토 완료 (`a708d48`). `[추가되었음 · 2026-09-26 · Claude]`
      (2026-09-26~27 Codex) 17 확인 + 80/7·82/4 unavailable. 기존 PA79~80 후보 8구를 직접 검증하고 PA81~82 11구를 새로 주석·검증했다.
      80/6 릴리스 8291.05→8291.00 정정. 80/7(8303.30 클로즈업→.35 이미 레그 리프트)·82/4(8570.50 클로즈업→.75 이미 앞발 들림)의 시각/observed는 null.
      81/3·4는 홈 뒤 라이브 광각(러버 접촉 해상도 한계 기록), 81/3부터 주자 2루 직접 판독. 82/1~3 릴리스 후보 미세 수리, 82/5는 마지막 컷어웨이 뒤 d8598.75/r8604.65.
      PA별 69 dry/write 및 63/64/68 통과, 기존 303행 보존, 후보 rows 0. [검증 기록](docs/results/mlb_p0/game_747139_timing_verification_pa79_82.json).
      새 판단 프레임 17구의 필드 정답·기권·오답: v1 119·51·0 / v2 119·51·0 / v3 117·53·0 / v4 119·51·0. unavailable 2구는 예측 대상이 아니다. 공유 행 변화 0·반복 일치. 최종 검사 결과는 상태 표. 전 경기 리드 최소 1.10 / 중앙값 4.55 / 최대 15.65초, 짧은 리드 7구.
      9/26 Claude 미검증 인계 기록은 `4643702`에 보존. 시각·점수판을 에이전트와 병합 세션이 직접 확인했으며 별도 사람 간 일치도 측정은 아니다.
- [x] A-14. **9회초 PA 74–78 (21구)** 주석 → 누적 303구. `[추가되었음 · 2026-09-26 · Claude]` 〔모델: Opus 5〕
      (2026-09-26, `8b99385`) **완료**: 21구 전부 확인(unavailable 0). 워크플로 v4 두 그룹(PA 74–76, 77–78; Opus 5 주석, Fable 5.1 렌즈) → 세션(Fable 5.1) 몽타주·연속성·릴리스·경계 확인.
      세션 정정 1건: 76/1(Lindor 투런) 판단 프레임 8000.00 → 7796.50. 7796.25는 Marte 클로즈업, 7796.50부터 홈 뒤 상단 라이브 광각에 투수 정지·타자 타석·점수판 판독 가능(규약 v2 '다른 카메라의 라이브 광각 허용', 선례 61/3·49/6·18/1). 이 축척에서 발은 안 보여 7800.00(중계 카메라 첫 프레임)을 보수적 대안으로 note에 기록.
      1라운드 타이밍 렌즈 반박 7건(77/1~77/4·78/2·78/3·78/7)은 전부 동작 시작이 0.25~0.5 s 늦게 적힌 것 → 수리 라운드에서 동작 시작만 정정(77/1 릴리스 7866.00→7866.05, 78/2 7975.20→7975.15는 허용 오차 안 미세 조정), 2라운드 두 렌즈 통과.
      경계: 74/1 SNY 와이프 잔광(7622.75 판독 불가 → 7623.00, 리드 8.40 s), 77/4 SNY 로고(7916.00 → 7916.25), 78/3 창 0.75 s(리드 1.55 s, 덕아웃 컷어웨이가 투구 직전까지), 78/8 릴리스 브래킷 약함(8093.90 유지, 대안 8093.85). PA 77·78은 점수판에 타자 줄이 한 번도 안 떠 신원은 유니폼·타석 방향·P: 순서로 확인(78은 7967~7970 s SNY 'EDDY ALVAREZ' 그래픽). [검증 기록](docs/results/mlb_p0/game_747139_timing_verification_pa74_78.json).
      9회초 리드 최소 1.55 / 중앙값 5.05 / 최대 8.40 s. OCR(`scripts/70 --reference 7990c47`): v1~v4 모두 오답 0, 초말 ▲9는 v1~v4 전부 정답(8회초 ▲ 오판독은 이닝 '8' 열 문제였음; 필드 v4 147·63·0, v3 146·64·0, v1·v2 143·67·0), 공유 행 변화 0.
- [x] A-13. **8회말 PA 66–73 (33구)** 주석 → 누적 282구. `[추가되었음 · 2026-09-26 · Claude]` 〔모델: Opus 5〕
      (2026-09-26, `3394363`) **완료**: 29 확인 + 70/3·72/1·72/5·73/4 unavailable(분할 화면 그래픽·관중 컷어웨이·투수 클로즈업·SNY 로고가 동작 시작까지 투수를 가림; 73/4는 릴리스도 로고 뒤라 전부 null).
      세션 모델이 Fable 5.1로 바뀐 첫 단위: 주석은 Opus 5 워크플로 v4, 검증 렌즈는 Fable 5.1, 세션(Fable 5.1)이 몽타주·연속성·릴리스·경계 확대를 직접 확인(검증 기록의 `verification.by`에 명시).
      이전 세션 종료로 워크플로 3개가 끊겨 저널을 복사해 재개했고, 재개 직후 주석 에이전트 6개가 사용자의 GitHub 질문을 임무로 오인해 빈 결과를 냈다 → 그 결과는 저널에서 지우고 다시 돌렸다.
      66/1·66/2는 워크플로의 타이밍 렌즈가 구조화 결과를 내지 못해 세션이 타이밍 렌즈만 따로 재실행(둘 다 반박 없음; 기록 `source` 필드).
      경계: 66/1 점수판 재생성(6623.00 이닝 화살표·카운트 미표시), 66/2 0.05 s 창(6641.75 양발 고정 → 6641.80 발 들림, 리드 1.20 s 짧은 리드 목록), 71/2 로고 뒤 7267.25(대안 7267.50), 69/3·73/2 릴리스 수리 후 확인. [검증 기록](docs/results/mlb_p0/game_747139_timing_verification_pa66_73.json).
      8회말 리드 최소 1.20 / 중앙값 4.40 / 최대 10.15 s. OCR(`scripts/70 --reference 2bf9a26`): 새 29구 모든 버전 오답 0(초말 ▼ 전부 정답, 알려진 오판독 추가 없음).
      GitHub: 사용자 요청으로 저장소를 public으로 전환(전환 전 추적 파일·전체 이력에서 토큰·자격증명 패턴 0건 확인). 9/25부터 결제 문제로 시작조차 못 하던 Actions validation이 다시 실행되어 ubuntu·macOS 모두 성공.
      A-11과 같은 절차. 탐색 시작은 PA 55/5 릴리스 5299.25 s 이후('END 7', 5320 s 부근이 8회초). 44구라 워크플로를 PA 3~4개씩 나누고 동시 에이전트를 줄인다(원격 MP4 읽기 시간 초과).
      Mets가 점수를 내는 반이닝이라 점수·주자 변화가 많다: 투구마다 manifest 사전 상태를 인자로 주고, 이닝 '8'·새 점수 숫자는 템플릿이 없어 OCR 기권이 정상.
- [x] A-11. **7회 PA 50–55 (18구: 7회초 PA 50–52 9구, 7회말 PA 53–55 9구)** 주석 → 누적 205구. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Opus 5〕
      (`19ca8d2`) **완료**: 17 확인 + 52/2 unavailable(불펜 투수 Ottavino 컷어웨이가 5011.15까지, 첫 라이브 5011.20에 이미 레그 킥). 워크플로 v4 두 개 → 두 렌즈 → 세션 확인.
      경계: 50/1·53/1은 점수판이 다시 그려지는 중인 직전 격자(조건 4 실패), 55/1~55/3은 Ottavino가 공을 받은 뒤 러버 위에서 발을 고쳐 딛는 동작이 끝난 첫 격자(수리 후 두 렌즈 통과),
      52/3은 0.5 s 짧은 창(5023.00~5023.25 양발 고정 확인), 55/4는 전체 화면 그래픽이 사라진 첫 격자. 52/4는 실제 릴리스가 기록보다 약 0.05 s 뒤(±0.15 안, 유지).
      7회 리드 최소 1.70 / 중앙값 4.90 / 최대 7.37 s, 새 짧은 리드 없음. OCR(`scripts/70 --reference f7e0a1e`): 새 17구 모든 버전 오답 0.
      A-10과 같은 절차. 탐색 시작은 PA 49/6 릴리스 4848.00 s 이후('END 6', 4900 s 부근이 7회초). 투수·타자 이름과 투구 수(P:N)는 manifest와 공개 MLB people API로 인자를 만든다(scratch build_args 방식).
      F-3e(OCR v5)를 진행할 거면 그 사전 등록 커밋을 A-11 주석 전에 둬야 7회 프레임이 blind가 된다. 이닝 '7'·점수 '3'은 템플릿이 없어 기권이 정상.
- [x] A-10. **6회 PA 41–49 (34구: 6회초 PA 41–43 7구, 6회말 PA 44–49 27구)** 주석 → 누적 187구. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Opus 5〕
      (`1c7f2bc`) **완료**: 32 확인 + 47/1·48/5 unavailable(47/1 경기장 전경 컷어웨이 중 레그 킥, 48/5 투수 클로즈업에서 복귀할 때 이미 레그 킥). 41/1·44/1은 이닝 요약 그래픽이라 partial.
      워크플로 v4 세 개(PA 41–43, 44–47, 48–49) → 두 렌즈 → 세션이 압축 몽타주·연속성 띠·릴리스 확대·경계 확대(타자·발)를 직접 확인. PA 49 주석자는 원격 MP4 읽기 시간 초과로 미완료 → 수리 에이전트 행을 두 렌즈가 통과, 세션 확인.
      경계 판단: 42/2 타자 허리 숙인 채 배트 흔들기 → 4072.25(대안 4071.00 기록), 43/1 4115.50(대안 4115.75), 46/5 타자 다시 파고듦 → 4351.00, 49/6 홈 뒤 상단 광각 라이브 샷 4841.75, 46/1·46/3 러버 진입 양발 기준.
      세션 확인: 릴리스 +0.05 s에 포수 옆에 보이는 흰 점은 날아가는 공(망원 원근; 49/6에서 0.40 s 뒤 홈 도착) — 릴리스 규약과 일관. Megill 몇 구는 실제 릴리스가 기록보다 0.05 s 뒤(±0.15 안, 유지).
      짧은 리드: 49/4 1.10 s(새 최소). 6회 리드 최소 1.10 / 중앙값 4.30 / 최대 9.20 s. PA 47은 scripts/69 --write의 재생성 단계가 한 번 실패해 재생성·후보 정리를 다시 실행(merge_history note).
      OCR(`scripts/70 --reference 139275e`): v4 사전 등록 판정 **실패**(기준 (1): 42/1 아웃 오판독, v1~v4 공통) — [판정 기록](docs/results/mlb_p0/game_747139_scoreboard_ocr_v4_acceptance.json). 42/1은 [알려진 오판독 목록](docs/results/mlb_p0/game_747139_scoreboard_known_misreads.json)에 v1~v4로 기록.
      A-9와 같은 절차(워크플로 v4, `scripts/71` 시트, `scripts/69` 병합, `scripts/70` OCR 갱신). 탐색 시작은 PA 40/2 릴리스 3967.00 s 이후('END 5').
      이 판단 프레임은 v4(F-3d)의 첫 blind 평가 재료이므로 OCR 결과를 보고 주석을 바꾸지 않는다. 6회 이닝 숫자 '6'은 템플릿이 없어 이닝 기권이 정상.
      병합 뒤 v4 판정: 사전 등록 파일의 `acceptance_criterion_for_A10` (1)~(5)를 그대로 적용한다. (1)~(3)은 `ocr_reports.new_rows_acceptance(evalset, v4 새 행 블록, {'v2': .., 'v3': ..}, negatives_totals=.., wrong_reads=ocr_reports.wrong_reads(evalset, v4 전체 예측))`, (4)는 provenance의 previous_prediction_comparison·반복 검사와 v1~v3 템플릿·음성 파일 바이트 비교, (5)는 `scripts/66 predict --templates docs/results/mlb_p0/sny_digit_templates_v4.json --diagnostics <경로> --no-grab`. v4가 실패해도 기준·옵션을 고치지 않고 결과를 기록한다(오판독은 알려진 오판독 목록에 v4로 올림).
- [x] A-9. **5회 PA 33–40 (33구: 5회초 PA 33–37 22구, 5회말 PA 38–40 11구)** 주석 → 누적 153구. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Opus 5〕
      A-8과 같은 절차(워크플로 v4, `scripts/71` 시트, `scripts/69` 병합, `scripts/70` OCR 갱신). 탐색 시작은 PA 32/1 릴리스 3137.85 s 이후('END 4').
      이 판단 프레임은 OCR v3·v4(F-3d)의 첫 blind 평가 재료이므로 OCR 결과를 보고 주석을 바꾸지 않는다.
      (`862ec01`) **5회말 PA 38~40 11구 병합**: 9 확인 + 39/2·39/4 unavailable(1루 쪽 카메라로 타자가 화면 밖인 채 투구 시작).
      세션은 `scripts/71` 시트와 압축 몽타주로 전 투구 확인; 불가 두 행에 남아 있던 릴리스·observed를 null로 정정. 39/3 리드 1.35 s(짧은 리드 목록 추가).
      OCR(`scripts/70`): 새 9구 모든 버전 오답 0, 이닝 '5'는 템플릿 없어 기권. PA 38/4 볼 '3'(카운트 폰트)은 v1·v2 기권, v3 정답 — v3 첫 blind 성공 1건(표본 1).
      (`2947a46`) **5회초 PA 33~37 22구 병합 → A-9 완료**: 20 확인 + 33/3·35/1 unavailable(33/3 투수 손 클로즈업에서 복귀할 때 이미 레그 킥, 35/1 로고 와이프 아래서 동작 시작).
      반박 3라운드 뒤에도 남은 35/2는 세션이 러버 옆 자유발 신발 가장자리를 픽셀로 재서(3408.50까지 안쪽으로 이동, 3408.75 정지) 판단 3408.50→3408.75로 정정. 불가 두 행의 observed·판독성은 null로 정정.
      33/1은 'TOP 5TH' 라인스코어 partial(이닝·점수만), 34/3은 상단 광각 라이브 샷(타자가 3414.25까지 몸을 숙여 파고듦 → 3414.50). 새 짧은 리드 없음(5회 최소 39/3 1.35 s).
      OCR(`scripts/70 --reference 862ec01`): 새 20구에서 **첫 실제 오판독** 34/3 초말 Top→Bot(v1·v2·v3 공통). 라벨이 맞고 판독기가 틀렸다(`evalset_3314.50.jpg`에 ▲5).
      판독 버전은 고치지 않고 `game_747139_scoreboard_known_misreads.json`에 원인·증거를 기록했다. `scripts/70`은 목록의 오판독을 NOTE로 출력하고, 목록 밖 오판독과 더는 일어나지 않는 목록 항목에서 실패한다(시험 추가).
      5회 29구 전체(필드 정답·기권·오답): v1·v2 246·37·1, v3 248·35·1. 이닝 '5' 템플릿이 없어 이닝은 전부 기권.
- [x] A-8. **4회 PA 27–32 (19구: 4회초 PA 27–29 11구, 4회말 PA 30–32 8구)** 주석 → 누적 120구. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Opus 5〕
      (2026-09-25 Claude Code 착수) 타석별 Opus 5 주석·두 렌즈 검증 → 세션 직접 확인 → 병합 → OCR v1·v2 재채점, 타석 단위 커밋.
      주석 워크플로 v4: A-7 교훈(릴리스는 던지는 팔이 앞으로 뻗은 프레임, 러버 도착은 양발, 타자는 투수를 향함)을 주석·검증 지시문에 넣었다.
      (`a0388de`) **PA 28·30·31·32 10구 병합**(모두 annotated). 반박→수리: 28/1·28/2 동작 시작, 30/2 d2994.00→2994.25(타자가 장갑을 봄)·r3001.44.
      세션 정정: 30/3 r3018.55→3018.60, 31/4 r3108.10→3108.13(세밀 크롭에서 팔이 아직 머리 뒤). 30/1은 bug 전환이 끝나는 첫 격자, 32/1은 타자가 다 파고든 뒤.
      OCR은 새 `scripts/70`으로 v1·v2를 한 번에 재채점: 새 10구 오답 0, 이닝 숫자 4만 기권.
      (`a0388de`) 위 PA 28·30~32 커밋. (`119f0c3`) **PA 27·29 9구 병합 → A-8 완료**(8 확인 + 29/6 unavailable: 투수 손 클로즈업 뒤 이미 레그 킥).
      반박→수리: 27/2 동작 2759.99·r2761.28, 29/2·29/3 동작 시작, 29/3 r2865.55, 29/5 d2899.75(타자가 파고듦)·r2904.67, 29/7 r2948.15.
      세션 정정: 29/6 워크플로 행이 unavailable인데 릴리스 시각·observed를 남겨 null로(검증기도 거부하는 형태). 29/3 d2864.00은 2863.75의 SNY 로고 윤곽이
      투수 위에 남아 한 격자 늦춘 판단이며 note에 대안 기록. 27/1 리드 1.37 s(bug 와이프가 동작 0.2 s 전에 끝남)는 짧은 리드 목록에 추가됐다.
      A-8 합계 19구: 18 확인·1 불가, 세션 정정 3행(29/6·30/3·31/4). 근거 `game_747139_timing_verification_pa27_32.json`.
      A-7과 같은 절차([재개 지시문](docs/CODEX_RESUME_PROMPT.md) §1): 새 후보 파일 `game_747139_timing_candidates_pa27_32.json`에 미검증으로 기록 →
      직접 프레임 검증 → `scripts/69` 타석별 병합 → OCR v1·v2 재채점. 탐색 시작은 PA 26/5 마지막 릴리스 2695.48 s 이후(3회 종료 'END 3' 이후).
      러버 도착 경계는 A-7의 잠정 해석(양발이 러버에 놓인 첫 격자)을 따르되 A-y 전까지 잠정이다. 이 타석들의 판단 프레임은 F-3c v3의 새 held-out이 된다.
- [x] A-v. 판단-릴리스 간격(리드)이 짧은 사례의 규약 → **파생 필드**로 결정 (`29eef93`) `[추가되었음 · 2026-09-22 · Claude]`
      note 문구가 아니라 코드가 계산한다: `63 check` 보고서에 `short_lead_threshold_seconds`(1.5), `short_lead_pitches`
      (release − decision < 1.5 s 투구 목록, 삭제하지 않고 나열), `lead_seconds_min`; 평가셋 v2 항목에 `lead_seconds`.
      현재 26구 중 짧은 리드 7: PA 5/5 1.15 s(카메라 늦은 복귀), PA 6/1~6 1.05~1.28 s. **발견**: PA 6 전부가 짧은 이유는 편집이
      아니라 주석 규약 차이다 — 워크플로 주석 에이전트가 "동작 직전 마지막 set 프레임"을 골랐고, PA 1~5의 사람 주석은 set 구간의
      더 이른 프레임을 골랐다. 리드는 규약에 따라 약 1초 달라지므로 규약을 못 박아야 한다(A-v2).
- [x] A-v2. 판단 프레임 규약 v2 확정 + PA 1~7 재검토 (`faa2eed`) `[추가되었음 · 2026-09-23 · Claude]`
      규약: decision_seconds = (1) 라이브 중계 샷 (2) 투수가 러버 위에서 정지(사인 확인 또는 come-set, 동작 전) (3) 타자가 타석 안
      (4) bug 판독 가능 — 네 조건이 **동시에 성립하기 시작하는 가장 이른 프레임**(0.25 s 격자). 릴리스는 그대로.
      Workflow: PA별 Opus 5 에이전트가 d−3 s부터 역방향 탐색 → 투구별 검증 에이전트가 "그보다 0.25/0.5 s 앞 프레임은 조건을 깨는가"를
      반박 시도. 결과: PA 1~7 29구 중 27구 이동(대부분 컷어웨이 복귀 직후로 0.25~8 s 앞당김; PA 6/2는 9 s 탐색 한도에 걸려 하한값), 1구 유지(PA 1/3), PA 2/2는 옛 프레임이 투수 클로즈업이라 1.25 s 뒤로 정정, PA 6/4는 워크플로 값(3루측 광각, 투수 미표시)을 세션이 576.5 s로 정정, **PA 5/5는 카메라가 레그 킥 이후에야 복귀해 v2 프레임이 없어 unavailable로 변경**(검증 4건 일치). 검증 에이전트 판정 반박 없음(PA 5/5 제외). 리드(release − decision): annotated 34구 최소 1.15 / 중앙값 3.95 / 최대 10.05 s(PA 6/2 하한); 1.5 s 미만 3구(PA 2/2 1.15, PA 9/1 1.28, PA 9/2 1.23).
      리뷰 파일의 frame_seconds·판독값도 새 판단 프레임에서 다시 읽은 값으로 갱신(라벨 충돌 0). 문서: docs/MLB_BROADCAST_TIMING.md "판단 프레임 규약 v2".
      PA 8~10은 주석 시점에 이미 "컷어웨이 복귀 후 첫 라이브 프레임"을 골라 규약 v2와 일치(PA 8 주석 방법 기록).
- [!] A-x. PA 1 / 6구는 통계 그래픽 가림으로 판단 화면 확정 불가. 그대로 `unavailable` 유지.
      삭제해서 커버리지를 높이지 않는다.
- [!] A-y. **사용자 요청으로 보류(2026-10-10). 서비스 마무리의 필수 선행 조건에서 제외.** 첫 부분 응답1구는 초구/3구 식별 불일치로 비교 제외, 유효 비교0구. 원본·고정44구 규약 보존. 사용자가 재개할 때만 실제 응답을 받아 비교하며 AI 판독으로 사람 검토를 대체 완료하지 않는다.(일치도 측정 미완료) `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Opus 5〕
      2026-09-27 (`41c9679`): 기준 `ed56f9b`, ID 해시 선정 일반 32구 + 진단 12구 = 44구(중복0) 등록. scripts72로 정답을 제외한 HTML·빈 JSON·안내 ZIP 생성/검사.
      입력/규약/묶음 해시·키/play_id·출처·null·시각·검토자 검증, 수정된 응답 덮어쓰기 차단. 외부 전송 없음.
      [고정 비교 규약·재현 명령](docs/BLIND_REVIEW_PROTOCOL.md). 기존 시각·점수판·OCR 자료 보존. 일치도 수치 없음.
      H-5(`2e8189c`): 안내문·HTML·JS 해시를 포함하는 v2 계약으로 별도 묶음 생성. v1/다른 자산 응답은 CLI·UI 모두 거부. 표본44구·기준4입력·비교 규약 불변.
- [x] A-z. **feed UTC로 재생 초를 외삽하지 말 것**을 실제 입력 UI·CLI·문서에 명시 (`c4ce22d`).
      2026-09-27: annotation.html 이동 입력 안내·판단/릴리스 재생 초 라벨, scripts63 설명·65 --times·71 --dec/--prep/--rel 도움말 보완.
      실제 prepare 생성 HTML와 CLI 도움말 확인. JS·시간값·UTC 변환 로직은 변경 없음.
      PA 3→PA 4 구간에서 wall-clock 146초가 영상 약 35초에 대응했다(이닝 교대 편집).
      선형 변환이 실제로 깨지는 것을 확인했다. `[추가되었음 · 2026-09-22 · Claude]`
- [x] A-w. 점수판 확대 보조 뷰 검토 → **페이지 뷰 대신 CLI 도구**로 결정 (`9ff2181`) `[추가되었음 · 2026-09-22 · Claude]`
      `scripts/65_grab_broadcast_frames.py --label <이름> --times t1 t2 …`(1~8개): timing JSON의 media_url에서 ffmpeg로 프레임을 뽑아
      `outputs/frames/<label>_full.png`(반크기 전체 프레임)·`<label>_bug.png`(SNY 점수판 3배 확대)를 만든다. 원격 range 읽기 실패("partial file")는
      3회 재시도. 브라우저 canvas 방식보다 빠르고 병렬 안전해 A-4 주석·검증과 B-6 리뷰에 사용했다. 테스트 `tests/test_grab_broadcast_frames.py`.
      프레임은 검토 보조물이며 OCR·라벨이 아니다. 1280x720 원본에서 카운트·아웃·타자 배너를 육안 판독하려면 확대가 필요했던 문제의 해결.

**2026-09-28 당시 첫 실행 명령** (역사 기록; 현재 실행 순서는 문서 상단):

```bash
uv run --frozen python scripts/checklist_model.py --next
git diff -- src/data/mlb_video.py src/vision/state_tracker.py
```

A-y 준비는 완료했다. 실제 별도 검토자 JSON을 받은 뒤 scripts72 check-response로 검사하고 고정 규약으로 비교한다.
응답이 없으면 일치도 수치를 만들거나 A-y를 완료로 바꾸지 않는다. 전 경기 주석은 끝났으므로 빈 후보를 다시 병합하지 않는다.
H-1·H-5·I-6·A-v·A-z는 완료, E-1은 원본 확보 필요다. F-4a의 규약·PA6 OCR 기준선·PA61 근거·고정 v1 평가는 완료했고(F-4a 전체는 부분 완료 유지), F-4b(v2 사전 등록 평가: 결과 v1과 동일, v1 유지)도 완료했고 F-4c(PA68·75: v1 = v2, 이름 오답 1·ID 오답 0)도 완료했고 F-4d(v3 전처리 후보: PA77·78 28역할 모두 v1과 동일 → 실패 기록, v1 유지)도 완료했고 F-4e(PA15·21: v2가 기준 충족·채택 후보, v3 오답 2로 실패)도 완료했고 F-4f(PA23·24: v1 = v2, 누적 차이 행 1건이라 전환 보류)도 완료했고 F-4g(남은 9타석 98역할: v2가 차이 행 12건 전부 정답 → **이름 OCR 현행 v2 전환**)도 완료했고 F-4h(교체 타석 규약: 첫 투구 전 교체는 수용·PA60 평가셋 8역할; 이름 OCR v4 후보 사전 등록 — 개발 재채점에서 SCHWELLENBACH 9/10·BRAZOBÁN 6/6 추가 정답, 오답 증가 0, 근거 아님)도 완료했고 다음은 F-4i(새 미검토 영상에서 v4 사전 등록 평가)였으나 2026-10-04 보류했다. SNY 압축 경기 경로는 확인했지만 규약 변경이 필요하다(F-4i 항목). 상세 절차는 [CODEX_RESUME_PROMPT.md](docs/CODEX_RESUME_PROMPT.md).

## B. 점수판 인식 평가셋

- [x] B-1. 검증된 주석 시각에 한정한 평가셋의 ID·라벨·가림 상태·오차 집계 규약 정의 — `src/data/scoreboard_evalset.py` (`f4ddb58`)
- [x] B-2. 규약 검증 코드와 테스트 — `scripts/64_build_scoreboard_evalset.py` build/check/score, `tests/test_scoreboard_evalset.py` (`f4ddb58`)
- [x] B-3. 확인 불가 사례를 제외해 인식률을 올리지 않는다 — `score_predictions`가 coverage·attempt_rate·accuracy·error_rate·abstain_rate를 분리 보고 (`f4ddb58`; 분모 정의는 B-5로 통일)
- [x] B-4. PA 1의 5구는 리뷰어 note에 점수판 언급이 없어 `visible_unstated`였다. 영상 재확인 완료 (`8f82f3c`) `[추가되었음 · 2026-09-22 · Claude]`
      76.0·88.0·102.8·119.0·134.5초 프레임을 캔버스로 받아 점수판 bug를 3배 확대해 읽음: 0-0/0-1/0-2/1-2/2-2, 0아웃, 주자 없음, ▲1, NYM 0·ATL 0 —
      10필드 모두 라벨과 일치. 같은 방법으로 PA 2~5의 14구도 다시 읽어 전부 일치(리뷰 파일에 필드별 기록). PA 1/6은 가림 유지.
- [x] B-5. 판정 기준·분모 보완 (`8f82f3c`) `[추가되었음 · 2026-09-22 · Claude]`
      note의 "scoreboard" 문자열 판정 제거 → `mlb_scoreboard_review_v1`(`docs/results/mlb_p0/game_747139_scoreboard_review.json`)에
      판단 프레임에서 사람이 읽은 필드별 `observed`·`readability`·검토자·방법 기록. 평가셋 v2는 confirmed 필드만 평가하고
      `excluded`(occluded / scoreboard_unreviewed / no_confirmed_field)·`label_conflicts`를 분리. 분모는 코드 docstring·
      docs/MLB_BROADCAST_TIMING.md·score 출력 `denominators`가 같은 문자열(테스트 고정): coverage = evaluable / total_pitches,
      attempt·correct·error·abstain = evaluable 분모, accuracy = correct / attempted. 오답·기권·제외 투구·미확인 필드 시도를 테스트로 검증.
- **상시 유지 규칙 B-6** (기존 작업에서 분리; 완료 처리 아님). 새 타석 주석을 추가할 때마다 리뷰 파일에 그 투구의 필드별 판독 행을 같이 넣는다(없으면 `scoreboard_unreviewed`로 제외). 〔모델: Opus 5〕
      `64 review-check` → `64 build --output docs/results/mlb_p0/game_747139_scoreboard_evalset.json` → `64 check`. `[추가되었음 · 2026-09-22 · Claude]`

> 기록 메타데이터를 OCR이 읽은 결과처럼 넣지 않는다. 실제 장면 확인이 필요한 입력은 미확인으로 남긴다.

## C. 새 8종 확률 모델 — 〔담당: 팀원〕 (2026-09-22 이관)

C·D 팀원 담당은 유지한다. 이 절은 9/22 연구 계획이며 8종 재학습을 최신 S 연결의 필수 조건이나 새 팀원 지시로 확정하지 않는다. S는 구종 선택 비중을 제공하므로 사건확률 기능은 별도 I-0/I-1 합의·검증 뒤에만 활성화한다.
팀원 레포 현황(2026-09-22, [docs/TEAMMATE_PITCHEEZY_2026-09-22.md](docs/TEAMMATE_PITCHEEZY_2026-09-22.md) §4): 8종 헤드·루킹/헛스윙 구분 없음, 10종이 6곳에 하드코딩.
당시 R의 10종 응답 소비 제안은 역사 기록이다. 최신 S의 `detail.probability`에는 이 변환을 적용하지 않는다.

- [x] C-0. 8종 관찰 정답 생성 (2,135,726/2,142,792행, 제외 사유 기록)
- [ ] C-1. 8종 정답을 기존 특징에 **투구 ID로** 연결, 시간 분할 유지 〔담당: 팀원〕
- [ ] C-2. 학습 + 독립 보정 〔담당: 팀원〕
- [ ] C-3. CE/Brier 검증 〔담당: 팀원〕
- [ ] C-4. 위 검증 통과 후에만 UI의 독립 스트라이크·볼·파울 확률 활성화 〔담당: 팀원〕
      (현재 null이며 0%로 대체하지 않는다. 10종 체크포인트를 8종으로 개명하지 않는다.)

## D. 투수 프로필 / 추천 지원 범위 — 〔담당: 팀원〕 (2026-09-22 이관)

팀원 담당은 유지한다. 아래 고정 2022 프로필·6명 코호트는 9/22 당시 경로 설명이며 최신 S 지원 범위를 뜻하지 않는다. 우리 135d 프로필 갱신을 S 통합 선행 작업으로 진행하지 않는다. 현재 조건은 I-0/I-2에서 분리 확인한다.
팀원 레포 현황(2026-09-22, [docs/TEAMMATE_PITCHEEZY_2026-09-22.md](docs/TEAMMATE_PITCHEEZY_2026-09-22.md) §4): as-of 날짜 이전 자료만 쓰는 타자 프로필·90일 레퍼토리 마스크
사이드카(`refresh_pitch_service.py`)는 있으나 투수 표현·신규 투수·9회 이후는 미지원(의도적 차단). 우리 135d
feature builder의 고정 2022 프로필을 그 방식으로 갱신하는 코드는 우리 쪽(I-2)이다.

- [x] D-0. 전체 경기 322상태 HTTP 점검 — 188 추천 / 94 구종 자료 부족 / 40 9회 이후 제외
- [ ] D-1. **경기 시점 이전 자료만** 사용하는 투수 프로필 갱신 (현재 고정 2022 프로필) 〔담당: 팀원〕
- [ ] D-2. 신규 투수 처리 방침 〔담당: 팀원〕
- [ ] D-3. 9회 이후 정책 평가 범위 확대 여부 결정 `[추가되었음 · 2026-09-22 · Claude]` 〔담당: 팀원〕

## E. 기존 영상 ID 재검증

- [!] E-1. **옛 영상이 통합 대상으로 선택될 때만 재개.** 옛 오타니 수집기는 CSV `iloc[i]` 사용 → 기존 영상 파일명은 정답이 아니다. 〔모델: Fable 5.1〕
      원본 확보 후 `playId`로 재대조한다.

## F. 위치 · 인식 · 실시간 (순차)

- [!] F-1. **의도 대리값·좌표 평면·평가 정의 합의 대기. 미트 x와 도착점만으로 제구 책임을 확정하지 않음.** 목표 위치와 제구 오차 — 팀원의 관측 위치 재가중 proxy는 정책 효과 음성(−0.019 %p). 〔모델: Fable 5.1〕
      **영상 기반 의도 라벨**로 재정의한 뒤 착수(I-0에서 범위 합의).
- [!] F-2. **I-4 최신 공급 계약 대기; 중복 구현 보류.** 타자 세부 특성 — 팀원 archetypes(6 성향률+신뢰도, 전날까지 자료)가 완성돼 있어 새로 만들지 않고 I-4로 소비. 〔모델: Fable 5.1〕
- [x] F-3. 자동 점수판 OCR — **v0 프로토타입** `src/vision/sny_scoreboard.py` + `scripts/66_sny_scoreboard_ocr.py` (`fc3d18b`)
      SNY bug 전용 휴리스틱: 아웃·주자 = 고정 창의 금색 채움, 초/말 = 화살표 행 프로파일, 숫자(볼·스트라이크·이닝·점수) =
      검증 프레임에서 잘라낸 글리프 템플릿 최근접 매칭(템플릿 없는 숫자·근소 차는 **기권**). 템플릿은 PA 1~2 프레임(in-sample),
      측정은 PA 3~7 held-out 17구: 10필드 오답 0, 볼 1건 기권(PA 5/6의 "3", 템플릿 0/1/2뿐), all_fields 16/17 정답·1 기권.
      임계값(MAX_DISTANCE 0.12 / MIN_MARGIN 0.15)은 그 "3"→"2" 오매칭을 보고 조인 것이므로 그 1건은 blind가 아니다.
      결과 `docs/results/mlb_p0/game_747139_scoreboard_ocr_v0.json`(held-out)·`_insample.json`·`_predictions.json`·
      `sny_digit_templates_v0.json`. 한계: 이 방송사 레이아웃·1280x720 전용, 숫자 3~9 템플릿 없음, 그래픽 가림 시 전 필드 기권.
- [x] F-3a. OCR v0 확장: 새 숫자(3~9)·2자리 이닝·득점 상황이 생기면 템플릿을 늘리고 held-out을 다시 잰다. `[추가되었음 · 2026-09-23 · Claude]` 〔모델: Fable 5.1〕
      (`66 templates --template-pas …` → `predict` → `score --exclude-pas …`). 다른 방송사 레이아웃은 별도 창 측정 필요.
      (2026-09-24, `342170f`) 2회초 프레임(이닝 "2")이 생겨 재측정: v0 템플릿(PA 1~2)은 held-out PA 3~9 26구에서 오답 0이지만 이닝 "2"를
      6건 기권. PA 9를 템플릿에 추가한 v1(`sny_digit_templates_v1.json`, 0/1/2 글리프 50개)은 held-out PA 3~8 24구에서 오답 0·기권 2
      (PA 5/6 볼 "3", PA 8/1 라인스코어 전 필드; PA 8/2 이닝만 기권). 음성 14프레임 거짓 판독 0 유지. 숫자 3~9는 여전히 템플릿 없음.
      (2026-09-24, `06abd0c`) PA 11~15 병합 후 템플릿 변경 없이 재채점: held-out 전 필드 49구 44 정답·5 기권·오답 0.
      새 20구 중 기권은 PA 11/1 이닝, 11/2 전 필드, 13/3 볼(17구 전 필드 정답). 기존 PA 4/1 이닝·5/6 볼도 기권이고 PA 8/1은 partial이다.
      기존 PA 8/2·10/1 이닝은 저장된 과거 예측의 null에서 이번 2로 바뀌었다. 과거 입력 해시가 없어 원인은 확정하지 않았으며 모델 개선으로 세지 않는다.
      현재 캐시·고정 템플릿 반복 예측은 60/60 동일. `game_747139_scoreboard_ocr_v1_provenance.json`에 입력/코드/출력 해시·환경을 남겼다.
      (2026-09-24, `eb1cdf6`) PA 16~19 추가 후 v1 고정 재채점: 전 필드 56구 44 정답·12 기권·오답 0.
      새 8구 중 6구는 이닝 숫자 3만 기권, PA 19/2는 전 필드 기권, partial PA 16/1은 보이는 4필드 모두 기권.
      판독 가능 새 74필드 중 54 정답·20 기권·오답 0. PA 19/2 전 필드 기권 원인은 미진단이다.
      (2026-09-25, Claude Code) PA 22·23·25 병합 후 v1 고정 재채점: 전 필드 62구 44 정답·18 기권·오답 0. 새 6구는 모두 이닝 3만 기권.
      기존 68구 예측 불변, 현재 74구 반복 예측 동일, 음성 거짓 판독 0 유지. provenance 갱신(기준 `3e395b2`).
      (2026-09-25, Claude Code) PA 21·24·26 병합 후: 전 필드 77구 44 정답·33 기권·오답 0. 새 15구 모두 이닝 3 기권, PA 24/5는 홈 득점도 기권(원인 미진단).
      기존 74구 예측 불변, 89구 반복 예측 동일, 음성 거짓 판독 0. provenance 기준 `5f69f26`.
      (2026-09-25, Claude Code) PA 20 병합 후(A-7 완료): 전 필드 83구 44 정답·39 기권·오답 0. 새 6구 모두 이닝 3만 기권.
      기존 89구 예측 불변, 95구 반복 동일, 음성 거짓 판독 0. provenance 기준 `ca76e65`. 3회 판단 프레임 35구가 v2 평가 재료다.
      (`edba714`) **OCR v2 완료**(Claude Code; 실제 작업은 Fable 5.1 워크플로 에이전트, 세션 Opus 5.5가 확인·통합).
      사전 등록: Fable 제안자 2명 + 심판이 v2 결과를 계산하기 전에 규칙을 고정 — v1 소스 PA 1·2·9 유지, 이닝 3이고 전 필드 확인·게이트 통과·자릿수대로
      분할되는 1투구 타석 중 '0'·'3' 외 새 글리프가 가장 적은 타석 → **PA 18/1**('3' 1개, '0' 4개 추가). 심판이 후보 bug 크롭은 봤으므로 'blind'가 아니라
      '규칙 고정 후 처음 계산한 held-out'이다. 코드·임계값(0.12/0.15/게이트)·v1 파일 불변. `sny_digit_templates_v2.json`, `..._ocr_v2*.json`,
      `..._negatives_score_v2.json`, `..._ocr_v2_comparison.json`(같은 held-out에서 v1 대비), `..._ocr_v2_provenance.json`.
      결과(PA 1·2·9·18 제외): 전 필드 82구 v2 **75 정답·7 기권·오답 0** vs v1 44·38·0. 변화 32구는 모두 이닝 None→3(라벨 일치), 다른 필드 변화 0.
      in-sample 포함 전체 93구 86 정답·7 기권·오답 0, 음성 거짓 판독 0. 숫자 3 판정 32건의 여유(margin)는 0.177~0.212, 2위는 모두 '2'로
      MIN_MARGIN 0.15에 가깝고, '3' 템플릿이 한 프레임뿐이라 32건은 독립 증거가 아니다. 이닝 '2' 글리프의 2위가 '3'으로 바뀌며 여유가 줄었다(13/3 0.171).
      남은 기권 7구와 원인(세션이 픽셀로 확인): 19/2·11/2 카메라 컷 프레임에서 점수판 윗선 흰색 0.575/0.585 < 0.60 → 전 필드 기권;
      4/1·11/1 전환 꼬리에서 점수판 오른쪽 테두리가 2픽셀 폭으로 이닝 창에 들어와 가짜 글리프; 13/3 볼 '2' 글리프 오른쪽 떨어진 1픽셀이
      경계를 넓혀 거리 0.129(잘라내면 0.076); 24/5 점수 폰트 '2'(18x12)가 카운트 폰트 템플릿과 0.1204로 근소 초과; 5/6 볼 '3'(17x11)은
      이닝 '3' 템플릿과 거리 0.198로 기권. 라인스코어 8/1·16/1은 설계상 기권. 고칠 방법은 F-3c.
      다음 OCR 단위: 숫자 3 템플릿 추가 시 학습에 쓴 PA를 held-out에서 제외하고 v2로 따로 평가; v1 결과·평가 범위는 보존한다.
      기존 60구 예측 불변, 현재 68구 반복 예측 동일. 최신 입력/코드/출력/프레임 해시는 `..._ocr_v1_provenance.json`.
- [x] F-3c. OCR v2 잔여 기권 수정(v3) + 숫자 4~9. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Fable 5.1〕
      (`cf9e07f`) Fable 5.1 워크플로(제안 2·심판·빌더·수리) + 세션 모델 검증 3관점×2라운드. v3 사전 등록(결과 계산 전): 템플릿 PA 1·2·9·18·**29**
      (이닝 '4' 6개, 카운트 폰트 '3' 1개, 점수 폰트 '2' 6개 추가)와 v3 템플릿 파일에만 담는 opt-in `reader_options`(top_line 게이트를 행 최대값으로, 창 가장자리 폭≤2 조각 무시).
      옵션이 없는 v1·v2 문서는 기존 경로 그대로(`scripts/70`으로 v1·v2 예측·채점·음성 바이트 동일 확인). 기본 임계값 불변. 평가를 세 덩어리로 분리:
      held-out 75구(모두 v2 정답) 무회귀 기준 **실패 73·0·2** — PA 20/5·20/7 볼 '2'가 새 카운트 폰트 '3'과 margin 0.1325<0.15로 기권(오답 아님);
      이미 진단된 19구(이닝 4 ×12, 게이트 11/2·19/2, 조각 4/1·11/1, 5/6, 24/5, 13/3)는 18구 복구지만 held-out 증거가 아니다; in-sample 17/17; 음성 거짓 판독 0.
      규칙대로 결과를 본 뒤 조정하지 않았다. v3 파일은 기록으로 두고 현행 판독은 v2. `..._ocr_v3_comparison.json`에 세 덩어리와 margin을 기록.
- [!] F-3e. **OCR 확대 보류; 피드 대조/보완이 실제로 필요해지고 미열람 영상이 있을 때 재개.** OCR v5 후보(새 사전 등록): 아웃·주자 칸이 옅게 채워질 때 빈 칸으로 읽지 말고 기권(42/1), 점수 '3' 템플릿(PA 46 이후 ATL 3), 이닝 숫자. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Fable 5.1〕
      1~7회 프레임은 모두 본 프레임이므로 개발 집합이다(A-11은 v5 사전 등록 없이 진행). 규칙·기준을 다음 주석 단위(A-12) 전에 커밋해야 그 프레임이 blind가 된다. 현행 v2를 바꿀지 여부는 사전 등록 기준 통과 뒤에만 정한다.
- [x] F-3d. OCR v4: 필드 묶음별 템플릿(카운트 칸은 카운트 폰트, 이닝 칸은 이닝 폰트, 점수 칸은 점수 폰트)으로 v3의 '2'/'3' margin 회귀를 막는다. `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Fable 5.1〕
      (`05a9bd9`) **v4 사전 등록 완료** — 이 커밋이 6회 주석 전 등록 시점. Fable 5.1 워크플로(설계 2 → 심판 → 빌더 → 검증 2관점 → 수리 1회 → 재검증 통과) + 세션 직접 확인.
      측정 결과 필드 묶음별 템플릿은 2-vs-3 기권을 0건도 고치지 못했다(풀링 때도 2위가 이미 카운트 폰트 '3'). 원인은 카운트 '2' 템플릿 사이 퍼짐(최대 0.148)으로 margin이 0.1325~0.1432.
      확정안: v3 템플릿(PA 1·2·9·18·29, 파일 `templates` 동일) + opt-in `min_margin_by_field` {balls·strikes 0.10}(MAX_DISTANCE 0.12 유지),
      `arrow_window` [262,46,279,64](▲ 왼쪽 끝 x264/265), `topbot_rule` blob_slope(화살표 덩어리 행 폭의 기울기 부호, |기울기|≥0.4, 6행 이상).
      개발 집합(142구·음성 14프레임, 모두 이미 봄): v3 대비 6행만 바뀌고 모두 라벨과 일치(볼 '2' 20/5·20/7·33/5·35/5, ▲ 34/3·37/5), 오판독 0, 음성 거짓 판독 0,
      exclude-pas 122구 전 필드 93 정답(v3 91, v2 75). **held-out·blind 아님**(margin 0.10과 기울기 0.4는 이 값들을 보고 정함 — 위험 목록에 기록).
      v1~v3 파일·판독 경로 불변(세션이 새 코드로 v1~v3를 다시 돌려 9개 보고서 동일 확인). 사전 등록 파일에 A-10 판정 기준 (1)~(5)와 LF 정규화 해시 기록,
      기준 (4)·(5)는 수리 라운드에서 A-10 뒤 계산 불가능한 조항을 고쳐 `amendments`에 기록(6회 프레임을 보기 전). `scripts/66 predict --diagnostics`, `ocr_reports.new_rows_acceptance` 추가.
      세션 정리: v4 개발 수치 고정은 살아있는 점수 파일이 아니라 사전 등록 기록에 두고(A-10 갱신 때 깨지지 않게), 'v4는 목록에 없어야 한다' 단언을 뺐다(실패도 기록 가능하게).
      (2026-09-25 A-10 후) **판정: 실패** — 6회 blind 32구에서 기준 (1) 오답 1건(42/1 아웃, v1~v4 공통), (2)~(5) 통과. v4 필드 246 정답·61 기권·1 오답(v3 240·67·1, v2 232·75·1). 옵션·기준은 바꾸지 않았다. [판정 기록](docs/results/mlb_p0/game_747139_scoreboard_ocr_v4_acceptance.json).
      (2026-09-25 A-9 후 변경) 5회 29구는 v1~v3 결과와 34/3 원인을 이미 봤으므로 v4에는 blind가 아니다. **F-3d = v4 규칙·코드 사전 등록 커밋**(v4 성능 주장 없음, 이미 본 사례로 동작만 확인)이고,
      첫 blind 채점은 A-10(6회) 병합 뒤 `scripts/70`의 새 행 비교가 v2·v3·v4를 함께 처음 계산해 기록한다. 5~9 이닝 숫자는 템플릿이 없어 이닝은 기권이 정상.
      v4 추가 후보(A-9에서 확인): 34/3 초말 화살표 — 판독 창을 x264까지 넓히거나 동률에 강한 꼭짓점 규칙(알려진 오판독 목록 항목, v1~v3 기록은 유지); 볼 '2' margin 기권(33/5·35/5에서 v3가 재현).
      (2026-09-25 A-8 후 추가 사례) PA 29/7 볼 '3'(카운트 폰트 17x11)도 v2가 거리 0.193으로 기권 — PA 5/6과 같은 원인. 4회 18구의 이닝 '4'도 템플릿 없음.
      이 사례들은 이미 보았으므로 v3 held-out에 넣지 않는다. 채점용 새 프레임은 5회 이후 주석(A-9)에서 나온다.
      후보: 윗선 게이트를 행 단위(y33)나 인접 프레임으로 완화(19/2·11/2), 이닝 창 오른쪽 테두리 열 제외 또는 폭 2 이하 가장자리 조각 무시(4/1·11/1),
      글리프 경계에서 1픽셀 고립 열 제거(13/3), 점수 폰트 '2'와 카운트 폰트 '3' 템플릿(24/5·5/6), '3' 템플릿 다양화.
      위 7구는 이미 보고 원인을 찾았으므로 v3 평가에서 held-out으로 세지 않는다. 규칙을 먼저 등록하고 A-8 등 새 판단 프레임으로 채점하며, v1·v2 파일은 보존한다.
- [x] F-3b. 판단 프레임 밖에서 OCR이 **기권하는지** 음성 평가셋으로 측정 (`b1ab6a5`) `[추가되었음 · 2026-09-23 · Claude]`
      `docs/results/mlb_p0/game_747139_scoreboard_negatives.json`(`mlb_scoreboard_negatives_v1`, 같은 MP4·manifest에 바인딩): 사람이
      눈으로 분류한 14프레임 — bug 없음 9(통계 그래픽 150·151.8·152.4, 타자 인트로 470, 회상 475·480, 리플레이 546, 타 카메라 840, 전체화면 그래픽 880),
      라인스코어 대체 1(780: 이닝·초말·득점만 판독 가능), 컷어웨이인데 bug 보임 4(465·495·606·610, 10필드 값 기록).
      `66 negatives` 채점(`src/vision/negatives.py`): 판독 불가 96필드 거짓 판독 **0**(첫 실행은 780의 라인스코어에서 아웃·주자 4건을
      자신 있게 0/False로 냈고, bug 상단 흰 경계선·패널 내 흰색 비율 게이트를 추가해 잡음), 판독 가능 44필드 중 40 정답·4 기권(780의
      이닝·초말·득점 — 라인스코어는 bug가 아니므로 전부 기권), 오답 0. 게이트 추가 후 평가셋 점수는 변하지 않았다(16/17, 기권 1).
- [x] F-4. 상태 추적 v0 — 그래픽·리플레이 중 마지막 확인 상태 유지 + 신선도 표시 (`f7dcac6`)
      `src/vision/state_tracker.py`(`ScoreboardTracker`): 판독기의 null(기권)에는 필드별 마지막 확인값을 유지하고 `age_seconds`·
      `stale`(기본 10 s 초과)을 함께 낸다. 불가능한 값(볼 4, 스트라이크 3 등)은 거부 목록에, 이닝 감소·득점 감소 같은 역행은 수용하되
      `suspect`에 기록. 값을 추측하지 않는다. 데모 `scripts/67_track_scoreboard_state.py`(PA 6 구간 460~535 s, 5초 간격 16프레임):
      16프레임 중 판독 13·기권 3(470 OZUNA 인트로 그래픽, 475·480 JULY 27 회상 — 눈으로 확인), 기권 구간에서 마지막 확인 상태(0-0·1아웃·1루)를 유지하며 age 5→10→15 s(15 s에서 stale), 485 s 복귀 시 즉시 재확인, 거부 0·suspect 0 — `docs/results/mlb_p0/game_747139_scoreboard_track_demo.json`(시연용, 라벨·벤치마크 아님).
      선수(투수·타자) 추적은 미구현 — 배너 이름 판독은 별도 항목(F-4a).
- [!] F-4a. **OCR 후속 보류; 완료 근거 보존, 현재 서비스 필수 선행 조건에서 제외.** **부분 완료: 규약·PA6 이름 OCR 기준선·PA61 근거·고정 v1 평가. 다음은 F-4b(v2 사전 등록·blind 평가).** `[추가되었음 · 2026-09-23 · Claude]` 〔모델: Fable 5.1〕
      2026-09-27 첫 단위 완료(`e34c8a6`): [규약](docs/PLAYER_IDENTITY_PROTOCOL.md), scripts73 build/check/summary, 출처 고정 평가 자료·검사.
      PA6 판단 프레임 6장×2역할=12건: 투수 6·타자 5건 직접 이름 판독, 첫 타자 1건 기권. 이름 대응 11건은 최종 feed 기준과 일치.
      470초 가린 소개 이름은 문맥 기록만 남기고 481초 타자에 대입하지 않았다. 모든 연속성 unknown, held 0. AI-assisted 비블라인드 개발 자료다.
      이름 대응은 전체 경기 이름 사전의 정확 일치만 사용하며 기대 역할/정답 ID로 후보를 줄이지 않는다. 교체 타석·미래 프레임·출처/해시 오류는 거부한다.
      신규32검사와 실제 feed·7이미지 재생성/바이트 검사 통과. 전체522 passed·2 deselected, Ruff79경로 통과.
      2026-09-28 두 번째 단위(`f5962d7`): [Windows OCR 기준선](docs/PLAYER_IDENTITY_OCR.md), scripts74 predict/score/check 구현.
      이미지 외 정답 입력 없이 이름·타순을 읽고 전체 명단으로 ID 대응한다. PA6 이름/ID 각각12기회 중9정답·0오답·3기권(읽을 수 있는11건 중9성공),
      타순6기회 중4정답·0오답·2기권. 611.45초 타자 빈 결과, 663.50초 `3.0ZUNA` 이름 거부·타순3 보존. 원문 보존, 퍼지/정답 보정 없음.
      부재1건·문맥470초1건 거짓 판독0, 엔진 오류0. 실제 예측 반복12역할+문맥1건 JSON 일치. 개발 자료에서 crop 경계를 조정한 결과다.
      신규51검사·실제엔진/출처·원문 재채점 통과, 전체573 passed·2 deselected, Ruff84경로 통과. 다른 작업 폴더에서 저장 결과 check도 통과.
      예측은 Windows OCR en-US 필요, 저장 결과 채점은 이식 가능하다. UI 선수 ID는 여전히 feed 기준이며 실시간 연결·교체·새 영상 검증은 남았다.
      다음 PA61(4구)은 교체 이벤트 없이 IGLESIAS 모호성 검증을 준비한다. PA60은 투수 교체 이벤트 때문에 현 기준 생성기에서 거부, 임의 해제 금지.
      2026-09-28 세 번째 단위(`abfa03c`, Claude 세션 Fable 5.1; 선점 `fdaf6b7`): PA61(8회초, 4구) 판단 프레임 6044.75·6063.00·6077.50·6094.00의 [직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa61.json)과 [평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa61.json).
      8역할 중 투수 `IGLESIAS` 4건, 타자 `VIENTOS`·타순 3 3건을 직접 읽었고 6044.75 타자 배너 부재 1건은 기권. 수동 대응: VIENTOS 3건은 명단 유일 일치로 feed 기준과 3/3 일치, IGLESIAS 4건은 전체 명단의 Raisel/Jose 두 후보라 `ambiguous_name` 기권(투수 역할·정답 ID로 좁히지 않음), 불일치 0. 6077.50은 라이브 광각 프레임이지만 bug는 같은 크기·위치로 완전히 읽힌다.
      고정 v1(설정·코드 해시 PA6 실행과 동일, 튜닝 없음) [예측](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa61_predictions.json)·[보고서](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa61_report.json): 이름 8기회 중 기준 판독 가능 7·시도 6·정답 4(IGLESIAS×4)·**오답 2**·기권 2; ID는 8기회 모두 기권(IGLESIAS 4 모호, VIENTOS 3은 이름 오판독으로 사전 불일치, 부재 1; 시도 0·오답 0); 타순 4기회 중 정답 2·기권 2. 엔진 오류 0, 부재 프레임 거짓 판독 0.
      오판독 원문: 6077.50·6094.00 타자 `3.VlENTOS`(대문자 I가 소문자 l) → 이름 `VLENTOS` 오답 2건(ID 기권으로 가리지 않고 이름 오답으로 보고), 6063.00 `a.VlENTOS`(타순 3이 a) → 타순 누락 기권. 이름 처리율은 4/8이며 IGLESIAS 정답 4건도 ID까지는 가지 못한다. 개선은 F-4b로 넘긴다.
      scripts73 build/check --verify-frames(full_input_rebuild, feed·8프레임 바이트 재검증)와 scripts74 predict→score→check --verify-frames 통과, 실제 Windows OCR en-US 실행. PA6 산출물·timing·숫자 OCR 결과 변경 없음. 전체 573 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4b. **이름 OCR v2 사전 등록 평가 — 결과 v1과 동일, v1 현행 유지** `[추가되었음 · 2026-09-28 · Claude]` 〔모델: Fable 5.1〕
      허용 후보: 대문자 전용 문맥의 l→I 정규화, 타순 자리의 숫자 검증. 금지: 정답 문자열 기반 보정, 퍼지 매칭, 기대 역할/정답 ID로 후보 축소. PA60 투수 교체 타석의 생성기 처리는 별도 항목으로 남기고 우회하지 않는다. v1 결과·PA6/PA61 자료는 보존한다.
      2026-09-28 사전 등록 커밋(`5323ba8`, Claude/Fable 5.1; 선점 `f29ac92`): `CONFIG_V2`(v1 crop·gate 동일 + `uppercase_context_l_to_I`·`decoupled_unreadable_batter_slot`), scripts74 `--reader v2`(별도 출력 강제), 파서 검사 추가. 대상은 결정 규칙(PA61 이후 4구 이상·전 투구 annotated·교체/수비 전환 없음인 첫 두 타석)으로 PA62·PA67, 채택 기준·예측은 [OCR 안내 v2 절](docs/PLAYER_IDENTITY_OCR.md). 대상 OCR 출력은 이 커밋 시점에 없다(프레임 자체는 시각 주석 때 본 개발 자료).
      2026-09-28 평가 완료(`0f8a5eb`): [PA62·67 직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa62_67.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa62_67.json) 16역할 = 투수 `IGLESIAS`×4·`MATON`×4, 타자 `NIMMO`/타순 4×4·`LAUREANO`/타순 6×1, 67/1~67/3 타자 배너 부재 3건. 수동 대응 9 observed(NIMMO·MATON·LAUREANO 유일 일치, feed와 9/9 일치)·7 기권(IGLESIAS 모호 4 + 부재 3), 불일치 0.
      [v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa62_67_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa62_67_report.json) 실제 Windows OCR 결과가 **행 단위로 동일**: 이름 16기회 중 기준 13·시도 10·정답 10·오답 0·기권 6, ID 기준 9 중 정답 6(NIMMO 1·MATON 4·LAUREANO 1)·기권 10(IGLESIAS 4 모호, NIMMO 3 미판독, 부재 3), 타순 8기회 중 정답 4·기권 4, 엔진 오류 0, 부재 프레임 거짓 판독 0.
      규칙 발화: 62/1·62/3 타자 원문 `41VlMMO`(`4.NIMMO`의 N→`1V`, I→`l`)에서 v2 `l→I`가 적용됐지만 `1VIMMO`는 이름 문법에 걸려 v1과 같이 기권(거짓 판독 없음). 62/2 원문 빈 문자열. 타순 자리 분리 규칙은 발화 사례 없음.
      판정: 사전 등록 기준(오답 ≤ v1, 정답 ≥ v1, 거짓 판독 0)은 충족했으나 **결과가 바뀐 행이 0건**이라 채택 근거가 없다 → **v1 현행 유지, v2는 옵션으로 보존**. 개발 표본 PA61에 v2를 돌리면([예측](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa61_predictions.json)·[보고서](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa61_report.json)) 이름 7/7·ID 3/3·타순 2/2가 되지만 규칙을 만든 표본이라 성능 근거가 아니다.
      새로 기록된 오인식 유형: `N`→`1V`(62/1·62/3), 빈 원문(62/2). 정답 기반 보정 없음. PA6·PA61 산출물은 코드 해시만 갱신(행 동일). 전체 587 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4c. **이름 OCR 오인식 유형 누적: PA68·PA75 v1·v2 동일 절차 평가 — v1 = v2, v1 현행 유지** `[추가되었음 · 2026-09-28 · Claude]` 〔모델: Fable 5.1〕
      대상 규칙은 F-4b와 같다(PA67 이후 4구 이상·전 투구 annotated·교체/수비 전환 없음인 첫 두 타석 → PA68 Maton 대 d'Arnaud, PA75 Johnson 대 Marte; feed로 재확인). 아포스트로피 이름 `D'ARNAUD`가 첫 사례다.
      결과를 본 뒤 규칙을 고치지 않는다. 누적된 유형(`N`→`1V`, `I`→`l`, 빈 원문, 타순 자리 오인식)이 충분하면 v3 후보(예: crop 확대 배율, 다른 엔진 어댑터)를 **별도 사전 등록** 뒤 새 타석에서 평가한다. PA60 교체 타석은 여전히 별도 항목.
      2026-09-28 완료(`dc59ac6`, Claude/Fable 5.1; 선점 `1802faa`): feed 재확인(PA68·PA75 비투구 이벤트 없음). [직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa68_75.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa68_75.json) 16역할 = 투수 `MATON`×4·`JOHNSON`×4, 타자 `D'ARNAUD`/타순 7×3·`MARTE`/타순 9×2, 배너 부재 3(68/1·75/1·75/2). 수동 대응 13 observed(모두 명단 유일, feed와 13/13 일치)·3 기권(부재), 불일치 0.
      [v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa68_75_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa68_75_report.json) 실제 OCR 결과 행 단위 동일: 이름 16기회·기준 13·시도 12·정답 11·**오답 1**·기권 4; ID 기준 13·정답 11·오답 0·기권 5; 타순 8기회·정답 4·기권 4; 엔진 오류 0, 부재 프레임 거짓 판독 0. v2 규칙은 발화 사례 없음(소문자 `l`·구분자 있는 오인식 타순이 없었다).
      새 오인식 유형: 68/3 `7.DtARNAUD`(아포스트로피→`t`, 이름 오답 `DTARNAUD`; 사전 불일치라 ID는 기권했지만 이름 오답으로 보고), 68/2 `zD'ARNAUD`(타순 `7.`이 `z`로 뭉개져 구분자 없음 → `batter_slot_missing` 기권). 68/4 `7.D'ARNAUD`·75/3·75/4 `9.MARTE`는 정답. 규칙·crop은 바꾸지 않았다.
      누적(개발 표본 PA6 제외, PA61·62·67·68·75 = 40역할, v1 = v2): 이름 기준 33·시도 28·정답 25·오답 3·기권 12 / ID 기준 25·정답 17·오답 0·기권 23 / 타순 기준 13·정답 10·오답 0·기권 10. 오인식 유형표는 [OCR 안내](docs/PLAYER_IDENTITY_OCR.md). 전체 587 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4d. **이름 OCR v3 후보 사전 등록(전처리)과 PA77·PA78 평가 — 결과 v1과 동일(실패 기록), v1 현행 유지** `[추가되었음 · 2026-09-28 · Claude]` 〔모델: Fable 5.1〕
      누적 40역할의 오인식 유형(`I`→`l`, `N`→`1V`, 아포스트로피→`t`, 타순 자리 `a.`/`z`, 빈 원문)은 모두 4배 LANCZOS 회색조 crop의 글자 형태 혼동이다. v3 후보는 **전처리만** 바꾼다(예: 확대 배율 6배 + 문턱값 이진화 옵션, crop·gate·파서는 v2와 동일).
      규칙·기준·대상(같은 결정 규칙의 다음 두 타석 PA77 Johnson 대 Jose Iglesias, PA78 Johnson 대 Eddy Alvarez — 배너 `IGLESIAS`·`E.ALVAREZ`의 동명이인·이니셜 사례)을 OCR 실행 전에 커밋한 뒤 v1·v2·v3를 같은 프레임으로 평가한다. 이니셜이 표시돼도 파서가 이니셜을 이름 대응에 쓰지 않는 현 규약을 바꾸지 않는다(변경은 별도 규약 항목).
      2026-09-28 사전 등록 커밋(`49727c0`, Claude/Fable 5.1; 선점 `e8246b0`): `CONFIG_V3` = v2 + 전처리(6배 LANCZOS, 회색값 100 이진화), scripts74 `--reader v3`, 검사 추가. 문턱값 100은 PA61 개발 표본에서 여섯 변형 중 고른 값(6배/128은 더 나빴음)이며 그 결과는 근거가 아니다. 대상 PA77(4구)·PA78(10구) 14프레임·28역할, 채택 기준(오답 ≤ v1, 정답 ≥ v1, 거짓 판독 0, 결과 다른 행 ≥ 1)은 [OCR 안내 v3 절](docs/PLAYER_IDENTITY_OCR.md). 대상 OCR 출력은 이 커밋 시점에 없다.
      2026-09-28 평가 완료(`3e07d11`): [PA77·78 직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa77_78.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa77_78.json) 28역할 = 투수 `JOHNSON`×14, 타자 배너 **14프레임 전부 부재**(두 타석 모두 판단 프레임에 타자 줄이 한 번도 없음). 수동 대응 14 observed(JOHNSON 유일, feed와 14/14 일치)·14 기권(부재), 불일치 0.
      [v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa77_78_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa77_78_report.json)·[v3](docs/results/mlb_p0/game_747139_player_identity_ocr_v3_pa77_78_report.json) 실제 OCR 결과가 28행 모두 동일: 이름 기준 14·정답 14·오답 0·기권 14(부재), ID 정답 14·오답 0, 타순 기준 0, 엔진 오류 0, 부재 프레임 거짓 판독 0(v3 이진화도 빈 패널에서 글자를 만들지 않았다).
      **판정: v3 실패 기록** — 사전 등록 기준 중 '결과가 v1과 다른 행 ≥ 1'을 채우지 못했다(오답·정답·거짓 판독 조건은 동률). v1 현행 유지, v3는 옵션으로 보존. 대상에 타자 줄이 전혀 없어 후보가 겨냥한 오인식 유형이 한 번도 나오지 않은 무력한 표본이었다.
      교훈: A-14 timing note에 이미 'PA77·78 판단 프레임에 타자 배너 없음'이 적혀 있었으나 결정 규칙이 이를 쓰지 않았다. 다음 규칙은 검증 기록의 배너 관찰을 조건에 넣는다(결과를 본 뒤 규칙을 바꾸는 것이 아니라 표본 선택 조건의 사전 추가).
      누적(PA61·62·67·68·75·77·78 = 68역할, v1 = v2; v3는 PA77·78만): 이름 기준 47·정답 39·오답 3·기권 26 / ID 기준 39·정답 31·오답 0·기권 37 / 타순 기준 13·정답 10·기권 24. 전체 588 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4e. **타자 줄이 기록된 타석(PA15·21)에서 v1·v2·v3 동일 절차 평가 — v2 채택 후보, v3 실패 기록, v1 현행 유지** `[추가되었음 · 2026-09-28 · Claude]` 〔모델: Fable 5.1〕
      결정 규칙(사전 등록): PA7 이후 번호순으로 4구 이상·전 투구 annotated·교체/수비 전환 이벤트 없음이고, **해당 단위의 검증 기록(timing_verification)·A-12/13 리뷰 노트에 타자 배너가 판단 프레임에 보였다고 기록된** 타석 중 PA6·61·62·67·68·75·77·78이 아닌 첫 두 타석. 규칙·crop·v3 설정은 바꾸지 않는다.
      채택 기준은 F-4d와 같다(오답 ≤ v1, 정답 ≥ v1, 거짓 판독 0, 결과 다른 행 ≥ 1). 실패하면 v3를 폐기 후보로 기록하고 이름 OCR 확장은 다른 화면 형식·다른 경기 영상 확보 뒤로 미룬다.
      2026-09-28 사전 등록 커밋(`1890cbd`, Claude/Fable 5.1): 결정 규칙(위)과 검증 기록 `bug_text`의 타순+이름 패턴을 그대로 적용해 **PA15**(Megill 대 Arcia, 5구, 4/5 기록)·**PA21**(Megill 대 Albies, 5구, 4/5 기록)을 대상으로 고정. PA11·14·19는 기록에 타자 줄이 없어 제외, PA20은 20/6 unavailable로 제외. 코드·설정 변경 없음, 대상 OCR 출력은 이 커밋 시점에 없다. 상세는 [OCR 안내 F-4e 절](docs/PLAYER_IDENTITY_OCR.md).
      2026-09-28 평가 완료(`2ddc404`): [PA15·21 직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa15_21.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa15_21.json) 20역할 = 투수 `MEGILL`×10, 타자 `ARCIA`/타순 9×4·`ALBIES`/타순 2×4, 1구째 타자 배너 부재 2. 수동 대응 18 observed(모두 명단 유일, feed와 18/18 일치)·2 기권, 불일치 0.
      실제 OCR([v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa15_21_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa15_21_report.json)·[v3](docs/results/mlb_p0/game_747139_player_identity_ocr_v3_pa15_21_report.json)), 이름 기준 18: **v1** 시도 10·정답 9·오답 1(`9.ARClA`→`ARCLA`)·기권 10 / **v2** 시도 10·정답 10·오답 0·기권 10(15/4의 `l`→`I` 규칙 발화로 `ARCIA`·타순 9 정답, v1과 다른 행 1) / **v3** 시도 12·정답 10·**오답 2**(`9 ARC JA`→`ARC JA`, `9 AR CIA`→`AR CIA`)·기권 8(21/1 투수 빈 원문을 `MEGILL`로 회복, v1과 다른 행 8). ID 오답 0(v1 9·v2 10·v3 10 정답), 타순 v1·v2 1·v3 2 정답, 엔진 오류 0, 부재 프레임 거짓 판독 0.
      **판정**: v2는 사전 등록 기준(오답 0 ≤ 1, 정답 10 ≥ 9, 거짓 판독 0, 다른 행 1 ≥ 1)을 처음으로 모두 충족 → **v2 채택 후보**(근거는 15/4 한 행). v3는 오답 2 > v1 1로 **실패 기록**(6배/100 이진화가 글자 사이를 띄워 `ARC JA`·`AR CIA`를 만들었다). v1은 현행 유지, 전환 결정은 F-4f 추가 표본 뒤.
      새 오인식 유형: 21/2 `"ALBIES`·21/3·21/4 `ZALBIES`(타순 `2.`이 `"`·`Z`로, 구분자 없음 → 기권), 15/2·15/3·15/5·21/5 빈 원문(타자 줄이 보이는데도 엔진이 빈 문자열), 21/1 투수 빈 원문(전환으로 기울어진 프레임). 규칙·설정은 바꾸지 않았다.
      누적 88역할(PA61·62·67·68·75·77·78·15·21): v1 이름 기준 65·정답 48·오답 4·기권 36, ID 기준 57·정답 40·오답 0·기권 48, 타순 기준 21·정답 11·기권 33; v2는 같은 행에서 이름 정답 49·오답 3, ID 정답 41(차이는 PA15/4 한 행). 전체 588 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4f. **PA23·PA24 v1·v2 동일 절차 평가 — 행 단위 동일, 누적 차이 행 1건이라 v2 현행 전환 보류(v1 유지)** `[추가되었음 · 2026-09-28 · Claude]` 〔모델: Fable 5.1〕
      F-4e 결정 규칙을 그대로 적용하면 다음은 PA23(Megill 대 Olson, 4구, 타자 줄 기록 2/4)·PA24(Megill 대 Soler, 5구, 3/5)다(사전 등록 커밋에서 검증 기록으로 재계산). v2가 v1과 다른 행에서 오답 0을 유지하고 누적 차이 행이 2건 이상이면 v2를 현행(scripts74 기본 reader)으로 전환하고 PA6 정본 예측을 v2로도 저장한다; 아니면 v1 유지. v3는 실패 후보로 두고 다시 돌리지 않는다.
      2026-09-29 사전 등록 커밋(`e54d796`, Claude/Fable 5.1; 선점 `6368b81`): 대상 PA23·PA24(9프레임·18역할)와 전환 기준(v2 오답 ≤ v1·정답 ≥ v1·거짓 판독 0, 차이 행에서 v2 오답 0, F-4e 합산 차이 행 ≥ 2 → v2 현행 전환)을 고정. 코드·설정 변경 없음, v3 미실행. 상세는 [OCR 안내 F-4f 절](docs/PLAYER_IDENTITY_OCR.md).
      2026-09-29 평가 완료(`41881cb`): [PA23·24 직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa23_24.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa23_24.json) 18역할 = 투수 `MEGILL`×9, 타자 `OLSON`/타순 4×2·`SOLER`/타순 5×3, 배너 부재 4(23/1·23/4·24/1, 24/5는 MLB.tv 보드에 가림). 수동 대응 14 observed(모두 명단 유일, feed와 14/14 일치)·4 기권, 불일치 0.
      [v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa23_24_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa23_24_report.json) 실제 OCR 결과 18행 동일: 이름 기준 14·시도 14·정답 13·오답 1(23/3 `4. OLSO N`→`OLSO N`, 이름 안에 공백)·기권 4; ID 정답 13·오답 0·기권 5; 타순 정답 5·오답 0; 엔진 오류 0, 부재 프레임 거짓 판독 0. v2 규칙 발화 0건.
      **판정: v2 현행 전환 보류** — 전환 기준 (1)·(2)는 충족(오답 1 = 1, 정답 13 = 13, 거짓 판독 0, 차이 행 0)이나 (3) F-4e 합산 차이 행이 1건(PA15/4)으로 2건 미만. v1 현행 유지, v2 채택 후보 유지. 새 오인식 유형: 이름 내부 공백(`OLSO N`; 파서는 `DE LA CRUZ`형 이름을 위해 공백을 허용하므로 문법만으로 거를 수 없다).
      누적 106역할(PA61·62·67·68·75·77·78·15·21·23·24): v1 이름 기준 79·정답 61·오답 5·기권 40, ID 기준 71·정답 53·오답 0·기권 53, 타순 기준 26·정답 16·기권 37; v2(PA61은 v1 값)는 이름 정답 62·오답 4, ID 정답 54. 전체 588 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4g. **남은 규칙 충족 9타석 일괄 v1·v2 평가 — 차이 행 12건 전부 v2 정답, v2 현행 전환** `[추가되었음 · 2026-09-29 · Claude]` 〔모델: Fable 5.1〕
      2타석 단위는 커밋·검사 오버헤드가 커서 속도가 나지 않는다. F-4e 결정 규칙으로 아직 안 쓴 타석 전부(검증 기록 bug_text에서 사전 등록 커밋 시 재계산; PA26·31·34·37·38·46·49·55 등 후보)를 하나의 review/evalset(`..._pa_rest.json`)로 묶어 직접 읽고 v1·v2를 한 번에 채점한다.
      전환 기준은 F-4f와 같다(차이 행에서 v2 오답 0, 누적 차이 행 ≥ 2 → v2 현행 전환). 프레임 추출은 8프레임 단위로 병렬, OCR은 v1·v2만. 결과를 본 뒤 규칙·기준을 바꾸지 않는다.
      2026-09-29 사전 등록 커밋(`0d25acb`, Claude/Fable 5.1): 검증 기록으로 재계산한 대상 = **PA26·31·34·37·38·46·49·55·81**(49프레임·98역할; 투수 Megill·Schwellenbach·Brazobán·Ottavino·Díaz, 타자 d'Arnaud·Arcia·Martinez·Bader·Albies·Harris II·Olson·Laureano). 자료 이름 `..._pa_rest.json`, `..._ocr_v{1,2}_pa_rest_*.json`. 전환 기준 동일, 코드·설정 변경 없음, 대상 OCR 출력은 이 커밋 시점에 없다.
      2026-09-29 평가 완료(`4e111bb`): [PA_rest 직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa_rest.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa_rest.json) 9타석 49프레임 98역할. 투수 MEGILL×22(26/4는 OFFICIAL SCORING: PASSED BALL 그래픽이 투수 줄을 대체해 unreadable)·SCHWELLENBACH×10·BRAZOBÁN×6·OTTAVINO×5·DÍAZ×6, 타자 37건(D'ARNAUD 12·ARCIA 3·MARTINEZ 4·BADER 4·ALBIES 2·HARRIS II 4·OLSON 3·LAUREANO 5), 배너 부재 12. 수동 대응 85 observed(모두 명단 유일, feed와 85/85 일치)·13 기권, 불일치 0.
      [v1](docs/results/mlb_p0/game_747139_player_identity_ocr_v1_pa_rest_report.json)·[v2](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa_rest_report.json) 실제 OCR, 이름 기준 85: **v1** 시도 62·정답 41·오답 21·기권 36 / **v2** 시도 66·정답 53·오답 13·기권 32. ID 기준 85: v1 정답 41·오답 0·기권 57 / v2 정답 53·오답 0·기권 45. 타순 기준 37: 둘 다 정답 32·기권 17. 엔진 오류 0, 부재·대체 그래픽 프레임 거짓 판독 0.
      v1과 다른 행 **12건, 전부 v2 정답**: `9.ARClA`×3·`6.MARTlNEZ`×3·`2.ALBlES`×2(l→I), `l. HARRIS II`×4(타순 자리 `l` → 이름만 판독, 타순 기권). F-4e의 1건과 합쳐 누적 차이 행 13건, 차이 행 v2 오답 0.
      **판정: 전환 기준 전부 충족 → v2를 현행 reader로 전환.** scripts74 `--reader` 기본값 v2, 정본 PA6 v2 [예측](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_predictions.json)·[보고서](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_report.json) 추가(이름 9·0·3, ID 9·0·3: PA6에는 발화 사례가 없어 v1과 동일), v1은 `--reader v1`로 고정 보존, reader끼리 정본 파일 덮어쓰기 거부. scripts74가 해시 대상이라 저장된 예측/보고서 19세트를 재생성해 행 동일성을 확인했다.
      v2도 못 읽는 유형(둘 다 동일): SCHWELLENBACH×10은 crop 오른쪽 경계에 글자가 닿아 `possible_truncated_name` 기권(crop 폭 한계), BRAZOBÁN×6은 `Á`→`Å`로 문법 기권, D'ARNAUD의 아포스트로피→`t`(`DtARNAUD`×8)·탈락(`DARNAUD`, `7NARNAUD`) 오답 10, `6.1-AUREANO`×2 기권, `LAU REANO`·`4mSON` 오답, 81/3 투수 `Diu` 오답(ID는 사전 불일치로 기권). ID 오답은 여전히 0.
      누적 12타석 204역할: v1 이름 기준 164·정답 102·오답 26·기권 76, ID 기준 156·정답 94·오답 0·기권 110, 타순 기준 63·정답 48·기권 54; v2(PA61은 v1 값) 이름 정답 115·오답 17, ID 정답 107. 전체 588 passed, 2 deselected, Ruff 84경로 통과.
- [x] F-4h. **이름 OCR 남은 유형별 후속 결정과 교체 타석 규약** `[추가되었음 · 2026-09-29 · Claude]` 〔모델: Fable 5.1〕
      (1) SCHWELLENBACH형 긴 이름의 crop 폭(현재 64~168) 확장과 아포스트로피·악센트(`Á`→`Å`) 정규화는 **새 사전 등록(v4 후보)** 뒤 다른 타석에서 평가한다; 결과를 본 표본(PA34·37·46·49)에서 튜닝하지 않는다. (2) PA60·63·66·71처럼 교체 이벤트가 있는 타석은 생성기가 거부하므로, 이벤트 순서로 투구별 기준을 만드는 규약을 먼저 문서화한 뒤 해제 여부를 결정한다.
      (3) 이 경기의 규칙 충족 타석은 모두 평가했으므로 새 독립 성능은 다른 경기 영상이 있어야 한다. A-y 실제 응답 대기는 그대로.
      2026-10-01 완료(`2876d8f`): (1) 규약 — 교체·수비 전환 이벤트가 **모두 첫 투구 전**이면 PA matchup을 투구별 기준으로 수용하고(이 경기 교체 타석 13개 전부 해당), 첫 투구 이후 이벤트는 계속 거부([규약](docs/PLAYER_IDENTITY_PROTOCOL.md) '교체 타석 규약' 절, 생성기 검사 추가). PA60(Raisel Iglesias 대 Jose Iglesias, 투수 교체 후 4구) [직접 판독](docs/results/mlb_p0/game_747139_player_identity_review_pa60.json)·[평가셋](docs/results/mlb_p0/game_747139_player_identity_evalset_pa60.json) 8역할: 이름 6 판독(투수 IGLESIAS×4, 타자 2.IGLESIAS×2)·배너 부재 2, ID는 동성 IGLESIAS 모호성으로 8 전부 기권. [v2 OCR](docs/results/mlb_p0/game_747139_player_identity_ocr_v2_pa60_report.json) 이름 4 정답·0 오답·4 기권(타자 `2.1GLESlAS`×2: 새 유형 어두 `I`→`1`). 규칙 충족 타석이 아니라 누적 집계 밖.
      (2) v4 후보 사전 등록([OCR 안내](docs/PLAYER_IDENTITY_OCR.md) v4 절, `CONFIG_V4`, scripts74 `--reader v4`): 투수 crop은 글자 잉크가 고정 경계(x=168) 마지막 열에 있을 때만 잉크 끝+4px까지 확장(최대 230, 남색 피치클록 칸 앞 정지), NFKD 악센트 접기. 아포스트로피·이름 내부 공백 유형은 손대지 않는다. **규칙은 이 경기 개발 프레임(PA26·34·49·60)에서 만들었으므로 개발 재채점은 근거가 아니다**: 9타석 묶음에서 v2 대비 차이 17행(SCHWELLENBACH 9 정답·1 기권 `SCHVÆLLENBACH`, BRAZOBÁN 6 정답, 26/4 그래픽 기권 유지), 이름 오답 13→13, ID 오답 0, 거짓 판독 0; PA60은 v2와 동일. 첫 안(고정 x=230 확장)은 엔진이 넓은 빈 crop에서 MEGILL 13행·IGLESIAS 2행을 빈 문자열로 돌려 폐기(8폭 실험 기록 보존).
      (3) 사전 등록 시험은 F-4i(다음 미검토 영상, 기준은 F-4g와 같음). 해시 대상(reader·생성기·scripts74) 변경으로 저장 예측/보고서 22세트(v1 8·v2 9·v3 3·v4 2, 44파일)를 실제 Windows OCR로 재생성해 행이 전부 같음을 확인(변경은 predictions의 pipeline_code_sha256과 report의 predictions_sha256뿐). 전체 595 passed, 2 deselected.
- [!] F-4i. **새 미검토 영상에서 이름 OCR v4 사전 등록 평가** `[추가되었음 · 2026-10-01 · Claude]` 〔모델: Fable 5.1〕 — **보류(2026-10-04, 사용자 결정): SNY 전체 경기 영상 없음, 압축 경기 경로는 규약 변경이 필요**
      2026-10-04 경로 조사(Claude 세션 Opus 5.5, F-4i 작업·OCR 실행 없음, 대상 프레임 판독 없음):
      - 영상: MLB 공식 압축 경기(statsapi `game/<pk>/content`의 `mp4Avc`, 1280×720)에서 메츠 홈 SNY 중계 경기 823574(2026-09-15 BAL@NYM)의 화면이 747139와 같은 SNY 점수판 형식임을 프레임 2장으로 확인했다. 투수 `P:투구수` 줄과 타순·타자 줄이 있고, 2026판은 타자 줄에 포지션·당일 성적이 붙는다. 823571(9/19 PHI@NYM)은 원정 NBCSP 화면이라 해당하지 않는다.
      - Statcast: Savant `statcast_search/csv`(game_pk=823574)가 봇 검사 없이 받아진다(HTTP 200). manifest용 2026 Statcast는 구할 수 있다.
      - 걸림돌 네 가지:
        (1) F-4e 대상 규칙(4구 이상·전 투구 annotated)이 압축 경기(타석당 보통 1~2구)에서 대상 0이다. 압축 경기용 규칙을 OCR 전에 새로 사전 등록해야 한다.
        (2) 평가셋 builder(`src/data/player_identity.py` 455~473행)가 타석의 모든 투구 annotated를 요구한다. 투구 단위로 바꾸면 해시 대상 파일 변경이라 747139 산출물을 실제 OCR로 재생성해야 한다.
        (3) 보이는 투구마다 판단 프레임 규약 v2 timing, 두 갈래 검증 기록(`bug_text`), 점수판 리뷰를 만들어야 한다.
        (4) timing 계약이 영상을 `sources.full_game` 키(전체 경기 전제)로만 받는다.
      - 결과는 압축 경기 단일 투구 프레임 기준이라 F-4 계열과 조건이 다르다. 예상 규모는 Fable 작업 반나절~하루다.
      - 재개 조건: SNY 전체 경기 영상 확보, 또는 위 변경을 사전 등록하고 압축 경기로 진행하기로 결정.
      선행: 같은 SNY 화면 형식의 다른 경기 영상(MLB 권리 — 프레임은 로컬 outputs/에만 둔다)과 그 경기의 고정 feed·timing(판단 프레임 규약 v2). 절차는 F-4g와 같다(F-4e 결정 규칙으로 대상 타석 선정을 사전 등록 커밋 → 판단 프레임 직접 판독·review/evalset `--verify-frames` → v2·v4 별도 출력 실행·채점 → [OCR 안내](docs/PLAYER_IDENTITY_OCR.md) v4 절의 기준으로 판정). 영상이 없으면 시작하지 않는다. 그동안은 동료 의도 모듈 v0(`feature/intent-v0`: M0 완료, M1 JSONL 산출 뒤 M2 plate 평면 보정)와 I-0·I-5 동료 답변 대기를 진행한다.

## G. 효용 검증

- [!] G-1. **정책·보상 단위·동일성·평가 조건 합의 후에만 재개. 기존 양쪽 CI의 미입증 결론 유지.** 추천이 실제로 실점을 줄이는지 검증(팀원 C·D 산출물의 I-1·I-2 통과 후). 현재 CI가 0을 포함하므로 〔모델: Fable 5.1〕
      **개선 입증으로 발표하지 않는다.**
- **상시 유지 규칙 G-2** (기존 작업에서 분리; 완료 처리 아님). 경기 747139는 기존 test cohort 포함. 이 경기로 튜닝한 결과를 새 독립 성능으로 보고하지 않는다. 〔모델: Opus 5〕
- [!] G-3. **공동 평가 합의 대기; I-0의 정책 ID 확인과 연결.** 공동 표의 **통화·평가 프로토콜 합의**: RE24 버전(`re24-2023_2025-d20260911-s2325-82b008b`) vs WE %p vs `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Opus 5〕
      Statcast `delta_run_exp` 중 하나, 같은 타석의 짝지은 Δ OPE(팀원 `scripts/ope_compare.py` 방식), 검출 한계(≈0.002/결정) 명시,
      2026 freeze(9/27 이후) 재실행 대기 여부. 합의 전 두 CI를 나란히 놓고 우열을 말하지 않는다.

## H. 운영 · 엔지니어링 부채

- [x] H-5. **Claude/Codex 대조 감사 후 출처·경로·묶음 버전 보강 완료**(`2e8189c`). `[추가되었음 · 2026-09-27 · Codex]` 〔모델: Fable 5.1〕
      scripts69의 사용자 입력·출력 절대 경로 전파와 충돌 보호, URL/시각/해시 기반 프레임 캐시, A-y 자산 해시 v2 계약을 적용했다.
      원본 데이터 보존·출처 정정 사이드카 추가. 현재 주석·OCR 보고 재현 일치, 전체421 passed·2 deselected. [감사 결과·차이·한계](docs/CROSS_AGENT_AUDIT_2026-09-27.md), HANDOFF46 참조.

- [x] H-1. Arrow 문자열 변환 "멈춤" 원인 규명 → **멈춤이 아니라 크래시** (`bf5f06b`) — [docs/H1_ARROW_CRASH_2026-09-23.md](docs/H1_ARROW_CRASH_2026-09-23.md)
      `hashlib`/`urllib.request`(TLS 슬롯 8개) → `torch` → 첫 pyarrow 문자열 변환 순서에서 pyarrow 24 `arrow.dll`의 mimalloc이 미할당
      TLS 슬롯 63을 읽어 `0xC0000005`로 죽는다(4/4 결정적, 25초 정체 뒤). OpenSSL/OpenMP 중복 아님. 완화 채택: `src/__init__.py`가
      Windows에서 torch보다 먼저 `pyarrow`를 import(3/3 정상), 최악 순서 새 프로세스 회귀 테스트 추가. 안전망 `ARROW_DEFAULT_MEMORY_POOL=system`.
      미검증: 슬롯에 1을 쓰는 torch DLL의 정체, 20초 정체의 정확한 원인, 최신 pyarrow에서의 수정 여부.
      현재는 59번 서버 + HTTP 경로를 정상 경로로 유지한다.
- **상시 유지 규칙 H-2** (기존 작업에서 분리; 완료 처리 아님). 주석 모듈의 지연 import 유지 (되돌리지 않는다. 회귀 테스트 있음) 〔모델: Opus 5〕
- [x] H-4. 주석·OCR 유지보수 도구: OCR 버전별 재채점+출처 기록을 한 명령으로(`scripts/70`), 판단 프레임 검토 시트 생성기(`scripts/71`). `[추가되었음 · 2026-09-25 · Claude]` 〔모델: Fable 5.1〕
      지금은 병합마다 v1·v2 predict/score/negatives와 두 provenance를 손으로 갱신한다. 동작은 기존 66 명령·기존 provenance 스키마와 같아야 하고 시험을 둔다.
      (`43c4d45`) Fable 5.1 워크플로가 구현, 세션 모델 검토 3관점×2라운드 + 다듬기 1라운드. `scripts/70_refresh_ocr_reports.py`(버전별 66 predict/score/negatives·반복 예측·
      provenance, 기준 커밋을 SHA로 확인, 필드별 오답·음성 거짓 판독·변경/삭제 행·평가셋 누락 행이면 exit 1)와 `scripts/71_timing_review_sheet.py`, 순수 함수
      `src/vision/ocr_reports.py`·`review_sheet.py`, 시험 23건. 동등성: 입력이 같을 때 v1·v2 예측·채점·음성 파일이 커밋본과 바이트 동일.
      검토에서 잡힌 결함(오답 검사가 all_fields만 봄, 잘못된 기준 커밋이 조용히 '이전 없음'이 됨, 복구 안내가 미커밋 입력까지 되돌림)은 모두 고쳤다.
      provenance에 `carried_from_previous`·`new_rows_comparison`(고정 키)·`"carried": true` 산출물이 생길 수 있다(스키마 id 불변). 사용법은 docs/MAINTENANCE.md.
      `check_project.py`의 lint 범위를 scripts 64–71·`src/vision`·점수판/주석 시험까지 넓혔다(이미 모두 통과, 이후 변경이 흐트러지지 않게).
- [!] H-3. **MLB 통합 운영 검증 이후로 보류.** KBO 확장 (MLB 완성 후) 〔모델: Fable 5.1〕

## I. 팀원 산출물 통합 (C·D 이관에 따라 신설)

- [!] I-0. **팀원 합의·기준 버전/실행 번들 대기(원문 수신 완료):** S의 정확한 소스 revision·배포 revision·API 필드·지원 범위·반출 형식·양쪽 계층별 정본을 합의한다. 서빙 `a6dffaea…`/2026 OPE `c13cc989…`/S6-v3 `6eb85ba7…` 대응 근거도 요청한다. 아래 C/D 상세는 9/22 연구 계약 기록이며 S 채택 확정이나 우리 쪽 구현 지시가 아니다. 〔모델: Opus 5〕
      시간 분할 증빙 / D: 프로필 파일 경로·스키마·경기 시점 이전 자료만 썼다는 증빙·신규 투수 방침.
      파일 경로·형식·검증 명령을 문서로 확정한다. **결정 필요(사용자·팀원)** `[추가되었음 · 2026-09-22 · Claude]`
      → 합의 항목은 [docs/TEAMMATE_PITCHEEZY_2026-09-22.md](docs/TEAMMATE_PITCHEEZY_2026-09-22.md) §6·§7: 투구 식별(play_id 조인표), 결과 클래스 대응표, 통화, 2026 OPE 전용 규칙,
      서비스 요청/응답 스키마 어댑터, 관측자 앱 12카운트 배치 요구, 명칭(우리=transition-models P0). I-1은 "팀원 10종
      서비스 어댑터로 UI 파울 분리 확률"로 재정의하는 안은 **9/22 제안**이다. 최신 S 선택 비중에는 적용 금지다.
- [!] I-1. **사건확률 계약·보정 자료 수신 대기. S 구종 선택 비중으로 대체할 수 없음.** C 산출물 수신 시 통합 검증 — 시간 분할·투구 ID 정렬 확인, 독립 보정과 CE/Brier 재현, 기존 10종 〔모델: Fable 5.1〕
      체크포인트와 혼용 금지 확인. 통과 전에는 UI 독립 스트라이크·볼·파울을 null로 유지한다. `[추가되었음 · 2026-09-22 · Claude]`
- [!] I-2. **프로필/모델 교체 합의 뒤 재개. 아래 322상태 재점검은 우리 구형 운영 경로 갱신 시에만 적용. S 지원률은 I-service2/I-release1에서 별도 확인.** D 산출물 수신 시 통합 검증 — 경기 시점 이전 자료만 사용했는지 확인, `scripts/62_check_game_service.py`로 〔모델: Fable 5.1〕
      322상태 재점검(추천/보류 수 변화 기록). `[추가되었음 · 2026-09-22 · Claude]`
- [x] I-3. 우리 manifest·timing JSON → 팀원 Video Lab **스키마 v2 제안서** — [docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md](docs/VIDEO_LAB_SCHEMA_V2_PROPOSAL.md) (`9271231`, **미전송**) `[추가되었음 · 2026-09-22 · Claude]
      Workflow: Opus 5 작성 + 검증 에이전트가 두 레포 파일을 직접 읽어 대조(1차 5건·2차 3건 반박 → 수리), Fable 5.1 세션 확인.
      내용: `pitch_id="{game_pk}:{at_bat_number}:{pitch_number}"`(팀원 카탈로그 `build_catalog.py:159`와 같은 형식) + `play_id`·
      `decision_seconds`·`uncertainty_seconds`·`note`·`manifest_sha256`·`source_media{clip_start_seconds}` 추가, `release_time`(배제 경계)
      vs `release_seconds`(사건 추정) 구분과 파생 규칙, `usable_for_tracking`·SSD 경로 하드코딩 해제 요청, 양쪽 검증 체크리스트 12항, 질문 9개.
      조인표는 실제 파일로 제공: `docs/results/mlb_p0/game_747139_pitch_timing_join.json`(`scripts/68_export_pitch_timing_join.py`, 테스트 포함).
      미해결: 원격 스트리밍 소스의 `clip_sha256` 요구(Q3), fps 출처(Q4), 시연 경기 747139 vs 코호트(Q8, I-5와 연결).
- [!] I-4. **S/R 중 소비할 특성 계약·as-of 증빙 수신 대기.** 타자 특성은 팀원 archetypes/refresh 스냅샷을 소비하는 어댑터(시간 정합 가드 유지) — F-2 대체. `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Fable 5.1〕
- [!] I-5. **새 S 전체 지원 범위·통합 대상 최종 확인 대기:** 849843 S262구 수신·첫 타석3구 영상 연결은 I-service2/3로 완료했으며 같은 원문을 다시 요청하지 않는다. 남은 것은 최신 서비스의 전체 경기 목록/지원 범위와 최종 통합 대상 합의다. 기존 시연은 E-site5에 보존한다. 아래 6명/42경기 후보는 9/22 R의 잠정 기록이며 최신 S 전체 범위로 사용하지 않는다. 〔모델: Opus 5〕 `[추가되었음 · 2026-09-22 · Claude]`
      (2026-09-22) 지원 투수 6명은 제안 파일(`mlb_cohort_proposal.json`) 기준이라 **잠정**이다. 실제 `/metadata` 출력 또는 동료가 보낸 번들 `metadata.json`으로만 확정한다.
      400을 받는다. (a) 팀원 코호트 확장 (b) 우리 주석·평가셋을 팀원 12경기 중 하나에 추가 (c) 두 데모 분리 유지 — 사용자·팀원 결정.
- [x] I-6. **결과 클래스 의미 계약 코드화 완료**(`ebde980`). `[추가되었음 · 2026-09-22 · Claude]` 〔모델: Fable 5.1〕
      `src/inference/outcome_contracts.py`: 우리10종·서비스10종·연구11종·관찰8의 schema/순서/의미·근거 고정, 확률·1:1 투구 키/play_id 검사.
      이름 객체는 키로, 배열은 명시된 정확한 순서로 검증한다. 비유한값·bool·누락/추가/중복·합계 오류를 거부하고 재정규화하지 않는다.
      다른 계약 전체로의 자동 변환은 거부한다. 포수 타격 방해·파울 번트 삼진·미지원 인플레이 반례와 한계는 [계약 안내](docs/OUTCOME_CLASS_CONTRACTS.md).
      동료 검토 커밋 `9d09694`의 고정 소스와 합성 입력 검증이며 실제 HTTP/모델/번들 검증이 아니다. C/D·I-0/I-1/I-2/I-5 의존성 유지.
      신규69검사·문서 사용 예제 통과, 전체490 passed·2 deselected·Ruff76경로 통과. 기존 UI/주석/OCR 산출물 변경0.

---

## Claude 모델 자동 배정

항목마다 붙은 `〔모델: …〕` 태그는 Claude 착수용 배정이며 실제 작성자 기록이 아니다. 실제 작성·검토 모델과 고정 커밋은 각 작업의 검토 기록/영수증을 따른다. Codex는 자기 모델로 진행한다.

태그가 그 단위를 수행할 Claude 모델이다. 모델 id는
`Opus 5` = `claude-opus-5`, `Fable 5.1` = `claude-fable-5-1`.

```bash
uv run --frozen python scripts/checklist_model.py --next        # 다음 단위의 모델 id
uv run --frozen python scripts/checklist_model.py A-4 --json    # 특정 항목
```

Claude Code 세션이 항목을 착수하는 순서:

1. 위 명령으로 태그 모델을 얻고 `get_session self`의 `model`과 비교한다.
2. **일치**하면 상태 요약 표의 파일 수정 권한을 자기 이름으로 바꿔 커밋하고 작업을 시작한다.
3. **불일치**하면 작업을 시작하지 않는다. 세션은 자기 모델을 바꿀 수 없으므로(앱 정책)
   `spawn_task`로 `[모델명] 항목ID 제목` 칩을 만들어 사용자가 클릭하게 하거나, 사용자에게 모델
   메뉴에서 태그 모델을 고른 뒤 "계속"이라고 하도록 요청한다. 다른 세션이 이미 떠 있으면
   `set_session_model(session_id, model)`로 그 세션의 모델을 태그대로 맞춘다(사용자 승인 1회).
   **또는(2026-09-23 추가, A-4에서 검증)** 사용자가 Workflow(ultracode)를 켠 세션이면 그 단위의 실작업을
   `agent(..., {model: 태그 모델 id})`로 돌리고, 세션 모델은 독립 검증·통합·커밋만 맡는다. 이때 검증은
   결과를 반박하는 별도 에이전트(투구별 2렌즈 등)로 하고, 상태 요약 표에 "워크플로 = 태그 모델"을 적는다.
4. 단위를 끝내면 다음 단위의 태그를 같은 방법으로 확인하고, 모델이 달라지면 3번대로 넘긴다.

이 Windows 노트북의 Claude에는 `/checklist-unit` 사용자 스킬(`~/.claude/skills/checklist-unit`)이
위 순서를 한 명령으로 수행한다. Codex는 태그와 무관하게 자기 모델로 진행한다.

## 도구 교대 프로토콜 (Codex ↔ Claude)

한 번에 **한 도구만** 파일을 수정한다. [상황판·우편 규약](docs/COLLABORATION_PROTOCOL.md)에 따라
시작 시 양쪽 board/우리 열린 mail 조회, 착수 시 우리 board+CHECKLIST 선점, 종료 시 우리 board 댓글과 선점 해제를 함께 수행한다.
board는 요약이고 CHECKLIST/커밋/검증 문서가 작업 근거다. 넘길 때는 아래를 남긴다.

1. 이 파일의 상태 요약 표 갱신 (최신 커밋 / 파일 수정 권한 / 카운트)
2. `docs/MLB_P0_HANDOFF.md`에 완료·미완료, 실행한 검사와 **실제 결과**, 막힌 이유
3. 다음 도구가 그대로 붙여 넣을 수 있는 첫 실행 명령

### 사용 한도로 중단될 때

- 한도 약 20%: 인계 기록을 먼저 갱신한다.
- 한도 약 10%: 새 대형 작업을 시작하지 않는다. 진행 중 변경·로그를 보존한다.
- 중단 시점의 부분 작업은 **커밋하거나**(검증을 통과한 단위만) 미커밋 상태로 남기되,
  이 파일에 `[~]`와 어디까지 했는지 적는다. 5시간 뒤 자동 재개를 보장하지 않는다.
- 추가 과금·구독 변경·API 전환은 사용자 승인 없이 하지 않는다.
- **인계 기준** (2026-09-22 Claude 추가): `[~]` 항목의 착수 시각 이후 **새 커밋 없이 5시간**이 지나면
  다른 도구는 최신 board·Git 상태와 실제 작업 지속 여부를 먼저 확인한다. 시간 경과만으로 현재 작업자의 변경을 덮어쓰지 않는다.
  인계가 가능한 경우 `git fetch` 후 마지막 커밋 상태에서 그 항목을 이어받고, 상태 요약 표의
  '파일 수정 권한'을 자기 이름으로 바꾼 뒤 시작한다. 브라우저 localStorage의 미내보내기 주석은
  인계되지 않으므로, 타석 하나가 끝날 때마다(부분이어도 `check`를 통과하면) JSON을 내보내 커밋한다.

### Codex가 이어받을 때 확인 순서

```bash
git fetch origin && git status --short --branch && git log -5 --oneline
```

`reset --hard`, `git clean`, 강제 푸시로 상태를 맞추지 않는다.
미커밋 변경이나 로컬 전용 커밋이 있으면 먼저 대조·보존한다.
그 다음 상단의 현재 계획과 상태를 확인한다. I-service2 실제 수신·로컬 연결은 완료했다. `--next`는 실행 가능한 등록 항목이 없으면 종료1이다. 모델/API 실행 번들과 정본 합의, 추가 사람 검토, 새 기기, 독립 영상 등 해당 대기 사유가 해결된 경우에만 항목 상태를 바꾼다. 아래 9월 순서는 역사 기록이다.
2026-09-26 기준 A-7~A-14(9회초까지 303구), F-3a(OCR v2)·F-3c(v3 실패 기록)·F-3d(v4 사전 등록, A-10에서 판정 실패 기록)·H-4(유지보수 도구)는 완료됐다.
**2026-10-04 OCR 경로 기록:** F-4h 완료 커밋 `2876d8f`의 교체 타석 규약·PA60 평가셋·v4 후보를 이번 통합에 포함했다. 현행 이름 OCR은 v2이며 v4는 개발 후보다. F-4i는 사용자 요청으로 보류했고 재개 결정·새 영상이 필요하다. A-y는 별도의 사용자 보류다. 최신 CV·서비스·통합 우선순위는 문서 상단을 따른다.
자세한 첫 실행 절차는 [docs/CODEX_RESUME_PROMPT.md](docs/CODEX_RESUME_PROMPT.md)를 따른다.

## 유지해야 할 정보 경계

- 투구는 키 + `play_id`로 연결한다. 배열 순서·CSV `iloc`·옛 파일명을 믿지 않는다.
- 현재 투구의 실제 구종·구속·회전·도착 위치·결과를 투구 전 입력에 넣지 않는다.
- 독립 스트라이크·볼·파울과 목표 위치는 미지원. null을 0%로 바꾸지 않는다.
- 원본 영상·대형 데이터·모델 캐시·자격증명을 Git에 넣지 않는다.
- 철회된 맥락 효과(+26.5pp) 주장과 과거 collapse 해석을 복원하지 않는다.
