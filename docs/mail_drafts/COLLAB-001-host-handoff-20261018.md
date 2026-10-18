COLLAB-001 — 우리 고정 전달팩 준비 완료

같은 형식으로 맞췄습니다. **소스·안내·파일별 SHA·검증/한계를 ZIP으로 전달하고, 요청과 결과는 이 mail 한 곳에 이어 남기겠습니다.** 우리 쪽 파일은 담당자에게 준비했으며 실제 비공개 전달/상대 수신은 아직 확인하지 않았습니다.

### 전달물
- `pitcheezy-host-handoff-20261018.zip` / 350,189 bytes.
- 소스: `3ea7ad69781daec8e80ce257ea39633ad6b2770a`. 우리 호스팅/업로드 수신·운영 도구와 합성 예제만 포함합니다. Song 코드·실제 설정·자격·영상은 없습니다.
- ZIP SHA-256: `2f700a486e8bb001a0167227c6562aea594524ec40c7d9d55272432e325586e0`.
- [먼저 읽기](https://github.com/Pitcheezy/transition-models/blob/24b35159b336586bb8802fed967f8111cc6cbbde/docs/handoff/ws_host_20261018/START_HERE.md) / [파일 목록](https://github.com/Pitcheezy/transition-models/blob/ec6ef354f9f939886ae99cd037efe0487128ab59/docs/handoff/ws_host_20261018/manifest.json) / [검증 결과](https://github.com/Pitcheezy/transition-models/blob/ec6ef354f9f939886ae99cd037efe0487128ab59/docs/handoff/ws_host_20261018/validation.json).

### 확인한 것
별도 Windows 폴더에 풀어 고정 의존성 설치, 문법, Node304/실패0, 전송 dry-run, CLI29회 loopback 합성 연결을 통과했습니다. 최종 ZIP102항목의 CRC·파일 SHA도 일치합니다.
재현은 Node24에서 아래 순서입니다. 첫 줄만 의존성을 내려받고 이후는 로컬 검사입니다.
```text
npm ci --ignore-scripts --prefix ops/public-host
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
node ops/public-host/publisher-cli.mjs --plan ops/public-host/examples/publish-plan.json
node ops/public-host/rehearse-operator-tools.mjs
```

### 범위와 남은 조건
- 공개 파일 v1 / 공개 발행 문서 초안 v0 / IntentEstimate v1.1 변경 없음. 운영 코드 수정 없이 기존 고정 소스를 포장했습니다.
- 단일 키·만료 제한은 이 소스에 있지만 **실제 호스트에는 미배포**입니다. 마지막 실제 확인은10/16 소스 `87168d7bc42f11f76886e475f919caff7674b60a`이며 오늘 재조회하지 않았습니다.
- 이 검사는 공동 HTTPS·실경기·총18 HTTP요청/120초 예산 검증이 아닙니다. 해당 범위와 실제 알림은 미측정입니다.
- 작성은 Codex(GPT-6 계열), 전달 문서는 별도 동일 모델 에이전트 대조입니다. 기존 운영 코드의 고정 다른 모델 검토 근거는 동봉 문서에 보존했습니다.

### 다음 한 단위
준비하신 **고정 소스/공개 빌드/스키마·미지원 예제/비활성 runner 설정/검증·한계**도 기존 사람 간 비공개 전달로 우리 담당자에게 보내주시면, 담당자가 작업 채팅에 첨부하고 우리는 명시 파일부터 검증하겠습니다. 구체 전달 가능 시점만 알려주시면 됩니다. 실제 파일/주소/토큰/개인 경로는 이 공개 이슈에 올리지 않습니다.

양쪽 파일 검증 후 접속 허용·시험 창·단일 writer·운영자·자격 회수를 확정해 한 키 합성 시험으로 진행합니다. 이 안내는 실제 접속·배포·실경기 승인이 아니며, COLLAB-001은 열어 둡니다.
