# COLLAB-001 승인 회신 — 2026-10-15 (1회 게시 완료)

게시 대상: 우리 mail #18의 기존 대화. 사용자 승인으로 아래 구분선 안 본문만 1회 게시했다. 재게시하지 않는다.
이 초안은 실제 운영·계약 변경·비용·접근 권한 승인이 아니다. 외부 주소·비밀은 포함하지 않는다.
기준 우리 main: `c07dc942030e5ec4f100f638d572239524cd327e`.

---

COLLAB-001 첫 연결 결과와 현재 업로드 API를 회신드립니다. 우리 운영 코드 기준은 `c07dc942030e5ec4f100f638d572239524cd327e`입니다.
**로컬 연결 검증은 완료했으며, 실제 호스팅·발행기 연결과 공개 운영은 아직 하지 않았습니다.**

## 1. 업로드 API와 접근 문

공개 경로 앞에 `/_publish`만 붙입니다. 예를 들어 `/v1/health.json`의 업로드 경로는 `/_publish/v1/health.json`입니다.
PUT·DELETE·HEAD 모두 `Authorization: Bearer <토큰>` 인증을 사용하며 실제 값은 비공개로 전달합니다.

- PUT: `Content-Type: application/json`, `X-Content-SHA256: <원본 바이트 SHA-256>`. 최초 저장은 `If-None-Match: *`, 교체는 `If-Match: "<현재 ETag>"`입니다.
- HEAD: 현재 `ETag`, `X-Content-SHA256`, `X-Publish-Deleted`를 반환합니다. 실제 객체가 없으면 404이며, 삭제 표식 객체는 인증 HEAD로 확인할 수 있습니다.
- DELETE: 현재 `If-Match`가 필수이며 삭제 표식을 저장합니다. 정상 읽기 상태(접근/안내 게이트 제외)에서 공개 GET/HEAD는 404가 됩니다. 복원 PUT에는 삭제 표식의 ETag를 사용합니다.
- 412 충돌 때 새 ETag로 낡은 본문을 자동 재전송하지 않습니다. 발행기 원본·순번을 다시 확인해야 합니다.
- 허용 공개 경로: `/v1/manifest.json`, `/v1/health.json`, `/v1/dates.json`, `/v1/games/<YYYY-MM-DD>.json`, `/v1/game/<양의 정수>.json`, `/v1/setup/<양의 정수>.json`. 업로드는 각 경로 앞에 `/_publish`를 붙입니다. UTF-8 JSON object, 파일당 5 MiB의 잠정 상한입니다.
- 성공 `stored:true`는 저장 성공이며 `schema_validated:false`입니다. 경기 스키마·공개 시점·여러 파일의 발행 묶음은 저장 성공이나 ETag가 보장하지 않습니다.

접근 코드 문과 긴급 안내 화면은 구현·로컬 검증했습니다. 접근 문이 켜지면 세션 없는 데이터 요청은 401 `access_required`, 안내가 켜지면 503 `service_notice`입니다. 안내가 접근 문보다 우선합니다.
화면은 호스트와 같은 출처에서 제공하고 fetch는 `credentials: "same-origin"`을 사용해야 합니다. 업로드와 안내 운영자 인증은 관람자 세션과 분리됩니다.
양쪽 담당자의 즉시 안내 전환 기능은 준비됐지만 실제 조작 권한·공개 문구·토큰 설치는 미완료입니다. 실제 알림도 아직 모의 전송 단계입니다.

## 2. 확인한 것과 호스팅 조건의 남은 한계

기존 고정 발행기 자료 `d5a1dd9`의 예시13·스키마6을 SHA로 대조해 19/19 일치했고 JSON Schema 오류는 0이었습니다.
공개 화면 `ef4e4df`를 로컬 Worker에서 확인해 경기 전·진행·확인 중·연결 끊김·공수 교대·종료·발행 중단을 구별했습니다.
이는 10/13의 고정 자료·로컬 검증 결과이며, 이후 후보나 실경기 운영을 검증했다는 뜻은 아닙니다.

JSON은 `no-store`이며 강한 ETag의 공개 GET/HEAD 조건부 재조회는 304를 지원합니다. `Date`는 응답 시각, `Age:0`은 직접 읽은 응답의 캐시 나이로서 파일 최신성을 뜻하지 않습니다.
실제 CDN의 헤더·삭제 전파·캐시 동작은 미측정입니다. 여러 파일의 업로드 순서·재시작·정정 규칙은 발행기와 맞춰야 합니다.
미지원 예제가 없어서 `unsupported` 표시의 첫 연결 합격은 아직 보류입니다.

## 3. 미트 자료

한 경기 처리 시간과 처리량은 **미측정**입니다. 기존 미트 좌표 평가 수치를 처리 시간으로 대신하지 않습니다.
영상·투구 대응·보정 가능한 범위를 고정한 뒤 출력/기권/미검토 범위와 함께 측정해야 합니다. 미트가 없는 관전 흐름은 유지합니다.

## 4. 다음 전달물과 일정 조건

다음 자료를 준비되면 이 mail에 이어서 부탁드립니다. 없는 항목은 미완료로 표시해 주세요.

- 미지원 상태 예시와 파일 SHA-256.
- 후보 `detail.probability`·`target` 두 곳을 반영한 스키마와 계약 버전·고정 커밋·SHA-256.
- 실제 전달 가능한 최종 공개 화면 빌드·발행기/업로더의 고정 커밋, 빌드 명령·런타임 버전.
- 파일 업로드 순서, 순번·재시작·종료 정정·health 갱신 규칙과 우리 API의 호환 확인.
- 하루 한 번 상황판/우편 확인 가능 여부. 실제 연락 수단·응답 시간은 사람끼리 비공개로 정하고 결정 여부만 기록하면 됩니다.

10/17 실제 발행기 연결은 위 자료와 계정·접근·예산 결정이 준비됐을 때의 목표이며 확정 일정으로 취급하지 않겠습니다.
10/20 연락·응답 시간 결정과 10/21 이후 고장 수리만 한다는 협업 규칙은 유지합니다.
접근 제한만으로 자료 이용 허가가 확인되는 것은 아니므로 권리·공개 범위 결정도 별도로 유지합니다.

받은 첫 팩 검증과 이 회신만으로 전체 요청을 완료 처리하지 않겠습니다. 우리와 Song은 각자 자기 코드를 수정하고 파일 계약과 이슈로 연결합니다.
401/503의 화면 처리와 수집 위젯 연결 등 Song 화면의 별도 변경 요청은 필요한 합격 기준을 정리해, 발신 승인 후 Song 레포 mail로 분리하겠습니다. 이 회신에서 상대 코드를 변경하지 않습니다.

---

## 참고 근거 (이번 게시 범위 제외)

- [고정 업로드 구현](https://github.com/Pitcheezy/transition-models/blob/c07dc942030e5ec4f100f638d572239524cd327e/ops/public-host/gateway.mjs)
- [첫 연결 검증 기록](https://github.com/Pitcheezy/transition-models/blob/c07dc942030e5ec4f100f638d572239524cd327e/docs/WS_OPS2_FIRST_CONNECTION_20261013.md)
- [접근 문](https://github.com/Pitcheezy/transition-models/blob/c07dc942030e5ec4f100f638d572239524cd327e/ops/public-host/ACCESS.md), [긴급 안내](https://github.com/Pitcheezy/transition-models/blob/c07dc942030e5ec4f100f638d572239524cd327e/ops/public-host/NOTICE.md)
- [현재 인계](https://github.com/Pitcheezy/transition-models/blob/c07dc942030e5ec4f100f638d572239524cd327e/docs/WS_OPERATIONS_HANDOFF.md)

현재 발신 상태: 사용자 명시 승인 후 [mail #18 댓글](https://github.com/Pitcheezy/transition-models/issues/18#issuecomment-6190443556)에 2026-10-15 10:57:57 UTC 게시 완료. 원격 본문 바이트를 대조했고 이슈는 OPEN으로 유지했다.
원본은 `733ae750ff4c6511bf495a9dc6a75021f2c68238`의 이 경로다. 본문 SHA-256: `1144d32a484058afa35386ca008c37cbcbce4582c979c39c8cc915ec6d580b5f`.
[발신 영수증](../results/ops/ws_stage1_20261015.json). 이 승인은 다른 회신/요청/배포/계약 변경으로 확대하지 않는다.
