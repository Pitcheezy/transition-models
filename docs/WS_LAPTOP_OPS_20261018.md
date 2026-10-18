# 노트북 운영 도구 연결 검사 — 2026-10-18

WS-laptop1. [착수·합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6244814626).
기준 main `48ec406589982547e298ff2ee4bc2d64ed0216c0`, 선점 `62dd0f08843c09ed04c937272c4e381298ac2506`,
고정 구현 `7deeac5d67f7ec9066ecb7df6598c600b6d072d6`.
작성 Codex(GPT-6 계열), 별도 `gpt-5.6-sol`이 고정 구현 `7deeac5` 전체 변경을 검토하여 PASS(P1/P2/P3 코드 지적 없음)로 판정했다.
검토자는 필요 없는 시험 반복을 하지 않았으며, 문서 표본 감사 범위 지적1건은 명확히 정정했다.

## 구현과 실제 확인

새 리허설이 기존 업로드·안내·유한 감시 CLI를 실제 별도 Node 프로세스로 실행한다.
관람 문 ON·수집/피드백 OFF·발행 키 하나·별도 합성 자격을 가진 새 loopback Worker/R2만 사용한다.
생산 runtime/CLI 코드는 수정하지 않았다. Mac/Mac mini·팀원 코드/프로세스/배포·실계정에 접근하지 않았다.
기존 노트북 서버의 검색/종료/포트 해제 없이 OS가 배정한 새 포트를 사용한다.

- 실제 CLI 29회, 15.801초. 합성 검사 시간이며 실경기 처리 속도나 지연 수치가 아니다.
- 세 도구 dry-run, 접근 인증, 파일 생성/HEAD/갱신/412, 철회/삭제 표식/공개404/조건부 복원.
- 정상 → 오래된 발행 → 정상, opened/recovered 이력과 양쪽 모의 알림. 복구 시 첫 표본의 열린 장애 때문에 종료1을 유지한다.
- 안내 ON → 감시의 안내 상태 구별 → 새 읽기 조건으로 OFF → 복구.
- 다른 키와 과거 만료 설정의 PUT/DELETE/HEAD403, 원본 바이트/ETag·안내OFF 보존.
- 입력34파일 SHA 보존, 비밀 없는 출력, 자식 프로세스·자기 런타임2개 종료와 임시 폴더 제거 확인.

[실행 영수증](results/ops/ws_laptop_operator_rehearsal_20261018.json)의 SHA-256:
`c9c9cb43497c11faf016d3a235d2b852f301deae41fcb03dbb6e865633fa53d1`.
각 관련 소스의 실제 바이트 SHA는 영수증 `source_sha256`에 있다.
환경은 Windows / Node24.1.0 / Miniflare4.20260730.0이다.

## 검사와 재현

저장소 루트에서 Node24와 기존 lock에 맞는 의존성이 설치된 상태로 실행한다.
출력의 부모 폴더는 먼저 준비하며 기존 출력은 덮어쓰지 않는다.

```text
node ops/public-host/rehearse-operator-tools.mjs --output .cache/operator-rehearsal-new.json
node --test ops/public-host/tests/operator-tools-rehearsal.test.mjs
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
python -m pytest tests/test_checklist_model.py -q
```

집중8/전체Node304·문법 통과, 체크리스트8 통과. Windows에서는 하위 프로세스에도 `PYTHONUTF8=1`을 전달한다.
처음 부모만 UTF-8로 실행했을 때 출력 디코딩 경고1건이 있었고 환경 변수 전달 뒤 경고 없이 통과했다.
전체 Node 로그 SHA: `a3a46a877ef3abeef4f827808e68a7a5b84f33381702321f619293ec7c719500`.
Windows workerd의 기존 WSARecv/WSASend 연결 종료 진단은 남아 있으며 이번에 해결한 것으로 처리하지 않는다.

## 한계와 다음

전체 HTTP 요청 수, 공동 시험의 18요청/120초 예산, 실제 시계의 만료 경계, 실제 Ctrl+C는 미측정이다.
만료 검사는 자기 런타임을 정상 종료하고 같은 임시 저장소에 과거 만료 설정으로 재시작한 결과다.
60초는 요청 작업 중단 신호이며 OS/파일시스템까지 강제 종료하는 보장이 아니다.
종료 확인 실패 시 영수증을 실패로 남기고 임시 저장소를 보존한다.
실제 브라우저/Mac/Cloudflare/Song 발행기/실경기/외부 이메일을 검사한 것이 아니다.

[협업 표본 감사](COLLABORATION_AUDIT_20261018.md)의 절차 편차와 미확인은 유지한다.
공동 연결은 최신 전달팩·접속 범위·시험 시간/운영자·별도 실행 승인 뒤 진행하며,
본인 전용 기존 시험 승인을 확대하지 않는다. 이번 결과는 새로운 배포·발신 승인이 아니다.
