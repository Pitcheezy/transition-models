# WS-ops4f — 로컬 저장소 재시작 리허설

새 임시 폴더의 **합성 자료만** 사용해 같은 R2/D1 저장소를 네 번 시작하고,
각 이전 인스턴스의 정상 종료를 기다린 뒤 세 번 재시작한다.
공개 계정·기존 서버·Song 발행기에는 연결하지 않는다.

## 실행

저장소 루트, 잠긴 Node 24 / Miniflare 의존성 설치 후:

```powershell
node ops/public-host/rehearse-lifecycle.mjs
node ops/public-host/rehearse-lifecycle.mjs --output .cache/new-lifecycle-result.json
node --test ops/public-host/tests/lifecycle.test.mjs
```

기본은 JSON 결과를 표준 출력한다. --output은 **새 파일만** 허용하며 기존 파일을 덮어쓰지 않는다.
외부 대상·기존 저장소 경로·계정·토큰 인자는 받지 않는다. 종료 코드 0은 검사 통과,
1은 검사 실패, 2는 입력/출력 또는 도구 오류다. 출력 파일 기록 실패 시 같은 검사를
이미 실행했을 수 있으므로 종료 코드만 보고 실행하지 않았다고 해석하지 않는다.

## 확인하는 것

1. 첫 시작: 공개 합성 JSON 하나, 철회한 다른 JSON 하나, 아직 유효한 세션/피드백,
   이미 만료된 세션/피드백을 만든다. 유효 세션에는 0이 아닌 sequence/active_ms를 저장한다.
2. 첫 재시작: 원본 JSON 바이트·ETag, 철회 상태·ETag, D1 전체 행의 canonical SHA와 budget을 비교한다.
   새 키로 교체한 뒤 옛 키의 PUT/DELETE/HEAD는 모두401이어야 한다.
   같은 세션/피드백 재전송은 budget을 소비하지 않아야 한다. 새 요청은 각 당일 상한까지
   수락하고 그 다음을429로 거부한다. 새 키 갱신은 성공하고 옛 ETag 삭제는412다.
3. 두 번째 재시작: 업로드·통계·피드백을 모두 OFF로 시작한다. 쓰기는503이어야 하고 기존 행은
   그대로 남아야 한다. **Miniflare 실제 scheduled 이벤트**를 호출하여 만료 행만 지우고,
   유효 행 ID와 당일 budget을 보존하는지 검사한다. 반복 정리는 결과가 같아야 한다.
4. 마지막 재시작: 정리 결과, 갱신된 공개 JSON·ETag, 다른 파일의 철회 상태가 계속 유지돼야 한다.

예약 호출은 설치된 Miniflare 4.20260730.0의 unsafeTriggerHandlers 옵션과
/cdn-cgi/handler/scheduled 진입점을 사용한다. 옵션은 이 임시 런타임에만 있다.
프로덕션 Worker에 예약 호출용 공개 경로를 추가하지 않는다.
우리 scheduled handler는 이벤트 시간 대신 현재 Date.now()로 정리하므로
미래 시각을 주입하지 않고 실제로 충분히 오래된 합성 행을 만든다.
90초 검사 중 UTC 날짜가 바뀌면 해당 실행은 실패로 남기고 새 날짜에 다시 실행한다.

## 정리와 결과 해석

네 인스턴스 각각 dispose 완료를 확인한다. 종료가 실패하거나5초 안에 확인되지 않으면
다음 재시작과 임시 폴더 삭제를 중단하고 passed=false / temporary_storage=retained로 기록한다.
임시 폴더 삭제 전 실제 경로가 OS temp의 직접 하위이며, 이번에 만든 정확한 이름이고
symlink/junction이 아닌지 검사한다. 중첩·다른 이름·다른 부모·링크 거부를 별도 시험한다.
검사 흐름은90초, 개별 HTTP는5초 제한이다. 소스 해시 읽기·OS 파일 작업 시간은 별도이며,
운영체제 자체가 응답하지 않을 때 강제 프로세스 종료를 보장하는 도구는 아니다.

결과에는 실행 환경·실행 소스 SHA·단계별 집계·정리 상태를 남긴다.
임시 경로·로컬 주소·토큰·세션/피드백 ID 원문은 내보내지 않는다.
D1 행 해시는 이번 합성 기록 보존 검사용이며 독립 성능 수치가 아니다.

- 실제 실행 영수증: [ws_lifecycle_rehearsal_20261012.json](../../docs/results/ops/ws_lifecycle_rehearsal_20261012.json).
- 자동 검사: 실제 영속 재시작, 삭제 경계, 외부 대상 인자 거부3건.
- Windows workerd의 WSARecv64 취소/종료 진단은 이번 실행에서도 관찰됐다.
  검사 통과·정상 dispose·임시 폴더 제거와 별개로 미해결 진단으로 유지한다.
- **정상 종료 후 재시작** 검사다. 강제 종료/전원 손실 복구·Cloudflare 실계정·분산 상태·
  생산 cron 배달·D1 Time Travel·백업 복원·실제 RTO/RPO 성공을 뜻하지 않는다.
- 키 회전은 새 인스턴스에 새 키 digest를 적용하는 로컬 검사이며 실제 secret 교체·전파 지연은 별도다.
- 후속 실제 연결은 [RUNBOOK](RUNBOOK.md), 고정 배포 목록과 수신한 Song 스키마/예제로 진행한다.
