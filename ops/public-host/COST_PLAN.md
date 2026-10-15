# 트래픽·비용 가정 — WS-ops4e

이 문서는 **실측이나 결제 승인 없이 산정한 운영 후보**다. 가격은 2026-10-12 공식 문서 조회값이다.
계정에 과금 상품을 추가하거나 배포하지 않았다. 실행 환경은 Python3.12 표준 라이브러리다.

## 먼저 볼 결과

7경기 × 경기당3시간 동안 평균100/1,000/10,000명이 보고, 5초마다 JSON2개를 읽는 가정이다.
피크 접속자는 평균의3배, JSON은32KiB, Worker CPU는 요청당5ms로 가정했다.
**CPU5ms는 측정값이 아니다.** 로컬 리허설의 HTTP 왕복 시간을 CPU 과금 시간으로 사용하지 않았다.
방문자 수/주기/크기는 실제 Song 화면 또는 경기에서 측정하지 않았다.

| 가정 | 공개 JSON 요청 | 피크 공개 요청/초 | JSON 전송량(GB) | 월간 기본 포함량이 남은 경우 | 포함량 소진 가정 |
|---|---:|---:|---:|---:|---:|
| 평균100명, 5초 | 3,024,000 | 120 | 99.09 | $5.00 | $12.19 |
| 평균1,000명, 5초 | 30,240,000 | 1,200 | 990.90 | $21.26 | $32.98 |
| 평균10,000명, 5초 | 302,400,000 | 12,000 | 9,909.04 | $229.85 | $241.56 |
| 평균1,000명, 1초 | 151,200,000 | 6,000 | 4,954.52 | $113.21 | $124.92 |

표의 전송량은 기본 공개 폴링 본문만이며 추가 조회·업로드·HEAD를 포함한 전체 트래픽이 아니다.

금액은 Workers Paid Standard + R2 Standard + D1 Paid의 **명시한 사용량 소계**다.
두 열 모두 월 기본요금$5를 한 번 포함한다. 오른쪽은 계정의 다른 사용량 청구서나 증분 금액이 아니고,
무료 포함량이 남지 않았다고 놓은 민감도 계산이다. 실제 계정 잔여량·월 경계·계약은 확인하지 않았다.
별도 제품·도메인·세금·환율·로그·알림·미입력 재시도/봇 요청은 제외하므로 실제 청구 상한이 아니다.
현재 예제는 수집 OFF이며 D1 사용량을0으로 둔다. 수집 ON 견적은 실제 D1 행 수를 따로 넣어야 한다.

## 공식 가격과 반영 방식

- [Workers 가격](https://developers.cloudflare.com/workers/platform/pricing/): 월$5, 요청1천만/CPU3천만ms 포함,
  초과 요청100만당$0.30·CPU100만ms당$0.02를 적용했다. Free는 일10만 요청 제한이며 Paid는 초과 과금이다.
- [정적 화면 과금](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/):
  우리 설정은 run_worker_first=true이므로 asset 요청도 Worker 요청에 넣는다.
  정적 파일을 최종 반환한다는 이유만으로 Worker 호출을 무료로 빼지 않는다.
- [R2 Standard 가격](https://developers.cloudflare.com/r2/pricing/): 10GB-month/A100만/B1천만 포함,
  초과 GB-month당$0.015·A100만당$4.50·B100만당$0.36. 초과 작업은100만 단위,
  저장은1GB-month 단위로 올림한다. GB-month는 기간 평균 일별 peak 저장량이며 현재 파일 크기 한 번과 다르다.
  R2 직접 전송료는 없지만 읽기 연산 비용은 있다. Infrequent Access는 이 계산 대상이 아니다.
- [D1 가격](https://developers.cloudflare.com/d1/platform/pricing/): Paid 읽기250억/쓰기5천만 행·저장5GB 포함,
  초과 읽기100만행$0.001·쓰기100만행$1·GB-month$0.75. SQL 횟수나 이벤트 수로 행 수를 대신하지 않는다.

작업량 원시값은 Decimal로 계산하고 금액은 마지막 소계에서 센트 반올림한다.
Worker/D1는 표기된 단가 비례식이며, 공급자의 최종 청구 반올림/계약을 복제한 회계 프로그램은 아니다.
가격이 바뀌면 코드의 PRICING_DATE/단가·이 문서·회귀 예제를 함께 갱신한다. 자동 최신 가격 조회는 없다.

## 코드에서 확인한 요청별 영향

`gateway.mjs`의 공개 GET/HEAD는 R2 get/head1회, 업로드 HEAD는 head1회다.
PUT은 put1회이고 **우리 DELETE도 tombstone을 쓰는 put1회**다. R2 물리 DeleteObject 무료 규칙을
우리 HTTP DELETE에 적용하지 않는다. limiter가 먼저 막으면 R2는 호출하지 않지만 Worker 요청은 발생한다.

`telemetry.mjs`의 session/feedback은 각각7/5문장 batch이며 budget/중복 검사도 실행된다.
보조 index와 정리 DELETE·집계 읽기가 있으므로 이벤트당1쓰기라고 계산하지 않는다.
실운영 D1 meta.rows_read/rows_written 또는 계정 metrics에서 실제량을 얻어 입력한다.

현재 공개 JSON은 no-store이며 WS-ops2 이후 강한 ETag 조건부304를 지원한다. 공유 캐시 최적화는 구현하지 않았다.
304 판정도 원본 R2를 확인하므로 읽기 횟수를 cache hit로 임의 차감하지 않는다. 갱신 주기를 줄이면 지연도 달라지므로
단순 비용만으로 정하지 않고 다음 투구 전 표시 비율을 함께 측정해야 한다.

## 재현과 입력

~~~text
python -B -S scripts/estimate_public_host_cost.py ops/public-host/examples/cost-scenarios.json
python -m pytest tests/test_public_host_cost.py -q
~~~

[고정 결과](../../docs/results/ops/ws_cost_scenarios_20261012.json)는 위 CLI 출력이다.
실제 입력 파일을 바꿔 새 결과를 만들 때 이 예제 실측 여부를 true로 고치지 않는다.

- viewer_hours: 청구 기간 전체의 모든 시청자 시청시간 합(시간). 경기 수나 동시접속 수 그 자체가 아니다.
- peak_viewers / poll_seconds / objects_per_poll: 피크 접속·갱신 초·주기당 JSON 수.
  공개 요청량=viewer_hours×3600×objects_per_poll÷poll_seconds를 올림한다.
  세션별 최초 로드/재시도/추가 탭/백그라운드 폴링은 이 단순식에서 복원하지 못한다.
- extra_worker_requests: static asset·telemetry·오류·초기 로드·봇·감시 등 **기본 폴링/발행 호출 밖** 요청 합.
  예제는 크기별50,000/500,000/5,000,000으로 가정한다. 사용자가 측정해 교체해야 한다.
- publisher_puts/deletes/heads: 발행기의 각각 전체 호출 수. 예제10,000/10/10,010.
- extra_r2_reads: 기본 폴링/발행 HEAD 밖의 R2 읽기. 예제2,000. 감시의 Worker 호출은 위 extra에도 넣는다.
- mean_cpu_ms / mean_json_bytes: 요청 평균 CPUms·JSON 평균 바이트. 네트워크 왕복시간과 다르다.
- r2_storage_gb_month / d1_storage_gb_month: 실제 계정의 기간 저장 측정량 또는 명시적 가정.
- d1_rows_read/written: 전체 SQL·중복/거부·정리/집계/관리 쿼리까지 반영한 행 수.

한 파일에서 최대20가정을 비교한다. 입력은 엄격한 JSON이며 bool/음수/무한/NaN/분수 요청 수,
잘못된 갱신 주기·중복 이름·초과 크기를 거부한다. 읽기 전용이고 네트워크·계정·결제 호출은 없다.

## 운영자가 결정할 것

제안 예산을 합의하기 전에 실제 수신 파일의 크기·발행 빈도, 화면 폴링 수·백그라운드 동작,
예상 시청자 시간, CPU 및 D1 측정을 넣어 다시 계산한다. 비용 알림과 실제 중지 권한을 정한다.
현재 업로드 limiter와 D1 일별 쓰기 상한은 **전체 HTTP·DB 읽기·월간 금액 상한이 아니다**.
정적 사이트/공개 조회 남용은 별도 edge 운영 문제다. 계정별 CPU 제한도 요청1건의 제한이다.
호스팅/예산 확정 후에만 실제 배포·부하·알림 연결로 진행한다. 지금은 아무 구매도 하지 않았다.
