# 이용 기록 스냅샷 집계 — WS-report2

운영자가 이미 확보한 **닫힌 SQLite 스냅샷**을 읽어 날짜·경기별 세션/활성 시간/피드백을 내보내는 로컬 도구다.
Cloudflare 계정, 네트워크, API 키가 필요 없다. 운영 DB 취득·원격 D1 접속·정리·스케줄 설치·게시를 하지 않는다.
실제 Cloudflare D1의 기본 내보내기 파일이나 SQL 덤프를 그대로 읽는 도구가 아니다. 검증된 로컬 SQLite 파일이 별도로 필요하다.

## 실행

저장소 루트, Node 24 이상. 현재 로컬 검증은 Node 24.1.0이다.
Node 내장 `node:sqlite`를 사용하며 이 버전의 ExperimentalWarning은 예상된다.
별도 SQLite 라이브러리를 설치하지 않는다. [공식 Node API](https://nodejs.org/download/release/v24.8.0/docs/api/sqlite.html).

```text
node ops/public-host/export-usage-cli.mjs --snapshot <비공개-스냅샷.sqlite> --from-day 2026-10-23 --to-day 2026-10-23 --output <새-비공개-집계.json>
```

`from-day`/`to-day`는 양끝을 포함하는 UTC 날짜이며 날짜 차이는 최대 90일이다.
CLI는 현재 시각에 만료되지 않은 행만 집계한다. 과거 시각을 지정해 만료 자료를 되살리는 옵션은 없다.
테스트 함수의 시계 주입은 합성 검증용이다. 운영 자료에 과거 시계를 주입하면 안 된다.

입력 조건:

- 최대 512 MiB, 각 테이블 최대 2백만 행인 일반 SQLite 파일. 실제 큰 DB 처리시간은 미측정이다.
- `usage_sessions`/`feedback`은 커밋된 migration의 정확한 열 이름·타입을 사용한다. 가상 테이블·뷰·누락 열을 거부한다.
- 원본을 쓰는 프로세스가 없는 별도 스냅샷을 사용한다. `-wal`/`-shm`/`-journal` 또는 WAL 형식 헤더가 있으면 거부한다.
- 입력 경로의 심볼릭 링크를 거부한다. 읽기 전용 연결과 한 읽기 트랜잭션을 사용하고 전후 SHA/크기/수정시각을 대조한다.
- 검사기는 원본 값을 고치거나 WAL checkpoint를 실행하지 않는다. 잘못된 날짜/음수 시간/안전 정수 초과/임의 피드백 값을 거부한다.
- 출력은 새 파일만 허용한다. 기존 파일과 원본·원본 sidecar 목적지는 거부한다. 권한 0600을 요청하지만 실제 Windows ACL은 별도 확인한다.
- 출력 JSON은 900,000바이트 이하로 제한한다. 너무 크면 날짜 범위를 줄인다.

## 출력과 해석

출력은 **운영자용 비공개 파일** `pitcheezy-usage-snapshot-v1`이다. Song 공개 발행 파일 v1의 변경이나 공개 업로드 대상이 아니다.

```json
{
  "schema": "pitcheezy-usage-snapshot-v1",
  "source_sha256": "<원본 SHA-256 64자리>",
  "coverage": "unverified",
  "aggregation": "utc_day",
  "usage_summary": {
    "schema": "pitcheezy-usage-summary-v1",
    "timezone": "UTC",
    "from_day": "2026-10-23",
    "to_day": "2026-10-23",
    "generated_at": "<추출 시각 UTC>",
    "sessions": [],
    "feedback": [],
    "limits": "<브라우저 세션과 활성 시간의 해석 한계>"
  }
}
```

빈 배열은 **현재 남아 있는 해당 날짜 기록 없음**이며 실제 0명·0세션의 증거가 아니다.
삭제된 만료 행, 수집 OFF 시간, 동의하지 않은 방문, 수집 실패는 스냅샷으로 복원할 수 없다.
값이 있어도 보존된 행의 합계일 뿐 전체 이용량을 보증하지 않는다.
UTC 하루 합계를 경기 중 2시간의 정확한 이용량으로 부르면 안 된다. 세션은 사람 수가 아니고 활성 시간은 브라우저 보고값이다.

`usage_summary.sessions[]`: `utc_day` 문자열, `game_pk` 정수(0은 특정 경기 없음), `sessions` 행 수,
`active_ms` 누적 활성 시간 합(밀리초), `mean_active_ms` 세션 평균 활성 시간(반올림 밀리초).
`feedback[]`: `utc_day`, `game_pk`, `rating`(helpful/unclear/problem),
`reason`(none/recommendation/explanation/delay/display/other), `responses` 행 수.
기존 `summarizeTelemetry` SQL을 그대로 재사용한다. 세션/피드백 ID·원본 경로·접속 주소는 출력하지 않는다.
표준 출력은 결과 파일 SHA·원본 SHA·날짜·집계 그룹 수만 담은 영수증이다. 오류는 안전한 코드만 내보낸다.

## 보고서 연결 상태

기존 [보고서 생성기](REPORT.md)는 이 새 포장 형식을 **거부**한다.
`usage_summary`만 꺼내 넣으면 `coverage=unverified`가 사라져 잘못된 완전성/0세션 해석을 만들 수 있으므로 금지한다.
[보고서 연결 변경안](../../docs/WS_REPORT2_REVIEW_PROPOSAL.md)의 승인을 기다린다.
이번 도구 구현을 보고서 연결·실계정 취득·실경기 측정 완료로 표시하지 않는다.

## 검사

```text
node --test ops/public-host/tests/export-usage.test.mjs
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
```

합성 SQLite와 실제 로컬 D1의 집계 일치, 원본/폴더 불변, 날짜/만료 경계, 불완전 자료 거부,
잘못된 DB/값/경로·기존 출력 거부, CLI 오류의 경로 비노출을 검사한다.
원격 D1 취득·WAL 복구·실제 이용량·대용량 성능·OS 적대적 파일 교체에 대한 절대적 원자성은 검증하지 않았다.
