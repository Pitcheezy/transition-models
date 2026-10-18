# 같은 Worker의 실제 만료 경계 — WS-publish3

2026-10-18. [사전 합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6245302206).
기준 main `5dc2ad8fdafeb0786d8ab8d4500d4c941373e259`, 선점 `d0023c6`, 고정 구현 `a2bb75b674f4bce77315a2c982687abf02ef48f2`.
기존 WS-publish2의 모의 시계 경계와 WS-laptop1의 과거 만료 설정 재시작 이후 남은 실제 시계 공백을 검사했다.
운영 runtime은 변경하지 않고 로컬 리허설/검사만 추가했다.

## 실제로 확인한 것

Windows / Node24.1.0 / Miniflare4.20260730.0. 새 loopback Worker1개, 합성 게임 키1개, 관람 문ON·수집/피드백OFF.
동일 런타임에서 실제20초 만료 시각을 지나며 검사했다. 재시작·시계 모킹·만료 연장·재시도는 없다.

- 전체 애플리케이션 HTTP **18회**, 로그인·읽기·HEAD·예상 거부·실패 시도까지 공통 계수.
- 가장 큰 본문 **40bytes** (상한2048bytes). 다른 데이터 키를 사용하지 않는다.
- 부팅·실제 시간 대기·런타임 종료·자기 임시 저장소 정리 포함 **20.261초** (합격 상한120초).
- 401 접근 문 → 로그인 → 미사용 키 HEAD404 → 생성/HEAD/GET → 조건부 갱신 → 철회/공개404/삭제표식 HEAD → 조건부 복원.
- 실제 만료 뒤 같은 자격의 PUT403·DELETE403·비공개 HEAD403. 뒤의 공개 GET/HEAD는 바이트·SHA·ETag를 보존했다.
- 만료 시각: `2026-10-18T03:47:01.007Z`, 만료 뒤 요청 시작 기준: `2026-10-18T03:47:01.119Z`.
- 자기 런타임 종료/임시 저장소 제거 확인. 기존 노트북 서버·Mac mini·Song·실계정 접속 없음.

[원본 영수증](results/ops/ws_live_expiry_20261018.json), SHA-256 `7f65c741a469e7d87c46b669ab9cb6f7264aadbaa13d48a1f92b2ff38ff22281`.
`source_sha256`은 실제 실행한 로컬 바이트다. Git blob과 줄바꿈이 다를 수 있으므로 원본 바이트/코드 고정 커밋을 구분한다.

## 재현과 합격 기준

Node24와 고정 lock 의존성이 설치된 저장소 루트에서 새 출력 경로를 사용한다.
출력 부모 폴더가 있어야 하며 기존 파일을 덮어쓰지 않는다.

```text
node ops/public-host/rehearse-live-expiry.mjs --output .cache/new-live-expiry.json
node --test ops/public-host/tests/live-expiry.test.mjs
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
```

실제 runtime 없는5검사와 같은 Worker 실제 통합1검사로 구성했다. 외부 대상/자격/포트/시계 옵션을 받지 않는다.
이상 응답/불확실 통신 뒤 후속 요청을 중단한다. 정리 미확인·예산 초과는 실패로 남긴다.
전체 검사·고정 다른 모델 검토 결과는 최종 완료 절에 기록한다.

## 한계

로컬 Node가 만료 뒤 요청을 보냈고 실제 workerd가 거부한 근거다. Worker 내부 정확한 밀리초 경계를 관측한 것은 아니며,
`>=` 의미 자체는 기존 모의 시계 단위 검사를 따른다. HTTP수는 이 리허설의 애플리케이션 요청이며 npm설치·Miniflare 내부 제어·관리 API 호출 수가 아니다.

**Song runner·공동 Cloudflare HTTPS·실경기·영구 자격 철회·외부 이메일·실제 Ctrl+C 검증은 아니다.**
로컬에서 맞춘18요청/120초 결과로 Song의 요청 예산을 검증했다고 하지 않는다.
공개 읽기가 계속 가능한 것은 만료가 발행 권한에 적용되기 때문이다. 영구 폐기는 digest 회수 등 별도 운영 조치가 필요하다.

100초 요청 중단 신호와5초 런타임 종료 확인을 사용하지만 OS/파일시스템이 멈추는 경우까지 강제 종료를 보장하지 않는다.
전체120초는 정상 반환 뒤 측정한 합격 조건이며, 시간 초과/정리 실패를 성공으로 바꾸지 않는다.
기존 Windows workerd 연결 종료 진단은 별도 한계이며 해결했다고 주장하지 않는다.

## 완료 검사와 다른 모델 검토

전체 Node310/실패0·체크리스트8·문법·상대 링크76 통과. [검사/검토 영수증](results/ops/ws_live_expiry_checks_20261018.json).
작성 Codex(GPT-6 계열), 다른 모델 `gpt-5.6-sol`이 고정 `a2bb75b674f4bce77315a2c982687abf02ef48f2`의 신규 리허설·검사·package 변경과 관련 helper/gateway를 검토하여 PASS(P1/P2/P3 없음).
검토자는 모의5개만 선택하려 했으나 이름 필터가 해당 환경에서 제외하지 않아 실제로6개를 실행했다. 실시간 검사20.216초/6통과이며 추가 반복하지 않았다. 새 loopback만 사용했고 원본/팀원/실계정 변경 없음.
PR/CI 병합 상태는 우리 board의 완료 기록을 따른다. 기존 공개 ZIP은 이 추가 리허설을 넣어 재발행하지 않고 기존해시를 보존한다.
