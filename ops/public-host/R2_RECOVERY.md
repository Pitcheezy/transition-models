# 원시 R2 복원 점검 — WS-recovery2

격리된 Miniflare의 합성 객체를 복원해, 정상 API 재발행과 원시 저장소 되감김의 차이를 확인한다.
실제 계정·기존 버킷·외부 주소·백업 경로 입력은 받지 않으며 운영 코드/계약을 바꾸지 않는다.
토큰은 실행 중 임시 생성하고 기록하지 않는다.

```text
node ops/public-host/rehearse-r2-recovery.mjs
node ops/public-host/rehearse-r2-recovery.mjs --output <새 결과.json>
node --test ops/public-host/tests/r2-recovery.test.mjs
```

결과는 합성 자료이며 `public_resume_authorized:false`를 유지한다. PASS는 원시 복원의 위험과 차단 범위를
예상대로 재현했다는 뜻이며, 실제 복구나 공개 재개가 안전하다는 뜻이 아니다.
출력 경로는 새 파일만 허용한다. 기존 파일을 덮어쓰지 않는다.

점검 범위: 정상 API 복원/옛 ETag 거부, 원시 과거 공개본·철회본·metadata 누락,
과거 안내 OFF/안내 키 부재, R2밖 JSON 읽기·업로드 OFF와 정적 화면의 차이, 정상 API 안내 재설정.
런타임 시작·요청·정리에 제한 시간을 두며 정리를 확인하지 못하면 성공으로 기록하지 않는다.

[운영 절차](RUNBOOK.md#원시-r2-복원은-별도-차단-상태에서-검사한다)를 읽는다.
공개 진입을 별도로 닫는 실제 방법은 계정 소유자 결정이며 현재 도구가 제공하지 않는다.
실계정 R2 복원, CDN 전체 상태, 실제 발행기 중지/재개, 사람의 공개 승인, RTO/RPO는 미측정이다.
