# 공개 보고서의 식별정보 입력 보호 — WS-report5

2026-10-20. 기준 `008e14a827a21515d4e8b75f936b5d721a842006`, 선점 `8c238be`.
[합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6284099296).
[검증 기록](results/ops/ws_report_privacy_20261020.json).

## 문제와 수정

공개 이슈 초안 생성기의 기존 검사는 HTTP 주소·Bearer·긴 토큰 모양만 거부했다.
이메일, IP/포트, Windows·개인 Unix 경로, 비HTTP URL은 합성 입력에서 Markdown에 그대로 나타났다.
실제 개인정보를 사용하거나 이 초안을 게시하지 않았다.

기존 자유문구 검사에 이메일·IPv4/IPv6·URL·Windows 드라이브/UNC·알려진 개인 홈 경로를 추가했다.
문제 입력은 Markdown/JSON 생성 전에 기존 `secret_or_address_like_content` 오류로 거부한다.
정상 한국어, 수치, 레포 상대경로, API 경로와 별도 출처 필드의 커밋/SHA는 유지한다.
공개 발행 파일이나 Song 계약은 바뀌지 않는다.

이는 알아볼 수 있는 형식의 실수 방지다. 이름·전화번호·가려 쓰거나 인코딩한 값 등 모든 개인정보를
탐지한다고 보장하지 않는다. 게시 전 사람 확인과 기존 발신 승인 조건은 유지한다.

## 검증

- 신규22 + 기존 보고서14 = 집중36 통과.
- 전체 Node368 통과, 실패0, 35.303초. 체크리스트8·변경 JavaScript 문법 통과.
- 실제 로컬 CLI가 문제 입력을 종료2로 거부하며 출력/잠금/임시 파일을 만들지 않고 원본을 보존했다.
- 최초 체크리스트 검사는8통과였으나 Windows 하위 프로세스 인코딩 경고1건이 있었다.
  `PYTHONUTF8=1`로 재실행해8통과·경고0을 확인했다. 이를 코드 결함 수정으로 기록하지 않는다.
- 작성: Codex / GPT-6 계열(정확한 세션 모델 ID는 노출되지 않음).
  고정 `61bb00c`의 `gpt-5.6-sol` 검토 PASS, P1/P2 없음·독립36검사 통과.
  모델 근거는 해당 ID를 지정한 성공한 하위 에이전트 호출이다. 공통 Codex 소개 문구를 모델 ID로
  오해한 검토자의 첫 판단은 철회됐으며, turn 내부 모델 조회로 확인했다고 주장하지 않는다.
  추가 Claude 검토 시도는 기존 OAuth 만료로 결과가 없었고 합격 근거에 포함하지 않는다.

```text
node --test tests/report.test.mjs tests/report-privacy.test.mjs (cwd ops/public-host)
node --test tests/*.test.mjs (cwd ops/public-host)
node --check ops/public-host/report.mjs
node --check ops/public-host/tests/report-privacy.test.mjs
PYTHONUTF8=1 python -B -m pytest -q tests/test_checklist_model.py
```

로컬 합성 입력 검사다. 실서비스·배포·발송·팀원 코드·Mac 접근은 수행하지 않았다.
이 변경은 운영자 보고서 도구에만 적용된다. 기존 전달 ZIP과 실제 배포 버전은 변경하지 않았다.
