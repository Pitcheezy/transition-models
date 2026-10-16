# WS-stage4 — 승인된 Cloudflare 합성 시험

2026-10-16. **본인 전용 신규 자원의 실제 HTTPS 시험을 완료했다.** 이용 기록·피드백은 계속 OFF이며, 시험 종료 뒤 자료 읽기·업로드도 OFF로 복귀했다. 기존 사이트·팀원 코드/프로세스/배포·실경기·메일 발송은 변경하지 않았다.

기준 main `0905874d783eb999776c4cbc75a8dd17feb9db32`, 선점 `e9a8fa1`, 초기 host `c07dc942030e5ec4f100f638d572239524cd327e`, 최종 배포 host `87168d7bc42f11f76886e475f919caff7674b60a`.
[합격 기준](https://github.com/Pitcheezy/transition-models/issues/3#issuecomment-6207325376) · [시험 영수증](results/ops/ws_stage4_20261016.json).

## 실제 만든 것과 최종 상태

- 사용자가 구체 범위를 승인한 뒤 전용 Worker 1개, private R2 Standard 1개, 빈 D1 1개, 접근 제한된 시험 Custom Domain을 생성했다. Workers Free를 유지했다. 월 $10는 준비 예산이며 청구 상한이 아니다.
- R2 공개 개발 URL OFF·R2 사용자 도메인 없음, Worker 기본/preview URL OFF를 확인했다. D1 `0001_telemetry.sql` 적용 후 Worker를 배포했다.
- 접근/서명/발행/안내 비밀 네 개를 등록했다. 실제 gate=true와 비밀 이름을 조회한 뒤 시험 호스트를 연결했다. 비밀 값·계정/자원 식별값·접속 주소는 공개 기록에 넣지 않는다.
- 최종 실제 재조회: 접근 문 ON, 세션3600초, 자료 읽기/업로드/이용 기록/피드백 OFF, 안내 OFF. 자원은 보존했다.
- D1 최종 SELECT: usage_sessions=0, feedback=0, telemetry_budget=0, DB65536bytes. 이는 저장 행 수이며 방문자0명을 뜻하지 않는다.
- API 토큰의 확인된 만료는 같은 날21:00 KST다. 자동 만료 전후 상태는 별개이며, 다음 작업에서 만료된 자격증명을 반복 사용하지 않는다.

## 실제 시험과 발견한 결함

자동 HTTPS 요청은 총88회, 요청 본문은 누적614bytes였다. 합성 공개 JSON 자체는22bytes다. 브라우저·Cloudflare 관리 API 호출은 이 카운터 밖이며 계정 전체 요청 수는 미측정이다. 최대199회/본문5MiB 제한은 시험 helper의 제한이며 인터넷 요청·청구의 상한이 아니다.

1. 초기17요청 통과: 미인증 page/asset/JSON401, 잘못된 코드 거부, 로그인/로그아웃, v3 Secure·HttpOnly·SameSite=Strict 쿠키와3600초 설정, 수집OFF, 읽기/업로드OFF.
2. 초기 active는12요청에서 중단됐다. 첫 PUT 결과가 unknown이었다. 중복 쓰기를 하지 않고7요청의 읽기 진단으로 저장된 합성 SHA·원문 일치를 확인했다. 업로드 HEAD는 Brotli 응답과 weak ETag를 반환했다.
3. gateway·notice의 **ETag가 있는 응답에만** `Cache-Control: no-store, no-transform`을 추가했다. 강한 ETag 검사와 조건부 갱신 규칙을 약하게 바꾸지 않았다. [Cloudflare 압축 설명](https://developers.cloudflare.com/speed/optimization/content/compression/)의 no-transform 지침과 실제 전후 결과를 근거로 한다.
4. 고정 수정 커밋을 다른 모델이 검토한 뒤 새 후보를 재배포했다.36요청 재개 통과: 기존 HEAD/SHA와 GET 바이트 확인 → 현재 ETag로 동일 바이트 PUT 성공 → HEAD/GET/304 → 중복 생성412 → 철회/404 → 복구/새 ETag → 과거 ETag 삭제412 → 안내ON/503·OFF/200와 감사2건.
5. 최종 OFF 배포 후16요청 통과. 설정 재조회로 gate/비밀 유지, 네 토글OFF, 기본/preview URL OFF를 다시 확인했다.

실제 노트북 Codex 브라우저에서 접속 코드 화면 → 로그인 후 합성 화면 → 복구된 합성 JSON을 확인했다. 이는 Song 관전 화면이나 실경기 시연이 아니다. 안내 HTML의 실제 브라우저 시각 검수와 Mac/아이폰 검수는 이번에 하지 않았다.

## 검사와 검토

- 집중 Node61개 통과. 전체 첫 검사는242/243: 기존 리허설의 Cache-Control 전체 문자열 비교1개가 실패했다. 두 리허설 도구에서 정확한 no-store 지시어 존재를 검사하도록 고쳤고, 잘못된 부분 문자열/파라미터를 계속 거부하는 회귀 검사를 추가했다.
- 최종 Node243/243, 리허설 집중6/6 통과. Windows workerd 종료 경고가 있었지만 최종 검사 실패는0이다.
- 다른 실제 모델 `gpt-5.6-sol`이 운영 고정 커밋 `87168d7`을 검토해 P1/P2 없음. 독립 focused 실행53통과/8환경 실패(EACCES)를 통과로 세지 않았다. 별도 순수 Worker32/32 통과. 후속 리허설3파일도 읽기 교차검토 P1/P2 없음.
- 수정 묶음13파일·109338bytes, ZIP SHA `8adbaca96f91d3f733bd91e8cfc0abf1d1e84f1636fc6a45ef72e6e36868c1ea`. manifest SHA `210b40d4b2981c2a10f38696d3dd6b86d4294aea6e4ca51bc72bc4d6829412a3`.
- 초기 후보와 수정 ON/OFF 후보는 각각 원본16파일을 보존했고 도구 복사본의 원래16파일과 바이트 일치를 확인했다. 모든 후보는 `mode=synthetic`, `deployable=false`를 유지한다. 가상 frontend 출처111…은 실제 Song 화면 출처가 아니다.

## 재현과 비공개 증거

실제 계정 재실행은 유효한 권한·합의된 자원/접속 범위를 먼저 확인한다. 다음 명령의 식별값·비밀은 비공개 실행안에서만 받는다. 셸 인수에 비밀 값을 넣지 않는다.

```text
node --test ops/public-host/tests/*.test.mjs
python -B -S scripts/build_public_host_release.py build --frontend ops/public-host/examples/synthetic-dist --provenance ops/public-host/examples/synthetic-provenance.json --host-commit 87168d7bc42f11f76886e475f919caff7674b60a --mode synthetic --output <새 출력>
python -B -S scripts/check_public_host_config.py <검증 후보>
node <고정 Wrangler 4.151.0> d1 migrations apply TELEMETRY_DB --remote --config <시험 설정>
node <고정 Wrangler 4.151.0> deploy --config <시험 설정> --env-file <빈 env>
node <고정 Wrangler 4.151.0> secret bulk --config <시험 설정> < <비공개 stdin>
node <비공개 helper v3> --mode active-resume --output <새 결과 파일명> --execute
node <비공개 helper v3> --mode finish --output <새 결과 파일명> --execute
```

helper의 환경 변수는 `PITCHEEZY_STAGE_ORIGIN`, `PITCHEEZY_ACCESS_CODE`, `PITCHEEZY_PUBLISH_TOKEN`, `PITCHEEZY_NOTICE_TOKEN`이다. Cloudflare 관리에는 `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`를 별도 프로필의 자식 프로세스에 전달했다. 실제 설정/관리 로그/원본 후보/helper/브라우저 캡처는 Git 제외 비공개 경로에 있다. 영수증에는 해시와 비식별 검사 결과만 남긴다.

## 실행 절차의 편차

착수 댓글에는 문제가 생기면 시험 경로를 먼저 끊는다고 적었으나, ETag 결함 때에는 추가 쓰기만 중단하고 접근 제한 경로는 유지한 채 읽기 진단·수정 배포를 했다. 접근 문은 계속 정상이며 기존 사이트/실자료를 열지 않았지만, 이 절차를 그대로 준수했다고 주장하지 않는다. 도메인 경로 해제 자체는 이번에 시험하지 않았다.

## 한계와 다음

Cloudflare 집계 화면은 No data였고 R2 aggregate는 실제 GET 성공 뒤에도0으로 표시됐다. 이를 실제 요청0/CPU0/저장0으로 해석하지 않는다. 전체 요청·CPU·집계 저장량·미래 청구는 미측정이다. 1시간 실제 만료·cron 실행·다중 지역 전파·부하 한계도 미측정이다. 승인된 합성 파일이 존재한다는 사실은 파일 계약·모델·과학적 효용의 검증이 아니다.

다음은 Song의 고정 관전 화면/발행기 전달물 수신, 양쪽 알림 수신자·응답 시간·안내 문구와 운영자 조작 경로 결정, 별도 승인된 실제 연결이다. 10/20 연락 조건 결정과10/21 동결 규칙을 유지한다. 실제 공개 운영이나 다른 사람의 접속 허용으로 이번 승인을 확대하지 않는다.
