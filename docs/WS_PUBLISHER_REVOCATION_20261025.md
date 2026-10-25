# 본인 시험 서버 배포·발행 회수 — 2026-10-25

**검토된 우리 runtime 배포와 원격 바이트 일치, 같은 발행 토큰의 404→401→503, 실제 저장 로그 3건 대조를 완료했다.** 본인 시험 서버의 합성 키 검사다. 형 최신 화면 설치·실제 파일 발행·공동시험·10/27 공개 운영 합격을 뜻하지 않는다.

## 실제 수행

- 사용자 저장 관리 토큰이 active임을 확인했다. 응답에서 만료일은 제공되지 않아 관리 토큰 만료는 모름이다. 권한을 확장하지 않았다.
- Wrangler 4.151.0 deploy는 대시보드 route/domain metadata 조회403으로 **업로드 전에 실패**했다. 실패 출력과 실행 영수증은 보존했다.
- 기존 원격 worker.js에는 scope/expiry 코드가 없었다. 공식 Worker별 content API로 검토된 bundle만 교체하고 원격 다운로드의 전체 바이트를 대조했다. assets·비밀·저장소·로그 설정은 유지했고 버전 annotations만 변경됐다.
- settings PATCH에서 기존 binding 이름을 모두 inherit로 보존하고 합성 키 하나와 절대 만료를 추가했다. 업로드OFF에서 본인 시험 토큰 digest를 등록한 뒤, 업로드ON → HEAD → digest 폐기 → 동일 HEAD → 업로드OFF → 동일 HEAD 순서로 수행했다.
- 각 단계의 latest와 100% deployed 버전, 코드 바이트, scope/expiry, 다른 설정 보존을 재조회했다. 고정 키는 `v1/game/900000025.json`, 만료는 `2026-10-24T19:19:18.011Z`다. 첫 요청 뒤 두 값을 바꾸지 않았다.

10/25 KST 결과:

- 02:44:28.174: 정상 인증 **404**, 버전 `709fc392-c137-4bf0-9b97-682a06b56560`. 정확한 유효 경로에서 인증/범위 검사를 통과한 뒤 시험 객체가 없다는 응답이다. 업로드 성공200은 아니다.
- 02:45:10.151: 같은 bearer 회수 후 **401**, 버전 `2ce9cee4-7ad7-4731-9ea1-89994c54173b`. 유효한 폐기 digest로 교체했으며 만료 전에 확인했다.
- 02:45:25.498: 업로드OFF 후 **503**, 최종 버전 `cd97abb2-96f1-4e21-ba4b-85e641386f97`. 상태만으로 원인을 추측하지 않고 OFF 관리 설정과 동일 서버 버전을 함께 대조했다.

직접 시험 요청은 HEAD 3회, 서비스 PUT/DELETE 0회, 자동 재시도/리다이렉트0회다. 관리 API 요청·로그 저장·예약 D1 정리는 별도이므로 모든 계정 쓰기가0이라고 주장하지 않는다. 실제 파일 저장/철회/복구·만료 경계 시험도 하지 않았다.

## 출처·로그·검토

- runtime 기준: `e9b362b75d6d4768c552740bfc6e0124872805e1`; 기록 기준 main `24fea70f12ba53d3503823c90b3b06cec045a277`; 선점 `880a0aa`.
- release ZIP SHA256: `fd55a869abb21a153d6fb37970b52884cc290eddb4fce5b5d0de09707b30ec8c`.
- 배포 bundle 54,114bytes / SHA256 `3312fbff2dac2a22b32e474392ee7eb107663c79e9749781810a681e5ee07cfd`. 교체 직후와 시험3단계의 원격 모듈 바이트가 일치했다. 이전 원격 bundle과는 다르다.
- 서버 로그 원본: 15,352bytes / SHA256 `db3a577b96da106f0204dccdfdaf9ee2cd30f1004ddca69fe10dfe218f006d96`. Cloudflare 대시보드에서 JSON으로 내려받았다.
- [공유 영수증](results/ops/ws_publisher_revocation_20261025.json) SHA256 `4e9d4ac6c2cd4614417f4ead153ae8c3da2b78d9083eee8e245015250b1fce47`. 비공개 cf-ray로 각 요청과 서버행을1:1 연결하고 시각·method·path·status·version을 대조했다. 원본 헤더/IP/계정/접속 주소·token digest는 공유본에 없다.
- 기존 scope runtime의 다른 모델 검토는 [고정 소스 기록](WS_PUBLISH_SCOPE_20261017.md)을 따른다. 이번 비공개 API 도우미와 유한 HEAD 실행기는 작성 Codex(GPT-6 계열, 세부 모델ID 미확인), 별도 실제 모델 `gpt-5.6-sol` 읽기 검토PASS. 검토자는 토큰·원본 로그를 읽거나 실제 요청을 보내지 않았다.
- [공식 content API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/content/methods/update/)와 [settings API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/script_and_version_settings/methods/edit/)를 사용했다. settings의 전체 binding 목록에서 바꾸지 않는 이름은 inherit, 바꿀 값만 plain_text로 전달했다. Worker별 Editor 범위 안에서 수행했다.

재현 기록: `node <private-dir>/publisher-probe.private.mjs baseline|revoked|off`를 각 단계별 한 번 실행했다. 실행기는 phase별 exclusive 시작파일·결과파일, 동일 bearer/key/expiry, 새 관리 조회, maxAttempts1을 요구한다. 비공개 도우미 SHA는 영수증에 있다. **현재 자격은 회수됐으므로 기존 명령을 다시 실행하지 않는다.** 새 실험은 별도 승인 창/자격/원장으로 준비한다.

## 후속 확인

[비상 안내 후속 시험](WS_NOTICE_TRIAL_20261025.md)에서 새runtime의 복구 관람 코드 로그인·안내ON/OFF·같은세션복구·안내자격회수를 확인했다. 아래 새runtime후로그인미실행과 최종cd97abb2는 이 발행 시험 종료 당시 이력이다. 현재 배포 버전과 남은 로그 조건은 후속 기록을 따른다.

## 종료 상태와 남은 조건

접근문ON, 업로드/자료읽기/이용기록/피드백OFF. 시험 발행 digest는 폐기값으로 교체했고 원래 bearer는401이었다. scope/expiry 유지. Logs/Invocation/저장ON·100%, Traces/IssuesOFF이며 기존 observability 전체를 보존했다. 전역 enabled=false와 별도 logs.enabled=true가 함께 존재하는 기존 응답을 임의로 바꾸지 않았고 실제 저장 로그로 동작을 확인했다.

기존 관람200→같은세션401은 [별도 관람 시험](WS_VIEWER_REVOCATION_20261025.md)의4요청 증거다. 새 runtime 배포 후 관람 로그인을 다시 시험한 것은 아니다. 복구 코드 로그인·실제 안내 전환·형 writer 연결은 이번3HEAD 검사에 포함되지 않는다.

현재 assets는 기존 합성 화면을 보존했다. 형 UI를 새로 설치하거나 최신본과 같다고 확인하지 않았다. 새v7/v4.5는 현재 확인한 공식mail과 로컬 첨부/다운로드에서 미수신이다. 파일명이 다른 비공개 전달 여부는 모름이다. [#38](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6343676338)과 [Song board 보고](https://github.com/SongRoute/pitcheezy/issues/35#issuecomment-6386286893)에 나온 최신 후보·결함 처리·공동시험 조건은 계속 남는다.

다음은 새 고정ZIP/전체SHA/검토 결과 → 최신 UI·계약 및 알려진 결함 처리 확인 → 승인된 창의 단일 writer 발행/읽기/철회/복구·긴급 안내·양측 로그 대조다. 공개 운영 판단과 30~50명 부하는 별도다. 팀원 코드·프로세스·배포는 접근하거나 바꾸지 않았다. [후속 회신 초안](mail_drafts/COLLAB-001-host-publisher-result-20261025.md)은 미발신이다.

## 기록 검사

원본/영수증 해시·3건 대조·요청수·최종 설정·소스 바이트를 검사했다. 고정runtime/client 6파일 일치, 새문서 상대링크4개·공유본 민감정보 제외·diff 검사 통과. `python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider`는 8 passed(2.18초). 서버 소스 수정이나 새 모델 학습은 없으므로 전체 학습 검사를 반복하지 않았다.

별도 문서 검토에서도 상태/시간/해시/현재 한계에 중요한 결함 없음. 회신의 완료 범위를 본인 호스트 배포·발행 인증/회수 점검으로 좁혔다.
