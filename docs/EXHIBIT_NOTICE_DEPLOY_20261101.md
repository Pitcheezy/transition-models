# 전시 안내 문구 배포·회신·QR 후속 — 2026-11-01

현재 상태와 다음 작업의 정본은 [CHECKLIST 상단](../CHECKLIST.md)이다. 이 문서는 이번 고정 실행의 증거다. 형의 고정 빌드·데이터·코드는 변경하지 않았다.

## 범위와 결론

사용자가 준비된 #38 회신 게시, maintenance 문구 배포, 폰 QR 확인, 형 요구 이후 작업 리뷰를 승인했다. 배포 전에 기존 적용 버전·설정·자격 보존과 복구 범위를 설명했다. 새 접속 대상·요금·DNS·Sites·PR 병합/닫기는 포함하지 않았다.

- [Song #38 회신 게시](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6555601601): 준비된 본문 1회 게시 후 원문 대조 일치. UTF-8 본문 SHA-256 `f487957f982b250a36415ef697e0e8e2442d2d913b65d14ca56fdd84a5c1703c`.
- 앱 신규 적용 버전: `6d652d4b-7d3c-4897-aefd-f37d0edce50c`.
- 호스트 소스: `c47643ace740d45898300b1f9f0d6e4184d8bd82`. 제품 문구 변경은 `0885a5a7836b08e14e5ac01a37ce0725223e9300`.
- 형 화면 소스: `fba6b2ff846dcfa9afad9ea5df4204007e0604c1`, 정적4파일·자료24개 원본 불변. 배포 후 원격 검사 **35/35**.
- 실제 maintenance ON→OFF 성공. 최종 OFF revision8, 접근 코드 ON, 자료 읽기 ON, 업로드·수집·피드백 OFF 유지.
- 사용자는 iPhone Safari·Chrome에서 홈과 서비스 접속 코드 화면이 열린다고 확인했다. 카메라 스캔·홈 영상·인증 뒤849843 화면까지는 미확인이다. 아래 브라우저 폭 검사를 실기기 완료로 쓰지 않는다.

## 배포와 보존 검사

기존 검토 후보 ZIP(535,003bytes, SHA `01b486601d5d5beb80806e555f0d5e41902ee0877caf5681fab9c8f40c5815ff`)을 새 폴더에 풀고 기존 설정을 복사했다. 후보 manifest SHA는 `2f3cc83d1f88e370146d83a2e283d9cf970c1a9bbf633e2d33e0bce4dea25a5c`다.

명령 순서(비공개 경로·값 생략):

1. `python -B -S scripts/check_public_host_config.py <후보 폴더>`로 채운 설정 검사.
2. 고정 `ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js` 4.151.0의 `deploy --dry-run --env-file <빈 파일> --config <복사본> --outdir <새 폴더>`. 별도 HOME/캐시/임시 폴더, 자동 dotenv·키링·진단 전송을 끈 격리 환경.
3. 현재 deployments/version 조회로 실제 적용 버전 `feed4fc1-949d-4672-98fb-35f4ab00fdc3`와 vars/bindings/로그 설정 대조. 이 버전은 자격 교체 이후 기준이다. 자격 교체 전 버전으로 복구하지 않는다.
4. 같은 고정 CLI `deploy --env-file <빈 파일> --config <새 배포 복사본>` 실행. 저장된 기존 로그인만 사용했으며 secret put·새 자격 발급·교체는 하지 않았다.
5. 배포 후 version 조회: vars·bindings·런타임 설정 전후 일치, 기존 secret 항목4개 유지. 실제 관람 로그인과 안내 운영자 인증도 성공했다. 저장된 secret 원문을 읽어 바이트 비교했다는 뜻은 아니다.
6. `node ops/public-host/verify-exhibit-remote.mjs --origin <공개 앱> --site <받은 site> --receipt <인수 영수증> --out <새 영수증> --notice-check`로 대조했다. 결과는 [원격 영수증](results/exhibition_20261101/notice-deploy-remote-verify-20261101.json).

dry-run 로컬 worker.js는 53,847bytes, SHA `eb82b58cc07c09e8c556d68b52618185f4372186f6c0adce42acc755fb67de9b`. 실제 서버의 컴파일된 worker.js를 내려받아 같은 해시라고 검증한 것은 아니다. 후보의 `deployable=false`는 오프라인 후보 검사 형식이며, 이후 승인된 실제 배포 기록은 이 문서의 적용 버전으로 구별한다.

대시보드 확인: Workers Logs ON, invocation 포함·저장 ON, 수집 비율100%, Traces/Issues OFF, Runtime cache Disabled. 설정 확인은 요청별 저장 로그 8단계 대조 완료를 뜻하지 않는다. DNS·도메인·홈·영상·R2 경기 데이터는 변경하지 않았다.

## 실제 안내 ON/OFF와 정상 복귀

기존 `notice-cli.mjs`의 조회→현재 ETag 조건부 변경→재조회 순서를 각1회 실행했다. 토큰은 비공개 파일에서 기존 환경 변수로 전달했고 명령행·영수증·Git에는 넣지 않았다. 자동 재시도는0이다.

- 사전 OFF revision6 → ON revision7: PUT200, `audit_recorded=true`, GET에서 ON·감사 기록 가용 확인.
- ON의 앱 HTML과 manifest: 각각503, no-store, 승인 문구 일치·개발용 공통 설명 없음. 08:39:40.739Z / 08:39:41.051Z. 실제 브라우저에도 **“잠시 자료를 확인하고 있어요. 곧 다시 보여 드릴게요.”**가 표시됐다.
- OFF revision8: PUT200, `audit_recorded=true`, GET에서 OFF·감사 기록 가용 확인.
- 08:40:20~21Z 최종 검사: 인증 없는 홈·manifest401, 발행 HEAD503, 기존 코드 로그인200, 인증 후 지정 경기 진입·manifest200 및 원본 바이트 일치.
- 브라우저의 직접 안내 HTML은 정적 페이지이므로 OFF 뒤 새로고침하여 접속 코드 화면 복귀를 확인했다. 이 관측을 **이미 열린 인증 앱의 자동 복원 시간**으로 쓰지 않는다. 해당 동작의 로컬 검사는 이전 인수 기록이며 실제 폰 복원 시간은 미측정이다.

이는 R2 안내 감사 기록·HTTP 응답 영수증이다. Cloudflare 요청별 저장 로그 전체를 대조했다는 뜻은 아니다. [비식별 실행 영수증](results/exhibition_20261101/notice-deploy-receipt-20261101.json)에 상태·시각·Ray·버전과 한계를 남겼다.

## 포스터 QR와 모바일 동선

원본 포스터 이미지(5,457×7,716px, 22,231,258bytes, SHA `4ef2fe5b629dbe24d85f509165a0f99676dd72681f37105209b8ee4fa2b7ded9`)를 OpenCV `QRCodeDetector().detectAndDecode`로 읽은 결과는 **`https://pitcheezy.com`**이다. 이미지·QR 수정은 없다.

실제 공개 홈을 브라우저에서 390×844와 320×740으로 검사했다. 각각 scrollWidth375/305로 가로 넘침 없음, 영상 readyState4·재생 중·오류 없음. 서비스 링크4개가 모두 `https://app.pitcheezy.com/?game=849843`를 가리킨다. 작은 폭에서 링크를 눌러 지정 경기 주소의 접속 코드 화면으로 이동함을 확인했다. 검사를 마치고 임시 화면 크기를 해제했다.

이 결과는 PC 브라우저의 모바일 크기 검사다. 실제 iPhone/Android의 카메라 스캔·쿠키·영상 재생·추천 화면은 별도 사용자 확인으로 남긴다. 앞선 Claude의 iPhone 접속 확인을 이번 전환 후 전체 QR 동선으로 재사용하지 않는다.

## 형 요구 이후 독립 리뷰

- 다른 모델 **gpt-6.1-terra**: 고정 호스팅 코드·안내·권한·캐시 처리·배포 후보를 읽기 검토. 새 차단 결함을 발견하지 못했다. 실제 Cloudflare 조작은 검토자가 실행하지 않았다.
- 별도 홈/클립 검토: 홈 한 페이지→형 고정 앱, 261클립 등록부, 제외 `849843:69:2`에서 정지, 같은 투구 ID 수동 맞춤이 형 요구와 일치. `node --test --test-reporter=spec tests/js/clip_chain.test.cjs` **30/30**.
- 발견·수정한 운영 문서 P2 두 건: 접속 코드가 보이면 자동으로 제한을 끄라는 지시를 **공개 범위 승인 전 ON 유지**로 정정. 시간당480회 계산을 검증된 수용량처럼 쓴 문구를 **계산치·30~50명 실측 미완료**로 정정. 재검토 통과.
- `NOTICE.md`는 승인된 maintenance와 미승인 data_hold를 분리했다. data_hold는 전시용 안내로 사용하지 않는다.

남은 항목:

1. 접속 코드 화면의 기존 **“개발용 입력 화면(승인 전 문구)”**는 별도 `access.mjs` 문구다. 이번 maintenance 배포 범위에 포함하지 않았다. 공개 전 문구 승인·수정·검토 대상으로 남긴다.
2. 실제 폰 QR 전체 동선, 8단계 요청별 저장 로그 영수증, 실제30~50명 용량은 미완료다.
3. 날짜 목록23일/파일5일의 차이, 포함된 다른14경기 유지 여부, 형의 `review/PROMPT.md`는 이번 #38에서 확인 요청했다. 원본은 임의 수정하지 않았다.
4. v4 클립팩 비공개 전달·두 모니터 실물 리허설·PR 정리는 별도다. 기존 코드·연구·폴더·PR은 삭제하지 않았다.

## 재개

CHECKLIST 상단을 먼저 읽는다. #38 발신과 이 안내 배포를 반복하지 않는다. 사용자 폰 응답을 받으면 기기·브라우저·확인 범위를 기록한다. 추가 배포·접근 범위 변경·새 대외 발신·PR 정리는 기존 승인 범위를 확인한다.

### 사용자 폰 응답·최종 기록 검사

사용자: “iphone safari chrome에서 모두 열리는데 서비스열기를누르면 개발용 입력화면이라고 나오네.” 홈·서비스 진입까지의 실기기 확인으로 기록하며 코드 입력 뒤 경기·추천 확인 완료로 해석하지 않는다. 접속 화면 문구 수정안을 다음 로컬 단위로 준비한다.

체크리스트8 passed, JSON 구문·필수 SHA 길이·현재 증거 상대링크·게시 원문 SHA 보존·diff 공백 검사 통과. 다른 모델 gpt-6.1-terra 최종 기록 검토 APPROVE. 기록 검토는 실제 서버·폰의 독립 재실행이 아니다.
