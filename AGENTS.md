# SmartPitch MDP Transition Probability Models

## 개인 검토 사용성 개선 완료 — 2026-10-08

CV-29: 미완성 초안 저장·복원과 현재 프레임 복귀 완료. 최종 사람 응답은 기존 규약으로 검사한다.
H-11: stdlib 전용 실행 도우미·자료 검사·빈 포트·현재 컴퓨터 주소 안내 완료.
새 팩 `outputs/cv_review_20261008_ui_v3/reviewer/`와 비공개 휴대용 ZIP을 준비했다.
관련145passed·Ruff163경로·JS구문 통과. 합성2장 브라우저에서 저장→새 창 복원→최종 내보내기 확인.
기존65파일 SHA 불변, 기존26응답을 새 팩에서도 수신 검사 통과했다. 새 사람 판독은 수행하지 않았다.
ZIP 압축 해제·표준 라이브러리 단독 검사까지 Windows에서 확인했으며 실제 Mac 사용 확인은 남아 있다.
[검증 기록](docs/results/cv_independent_20261008/review_draft_launcher_v1.json).
수정 권한 반납. 아래 추가 구현 없음/진행 중 기록은 과거 시점의 이력이다.

## 독립 수정·이관 완료 — 2026-10-08

H-8 응답 불러오기(`3ee4b93`), H-9 경기/보정 결속(`02fedaf`), CV-28 부분 가림 이유(`7745f0e`),
H-10 명시 경로·측정된 RMS 0(`f1ec3b9`), H-port4 최신 소스49개 이관 v2를 완료했다.
이관 소스 `bf1fb5d`; 압축 해제 Python244passed/1skipped·Node68passed, Windows/Linux/macOS
전체 CPU각1971passed/8skipped/2deselected. 기존 ZIP·사람 응답·M3·관측 보고서는 보존했다.
[새 이관 기록](docs/handoff/delivery_v2.json)을 사용하되 문서 경로는 저장소 루트 기준이다. 전송·공개 배포는 하지 않았다.
현재 추가 독립 구현 단위는 없으며 수정 권한을 반납했다. 실제 새 S 응답→I-service2,
추가 독립 사람 응답→CV-6/A-y, 새 영상/독립 라벨러→CV-7, 새 기기 실행 확인 순으로 조건에 맞춰 재개한다.
사용자 중지 지시는 없지만 자료를 만들어 대기를 해제하거나 동일 실험을 반복하지 않는다. 아래 기록은 과거 이력이다.

## CV-6b 저장 경로 감사 완료 — 2026-10-08

기존26기권의 저장 A/B52행·새 사람 응답26행 연결과 당시 결정26건 재현을 완료했다.
두 미트 점이 있어도 plate가 없어 제외된3건, 다른 프레임의 좌표거리 초과6건 등은
**처리 경로의 설명**이며 시각적 원인/AI 오류율이 아니다. [재현 보고서](docs/CV_SAVED_PROCESSING_ROUTES_20261008.md).
H-7 `4111eed`는 저장소 날짜 검사 수정이며 공개 Site 재배포는 하지 않았다.
수정 권한 반납. 사람 원응답/M3는 고정, 새 S 원문→I-service2, 독립 판단→CV-6/CV-7로 재개한다.

## CV6 첫 사람 응답 처리 완료 — 2026-10-08

실제 응답1개·26장 모두 marked/full, 미검토0. 출처·좌표 범위 검사와 CV26 원본 연결을 통과했다.
자세는 원문 resting18/moving5/presented_target2/unknown1을 보존했다. 사용자가 지적한 낮은 준비 자세와
휴식/움직임의 모호함은 전역 피드백으로 별도 기록했다. 자세를 임의 재분류하거나 목표/의도 정답으로 쓰지 않는다.
원본9,035bytes·SHA 및 검토 팩31파일 불변, 새 점26개 준비·학습 선택0. 사람 간 일치도·독립 정확도 미측정.
CV-6a 수신과 CV-6b 저장된 처리 경로 감사, H-7 날짜 검사 수정은 완료했다. CV-6의 시각적 원인 확정·합의는 미완료다.
원응답은 `outputs/cv_review_response_20261008_v1/`에 비공개 보존했다. 아래 응답0 기록은 수신 이전 이력이다.
[수신 결과와 자세 해석](docs/CV_FIRST_HUMAN_REVIEW_20261008.md). 선점 `61fe8c6`, 완료는 같은 커밋.

## H-6 완료 — 수동 시연에서 최신 입력 보존 (2026-10-08)

예시를 불러오는 동안 바꾼 볼카운트가 늦은 응답에 덮어써지는 오류를 재현해 수정했다.
초기 연결·예시·예측의 지연/역순 응답과 오류는 최신 입력 및 요청의 상태를 덮어쓰지 않는다.
검사: 관련 34 passed(11.96초)·Ruff159경로·JS구문 통과; 새 14시나리오는 수정 전 12실패/2통과 → 수정 후 14통과. 모델 재학습·정확도 측정·공개 Site 배포는 하지 않았다.
사용자는 외출 중이므로 CV6 실제 사람 응답0·미검토26을 유지한다. 검토 화면의 입력을 대신하지 않았다.
다음 독립 단위는 H-7(공개 화면 수신기의 존재하지 않는 날짜 허용 오류)이다.
팀원 새 S 원문·CV6 실제 응답이 오면 각각 I-service2·CV-6으로 재개한다.

## CV27 완료 — 본인이 시작할 사람 검토 (2026-10-08)

CV6의26장 재검토는 본인 영상 파트이며 팀원 모델/API 답변이 선행 조건이 아니다.
한 사람의 응답은 개발 자료로 사용하고, 두 사람 가용성 합의와 CV7 새 영상 독립 평가는 구분한다.
[사용자 순서 안내](docs/CV_HUMAN_REVIEW_START_HERE.md)와 새 한글 UI 팩 `outputs/cv_review_20261008_ko_v1`를 준비했다.
로컬 주소 `http://127.0.0.1:8792/`는 reviewer 폴더만 제공한다. 실제 사람 판정은0·미검토26이다.
원래 부분 가림 이유 필수 규약을 JS/Python 검사가 누락하던 오류를 고치고 오류 프레임 번호를 표시한다.
기존 팩31파일·26이미지·manifest·빈 응답 양식 불변, 응답 schema 동일. 관련75tests 통과.
본인의 새 JSON이 오면 검사→집계→CV26 연결로 진행한다. 팀원 코드/API·M3·기존 라벨은 변경하지 않았다.

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

## STATUS 비교 후 현재 계획 — 2026-10-07

사용자 요청에 따라 [CHECKLIST](CHECKLIST.md) 상단에서 계층별 재사용안과 완료 조건을 재정렬했다.
우리 미트/영상/계약/화면 자산은 보존하고 S 피드·추천·서비스를 통합 후보로 검토한다.
S 자체 점검 보고를 우리 실행 검증으로 취급하지 않으며 최종 정본/역할은 I-0 합의 전이다.
H-port1 완료: 기준 `441f5e5`의 소스48개와 외부자료 목록·실행 안내를 포장하고 압축 해제 검사를 통과했다.
이관 안내는 `docs/handoff/README.md`, 전달 식별자/검사 결과는 `docs/handoff/delivery_v1.json`이다.
새 S 원문이 오면 I-service2(로컬 한 타석 계약 대조·표시)를 명시해 재개한다.
CV 부분 진행과 OCR 확장은 보류, CV6 사람 응답과 CV7 독립 자료는 대기로 바로잡았다.
10/7 H-port1 직후에는 자동 다음 작업이 없었다. 10/8 사용자 지시로 우리 독립 작업을 재개했으며 현재 순서는 상단을 따른다. 팀원 C/D·미수신 S 계약을 임의 재개하지 않는다.
M3·완료 이력·C/D 팀원 담당은 유지한다. 우리 이관 도구/검사만 추가했으며 팀원 저장소·공개 배포는 바꾸지 않았다.
아래 절은 이전 시점의 기록이며 현재 순서보다 우선하지 않는다.


## S 응답 통합 준비 완료 — 2026-10-07

우리 `feature/intent-v0`에 로컬 `pitcheezy-service-game-v2` 검사·정규화 도구를 추가했다.
팀원 2026-10-07 STATUS를 기준으로 만든 **임시 계약**이며 실제 S 원문·서버는 확인하지 않았다.
추천 선택 비중·투구 키·사전상황을 보존하고 실제 결과는 공개 단계에 분리한다.
비null `catcher_setup`의 구조는 미확인이라 x로 해석하지 않는다.
실행법과 제한은 [통합 안내](docs/SERVICE_GAME_V2_INTEGRATION.md)에 있다.

다음은 실제 ready/unsupported/missing 응답·버전·SHA와 셋업 계약을 받은 뒤 이 도구로 대조하는 것이다.
이 단위 직후에는 CV 진행 표시가 남아 있었다. 현재는 상단 I-plan1에서 대기/보류를 정리했다.
정책 ID와 추천 계산 시점의 검증은 별도이며, 합성 테스트 통과를 실제 API 연결로 보고하지 않는다.
팀원 코드·서버·공개 사이트·기존 M3/JSONL은 변경하지 않았다. CV6 실제 사람 응답 대기는 유지한다.
아래 CV24 등 기록은 이전 작업 이력이다.

## CV24 완료 — 정확한 프레임 추출 가속 (2026-10-07)

우리 저장소 `feature/intent-v0`에서만 작업했다. 사전등록 `d1e2c4f` 뒤 같은14장·교대순서로
28회 추출 비교: PTS/MD5/JPEG 전부 동일, 중앙 2.185→0.848초(61.2% 감소).
같은14시각 모델 루프1회는 14수락·오류0·5초이내14/14,
발행중앙3.883초·최대4.047초. 기존입력/후보14개동일, 확정미트0 유지.
입력전준비18.563초·전체명령92.192초도 별도로 기록했다.
CV23 과거루프와의비교이며 라이브보장/정확도개선은 아니다.

관련140tests·새19tests(실제합성영상2건포함), 전체CPU `1667 passed, 5 skipped, 2 deselected, 2 warnings in 407.57s (0:06:47)`·Ruff145경로 통과.
실패재시도없음·구형영수증호환·입력/코드SHA검사유지. M3입력25SHA불변.
팀원 코드/API·공개사이트·기존JSONL 고정. Codex 수정권한반납.

다음핵심은CV6 실제26장사람응답→검사/집계→미트전용모델개발기준이며, CV7은미열람영상과
독립라벨러가필요하다. 26장은기존84개사람점의부분집합이라새이미지26장이추가된것이아니다.
기존도구로준비완료인사람검토를AI판정으로대체하지않는다. 추가속도반복은우선하지않는다.
[실측·재현·남은작업](docs/CV_EXACT_FRAME_SEEK_V1.md).


## CV23 완료·다음은 판독 품질 — 2026-10-07

연속 방송66.81675초의4,005프레임을 누락 없이 검증하고, 사전등록 `e5a1c58` 뒤
고정14시각을 실제처리했다. 수락14·오류0·미시도0, 단일후보5·복수1·없음8·확정미트0.
5초이내5/14·발행중앙5.375초·최대9.859초·전체명령99.922초다. 늦은2응답도구간끝뒤로보존했다.
기존짧은10장실험의속도를긴구간서비스보장으로확대하지않는다. 물리적입장/독립정확도/live미완료.

전체 CPU `1648 passed, 5 skipped, 2 deselected, 2 warnings in 403.09s (0:06:43)`·Ruff144경로, 관련58tests 통과. M3입력25SHA불변.
새구간coverage CLI와보고서표본수설명수정 완료. 수정전보고서로컬보존·문구외수치동일·추가모델호출0.
팀원 코드/API·사이트·M3·JSONL 불변. CV23완료는CV5a4엄격전체타석완료와구분한다.

다음품질단계는CV6 실제26장사람응답이다. 검토UI는 http://127.0.0.1:8788/ 에로컬만열었으며
검토자ID빈칸·원응답0유지. 사람대신클릭하지않았다. 저장응답검사→집계→목표전용모델판단순서다.
CPU검사는모델정확도가아니다. 추가속도반복보다판독품질을우선한다. Codex수정권한반납.
[실측과재현](docs/CV_BROADCAST_INTERVAL_REPLAY_V1.md).

## CV20–22 완료·다음 품질 검토 — 2026-10-07

최신 지시에 따라 사용량 보존 하한 없이 우리 CV 작업을 진행했다. 팀원 코드/API,
공개 사이트, M3, 기존 JSONL은 변경하지 않았다.

CV20 한 번은 5초 이내10/10이었다. CV22 사전등록 `cf355ec` 후 같은10장을 새 프로세스에서
세 번 반복한 결과는 **29/30**, 모든10개가 기준을 만족한 실행은 **2/3**이다.
각 실행의 중앙값4.297/4.368/4.407초, 최대4.828/5.110/4.860초. 수락30·오류0·미시도0,
입력/출력동일30/30·확정미트0. 고유10장의 개발 반복이며 지속적인 실시간 성능은 미검증이다.

CV21 기기별 계획 CLI와 실제 준비 완료, 관련99tests·Ruff142 통과. 코드 `cf355ec`의
Linux/macOS CI는 각각1632 passed·6 skipped·2 deselected다. Mac 실기기 모델 실행과 구분한다.
원래 M3 입력25개 SHA 불변. [반복 결과](docs/CV_LOCAL_REPEATABILITY_V1.md),
[기기별 준비](docs/CV_LOCAL_MACHINE_PLAN_V1.md).

다음 품질 작업은 CV6 준비된26장에 대한 실제 사람 응답이다. 기존86장 검토 완료와 구분하며
새 응답은 아직0건이다. CV5a4 전체 타석 경계/연속 검토, CV7 미열람 독립 검증도 남았다.
독립적으로 가능한 속도 후속은 저장 기록에서 나타난 후반 프레임 추출 비용 점검이다.
범용 후보 모델의 서비스 채택은 보류한다. 모델 작업과 worker는 종료했고 수정 권한은 반납했다.
로컬84장 비교 화면은 127.0.0.1:8786에 남겨두었다.

## CV-12–19 완료 기록·다음 품질 검토 — 2026-10-07

CV18 사전등록 `7d75ed0` 푸시 후 단1회 실행했다. 준비20.015초, warm루프51.547초,
명령 전체76.115초(45초 입력 일정 포함), 발행중앙4.9845초·범위4.516–6.531초·≤5초5/10.
10수락·오류0·미시도0, 단일후보4·복수2·없음4·확정미트0. 합성warmup5회/engine1개,
연구프레임은READY후만 제공, worker정상종료확인. 세 방식 출력10/10동일, 정확도 주장은 없다.
[준비·실측 결과](docs/CV_LOCAL_READY_V1.md). 범용모델과84점tinyCNN은 채택보류를 유지한다.
CV16의84장 로컬 비교 화면은 [사용법](docs/CV_LOCAL_POINT_REVIEW_V1.md)을 따른다.
CV19 실제Linux/mac CI성공, 전체Windows1563 passed·5 skipped·2 deselected(401.33초),Ruff139경로.
최종코드 `7d75ed0` Linux/mac CPU도 각각1562 passed·6 skipped·2 deselected로 성공했다.
M3입력25개 SHA 불변과 이번턴의 기존 M3/JSONL/시연 추적파일 변경0 확인. 팀원 코드/API·사이트·JSONL 고정.

다음 품질 단위는 CV6 준비된26장에 대한 실제 사람 응답이다. 기존86장 사람검토 완료와 구분한다.
새 규약의 미트중심/가림/자세/기권을 기록하고 익명 원응답을 검사한다. 기존AI와 사람점은 보이지 않는다.
개발26장만으로 독립 정확도를 주장하지 않는다. 응답 대기 중 CV5a4 전체타석 범위 확인과
출처·시각 보호를 유지하는 영상공급 개선은 가능하다. 새학습/자동서비스 채택은 하지 않았다.
수정권한 반납, 잔여20% 하한 보존. 모델 작업은 종료됐고 로컬 비교자료 서버만127.0.0.1:8786에 남아 있다.

첫 확인은 `git fetch origin`, `git status --short --branch`, `git log -5 --oneline` 후
이 절과 CHECKLIST다. 기존 실험 출력에 덮어쓰기/재시도하지 않는다.

## CV-18 실행 전 고정·CV-19 원격 검사 완료 — 2026-10-07

CV-18은 같은10시각/모델/설정에서 입력 일정 전에 검정1280×720 합성이미지5회로 준비한다.
코드와 규약을 실제 호출 전에 고정했다. 준비 timeout60초·실패보존·재시도없음,
시작 비용과 warm loop를 분리하며 명령 시작→종료 전체 시간도 외부에서 잰다.
새ready20 + 기존worker28 합성검사 통과. 실제모델호출0 상태에서 사전등록했다.
[규약](docs/CV_LOCAL_READY_V1.md). 기존 CV-17은10수락·총72.766초·발행≤5초0/10이었다.
CV-19 수정 `5b108f2`의 실제Linux/mac CI는 각각1542 passed로 성공했다.
팀원 영역·사이트·M3·JSONL 고정, Codex계속·잔여20% 보존.

## CV-14 실제 연결 완료·CV-15/16 준비 — 2026-10-07

로컬 글러브 shadow 어댑터를 기존 10시각 영상 루프로 실제 실행했다. 10수락·오류0,
단일후보4·복수2·후보없음4이며 확정 미트 좌표는0이다. 전체233.562초, 예정→발행≤5초0/10.
초기화 중앙15.041초로 매 프레임 새 모델을 여는 비용이 컸다. 실시간 성공으로 세지 않는다.
사전등록 `1d8fffc` 푸시 후 실행, 입력10SHA·코드·응답 결속 검증 및179tests/Ruff 통과.
[연결 기록](docs/CV_LOCAL_OBSERVER_V1.md). 다음은 CV-15 기존84점 기반 조건부 회귀와 CV-16 로컬 비교 viewer다.
팀원 영역·사이트·M3·JSONL 불변. 잔여20% 하한 유지, Codex 작업 계속.

## CV-13 완료·CV-14 연결 / CV-15 조건부 회귀 준비 — 2026-10-07

고정 로컬 비교 1,118회, 오류/미시도 0. SSD 전체/crop 후보 0/86, Faster 전체 16/86·crop 5/86.
기존 점과 조건부 거리 중앙값 151.93/64.61px로 범용 COCO 모델을 서비스 미트 판독기로 채택하지 않는다.
GPU 반복 처리는 약 0.12–0.39초, 최초 모델 준비는 약 15.4–18.1초로 분리한다.
사전 등록 `8ac36f7`을 원격에 푸시한 뒤 실행했다. 결과는 [로컬 탐지 결과](docs/CV_LOCAL_DETECTOR_RESULTS_V1.md)에 보존했다.
다음은 확정 미트 없이 후보/기권/시간을 연결하는 CV-14와, 기존 84개 점을 이용한 조건부 위치 회귀
CV-15 준비다. 추가 사람/미열람 검증·전체 타석·실시간 완료로 세지 않는다. 잔여 20% 하한 유지.
팀원 모델/API·사이트·M3·기존 JSONL 불변. Codex 작업 계속.

## CV-12 준비 완료·CV-13 비교 조건 고정 — 2026-10-07

로컬 COCO 글러브 탐지 후보 2개를 준비하고 원본 86장의 SHA 및 기존 사람 라벨 연결을 확인했다.
GPU 통합 점검은 검은 이미지 모델별 1회로 제한했다. 실제 86장 모델 호출 전 비교 조건을 고정한다.
84개 기존 점은 조건부 위치 차이 기준이며, 2개 과거 기권은 현행 미트 부재 음성이 아니다.
다음은 2모델 × 전체 화면/기존 crop의 GPU 개발 비교와 사전 지정한 crop CPU 비교다.
첫 회 결과를 보존하며 반복 실행은 시간 측정용이다. 이 준비를 새로운 정확도나 실시간 성공으로 세지 않는다.
Codex가 CV-13을 진행한다. 잔여 사용량 20% 하한, 팀원 영역·사이트·M3·기존 JSONL 고정을 유지한다.
방법과 사전 등록: [로컬 탐지 비교](docs/CV_LOCAL_DETECTOR_V1.md).

## 사용 한도20% 보존·CV-12 재개 — 2026-10-07

최신 사용자 지시: 남은 사용량20%까지 진행하고 그 하한을 보존한다. 시작 시 확인 가능한 주간 한도는84% 남았다.
Codex가 CV-12 로컬 관측 후보·기존86장 사람 라벨 정합 점검을 선점했다. 이전 하한 해제 기록보다 이 지시가 우선한다.
작업 단위마다 검증·커밋·푸시한다. 팀원 모델/API·사이트·고정 M3·기존 JSONL은 변경하지 않는다.


## CV-11 완료·다음 CV-12 — 2026-10-06

같은10개 프레임·구조화 출력 조건에서 Opus/Haiku를 순서대로 각1회 비교했다.
사전 등록 `61ddfcb`; 양쪽10/10수락·형식오류0, 좌표7/8·기권3/2.
순차 루프234.500/267.437초, 1회처리 중앙23.868/24.563초, 예정→발행≤5초 각0/10.
CLI 구간 중앙17.219/17.618초로 모델명 교체의 실시간 개선은 관측하지 못했다.
좌표7쌍 차이 중앙249.9px는 모델 간 불일치이며 정확도가 아니다.
Codex의 원본2장 표본 확인에서 일부 Haiku 좌표가 미트 밖 배경을 가리켰다.
사람 라벨/새 독립 성능으로 세지 않고 운영 채택을 보류한다. 기존 M3 수치와 비교하지 않는다.
전체 CPU 검사1119 passed /5 skipped/2 deselected, lint/format113경로 통과.
이전 CV-9/10 결과 보존, 모델·영상 원문은 Git 제외. 보고서: [CV-11 결과](docs/CV_LATENCY_MODEL_COMPARISON_V1.md).

다음 한 단위는 CHECKLIST CV-12: 로컬 관측 후보·환경과 기존 사람 라벨86장 정의/원본 정합을
먼저 점검하고 개발 비교 규약을 고정한다. 아직 모델 설치·학습·실시간 적용은 하지 않았다.
CV-5a4 전체 타석 확인·CV-6 추가 사람 검토·CV-7 미열람 독립 검증은 별도 미완료다.
팀원 모델/API·사이트·고정 M3·기존 JSONL 불변. 수정 권한 반납, 실행 중 관측 프로세스 없음.
이전 사용량3% 보존 제한은 해제됐다. 아래 절은 과거 인계 기록이다.


## 잔여 한도 후속 작업 최종 기록 — 2026-10-06

최신 사용자 지시: 3% 보존 제한 해제. 남은 허용 사용량까지 진행했으며 이 절이 과거 하한보다 우선한다.
CV-9: 고정10시각 4좌표·3기권·3형식오류, 발행≤5초 0/10, 160.938초. 원래 결과 보존.
CV-10 완료: 구조화 v1은 API 스키마 비호환 0/3, 호환 수정 v2는 3/3수락
(좌표3·기권0·불확실0·오류0), 발행≤5초 0/3.
실패 선정 개발 표본이며 정확도·독립 성능·실시간 성공으로 해석하지 않는다. 관련91tests·Ruff 통과.
[구조화 출력 기록](docs/CV_STRUCTURED_OUTPUT_V1.md), [10시각 지연](docs/CV_BOUNDED_LATENCY_V1.md).
다음은 CV-5a4 전체 범위 검토와 더 빠른 관측기/연결 재사용 지연 비교다. 5초 처리 기준은 미충족.
팀원 모델/API·사이트·M3·기존 JSONL 불변. 수정 권한 반납. 현재 진행 중 프로세스 없음.

## 잔여 한도 사용·10시각 지연 진단 — 2026-10-06

사용자가 3% 보존 제한을 해제했다. 현재 허용된 잔여 한도까지 우리 CV 작업을 계속한다.
과거 3%/10%/50% 하한보다 우선한다. 팀원 모델/API·공개 사이트·기존 M3·JSONL은 고정한다.
CV-9 완료: 사전 등록 ac5fc7f, 10회 중 7수락(4좌표·3기권), 3응답 계약 오류.
예정→검증 후 발행 5초 이내 0/10, 총 160.938초. 수락/좌표 출력은 정확도가 아니다.
74 관련 테스트·Ruff 통과. 앞 구간 2,449장 원본 매칭·기존과 600장 동일 중첩 확인.
전체 타석/연속 검토는 미완료. 다음은 출력 형식 제약 보완을 별도 버전으로 검증하는 CV-10이다.
보고서: [고정 10시각 지연 진단](docs/CV_BOUNDED_LATENCY_V1.md).
아래 절은 과거 인계 기록이며 최신 상태와 충돌하면 이 절을 우선한다.

## 발표 이후 CV 재개 — 2026-10-06

사용자가 발표 종료를 알리고 남은 우리 작업 재개를 요청했다. 잔여 사용량 **3% 보존**.
아래 과거의 시연 전용·CV 보류·10%/50% 하한보다 이 지시가 우선한다.
발표 종료는 사용자 보고이며 E-demo2 세부 리허설 결과나 E-site5 Song 확인은 미수신이다.

CV-5a4의 **화면 경계 증거 한 단위**를 진행했다. 55장 순서 표본과 경계 인접 프레임을
직접 확인했다. 더그아웃→중앙 카메라 전환은 원본 180.246733초(순번 313→314),
점수판 0-2/1아웃→0-0/2아웃 전환은 227.193633초(3127→3128)다.
이는 화면 전환 시각이며 실제 타석 진입·심판 판정 시각이 아니다. 전체 연속 재생 검토와
직전 타석 종료 확인은 아직 남아 `full_pa_verified=false`를 유지했다.
5초 간격 후보 10개의 실제 PTS 매핑을 확인했으나 전체 타석 실행 계획으로 확정하거나 호출하지 않았다.
기록: [경계 검토](docs/CV_PA_BOUNDARY_REVIEW_V1.md), [근거 JSON](docs/results/cv_followup_20261006/pa_boundary_review_v1.json).

인계 도구가 두 글자 작업군 CV를 누락해 예전 F-4a를 선택하던 오류도 수정했다(CV-8).
검증: 체크리스트 6 tests·Ruff 통과, 실제 `--next`는 CV-5a4, 10개 추출 근거 및 10개 후보 시각 매핑 재검사 통과.
다음 한 단위: CV-5a4의 연속 재생 검토 및 필요한 앞 구간 확장 → 경계 확정 → 실행 계획 고정.
이후 실제 순차 관측과 처리 지연/적체를 평가한다. 새 모델 호출 0회.
CV-6 추가 사람 응답은 0건으로 유지한다. 팀원 코드·서비스·사이트·M3·기존 JSONL은 변경하지 않았다.
수정 권한 반납. 아래 내용은 과거 인계 기록이며 최신 지시와 충돌하면 이 절을 우선한다.

## 공개 홈 4투구 하이라이트 — 2026-10-06, Site v9

사용자 요청으로 홈의 3초 단일 영상을 **23.833333초 / 서로 다른 네 투구**로 교체했다.
849843 첫 타석 1·2·3구의 공식 영상과 둘째 타석 5구의 기존 발췌를 시간순으로 연결했다.
네 연속 투구/전체 중계가 아니다. 720p·30fps·무음 반복, 715프레임, 약 11.57MB.
기존 홈 디자인·재생/일시정지·동작 줄이기·오류 재시도는 유지했다. 대표 미트 버튼은 현재
재생 위치와 관계없이 기존 첫 타석 3구의 별도 판독 정지 프레임을 열고 그렇게 명시한다.
움직이는 하이라이트에는 미트 점을 표시하지 않는다. 첫 타석 페이지·모델·팀원 저장소 불변.

출처: `docs/results/mlb_p0/hero_reel_v1.json`. 원본 4개 SHA 보존, 새 영상 SHA와 전체 디코드
검사 통과. 30fps 전환은 기존 프레임 선택/반복이며 생성·보간 프레임은 없다.
사이트 77 Node·출처/미디어 해시·JS/HTML 검사·Ruff 통과. Windows 브라우저에서 새 영상
23.833333초·무음 반복·재생/정지·대표 장면·영상 복귀 시 점 제거 확인. Safari/iPhone은 미검수.

Site v9 배포 성공: 소스 `a3a7a6bb7bc434c6ba93ae45f12bca23c8898012`, 배포 `appgdep_6ac4a34611d08191bc5d9d1ae7cc93ba`.
공개 홈 https://pitcheezy.com . 기존 오프라인 ZIP v4는 Site v8의 고정 발표 묶음으로 보존했다.
새로 패키지를 만들 때 하이라이트가 빠지지 않도록 허용 목록을 갱신했다. 이번에는 ZIP 재생성 없음.
잔여 사용량 3% 하한 유지. 수정 권한 반납. E-site5/Song 확인과 E-demo2 실기기 리허설은 대기 유지.

## 첫 타석 공식 영상 3구 · 시연 v8 — 2026-10-06

최신 사용자 지시는 잔여 사용량 **3% 보존**, 우리 사이트 작업만 계속하는 것이다.
아래 과거 10%/50%와 영상 미확보 기록보다 이 상태를 우선한다. 수정 권한은 반납했다.

- 공개 시작: https://pitcheezy.com/receiver.html?demo=849843-pa1
- 849843:1:1–3 공식 H.264/AAC 클립 3개(각 약 7초)·투구 전 포스터를 확보했다.
  공식 feed의 gamePk/atBatIndex+1/pitchNumber/playId와 선수·구종·구속을 대조했다.
  배열 순서·파일명·feed UTC로 영상 시각을 추정하지 않았다. 출처·크기·해시는
  `docs/results/mlb_p0/first_pa_media_v1.json`에 기록했다.
- 각 영상 종료 → 저장 실제 결과 공개 → 다음 구. 투구 선택·숨기기는 재생/표시를 초기화한다.
  3구에서만 별도 판독 정지 장면을 열어 AI 미트 중심을 표시한다. 이 점은 기존 condensed
  영상 3084번 프레임에만 대응한다. 새 클립의 시간축·좌표로 옮기거나 영상에 고정하지 않았다.
  1·2구의 미트 주석은 없음이며 기권으로 세지 않는다. 영상 오류 재시도·정상 일시정지 복구 포함.
- 홈의 주된 시작 링크를 실제 첫 타석으로 연결했다. 큰 화면은 영상/추천을 나란히 표시하고
  좁은 화면은 세로 배치한다. 구종 선택 비중≠사건확률, 저장 사후 결과, 미검토 AI x,
  실시간 추론·자동 중계 동기화 아님을 유지했다. 모델/API·팀원 저장소 변경 없음.
- 사이트 77 Node 검사, 체크리스트 4 passed, Ruff와 JS 문법/HTML 링크/원본·새 미디어 SHA 통과.
  Windows 앱 브라우저에서 세 구 재생 종료의 결과(싱커96.3/스위퍼86.4/포심97.6),
  3구 정지 장면, 영상 복귀·숨김·구 선택의 점 제거와 0초 초기화를 확인했다.
  1280/390px 배치·가로 넘침 없음 확인. Safari/iPhone 실기기·현장 낭독은 미확인.
- Site v8 배포 `succeeded`. 소스 `1058c4358223d77217e66be7a59929caaa25d730`, 배포 `appgdep_6ac49eab37848191803f1677336e97bb`.
- 비공개 오프라인 v4: 38파일+manifest, 약 18.09MB. 세 구 영상·실제 응답·대본·기존 장표·
  private 비교자료 포함. 원본 비교자료/장표와 고정 M3·JSONL·기존 영상은 바이트 보존했다.
  ZIP은 공개 사이트/GitHub에 포함하지 않았다. 자세한 실행은 `docs/PITCH_STUDIO_OFFLINE_BUNDLE.md`.

E-site5는 우리 첫 타석 연결을 완료했으나 Song 최종 확인은 대기한다. E-demo2도 대기다.
투구별 3개 클립이며 연속 중계 영상·실시간 처리·새 독립 성능 검증은 아니다.
1구 시작 장면에는 메인 점수판이 없으므로 화면 상황은 공식 기록이며 OCR 결과가 아니다.
프레임 검토는 AI 확인이고 사람 간 일치도가 아니다. 실행 백엔드의 정확한 모델 커밋은 미확인이다.
다음 한 단위는 실제 발표 기기의 재생·좌우/단위·공개/기권·글자·낭독 및 Song 확인을 기록하는 것이다.
확인 응답 없이 완료로 바꾸지 않는다. 이후 개발은 별도 CV-5a 계획과 미검토 영상 검증으로 이어간다.

## 최신 사이트 상태 — 2026-10-06

E-site5: 실제 첫 타석 응답 수신과 `849843:1:3` 실제 영상 연결 완료. 1·2구 영상은 미확보다.
Site v7, 소스 `bf2250da3cad7e5cddb2bcb038a1f33f79319595`. 저장 영상 종료 후 저장 결과/미트 x 공개,
숨김·투구 이동 시 재생 초기화. 사이트 72 Node 검사와 체크리스트 4 passed, Windows 브라우저 동작 확인.
자세한 범위는 docs/PITCH_STUDIO_RECEIVER.md 맨 위. 아래 “실제 응답 대기”/v4는 과거 상태다.
E-site5 전체와 E-demo2는 미완료: 전체 타석 영상·실시간 자동 동기화·Song 리허설을 완료로 세지 않는다.
팀원 모델/API/저장소는 변경하지 않았다. 수정 권한 반납, 잔여 사용량 10% 보존 유지.

## 오늘 시연 보완 완료 — 2026-10-06

최신 사용자 범위는 오늘 데모 우선·잔여 사용량 10% 보존이다. 아래 과거 50% 하한과
CV 개발 자동 재개 지시보다 우선한다. E-demo4: 홈 재생/일시정지·자동재생 차단 재시도·
영상 파일 오류의 정지 폴백, 정상/기권 투구 바로가기를 보완했다. Site v4 배포 성공,
소스 `d52bb61a5b2a7dc1871efa3f19777bf0061108de`. pitcheezy.com은 기존 도메인 연결 유지.
발표 안내는 docs/PITCH_STUDIO_DEMO_RUNBOOK.md, 비공개 오프라인 묶음은
docs/PITCH_STUDIO_OFFLINE_BUNDLE.md의 v3를 사용한다. 2분 목표 동선·30초 대체 대사 포함.
6개 재생 + 34개 수신 Node 검사, 체크리스트 4 passed(PYTHONUTF8=1), Ruff, 데이터 원본 대조,
29파일 ZIP/해시 검증 통과. 207파일 기준 203개 불변·승인된 사이트 파일 4개만 변경했다.
Windows 브라우저 정상 폭/390px 홈, 정상/기권 공개·상태 초기화·바로가기 검수 완료.
실제 Safari/Mac/iPhone·file URL 렌더링·낭독 시간은 미확인이다. 이를 현장 리허설 완료로 세지 않는다.
기존 M3·JSONL·장표·private 비교자료 불변, 팀원 저장소 수정/메시지 전송 없음.
**다음 한 단위는 E-demo2:** 사용자/Song의 실제 화면 6항목과 낭독 시간을 받아 기록한다.
E-site5 실제 모델 응답은 계속 대기이며 CV-5a4는 기존 사전 점검 상태다. 수정 권한 반납.

## 정확한 프레임 추출·실제 관측 — 2026-10-06

[실제 PTS 관측 연결](docs/CV_MAPPED_OBSERVATION_V1.md) 완료: 180/185/190초 상한의
세 프레임을 원본 체크섬으로 재검증하고 익명 AI 응답 3건(1표시·2기권)을 수신했다.
요청 시각과 실제 PTS를 분리한 v2 경로이며 기존 v1·M3·시연본·사이트는 유지한다.
180 관련 tests, 전체 987 passed / 5 skipped / 2 deselected, Ruff 107경로. 207파일 SHA 불변.
요청→수신 약 69초에는 도구/승인/큐/컨트롤러 대기가 포함된다. 실시간 지연·정확도는 미측정이다.
CV-5a 전체 자동 연속 타석은 미완료. 다음은 실제 모델 호출 어댑터·시간순 공급·입력 도착/발행 계측.
E-site5/E-demo2는 실제 응답/현장 확인 대기. 팀원 영역 제외, 잔여 사용량 50% 이상 유지.
수정 권한은 반납했다. 이전 10% 하한·과거 다음 작업 지시보다 이 최신 상태를 우선한다.


## CV 시간축 대응 — 2026-10-06

사용자 최신 지시에 따라 우리 CV 후속을 재개하며 **잔여 사용량 50% 이상**을 유지한다.
이전 10% 하한보다 우선한다. [원본/클립 PTS 검증](docs/CV_CLIP_CLOCK_V1.md):
새 원본 구간·클립 디코딩 3,298장 고유 대응, 1/60000초 시간 단위와 누락 1구간 확인.
185초 cutoff는 184.9848초 프레임을 선택하며 다음 프레임은 아직 공개하지 않는다.
기존 M3·시연 자료·사이트 207파일 SHA 불변. 전체 검사 906 passed / 5 skipped / 2 deselected, Ruff 104 paths.
CV-5a 전체·실시간 관측은 미완료다. 다음은 영상/체크섬에 결속된 정확한 프레임 추출이다.
E-site5 실제 응답과 E-demo2 현장 확인은 대기 유지. 팀원 영역은 변경하지 않았다.


## 우리 오프라인 시연 묶음 — 2026-10-05

[사이트·장표·비교 그림 묶음](docs/PITCH_STUDIO_OFFLINE_BUNDLE.md) v2 준비. ZIP 약 4.56MB,
내용 29파일+manifest, 기존 자료 해시·ZIP 바이트·HTML 링크 검사 통과.
시작 파일 START_HERE.html과 사이트 포함 2분 목표 대본을 추가했다. 실제 낭독은 미측정이다.
앱 브라우저 file URL 정책으로 직접 렌더링은 미확인. 실제 발표 기기에서 확인해야 한다.
private 비교 그림을 포함하므로 묶음 전체는 비공개 파일 전달/현장용이며 공개 업로드하지 않는다.
팀원 영역·공개 Site·고정 M3·기존 장표는 변경하지 않았다. E-site5/E-demo2는 대기 유지.
수정 권한 반납. 다음은 실제 응답/현장 확인 결과를 받아 검증하는 단위다.

## 우리 쪽 응답 수신 준비 — 2026-10-05

[로컬 파일 수신·검증 도구](docs/PITCH_STUDIO_RECEIVER.md) 완료. `receiver.html`에서 한 타석의
공개용 timeline/reveal 전달 파일을 브라우저 안에서 검사·표시한다. 34 Node 테스트 및
브라우저 정상/실패·공개 상태·모바일 확인 완료. 서버 호출·파일 업로드·팀원 수정은 없다.
실제 응답은 아직 미수신이며 합성 검사 자료만 포함했다. 모델/영상 진위 인증이 아니다.
다음은 실제 응답을 받은 뒤 원본 경기·투구 연결과 영상 공개 시점을 확인하는 E-site5다.
M3·기존 JSONL·장표는 그대로다. 수정 권한 반납. DNS·Song 실제 화면 리허설은 별도 대기다.

## 최종 서비스 콘셉트 사이트 — 2026-10-05

사용자 요청으로 홈·분석 스튜디오·실제 관측 리포트를 분리했다.
[사이트 실행·검증·연결 명세](docs/INTENT_DEMO_SITE.md)를 따른다. 공개 주소:
https://pitcheezy-pitch-studio.sritone723.chatgpt.site
실제 MLB 리플레이 위 정지 프레임 미트 표시, 경기명·날짜·선수명,
투구 전 목표·결과 확률·투수 실행·타자 대응·유지/교체 비교의 최종 제품 화면이다.
예측·선수 평가·교체 수치는 별도 설명용 데이터이며 실제 서비스 연결이나 인과 판정은 아니다.
사용자가 이번 홈에 MLB 영상 공개를 승인했다. 고정 M3·기존 JSONL·장표는 변경하지 않았다.
동료 저장소는 읽기 전용으로 확인했으며 수정하지 않았다. 수정 권한은 반납했다.
다음 한 단위는 동료의 한 타석 watch/reveal 실제 응답 확보 후 투구 키 연결·공개 시점 검증이다.
Song UI 리허설은 별도 대기, pitcheezy.com은 Cloudflare 로그인·DNS 연결 대기다.

## 10/6 시연 우선 — 2026-10-05 P0 준비 완료

사용자 최신 지시에 따라 아래 CV-5a 개발보다 시연 준비를 우선한다. [39구 화면 대조표](docs/INTENT_V0_DEMO_SCREEN_CHECK.md)와 [1분 대본·Q&A](docs/INTENT_V0_DEMO_SCRIPT.md)를 준비했다. 39고유키/27좌표/12기권, 스캔·창 키 일치, 로컬 schema 39/39, 장표·보고서·대본 숫자·확정 문구 일치를 확인했다. 의도 회귀 검사 251 passed, 체크리스트 가드 4 passed. 고정 자료 186개 바이트 불변, 리허설 문서는 링크 한 줄만 추가했다. 코드·기존 결과·팀원 저장소는 변경하지 않았다.

**다음은 사용자/Song의 실제 화면 확인 결과를 받아 기록하는 P1**이다. 대조표의 6단계는 모두 미확인이다. 공개 전후 표시·되감기·기권 처리·영상 대응을 서류 검사로 완료 처리하지 않는다. 이미 전달한 장표·로컬 ZIP·JSONL을 다시 만들거나 재전달하지 않는다. CV-5a PTS 매핑·자동 관측과 CV-6/CV-7은 이번 작업에서 재개하지 않았다. 수정 권한은 반납했다. 아래 이전 CV 재개 지시는 이 시연 우선순위보다 뒤다.


## CV-5a 현재 상태 — 2026-10-05

[실제 AI 관측 호출 기록](docs/CV_OBSERVATION_SESSION_V1.md): 원본 프레임 3장 실제 판독(2기권·1좌표), 요청→응답 경과 기록 완료. 자동 전체 타석 리플레이·정확도·실시간 가용률은 미완료다. [클립 시간축 대조](docs/CV_CLIP_CLOCK_AUDIT_V1.md)에서 3개 시각 중 1개의 한 프레임 불일치를 확인했다. 다음은 디코딩 프레임 PTS 대응을 검증한 뒤 실제 모델 어댑터 자동 실행을 연결하는 것이다. 최종 전체 검사 834 passed / 5 skipped / 2 deselected, Ruff 100경로. 수정 권한 반납. 최신 사용자 지시에 따라 잔여 사용량 하한은 10%다.

## 사람 검토 상태 구분 — 2026-10-05

기존 M3 사람 검토는 86장 완료(84표시·2기권)다. 이 수치는 기존 인계 기록에 이미 포함된 결과다. 아래의 CV-6 “응답 0 / 미검토 26”은 새 관측 규약으로 하는 추가 재검토만 뜻한다. 기존 사람 라벨이 없는 상태가 아니다. 10/6 시연을 위해 기존 86장을 다시 검토할 필요는 없다.

다음 구현은 CV-5a로 돌아간다: 개발용 연속 한 타석의 영상·출처 확인, 실제 관측기 연결, 입력 도착·출력 발행 시각 측정 순서다. 저장 주석 변환기 intent.run을 자동 검출기로 취급하지 않는다. CV-6 추가 도구 개발은 마치고 실제 추가 응답이 있을 때 재개한다. CV-6 재검토는 CV-5a의 필수 선행 조건이 아니다. 기존 M3·시연 산출물 및 팀원 영역은 고정한다.


## Current intent branch — 2026-10-05

On `feature/intent-v0`, read CHECKLIST's CV section and
[CV follow-up](docs/CV_FOLLOWUP_2026-10-05.md) before the historical OCR plan below.
CV-1–4 add retrospective temporal/quality diagnostics, a standalone measured-trace
guard and a source-bound resumable local runner. CV-5 adds verified anonymous prefix
frame delivery for two sampled windows (122 frames), not observer inference. Read
[the prefix report](docs/CV_PREFIX_REPLAY_V1.md). Next: CV-5a actual observer and timing
instrumentation on continuous video. CV-6 source-only review preparation is ready:
[26-frame review queue](docs/CV_REVIEW_QUEUE_V1.md) and
[offline click-and-export UI](docs/CV_REVIEW_UI_V1.md), zero completed human responses.
Use [response summary](docs/CV_REVIEW_SUMMARY_V1.md) after real submissions; the current
26-frame report has zero reviewers. Do not mark CV-6 done or create human labels without real reviewer submissions.
These tools do not complete live CV or M4.
Existing M3, IntentEstimate v1 JSONL and 10/6 presentation files remain frozen.
F-4i name OCR remains on hold. Teammate model/profile/policy/feed/service/UI work is
excluded; SongRoute/pitcheezy is read-only. Next CV definition and evaluation gates:
[CV observation protocol](docs/CV_OBSERVATION_PROTOCOL_V1.md).
The task requires preserving at least 10% remaining account usage (latest user authorization).

## Open work

[CHECKLIST.md](CHECKLIST.md) lists every remaining task, the next work unit, and the
Codex/Claude handoff protocol. Update it in the same commit as the work it tracks.

## MLB-first P0 — 2026-09-28

The product goal is pre-pitch broadcast situation recognition, outcome probabilities,
and eventually pitch-type/target-location recommendations. MLB is the first delivery
target; KBO comes later. Read docs/MLB_P0.md and docs/MLB_P0_HANDOFF.md for current work.
Start from docs/CODEX_RESUME_PROMPT.md. A-z is complete: the annotation UI and CLI help
explicitly prohibit deriving playback seconds from feed UTC (handoff checkpoint 44).
CHECKLIST A-y preparation is complete: script 72 builds a source-only reviewer package
for 44 pitches (32 core + 12 diagnostic). Read docs/BLIND_REVIEW_PROTOCOL.md and handoff
checkpoint 45. H-5 audit and source/path/package hardening are complete (checkpoint 46;
docs/CROSS_AGENT_AUDIT_2026-09-27.md). Reviewer packages now use asset-bound v2;
the frozen study and labels are unchanged. I-6 explicit outcome contracts and rejection of
unsupported conversions are complete (checkpoint 47; docs/OUTCOME_CLASS_CONTRACTS.md).
They are standalone guards, not a live teammate-service integration. F-4a's source-aware
identity protocol and PA6 preparation are complete (checkpoint 48; docs/PLAYER_IDENTITY_PROTOCOL.md):
12 player-role opportunities, 11 manually readable names and 1 abstention. This is not automatic OCR.
F-4a now also has a small SNY name-panel OCR baseline (checkpoint 49; docs/PLAYER_IDENTITY_OCR.md),
keeping OCR text, frozen final-feed roster lookup, and reference IDs separate. Prediction currently needs
Windows OCR en-US; saved-result scoring is portable. This remains partial, developed on six PA6 frames.
Next prepare PA61's four-pitch name evidence and check the frozen v1 baseline on its ambiguous pitcher surname.
PA60 contains a pitching substitution and remains unsupported by the conservative reference builder.
Do not turn this already reviewed game's new name cases into an independent validation claim.
A-y awaits an actual independent
response, then comparison under the frozen protocol. It remains incomplete until those results exist;
do not invent agreement scores or call AI-only cross-checks human inter-rater agreement.
Scripts 58–74 cover video identity, manual inference UI, source inspection, observation
targets, whole-game checks, manual timing, scoreboard evaluation/OCR, verified merges,
OCR report refresh, timing review sheets, blind reviewer packages, and player identity/OCR evaluation.
Read docs/MLB_BROADCAST_TIMING.md: all 322 pitches reviewed, with 297 timed,
25 unavailable, and 0 unreviewed. A-15 (PA 79–82) completes this game's manual review;
see handoff checkpoint 43 for the verification results and limitations.
This is manual timing, not automatic synchronization. The SNY scoreboard OCR prototype
supports one broadcast layout; see the latest handoff/report for measured results.
Game 747139 has now been reviewed throughout and is development/demo material. New OCR
versions need unseen video for new blind validation; these frames cannot become unseen again.
CHECKLIST C and D belong to the teammate. Integration awaits the agreed interface/artifacts.
Current UI uses the existing ten-class model and
must leave independent strike/ball/foul and target-location outputs unavailable.
Never pair video/Statcast rows by list order or trust old pose-video filenames.
Do not claim completed general broadcast OCR, automatic broadcast synchronization,
new eight-class model accuracy, or actual run reduction. See the guide for pending work.

## Current operational validation — 2026-09-21

Read [the final validation report](docs/OPERATIONAL_VALIDATION_2026-09-21.md) first.
Aligned 77d/135d MLPs were repeated with seeds 42/43/44. Nine operational models were
trained using frozen 2022 profiles, 2023 training, Jan–May 2024 selection, June calibration,
and July–September test. Selected MLP135 ensemble CE=1.274251 vs empirical=1.287400.
Policy evaluation is complete, but run-cost improvement is NOT established:
delta=-0.0862 runs/100 decisions, 95% CI [-0.4046,+0.2304].
Use scripts 51–57 and src/inference/operational.py for this new schema.
Never pass old UMAP/Arsenal 135d vectors/checkpoints to the new operational runtime.
Final dataset: data/operational_20260921_v2; final nuisance: policy_nuisance_v2.
Maintenance validation: 177 passed, 2 skipped. Run `uv run --frozen python scripts/check_project.py`.
See docs/MAINTENANCE.md for portable paths, resume, CI, and artifact transfer.
Old phase conclusions below are historical.

## 2026-09-21 correction — read before interpreting historical results

77d point vectors and batter-sorted sequence labels were incorrectly paired in scripts 13–15.
Roughly 70% of targets differed. Historical collapse and Arsenal +26.5pp/context-causality claims
below are withdrawn. The corrected loaders require aligned vectors, labels, pitch IDs, and class
order in one artifact; never fall back to `labels_10_{split}.npy` for point models.
Use fresh run directories and `scripts/49_compare_aligned_runs.py` for identity-checked comparisons.
Corrected seed-42 MLP CE: 77d 67.67% / CE 0.8517; 135d 67.60% / CE 0.8546.
These are observed-pitch classification results, not demonstrated policy utility or pre-pitch accuracy.
See [the correction report](docs/ALIGNMENT_REPAIR_2026-09-21.md). The phase checklist below is historical.

## Project Goal

SmartPitch MDP의 전이확률(transition probability) 추정 모델 3가지를 비교 실험한다.
동일한 MLB Statcast 데이터에 대해 학습·평가하여 정확도, 캘리브레이션, 추론 속도를 비교한다.

## Models

| ID | Name | Reference | Input | Output | Architecture |
|----|------|-----------|-------|--------|-------------|
| Model C | MIT Sloan 2025 Transformer | MIT Sloan 2025 | 87-dim × 400 sequence | 24-dim (full state transition) | 12-layer Encoder, sub-token masking |
| Model B | Otremba 2022 MLP | Otremba 2022 | 77-dim | 4-dim (Strike/Ball/Foul/InPlay) | 2-layer, 128 hidden units |
| Model A | SmartPitch MLP (wrapper) | Internal | TBD | TBD | Existing SmartPitch MLP via wrapper |

## Environment

- **Python**: 3.12 (managed by uv)
- **Package manager**: uv
- **Deep learning**: PyTorch (Mac MPS for local dev, CUDA for GPU server)
- **Experiment tracking**: W&B
- **Config**: OmegaConf + YAML (configs/)

## Code Conventions

- 한국어 주석 OK, docstring은 영어로 작성
- Formatter/Linter: ruff (line-length 100, select E/W/F/I/B/UP)
- Testing: pytest (tests/)
- Import order: stdlib → third-party → local (ruff I rule)

## Directory Structure

```
src/
  models/       # Model definitions (model_a.py, model_b.py, model_c.py)
  data/         # Dataset, feature engineering, dataloaders
  training/     # Training loops, schedulers
  evaluation/   # Metrics, calibration, comparison
  utils/        # Common helpers
configs/        # YAML config files per model/experiment
scripts/        # Standalone scripts (data prep, training, eval)
notebooks/      # Exploration notebooks
data/           # Raw/processed data (git-ignored except .gitkeep)
outputs/        # Checkpoints, logs, figures (git-ignored except .gitkeep)
references/     # Papers (git-ignored PDFs)
tests/          # pytest tests
```

## Progress Checklist

### Phase 1-2: Setup & Data Acquisition
- [x] Project scaffolding & environment setup
- [x] Sanity check (PyTorch, MPS)
- [x] Data acquisition (pybaseball / Statcast)
  - 1,534,286 pitches (2023: 774,038 / 2024: 760,248), 118 columns

### Phase 3: Data Pipeline
- [x] 3.1: Data exploration
  - 8 deprecated columns 식별, 400+ pitches 타자 586명 (sliding window 가능)
  - 시즌 간 분포 거의 동일
  - notebooks/01_data_exploration.ipynb (9셀, 한국어 주석)
- [x] 3.2: Feature mapping (4/10-class labels, hit location)
  - 4-class 매핑 100% (Ball/Strike/Foul/InPlay)
  - 10-class 매핑 99.96% (660건 truncated_pa → 전처리 시 제거)
  - Hit location 9-class: InPlay 한정 (22.7%)
  - src/data/features.py, tests/test_features.py (27 tests), scripts/03_validate_mapping.py
- [x] 3.3: Preprocessing pipeline (lazy loading)
  - 1,534,286 → 1,488,976 rows (정제 후, 3.0% 제거)
  - 87차원 Model C vector: 연속(15)+pitch_type(17)+zone(14)+balls(4)+strikes(3)+outs(3)+base(8)+stand(2)+throws(2)+result(10)+hitloc(9)
  - 77차원 Model B vector: 위 68차원 + inning(9)
  - StandardScaler (train fit), stride=8 (실용적 속도 고려, stride=1은 1 epoch=76분)
  - Sub-token masking: __getitem__에서 indices [68:87] → 0
  - Split: Train 749,880 / Val 385,320 / Test 353,776 (날짜 겹침 없음)
  - src/data/preprocess.py, scripts/04_preprocess.py
- [x] 3.4: PyTorch Dataset (lazy loading)
  - PitchSequenceDataset: O(1) numpy slice, stride=8
    - Train 65,418 / Val 25,077 / Test 22,127 sequences (stride=1 대비 8x 감소)
  - PitchPointDataset: eager (77-dim, 작음)
  - 디스크: vectors .npy + indices .pkl ≈ 1 GB (이전 3.2 GB에서 축소)
  - 77 tests all pass

### Phase 4: Model Implementation
- [x] 4.1: Common base interface (src/models/base.py)
  - TransitionModel ABC: forward, predict_proba, num_classes, model_name
- [x] 4.2: Model B — OtrembaMLP (src/models/otremba_mlp.py)
  - 77→128→128→4, ReLU, 27,012 params
  - Sanity check: loss 1.41→1.31 (10 epochs, MPS), softmax 합=1 ✓
- [x] 4.3: Model C — PitchTransformer (src/models/transformer.py)
  - 87×400 → embed(256) → 12-layer Encoder → last-token + residual → 24-dim
  - 9,659,672 params, MPS 호환, 3.3s/epoch (64 seq, batch=8)
  - Multi-task: pitch_result(10) + hit_location(9) + continuous(5)
  - Sanity check: loss 19.1→18.0, accuracy 41%→48% (5 epochs)

### Phase 5: Training ✅
- [x] 5.1: Training loop (src/training/train.py)
  - TrainingConfig dataclass, AdamW + CosineAnnealingLR (per-batch step)
- [x] 5.2: W&B integration (project=transition-models, entity=pitcheezy)
- [x] 5.3: Checkpoint management (best + last per run)
- [x] 5.4: Sanity check learning (CUDA, small subset)
- [x] 5.5: Full training ✅
  - Model B v1 (2시즌): model_b_full_v1 — best val_loss 0.8730 (epoch 10), val_acc 60.6%, 8분
  - Model C v2 (2시즌): model_c_full_v2 — best val_loss 1.8334 (epoch 29), val pr_acc 67.1%, 4시간 53분
  - Model B v2 (3시즌): model_b_full_v2 — best val_loss 0.8700 (epoch 12), val_acc 61.0%, ~11분
  - Model C v3 (3시즌): model_c_full_v3 — best val_loss 1.8190 (epoch 21), val pr_acc 67.3%, ~10시간 (RTX 4070, stride=8, 150K seqs)

### Phase 6: Evaluation & Comparison ✅
- [x] 6.1: Metrics (cross entropy, brier score, top-k precision)
  - src/evaluation/metrics.py, evaluate.py, scripts/10_evaluate_models.py
  - **2시즌** — Model B: top-1 60.8%, CE 0.876 / Model C: top-1 66.7%, CE 0.880
  - **3시즌** — Model B: top-1 60.9%, CE 0.872 / Model C: top-1 67.2%, CE 0.868
  - 13 unit tests all pass
- [x] 6.2: Per-class performance analysis
  - Model B (3시즌): Ball 91.7%, Strike 56.4%, Foul 29.6%, InPlay 38.2%
  - Model C (3시즌): Ball 87.6%, Strike 82.2%, Walk 85.6%, Strikeout 17.3%, FieldOut 10.7% / Single-HR 0%
  - evaluation_b.npz + evaluation_c.npz (2시즌), evaluation_b_3season.npz + evaluation_c_3season.npz (3시즌)
- [x] 6.3: Comparison report (3 models)
  - notebooks/05_comparison_results.ipynb (Model A baseline vs B vs C)
  - Model A 35.6% → Model B 60.8% (2시즌) / 60.9% (3시즌) → Model C 66.7% (2시즌) / 67.2% (3시즌)
- [x] 6.4: Visualization (loss curves, confusion matrices)
  - 04 노트북 결과 섹션 완성, 05 노트북 신규 작성

### Phase 7: Inference & Integration ✅
- [x] 7.1: Inference wrappers (src/inference/transition_model.py)
  - TransitionModelB: predict(x: (77,) or (N,77)) → (4,) or (N,4) numpy
  - TransitionModelC: predict(x: (400,87) or (N,400,87)) → {"pitch_result": (10,), "hit_location": (9,)}
  - predict_top_k(x, k) → [{"class": str, "probability": float}]
  - 자동 checkpoint 로드, CUDA/MPS/CPU 자동 감지
- [x] 7.2: Demo script (scripts/11_inference_demo.py)
  - Model B + Model C 예측 출력, DQN 패턴 3-step 시뮬레이션
- [x] 7.3: Documentation (docs/INFERENCE_GUIDE.md, 290 lines)
  - TL;DR 3줄, 77/87-dim feature 인덱스 표, DQN 환경 통합 코드, 트러블슈팅
- [x] 7.4: Unit tests (tests/test_inference.py, 8 tests all pass)

### 전체 테스트 검증 (2026-05-08) ✅
- 116 collected / **114 passed** / 2 skipped (MPS, Windows 정상) / 0 failed
- 실행 시간: 27.5초
- 커버리지: features, preprocess, dataset, models, transformer, training, evaluation, inference

### Phase 8: 3시즌 데이터 확장 ✅ (2026-05-14)
- [x] 2022 Statcast 데이터 다운로드 (775,330 pitches, 118 cols)
- [x] 3시즌 정합성 검증: FT=0, spin_rate 차이 10.4 RPM, 컬럼 완전 일치
- [x] sac_bunt_double_play → FIELD_OUT 매핑 추가 (2022 신규 이벤트)
- [x] preprocess.py: split_by_season(train_years) 파라미터화
- [x] 04_preprocess.py: --years argparse (train=years[:-1], val/test=last year)
- [x] Model B v2 재학습: top-1 60.8% → 60.9% (+0.1pp), CE 0.876 → 0.872
- [x] Model C v3 재학습: top-1 66.7% → 67.2% (+0.5pp), CE 0.880 → 0.868
- [x] 3시즌 evaluation 저장: evaluation_b_3season.npz, evaluation_c_3season.npz

### Phase 9: 발표 피드백 반영 — 두 그룹 비교 ✅ (2026-05-23)

**두 비교 그룹**:
- **Group 1 (10-class)**: Architecture 효과 — LR, LightGBM, MLP, RNN, Transformer
- **Group 2 (4-class MDP 호환)**: LR, LightGBM, MLP (Model B)

**스크립트**:
- [x] scripts/13_train_logistic_regression.py (10-class LR)
- [x] scripts/14_train_lightgbm.py (10-class LightGBM)
- [x] scripts/15_train_mlp_10class.py (10-class MLP)
- [x] scripts/16_train_rnn.py (10-class RNN/LSTM)
- [x] scripts/17_evaluate_all_10cls.py (10-class 종합 평가)
- [x] scripts/18_train_logistic_regression_4cls.py (4-class LR)
- [x] scripts/19_train_lightgbm_4cls.py (4-class LightGBM)
- [x] scripts/20_evaluate_all_4cls.py (4-class 종합 평가)

**학습 결과**:
- LR 10cls: Top-1 41.1% (collapse — sqrt-balanced weight 적용해도 Strike만 예측, CE 1.614)
- LightGBM 10cls: Top-1 13.0% (역방향 collapse — inverse-freq 과보정, 전 클래스 균등 예측, CE 2.087)
- MLP 10cls: Top-1 41.1% (collapse — Focal Loss γ=2.0 적용해도 Strike만 예측, CE 1.470)
- RNN 10cls: Top-1 66.9%, Top-3 94.8%, CE 0.8728 (완료)
- Transformer 10cls: Top-1 67.2% (기존 결과)
- LR 4cls: Top-1 56.3%, CE 1.0516 (balanced weights)
- LightGBM 4cls: Top-1 60.8%, CE 0.8719 (is_unbalance=True)
- MLP 4cls (Model B): Top-1 60.9%, CE 0.8723 (기존 결과)

**2026-09-21 정정**: 위 77d 10-class 실행은 입력/정답 순서가 달라 원인 해석을 철회한다.
정렬 복구 후 77d MLP는 세 시드 모두 약 67.6%다. 특징 부족, 맥락 효과, sequence 우월성을
위 과거 비교로 입증할 수 없다. 최종 결과는 docs/OPERATIONAL_VALIDATION_2026-09-21.md 참조.

**노트북**:
- [x] notebooks/06_logistic_regression.ipynb
- [x] notebooks/07_lightgbm.ipynb
- [x] notebooks/08_mlp_10class.ipynb
- [x] notebooks/09_rnn.ipynb
- [x] notebooks/10_all_models_comparison.ipynb
- [x] notebooks/11_mdp_dqn_compatibility.ipynb
- [x] notebooks/00_project_journey.ipynb Phase 9 섹션 추가

**평가 파일**:
- outputs/evaluation_lr_10cls.npz, evaluation_lr_4cls.npz
- outputs/evaluation_lgb_10cls.npz, evaluation_lgb_4cls.npz
- outputs/evaluation_mlp_10cls.npz
- outputs/evaluation_rnn_10cls.npz
- outputs/all_models_comparison_10cls.json
- outputs/all_models_comparison_4cls.json

### Phase 9.5: MDP 호환 10-class 돌파 — 135-dim Arsenal MLP ✅ (2026-05-25)

**동기**: Sequence 모델(RNN/Transformer)은 10-class 67%+를 달성하지만 MDP state 비호환.
77-dim MLP collapse의 원인이 "feature 부족"인지 "context 부족"인지 분리 실험.
투수 arsenal 통계(pitcher repertoire embedding)를 정적 feature로 추가해 context를 근사.

**실험 설계**:
- 입력: 135-dim = 77-dim (Model B) + 5-dim UMAP (0-fill) + 53-dim arsenal
  - [77:82]: UMAP 5d → inference 시 0.0 (학습 데이터 평균값, 투구 후 측정값 미보유)
  - [82:83]: count_cluster_id (scaled)
  - [83:115]: arsenal_func 32d (pitcher pitch type distribution + movement stats)
  - [115:135]: arsenal_moment 20d (arsenal distribution moments)
- 손실: Focal Loss (γ=2.0) — Walk/Strikeout/FieldOut 희소 클래스 보정
- 아키텍처: MLP 135→128→128→10 (dropout=0.2), `TransitionModelMLP10`
- 스크립트: scripts/24_train_mlp_135dim_10cls_focal.py, scripts/25_evaluate_mlp_135dim_10cls_focal.py

**6-model 비교표** (10-class Top-1):

| 모델 | Input | Top-1 | Top-3 | MDP 호환 | 비고 |
|------|-------|-------|-------|---------|------|
| LR | 77d i.i.d. | 41.1% | 86.2% | ✅ | collapse (Strike만 예측) |
| LightGBM | 77d i.i.d. | 13.0% | — | ✅ | collapse (역방향, 균등 예측) |
| MLP (77d) | 77d i.i.d. | 41.1% | 86.2% | ✅ | collapse |
| **MLP 135d focal** | **135d i.i.d.** | **67.6%** | **—** | **✅** | **MDP 호환 최선** |
| RNN (LSTM) | 400×87 seq | 66.9% | 94.8% | ❌ | sequence 의존 |
| Transformer | 400×87 seq | 67.2% | 94.7% | ❌ | sequence 의존 |

**해석 정정**:
1. +26.5pp를 맥락 효과로 해석한 주장은 철회한다. 77d 기준선의 정렬 오류가 확인됐다.
2. 입력 형식의 MDP 연결 가능성과 운영 성능/정책 효용은 별도 검증 대상이다.
3. Single~HR의 과거 0%는 argmax recall이다. 해당 사건의 확률은 0이 아니며,
   타자 특징 부재가 유일한 원인이라는 설명도 검증하지 않았다.
4. 4-class의 비슷한 정확도만으로 표현력의 한계나 포화를 확정할 수 없다.

**배포 판단**: 기존 `TransitionModelMLP10`을 최선으로 권장하지 않는다.
독립 calibration과 운영 평가를 수행한 새 schema/model을 별도로 사용한다.
구형 UMAP/Arsenal 135d checkpoint와 새 운영 135d checkpoint를 혼용하지 않는다.

**산출물**:
- outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt (epoch 25, val_focal_loss 0.4505)
- outputs/evaluation_mlp_135dim_10cls_focal.npz (Top-1 67.6%, per-class accuracy)
- outputs/arsenal_by_pitcher_cluster.json (4클러스터, pitcher 2,007명 매핑)
- docs/handoff_to_rl_agent.md (rl-agent 통합 코드 골격 포함)
- docs/rl_agent_teammate_guide.md (다운로드 및 통합 단계별 가이드)
- src/inference/transition_model.py — `TransitionModelMLP10` 클래스 추가

### Phase 10: 135-dim 전 모델 확장 + Hybrid Sequence ✅ (2026-05-27)

**목표**: Phase 9.5 MLP 135d 성과를 나머지 모델(LR, LightGBM, RNN, Transformer)에도 적용,  
"context = architecture-agnostic" 가설 탐색. 과거 기준선 정렬 오류로 입증 주장은 철회.

**Phase 10.1 — iid 135d (LR + LightGBM × {10cls, 4cls})**
- [x] scripts/26_train_logistic_regression_135d_10cls.py — Top-1 **62.4%** (77d 41.1% → +21.3pp)
- [x] scripts/27_train_lightgbm_135d_10cls.py — Top-1 **67.3%** (77d 13.0% → +54.3pp), Macro-F1 30.5%
- [x] scripts/28_train_logistic_regression_135d_4cls.py — Top-1 **56.3%** (77d와 동일, 4cls 포화)
- [x] scripts/29_train_lightgbm_135d_4cls.py — Top-1 **60.9%** (+0.1pp, 4cls 포화)

**Phase 10.2 — 평가 통합**
- [x] scripts/17_evaluate_all_10cls.py 수정 (135d 모델 + hybrid 모델 7개 추가, graceful skip)
- [x] scripts/20_evaluate_all_4cls.py 수정 (135d 모델 2개 추가)
- [x] outputs/baseline_master_comparison.json 신규 (G1~G6' 비교 그룹 통합)

**Phase 10.3 — RNN Hybrid (sequence 87d×400 + static 58d)**
- [x] scripts/30_align_static58_for_sequence.py — static_58_{train,val,test}.npy 생성 (99.9% 매칭)
- [x] src/data/dataset.py — PitchSequenceDatasetHybrid 추가
- [x] src/models/rnn_hybrid.py 신규 — PitchRNNHybrid(seq 87d + static 58d → head concat)
- [x] scripts/31_train_rnn_hybrid_10cls.py (drop=True) — Top-1 **67.2%**, Top-3 94.9%, CE 0.870 (N=22,119, 1.5h)
- [x] scripts/31_train_rnn_hybrid_10cls.py (drop=False) — Top-1 **67.1%**, Top-3 94.9%, CE 0.871 (N=22,127, G5 fair compare)

**Phase 10.4 — Transformer Hybrid**
- [x] src/models/transformer.py 수정 — static_dim 인자 추가 (역호환 유지)
- [x] scripts/32_train_transformer_hybrid_10cls.py (drop=True) — Top-1 **66.8%** (vs Transformer 77d 67.2%, eager mode 4.2h)
- [x] scripts/32_train_transformer_hybrid_10cls.py (drop=False) — Top-1 **67.1%**, Top-3 94.8%, CE 0.870 (N=22,127, G5 fair compare)

**전체 비교표 (10-class Top-1)**:

| 그룹 | 모델 | Top-1 | MDP 호환 |
|------|------|-------|---------|
| G3: iid 77d | LR / LGB / MLP | 41.1% / 13.0% / 41.1% | ✅ (collapse) |
| G4: iid 135d | LR / LGB / MLP | 62.4% / 67.3% / **67.6%** | ✅ |
| G5: seq 87d | RNN / Transformer | 66.9% / 67.2% | ❌ |
| G6: seq hybrid (drop) | RNN-H / Trans-H | 67.2% / 66.8% | ❌ |
| G6': seq hybrid (fullN) | RNN-H / Trans-H | 67.1% / 67.1% | ❌ |

**과거 해석 철회 및 범위**:
- 41% → 67%를 context 효과로 해석할 수 없다. 복구된 동일 투구 비교를 사용한다.
- Hybrid의 작은 정확도 차이는 seed/표본 변동을 고려해야 하며 내재적 학습의 증거가 아니다.
- "MDP 최선"은 확정하지 않는다. 운영 특징과 확률 품질, 독립 정책 평가 결과를 사용한다.

**산출물**:
- data/processed/static_58_{train,val,test}.npy (sequence 정렬, 58d)
- outputs/evaluation_{lr,lgb}_135d_{10,4}cls.npz
- outputs/evaluation_rnn_hybrid_{drop,fullN}_10cls.npz
- outputs/evaluation_transformer_hybrid_{drop,fullN}_10cls.npz
- outputs/checkpoints/rnn_hybrid_{drop,fullN}_10cls_best.pt
- outputs/checkpoints/transformer_hybrid_{drop,fullN}_10cls_best.pt
- outputs/all_models_comparison_{10,4}cls.json (업데이트)
- outputs/baseline_master_comparison.json (신규, G1~G6' 통합)
- docs/handoff_to_rl_agent.md, docs/rl_agent_teammate_guide.md (Phase 10 반영 업데이트)

### Future Work
- Single~HR 개선: 타자 arsenal feature (batter_func/moment) 추가 → "135+α dim"
- Weighted sampler + γ=3.0 조합으로 Single~HR > 5% 목표
- Continuous regression target 실제 구현 (현재 placeholder 0)
- Model A wrapper 구현 (실제 SmartPitch 통합)
- Ablation study (sub-token mask, last-pitch residual 효과 분리)
- UMAP Option C: 50% dropout ablation으로 0-fill 영향 정량화
- Transformer embedding → MDP state 통합 (Hybrid 시스템, 장기 과제)
