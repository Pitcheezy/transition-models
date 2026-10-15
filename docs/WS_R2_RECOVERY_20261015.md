# WS-recovery2 — 원시 R2 복원과 안내 상태

선택한 합성 원시 객체를 복원하는 격리 Miniflare9사례를 실제 실행했다. 정상 API 재발행과
원시 저장소 되감김은 다르다. runtime gateway/notice 구현이나 공개 파일 계약을 수정한 작업은 아니다.

기준 main `33f46aa956d302d193ea288e8b9a38a6e6786d1c`, 고정 구현 `b74c0012ccbd2ae6db6d318a43c984589e0ac044`.
[선점·합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6189530299),
[실행 결과·환경·소스 SHA](results/ops/ws_r2_recovery_20261015.json), [실행 방법](../ops/public-host/R2_RECOVERY.md).

확인한 결과:

- 정상 API 복원은 새 ETag를 만들고 이전 DELETE를412로 거부한다.
- 과거 raw 공개본을 넣으면 철회가 풀리고 옛 ETag가 돌아와 이전 DELETE도200으로 다시 받아들인다.
- 과거 tombstone은 새 공개본을404로 숨기고, 최신 작성자의 조건도412로 거부한다.
- metadata가 빠진 저장 객체는503으로 거부한다.
- 안내 ON 뒤 raw OFF를 복원하면 화면/자료가200으로 돌아온다. 과거 상태에 맞는 감사 행이 남아 있으면
  `audit_unavailable:false`도 가능하다. 이 실험은 새 감사 행을 삭제하지 않고 선택한 상태 객체만 복원했다.
- 안내 키를 지워도 OFF/revision0으로 읽는다.
- R2밖 JSON 읽기·업로드 토글은 raw 복원 뒤에도503으로 막지만 정적 화면은200이다.
- 양쪽 런타임을 정상 API 안내ON으로 마무리하고 종료를 확인했다.

공개 재개 승인=false, 실계정/전체 버킷/강제종료 복구 검증=false, RTO/RPO=null을 유지한다.
안내 캐시는 로컬 운영자 GET으로 무효화했으며 다중 지역 지연 측정이 아니다.
[운영 절차](../ops/public-host/RUNBOOK.md)에 별도 접근 차단·버킷 밖 최신 근거 대조·정상 API 재발행/안내 재설정을 추가했다.
같은 버킷의 안내ON만으로 원시 복구를 보호한다고 쓰지 않는다.

검사: `node --test ops/public-host/tests/r2-recovery.test.mjs` 3pass,
`npm --prefix ops/public-host test` 전체235pass, `npm --prefix ops/public-host run check` 통과,
`python -m pytest tests/test_checklist_model.py -q` 8pass, 로컬 문서 링크51개 확인.
실행: `node ops/public-host/rehearse-r2-recovery.mjs --output docs/results/ops/ws_r2_recovery_20261015.json`.
결과 파일 SHA-256: `7b46a0bfd3c35ed53edf3b6f9631fd81e874ab83176bbed14f115fa89e58d228`.

작성 GPT-6 계열(Codex, 정확한 세션 모델 id 미노출), 검토 모델 `gpt-5.6-sol`.
고정 구현 검토 PASS, 집중3검사·독립 단독 리허설9사례/종료2회·문법검사 통과, 지적 없음.
실제 계정/팀원 저장소/공개 배포/기존 실행 프로세스는 변경하지 않았다.
