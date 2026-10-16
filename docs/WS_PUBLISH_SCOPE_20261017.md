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
- Python 설정/패키지142개 통과. 검증 바이트 재사용 회귀 추가 후 관련12개 통과(현재 수집143개). ruff 통과.
- 고정 Git ZIP runtime 검사 및 다른 모델 검토는 최종 기록으로 갱신한다.

합성 입력·임시 loopback Worker/R2 검사다. 실제 Cloudflare·팀원 발행기·공동 리허설·메일 발송은 미실행이다.
