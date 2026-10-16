# 제한된 시험 발행 보호 — 2026-10-17

WS-publish2는 새 연결 시험 요청의 단일 키·짧은 시간 범위를 우리 호스팅에서 제한할 선택적 기능이다.
기존 실자원은 변경하지 않았다. Song 고정 소스/빌드 미수신과 접속 확대·실제 시험 승인 대기는 유지한다.

- 기준 main `e8d635b4dd49f2b2cdc8876a1584a3fcd8121e60`, 선점 `ee721fcb9049acaa835b495a8273fe5179e1ac82`.
- [착수 전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6218769240).
- [설정·운영 절차·한계](../ops/public-host/PUBLISH_SCOPE.md), [파일 해시·실행 결과](results/ops/ws_publish_scope_20261017.json).

## 구현

`PUBLISH_KEY_SCOPE`와 `PUBLISH_EXPIRES_AT` 쌍으로 정확한 저장키와 UTC 만료를 지정한다. 둘 다 없으면 기존 동작,
부분·빈값·잘못된 날짜/키면 거부한다. 인증 후 limiter 전후 및 최종 저장 직전에 검사한다.
공개 조회·안내·관람 인증과 JSON v1은 그대로다. 만료 시점 전에 이미 전달한 저장 호출의 완료 시각까지 제한하지 않는다.

오프라인 설정 검사는 runtime 다섯 파일을 신뢰한 현재 체크아웃과 줄바꿈(CRLF→LF)만 정규화해 대조한다.
새 설정을 무시하는 옛 번들·해시만 갱신한 다른 코드를 거부한다. `deployable:false`와 공개 파일 계약은 유지한다.
토큰 영구 폐기는 별도다. 제한 해제 전에 digest 제거/교체와 업로드OFF를 확인한다.

## 검사

- `cd ops/public-host && npm test`: 296/296, 17.194초. 신규12개(기존 worker와 집중44개 포함).
- `npm run check`, `git diff --check`: 통과.
- `python -m pytest tests/test_public_host_config.py tests/test_public_host_release.py tests/test_checklist_model.py -q`: 최종209개(설정143·패키지58·체크리스트8), 50.35초. ruff 통과.
- 고정 소스 `834f8387772adae836f5aabf9d0d3c3d7e77caa7`로 만든 ZIP 111,044바이트/13파일(운영12+합성화면1), 목록·설정 검사 통과. ZIP SHA `126053ebe5546cc804185a6f952866b89c130b0816756d17f944995eada45794`.
- 그 ZIP에서 꺼낸 runtime을 임시 loopback Worker/R2로 실행해 12요청 통과: 정상 발행/읽기·다른키 거부·중복412·철회404·복구, 만료PUT/DELETE/HEAD거부·공개경로 유지. 원본 Git blob과 체크아웃 줄바꿈 차이도 설정 검사에서 수용했다.
- 임시 포장 검사 스크립트가 반환값에 없는 `ok`를 요구해 처음 중단됐다. 저장소 코드는 바꾸지 않고 임시 wrapper만 고쳐 기존 ZIP의 고정 커밋·목록을 재검사한 뒤 진행했다.
- 작성 Codex(GPT-6계열)와 다른 실제 모델 `gpt-5.6-sol`이 위 고정 소스를 검토해 P1/P2 없음. 전체 검사를 반복하지 않은 읽기 검토다.

합성 입력·임시 loopback Worker/R2 검사다. 실제 Cloudflare·팀원 발행기·공동 리허설·메일 발송은 미실행이다.
