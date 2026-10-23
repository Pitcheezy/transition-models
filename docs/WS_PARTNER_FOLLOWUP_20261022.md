# 반환팩 수신과 공동시험 추가 조건 — 2026-10-22

우리 기준 `d9d48642c5a695b82d4cf1069c459ab9798809a9`, 상대 수신본 기준 `000e4ba0d83bb81fee8db82539e67c7ab0e7d0b3`.
이번 작업은 이슈 조회·우리 소스의 읽기 감사·문서 정리다. 상대 코드/프로세스/배포와 Cloudflare 설정은 변경하지 않았다.

## 1. 전달과 수신

사용자가 반환팩 v2와 메시지를 직접 전달했다고 확인했다. 이후 [상대 상황판](https://github.com/SongRoute/pitcheezy/issues/35#issuecomment-6341660303)과 [수신 검토](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6341653062)를 조회했다.

- 파일: `pitcheezy-host-final-intake-v2-20261021.zip`, 252,996 bytes.
- 전체 SHA-256: `e66dabb8200e4536a88cee6863f0162ea1bcb98a1abbee0e2869a6c90cfe0a99`.
- 상대 보고: `python3 -B -S verify_return.py` 1회, exit 0, `PASS_INTEGRITY_ONLY`, 검사 대상 13파일. 읽기 검토는 `PASS_WITH_NOTES`.
- 기존 기능 34개는 상대가 이번에 재실행하지 않았다. v1 원본을 보유하지 않아 기존 9파일 바이트 동일도 제공자 보고로 구분했다. 수신 보고를 새 기능 검증·운영 합격으로 바꾸지 않는다.
- 사용자 승인에 따라 [#38 요청](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6332176519)을 게시하고 저장을 재조회했다. 세 결함의 상태/영향·최종 수정본·해시·다른 모델 검토·재현 결과를 요청했다. 이 조회 시점에 해당 댓글 뒤 새 회신은 없었다.

## 2. 상대의 최신 제안과 남은 결정

[TRIAGE 기록](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6335703619)은 세 결함 모두 미수정이라고 명시한다. 수정본을 받았거나 해당 회귀가 통과했다고 기록하지 않는다.

- `OPS-CRED-01`: 상대는 공동시험 실행본과 무관하다고 판단하고, 1차전 운영에는 환경변수 토큰 경로를 쓰겠다고 했다. 실제 사용 경로를 우리 쪽에서 검사한 것은 아니다.
- `ONEKEY-PROBE-01`: 시작 전 `game_key`, scope, expiry를 공동 원장에 고정하고, 본시험부터 후속 검사까지 변경되면 해당 회차를 무효 처리하며, 우리 서버 로그의 키/scope 일치를 합격 조건에 추가하자는 제안이다.
- `OPS-ALERT-JSON01`: 공동시험에 해당 감시기를 쓰지 않고 1차전에는 상태 파일 갱신을 수동 확인하겠다는 상대 제안이다. 우리 알림 연동/양측 수신 검증 완료를 뜻하지 않는다.
- [열린 화면에 대한 상대 결정](https://github.com/SongRoute/pitcheezy/issues/37#issuecomment-6325230222): 1차전은 기존 `000e4ba0`을 유지하고 비상시 화면 밖 공지로 새로고침을 안내, UI 수정은 이후 적용한다. 우리 담당의 수용·운영 GO 근거는 없다.

우리 담당은 10/22 18:00~19:30 KST 및 21:00 판단 참여 가능이라고 답했다. 이번 후속 조회 시각에는 그 시간이 지났다. 이 채팅/조회에서 실제 공동 실행 결과나 창별 양측 GO를 확인하지 못했으므로, 그 참석 가능 답변을 새 시험 창에 재사용하지 않는다. 재개 시 양측이 새 시각과 조건을 확인한다.

## 3. 우리 서버 증거의 현재 한계

현재 우리 소스의 읽기 감사 결과다. 실행 중인 배포와 동일하다는 주장은 아니다.

- [gateway.mjs](../ops/public-host/gateway.mjs)의 `publisherScope`/`enforcePublisherScope`는 요청 경로에서 얻은 키를 서버 환경변수 `PUBLISH_KEY_SCOPE`, `PUBLISH_EXPIRES_AT`와 대조한다. scope/expiry는 HTTP 요청 필드가 아니다.
- 다른 키와 만료가 모두 403이고, HEAD 응답은 오류 본문을 제거한다. HEAD의 403 하나만으로 올바른 키의 만료를 입증할 수 없다.
- [worker.mjs](../ops/public-host/worker.mjs)와 gateway에는 발행 요청별 자체 로그/요청 ID 기록이 없고, [설정 예제](../ops/public-host/wrangler.example.jsonc)에는 observability/logpush/tail 선언이 없다. 별도로 설정된 실제 Cloudflare 요청 기록의 존재·접근·보관·누락 여부는 미확인이다.
- R2 객체 metadata는 성공한 객체의 SHA/삭제 상태 등에 관한 기록이다. [notice.mjs](../ops/public-host/notice.mjs)의 audit는 안내 전환 기록이다. 어느 것도 거절된 HEAD나 전체 발행 요청 이력을 대체하지 않는다.
- 실행 전후 설정이 같다는 사실만으로 그 사이 변경이 없었다고 증명할 수 없다.

따라서 **서버 로그 조건은 아직 충족하지 않았다.** 실제 기록 확보 없이 요청 성공 수나 클라이언트 요약만으로 이를 통과시키지 않는다.

## 4. GATE-06 보완안 — 합의 전 준비

기존 [GATE-06 계획](WS_JOINT_TRIAL_GATE06_20261021.md)의 요청 예산·단일 writer·정상/긴급 회수 규칙을 유지한다. 다음은 추가 합의안이며 자동 승인이나 계약 변경이 아니다.

1. 비공개 원장에 실행본/등록서 SHA, 고정 클라이언트·화면 출처, 실행 대상, `game_key`, `publish_key_scope`, `publish_expires_at`, 호스트 deployment/version 및 소스 근거를 고정한다. 실제 값·주소는 공개 이슈에 넣지 않는다.
2. 본시험과 후속 probe 직전에 같은 원장/계획 SHA인지 검사한다. 키·scope·expiry·대상이 바뀌거나 근거가 불명확하면 해당 회차를 무효로 남기고 기존 긴급 중단 절차를 따른다. 옛 회차에 새 조건을 덧씌우지 않는다.
3. 실제 배포 version/비밀을 제외한 설정 snapshot, 해당 구간의 관리 변경 이력, 시각·메서드·경로·상태 등 최소 요청 기록을 함께 대조하는 방안을 준비한다. Authorization/Cookie/토큰 원문을 기록하거나 전달하지 않는다. 단일 정적 설정 snapshot 또는 403만으로 대체하지 않는다.
4. Cloudflare에서 기존 기록을 실제로 확보할 수 있는지 먼저 읽기 전용으로 확인한다. 기록이 없거나 요청과 연결할 수 없으면 해당 합격 조건은 미충족이다. 자동으로 관측 설정을 켜거나 새 코드·권한을 배포하지 않는다. 수정 실행본 또는 다른 검증 근거가 필요하면 사람끼리 합의한다.
5. 관리 조회/기록 확보 비용과 횟수는 기존 서비스 정상 경로 32회 제안에 섞지 않고 별도 원장에 남긴다. 실제 추가 요청 횟수는 미측정이다.
6. 미수정 실행본의 절차 대응, 외부 새로고침 공지, 수동 감시를 우리 담당이 수용했는지 따로 확인한다. 수신 검사 통과나 상대 내부 결정으로 우리 수용을 추정하지 않는다.

## 5. Cloudflare 읽기 조회 상태

사용자는 대시보드를 열었다고 확인했지만, 도구가 제어하는 탭은 2단계 인증 안내를 표시했고 사용자 화면의 도메인 등록 완료 탭은 도구 목록에 없었다. 목록 조회·기존 탭 새로고침·사용자 화면 탭 연결 시도를 했으며, 조회용 탭을 화면에 표시하고 직접 보안 선택 완료를 요청했다.

이전에 자동 승인 검토가 보안 안내의 `Skip for now` 클릭을 거절했다. 우회 탐색·계정 보안 설정 변경·만료된 관리 토큰 재사용은 하지 않았다. 현재 배포 version·설정·로그·알림 상태는 **미확인**이며, 마지막 실자원 확인은 10/16이다. 대시보드 로그인 또는 도메인 등록 성공만으로 배포 정상이라고 기록하지 않는다.

## 6. 재확인 방법과 다음

조회 명령은 `gh api repos/Pitcheezy/transition-models/commits/main`, `gh issue view 38 -R SongRoute/pitcheezy --json state,comments`, 각 근거 댓글의 `gh api repos/SongRoute/pitcheezy/issues/comments/<id>`다. 소스 감사는 `rg -n`으로 scope/expiry 검사·HEAD 응답·console/observability/metadata 기록을 확인했다. 이번 검사 종류는 이슈 조회와 정적 문서/소스 검토이며 새 합성 실행·실경기·운영 성공 수치는 없다.

다음은 조회용 Cloudflare 탭 연결 후 실제 배포/기존 로그 가용성 확인, #38의 공식 회신 확인, 미수정 실행본의 보완 절차·새 시험 창에 대한 양측 결정이다. [추가 회신 초안](mail_drafts/COLLAB-001-trial-evidence-draft-20261022.md)은 미발신이다.

문서 검증: `PYTHONUTF8=1 python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider` 8 passed, 변경 구간/신규 문서 상대 링크16개·신규 문서 개인정보 제외·`git diff --check` 통과. 첫 실행의 Windows 자식 프로세스 인코딩 경고는 UTF-8 환경 지정 후 재검사에서 없었다. 문서만 변경하여 전체 모델/운영 테스트는 재실행하지 않았다.

별도 에이전트의 문서 읽기 교차검토 PASS. 만료값의 ISO 문자열 형식을 명확히 했다. 운영 코드 변경이 없으며 이 검토를 운영 코드의 다른 모델 검토로 세지 않는다.
