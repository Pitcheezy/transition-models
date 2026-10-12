# 월드시리즈 공개 운영 — 현재 인계

2026-10-12. **우리 운영 기반은 로컬/CI 검증까지 완료했으며, 실제 공개 연결과 배포는 미완료다.**
작업 기준은 우리 최신 main이다. 완료 작업을 다시 만들기 전에
[CHECKLIST](../CHECKLIST.md) 상단과 [우리 board](https://github.com/Pitcheezy/transition-models/issues/3)를 확인한다.
역사적 “다음 단위” 문구는 현재 지시가 아니다.

## 무엇을 맡고 무엇을 기다리는가

- 우리: 공개 호스팅·업로드 수신·이용 기록·피드백·감시/알림·미트 자료.
- Song: 목표·공개 발행 계약·추천 모델·발행기·관전 화면 본체. 우리 작업으로 상대 소스/프로세스/배포를 바꾸지 않는다.
- 공개 후보 경로는 **맥미니의 공개 JSON → 우리 저장소/호스트 → 관전 화면**이다.
  팬 요청을 맥미니에 전달하는 프록시가 아니며 모델 가중치 직접 이식도 선행 조건이 아니다.
- 기존 Sites 데모·DNS·현재 로컬 영상팩은 이번 운영 코드 병합으로 자동 갱신되지 않는다.
- A-y/F-4i 보류와 CV 독립 사람/영상 평가 조건은 유지한다. 코드 검사를 사람 검토로 치환하지 않는다.

## 새 협업 규칙과 바로 다음 작업

[협업 규약 v1](COLLABORATION_PROTOCOL.md)을 사용자가 채택했다. 접점은 공개 파일 v1과 업로드 API다.
추가는 알림 후 진행, 삭제/의미 변경은 Song 승인 후 v2. 역할 확정과 실제 파일 검증/출시는 구별한다.
[실행 계획](WS_COLLAB_V1_ACTIONS.md)에 즉시 안내 화면(WS-safe1), 접근 문(WS-access1),
양쪽 알림(WS-alert1), 경기별 기록(WS-report1), 다른 모델 검토(WS-review1)의 합격 기준을 적었다.
WS-safe1은 2026-10-13 로컬 구현·합성 검증을 마쳤고(실제 전환·문구·토큰·다른 모델 검토는 남음), 나머지는 문서 반영만으로 완료되지 않았다.
독립 로컬 개발은 가능하며 실제 계정/공개 전환은 사람 결정이다.
10/20 연락/응답 시간 결정, 10/21 이후 고장 수리만, 10/23~31 경기별 근거를 기록한다.

## 준비된 것의 위치

- [호스트](../ops/public-host/README.md): Worker/R2 GET·HEAD, 인증 PUT·DELETE·HEAD,
  정확한 바이트/SHA, 조건부 갱신·삭제 표식,404/no-store/Date/Age.
- [업로드 제한](../ops/public-host/UPLOAD_LIMITS.md) ·
  [단일 파일 전송기](../ops/public-host/PUBLISHER.md): 기본 dry-run,
  같은 바이트·ETag 재시도, 저장 여부 불명과 충돌 구분. 다중 파일 원자성/경기 스키마 검증은 미구현.
- [수집/위젯](../ops/public-host/TELEMETRY.md): 별도 동의·피드백 토글,
  메모리 ID·활성 시간, private D1, 중복/역순·당일 상한·집계·만료 정리.
  제한기 boolean true만 허용한다. 실제 사용자 수집은 켜지 않았다.
- [배포 패키지](../ops/public-host/RELEASE.md): 양쪽 고정 커밋·파일 SHA를 넣는 결정적 ZIP/manifest.
  출처·권리·서비스 동작 인증이 아니며 deployable=false다.
- [설정 검사](../ops/public-host/CONFIG_CHECK.md): 파일 목록/경로/설정과 화면 보관 안내 대조.
  계정 자원과 secret 존재를 확인하는 도구는 아니다.
- [긴급 안내 스위치](../ops/public-host/NOTICE.md): 운영자 토큰 digest·조건부 쓰기·감사 기록으로 화면/asset/JSON/수집을
  503 안내로 전환하고 업로드는 유지. 로컬 Worker·Chromium 검증과 loopback 실측까지이며 실제 문구·전환·토큰·다중 colo 지연은 별도다.
- [감시](../ops/public-host/MONITORING.md): 단발 읽기·지정된 발행 시각·장애/복구 상태·안내 상태 구별(`notice_active`).
  현재 상시 스케줄과 외부 알림은 미연결이다.
- [합성 리허설](../ops/public-host/REHEARSAL.md) ·
  [영속 재시작](../ops/public-host/LIFECYCLE.md): 실제 로컬 Worker/R2/D1,
  브라우저·충돌·철회/복원·키 교체·수집 OFF 정리. CDN/실계정 복원 성공은 아니다.
- [장애 대응](../ops/public-host/RUNBOOK.md) · [비용 산정](../ops/public-host/COST_PLAN.md):
  대응 절차와 날짜가 붙은 가격/부하 가정. 실제 비용·승인 예산·수용량은 미측정이다.

## 계정 없이 실행하는 최소 확인

저장소 루트에서 Node24 이상·Python3.12를 사용한다. 의존성 설치는 최초 또는 lock 변경 때만 한다.

```powershell
npm ci --ignore-scripts --prefix ops/public-host
npm --prefix ops/public-host run check
npm --prefix ops/public-host test
python -B -S scripts/estimate_public_host_cost.py ops/public-host/examples/cost-scenarios.json
node ops/public-host/publisher-cli.mjs --plan ops/public-host/examples/publish-plan.json
```

마지막 명령은 네트워크·토큰 없이 계획/바이트를 검사하는 dry-run이다.
기본 예제를 실제 전송 계획으로 바꾸지 않는다.
실제 배포 명령은 계정·도메인·권리·버전이 확정되기 전에는 여기서 만들어 실행하지 않는다.

로컬 리허설만 개별 실행하려면:

```powershell
node ops/public-host/rehearse-local.mjs
node ops/public-host/rehearse-lifecycle.mjs
```

이 두 명령은 합성 로컬 런타임을 만들고 종료한다. 검사/회귀에 이미 포함된 경우
바뀐 코드나 새로운 우려 없이 반복 실행할 필요는 없다.
작업 환경·관측량·수치와 한계는 [기록 폴더](results/ops/)의 해당 영수증으로 대조한다.

## 다음 작업은 입력에 따라 고른다

1. **WS-ops2 — mail #18에 첫 연결 안내 수신, 실제 파일 검증은 다음:** 공개 화면 고정 커밋·빌드 명령/산출물,
   JSON Schema·상태별 예제·SHA, 공개 발행 계약/validator 버전,
   순번·재시작·묶음·정정/철회·health 규칙을 대조한다.
   받은 파일을 우리 schema라고 추측해 자동 변환하지 않는다.
   실제 후보에 package/config 검사 후 비공개 첫 연결을 수행한다.
   합격 기준은 갱신·미지원·setup 없음·발행 중단·공개 전후·정정/철회가 실제 화면에
   구별되어 나타나고, 양쪽 소스와 데이터 출처를 고정할 수 있는 것이다.
2. **WS-ops4 — 사용자/계정 결정 후:** 호스팅 소유자와 권한·월간 예산·공개 범위,
   수집 동의/보관/토글·알림 채널을 확정한다. private R2/D1와 제한된 업로드 비밀을 마련하고
   실제 staging/CDN·발행기 연결·복구·Chrome/Safari/모바일을 검사한다.
   계정 구성·결제·공개 전환은 로컬 검사의 자동 후속 단계가 아니다.
3. **실운영 리허설:** 실제 응답 속도와 피드 지연, 다음 투구 전에 추천이 표시된 비율을
   별도로 기록한다. HTTP200이나 건강한 health만으로 추천 정확성/제공 시점을 주장하지 않는다.
   실제 조건이 준비되지 않으면 미완료로 남긴다.

## 운영자가 기억할 한계

- 구종 선택 비중은 사건확률이 아니다. 추천 효과나 투수 의도를 운영 기반이 증명하지 않는다.
- 여러 파일의 ETag는 같은 발행 묶음이나 투구 공개 시점을 보장하지 않는다.
- 네 기능 스위치를 꺼도 정적 화면은 남는다. 화면 전체를 안내로 바꾸는 것은 [안내 스위치](../ops/public-host/NOTICE.md)이며,
  둘 다 요청 비용을 자동 중단하지 않고 내려받은 자료를 회수하지 않는다.
- 제한기는 위치별 근사치이며 전역 비용 상한이 아니다. D1 당일 상한은 HTTP/읽기 과금 상한이 아니다.
- Windows workerd WSARecv64 종료 진단과 Windows WebKit의 credentials=omit 쿠키 전송 관찰은
  미해결 한계다. 실제 Safari/운영 로그 정책과 함께 확인해야 한다.
- 정상 종료 후 로컬 재시작 통과는 강제 종료/전원 손실·클라우드 백업 복원·생산 cron 성공이 아니다.

## 세션과 CI 규칙

1. 하루 한 번 양쪽 board/열린 mail을 읽는다. 착수 전 이슈에 합격 기준을 적고 우리 board/CHECKLIST를 선점한다.
2. 최신 main에서 짧은 작업 브랜치를 만든다. PR을 일찍 열고 해당 검사를 통과한 정확한 커밋만 병합한다.
   자동 CI는 PR과 main push이며, PR 없는 작업 브랜치/tag에는 자동 실행되지 않는다.
   필요하면 workflow_dispatch를 수동 실행한다. 실제 branch protection 강제 여부는 별도 확인이다.
3. 완료 댓글에 범위·검증·커밋·산출물/SHA·다음을 기록하고 자기 진행 줄만 반납한다.
   공개 이슈에는 비밀·접속 주소·개인정보를 넣지 않는다. 상대에게 발신/변경할 권한을 새로 추정하지 않는다.

[현재 협업 규약](COLLABORATION_PROTOCOL.md)과 [보존한 초기 운영 인계](history/WS_OPERATIONS_HANDOFF_20261012.md)를 구별한다.
운영 코드의 다른 모델 검토가 출시 조건이다. 기존 같은 Codex 검토로 소급 충족하지 않는다.
이 문서는 실제 파일 검증·출시 완료 기록을 대신하지 않는다.
