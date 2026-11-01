# EXHIBIT-scope1 — 새 단일 경기 묶음 로컬 인수

2026-11-01. 사용자 제공 새 ZIP·sidecar·RECEIPT를 원본 보존하고 인수했다. 최종 검사 코드 `9e3a8293911ff2a37b6cc27277891960f8c3d98d`; 도구 구현 `6ba78749f07c6075926474c1aaf99a9578ec5aeb`. **로컬 인수 합격이며 실제 배포·실기기·공동시험 합격은 아니다.** 현재 담당/다음 단위는 [CHECKLIST](../CHECKLIST.md)만 정본이다.

## 1. 입력과 범위

- ZIP `bundle-849843-main-c47fe6cb-20261101.zip`: **182,517 bytes**, SHA-256 `3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51`.
- sidecar 107bytes, SHA `a762ee93299749329d8b3a9a967da12c6c5da0a356a9c38cdf0f948370a038bb`.
- 별도 RECEIPT 4,062bytes, SHA `f4905d574305b1df771a4b964d8cc5398f5adec70f779ac7808178321fe265b0`.
- 웹 소스 선언: `c47fe6cb78479362e7250141da946814cc33bd31`.
- 자료 생성 소스 선언·v1 manifest commit: `cb1cfa8f759fd77adc75595316a389208c752dba`. 웹 커밋으로 덮어쓰지 않는다.
- 원본·추출본·개별 화면/명령 로그: Git 밖 `D:/pitcheezy_exhibit_check/scope1-c47fe6cb-20261101/`. `original/`, `received/`, `browser-final/`, `host-browser-final/`을 사용한다. 최초 검사 `browser/`·`host-browser/`도 보존했다. 자격·실제 시험 주소는 없다.

## 2. 실제 검사

- CRC·안전 경로·중복/대소문자/파일-부모 충돌·symlink·암호화·확장 크기 검사 통과. ZIP **20파일**, manifest **19행**(자신 제외), 원본 SHA/크기와 LF 정규화 SHA 모두 일치. 확인 후에만 루트 폴더를 제거해 새 폴더로 추출했다. 받은 `verify_bundle.py`는 실행하지 않고 바이트로만 검사했다.
- `site/` 웹4 + JSON6 = **10파일/1,159,353bytes**. index SHA `85616c4b2f49c5f9f0252bc9a687606fbbe6ce2e54253424bc956803db5a4289`.
- **849843·2026-09-30 한 경기/하루, 262구·71타석·추천246·미지원16**. 키 고유·연속 index·타석 구수/경계 일치. setup39키는 경기 내 키이며 estimated27/unavailable12. 광고 날짜1/실제 날짜파일1, 누락0.
- 완료 경기 archive, `next=null`. 저장된 health에 `game_checks['849843']` 존재, manifest 기본 주기10초. 과거 health는 실시간 발행기 생존 증거가 아니다.
- 우리 인수 도구 **Python63**, 로컬 호스트 도구 회귀 **Node10**, 브라우저 파일 변조/누락/추가 거부 **Node3** 통과. 기록 갱신 뒤 체크리스트8·JSON4·상대 링크·diff 공백 검사도 통과.
- **실제 받은 화면 Chrome headless 50/50**: 1440·390·320폭, 지정 경기/날짜, 가로 넘침 없음, 타석 선택, 안내 시 추천·존·타석목록 숨김, 일반 오류 후 과거 추천 미노출, 정상 자료 뒤 새로고침 없는 복원. 변경 없는 경기의 재확인 조건도 검사했다. 해당 polling 검사는 가상 시계를 진행했으며 실제 안내 반응 시간/요청량 측정이 아니다.
- **우리 Worker 로컬 연결 58/58**: 빈 로컬 저장소에 기존 발행 API로 JSON6 입력·읽기 원본 일치, 정적4 바이트 일치, 인증 없는401→로그인200, 안내503→정상200 및 열린 화면 복원. 인증 후 제외 경기/셋업849845·날짜2026-09-29 직접 경로404. 이는 새 저장소에서의 동작이며 기존 Cloudflare 자료가 차단됐다는 뜻이 아니다.
- 로컬 실제 시계 안내 반응: PC 숨김9,294ms/복원2,613ms, 390폭 숨김10,359ms/복원3,685ms. 각1회·loopback 측정이며 Cloudflare 지연이나 상한을 보장하지 않는다. 이 테스트는 가상 시계를 쓰지 않았다.
- PC/390 캡처 직접 확인. 폰은 Chrome 화면 크기 모사이며 실제 iPhone Safari가 아니다. 시험 서버·브라우저 종료 완료. 받은20파일은 최종 검사 후에도 바이트 불변이다.

영수증의 공통 limitation에 있는 `missing dates retained`/누락 날짜404 설명은 과거 묶음도 검사하는 도구의 일반 문구다. 이번 `missing_date_files=[]`, `missing_advertised_date.date=null`이며, 광고된 날짜가 누락된 관측은 없다. 실제404 검사는 명시한 전시 제외 경로를 대상으로 했다. 문서 읽기 감사에서도 배포/실폰/검토 범위 혼동과 비공개 값 노출은 발견하지 못했다.

## 3. 다른 모델 검토

다른 모델 **gpt-6.1-terra**가 우리 검사 도구 고정 `6ba7874`를 읽고 P2 두 건을 제기했다. 브라우저가 영수증과 다른 파일도 시험할 수 있던 문제, 호스트 영수증의 자료 생성 커밋 누락이다. `9e3a829`에서 전체 파일 목록/크기/SHA를 검증하고 검증된 메모리 바이트만 제공하며, 두 커밋과 선언 근거를 분리했다. 변조/누락/추가 거부3검사 추가. 재검토 **APPROVE**, 검토 범위에서 남은 P1/P2 없음. 운영 runtime5 Git blob은 승인 후보 `aa6f7ab`와 동일하며 배포 코드는 바꾸지 않았다.

이 검토는 **우리 인수·리허설 도구** 대상이다. Song 앱 전체 소스 교차검토(EXHIBIT-review3)·소스 재빌드와 구별한다. 발신자 RECEIPT의 작성/검토 모델 ID는 미검증이며 ZIP 밖 증거6개는 해시만 받았다. 발신자의 schema6/Chromium61 결과를 우리 재실행 결과로 쓰지 않는다. 이번 우리 구조·관계 검사는 전체 JSON Schema 재검증을 대체하지 않는다.

## 4. 재현

지정 작업 폴더에서 아래 명령을 실행한다. `<새 출력>`은 존재하지 않는 폴더를 사용한다. 실제 서버 접속을 하지 않는다.

```text
python -I -B scripts/intake_exhibition_bundle.py <원본ZIP> --profile exhibition-c47fe6cb --output <새 추출>
python -B -m pytest tests/test_exhibition_bundle_intake.py -q -p no:cacheprovider
node --test tests/browser/exhibition-build-integrity.test.cjs
node --test ops/public-host/tests/exhibit-host.test.mjs ops/public-host/tests/exhibit-tools-imports.test.mjs
node tests/browser/exhibition-build-acceptance.cjs <추출>/site <새 브라우저 출력>
node ops/public-host/rehearse-exhibit-host.mjs --site <추출>/site --receipt <추출>/intake-receipt.json --out <새 호스트 출력> --expect-data 6 --browser --access --playwright <설치된 Playwright 모듈>
```

브라우저 명령의 `PLAYWRIGHT_MODULE`은 `tests/browser/node_modules/playwright` 절대경로로 설정했다. Python3.12, Node24.1.0, Chrome155.0.8059.86, Playwright1.62.1, Miniflare4.20260730.0. 테스트 합성 자격만 사용했으며 실제 접속코드/토큰을 읽거나 생성하지 않았다.

[인수 영수증](results/exhibition_20261101/scoped-build-intake.json) · [화면50](results/exhibition_20261101/scoped-build-browser.json) · [로컬 호스트58](results/exhibition_20261101/scoped-host-local.json) · [검토·보존](results/exhibition_20261101/scoped-intake-review.json)

## 5. 다음 적용 조건

별도 시험 호스트의 새 Worker/R2/D1·요청 제한 공간·자격을 준비하고 사용자에게 범위/복구를 설명한 뒤 원격 단계별 승인을 받는다. 정적4와 업로드API 입력6을 분리하고, 접근 제한ON·수집/피드백OFF·로그 저장을 유지한다. 실제 바이트·안내·인증·제외URL404·요청량·폰 지정 경기 동선이 통과한 뒤에만 app 연결 교체를 별도로 승인받는다. 기존 앱과24자료·홈·영상·연구는 보존한다.

새 호스트·배포·DNS/Route·Cloudflare 설정 변경·#38 발신·PR상태 변경은 이번 단위에서0건이다. 최신 [회신 초안](mail_drafts/EXHIBIT-song-reply2-20261101.md)은 사용자에게 제시 후 발신 결정을 받는다. 로컬 시험 합격으로 접근 제한을 끄거나 실제 공동시험 합격을 기록하지 않는다.

## 후속 소스 표본 검토 — 전체 검토는 미완료

검토 도구에서 gpt-6.1-terra를 선택해 고정 웹 `c47fe6cb78479362e7250141da946814cc33bd31`의 읽기 전용 검토를 수행했다. 원래 프롬프트 대상32e79c2f와 새 후보를 혼동하지 않았다. 기준 `61be7a86fdea108caed975cdde98d63296be50ad` 대비 GitHub 비교가 반환한173파일 중 요청 범위91파일이며, 변경4파일의 전부 또는 일부와 기존 publish.ts 일부를 읽었다. 나머지87파일·실행 검증은 미완료다. API 반환 목록의 완전성도 독립 확인하지 않았다. 따라서 EXHIBIT-review3 전체 합격은 판정하지 않는다.

정적 코드에서 **P2 후보**를 찾았다: API 모드의 완료 경기에서 안내503 → 자동 재시도404 → 서버 정상화 순서이면 자동 복원이 멈출 수 있다. `GameScreen.tsx`325–337의 완료 경기 pollMs=0과351–354의0/5xx 한정 재시도 때문에,282–287의 hold가416–427의 화면 차단으로 계속 남는 경로다. 실행 재현은 하지 않았다.

이 경로는 현재 받은 **정적 전시 모드의 차단 근거가 아니다**. 같은 파일332–345는 자료가 있는 정적 모드에서 완료 경기의 auto/pinned 모두 polling을 유지하고,250–257은 hold 중 health만으로 조기 반환하지 않으며 game 본문을 요구한다. publish.ts17–45는 양수 polling 간격을 보장한다. 가시 탭·정상 타이머 전제이며, 우리 받은 정적 빌드의 안내/복원 로컬 검사는 앞 절의 별도 실측 근거다.

고정 근거: [GameScreen](https://github.com/SongRoute/pitcheezy/blob/c47fe6cb78479362e7250141da946814cc33bd31/apps/observer/web/src/service/GameScreen.tsx#L250-L354), [publish 설정](https://github.com/SongRoute/pitcheezy/blob/c47fe6cb78479362e7250141da946814cc33bd31/apps/observer/web/src/service/publish.ts#L17-L45). 후속 회신 시 재현 미실시·API 모드 한정을 함께 전달한다. 사용자 지시에 따라 지금 발신하지 않았다.

운영 ws_alert.py는 기준914줄→대상923줄,542–550의 ops_armb_off 규칙9줄 삽입 외 앞/뒤 바이트가 동일한 것을 메모리 비교했다. 이것으로 전체 알림·발행기 검토를 대체하지 않는다. 팀원 파일·프로세스·배포는 변경하지 않았다.
