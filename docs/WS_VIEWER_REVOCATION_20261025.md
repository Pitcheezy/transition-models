# 실제 관람 자격 회수 — 2026-10-25

**본인 시험 서버에서 로그인200 → 같은 세션 홈200 → 회수 후 같은 세션401을 확인했다.** 첫 실패를 포함한4요청을 실제 서버 로그에 1:1 대조했다. 발행 토큰 회수·형 최신본 일치·공동시험은 미완료다.

## 실제 결과

사용자가 승인한 새 본인 자격을 마련했고, 인증값 입력·저장은 사용자가 직접 수행했다. 시험/복구 digest를 등록한 뒤 시험 digest만 제거했다. 접근문과 세션 서명 secret은 유지했다.

- 10/25 01:58:09 KST: 최초 로그인401. 서버 버전9b1a5467. 로컬 코드와 예정 digest는 일치했지만 저장 secret은 읽을 수 없어 실패 원인은 모름이다. 실패 영수증을 보존했다.
- 사용자가 한 줄 파일로 재등록한 뒤02:02:43 로그인200·02:02:44 같은 쿠키의 홈200. 서버 버전2d6eec9d.
- 사용자가 복구 digest만 남긴 뒤02:05:35 기존 쿠키로 홈401·접근문 응답·no-store 확인. 서버 버전29bc9d09, Dashboard Ready·100% 확인.
- 세션은 v3, 수명3600초, Secure/HttpOnly/SameSite=Strict/Host-prefix다. 회수 응답 서버 Date 기준3428초가 남아 있었다. 서버 로그 시각도 만료 전이다. 새 로그인·로그아웃·자동재시도·리다이렉트 없이 같은 저장 쿠키를 사용했다.

직접 서비스 요청은 **첫 실패1 + 성공기준2 + 회수1 =4회**다. 대시보드/기타 브라우저/Preview 전체 요청 수는 미측정이다. 소스 확인용 편집 화면에서16:52:29 UTC Preview GET2개가 표시됐으나 production 시험 증거로 분류하지 않는다. 코드 수정·배포는 하지 않았고 bundled worker.js 해시도 확보하지 못했다.

## 증거·재현·한계

[공유 영수증](results/ops/ws_viewer_revocation_20261025.json)은 시간·method·path·status·전체scriptVersion과 대조 결과를 담는다. 원본20,065bytes/SHA256 a90c1a744b18c09d6c3cf7dab1fcbbce4b8aa686821f87563534706233b95287, 공유본SHA256 0cb09bb6f54ea5ff42f6ea212ff3c731e29d73c28b9d7e602f1e77c3d06f4571. 원본/비밀은 로컬에만 보관한다.

클라이언트/서버 cf-ray를 비공개 대조해 각1행씩 연결하고 요청 시각 범위·method·path·status·version을 전수 확인했다. cf-ray/IP/쿠키/헤더/계정정보는 공유본에 없다. UI Success는 HTTP200을 뜻하지 않는다.

명령: `node <private-dir>/viewer-probe-attempt2.private.mjs baseline <등록버전UUID>` → 사용자 회수 → `node <private-dir>/viewer-probe-attempt2.private.mjs revoked <회수버전UUID>`. 기존 결과는 덮어쓰지 않는다. 재실행은 새 서비스 요청이므로 자동 반복하지 않는다. 파일 대조는 Python json/hashlib/datetime으로 수행했다. 소스 기준6262afb55cc11975ed9da5a11a77a0fc3c970d63.

별도 에이전트가 요청수·쿠키·만료 guard를 정적으로 검토했다. 운영 코드 변경/다른 모델 운영 검토는 아니다. 세션 파일의 외부 변경 방지는 구현하지 않았다. 브라우저 렌더링·복구 코드 로그인·발행 자격·안내 전환·공동 GATE-06 검사가 아니며, 전체 시험 구간 설정 불변도 입증하지 않았다.

## 종료 상태·최신본 일치

접근문ON/세션3600초, 자료읽기·업로드·우리 이용기록·피드백OFF, Logs/Invocation/저장ON·100%, Traces/IssuesOFF를 다시 읽었다. 복구 digest는 남겼지만 복구 로그인은 미시험이다. PUBLISH_KEY_SCOPE/PUBLISH_EXPIRES_AT는 없다. 업로드OFF의503을 발행 회수401로 처리하지 않았다.

현재 정상 홈 제목은 **합성 배포 검사**이며 형 관전 화면이 아니다. 응답에 Cloudflare beacon 스크립트가 있지만 HTTP 검사기는 실행하지 않았다. 우리 TELEMETRY_ENABLED=false를 제3자 계정 분석까지 모두OFF로 확대하지 않는다.

받은 final2/v4.4는 다시 해시 일치 확인했다: f8f1c48a9925913857827144e8fb997016417d4f6cac7b71d333d25a33646796 / c431b3f737c4d7eaa1e8d8e1e119b2c25dfb32f65588f7c8dcda7c23c1bab18e. 이는 기존 수신본 식별이다. [#38 회신](https://github.com/SongRoute/pitcheezy/issues/38#issuecomment-6343676338)이 예고한 새v7/v4.5는 조사한 첨부/다운로드에 없다. [Song UI 보고](https://github.com/SongRoute/pitcheezy/issues/35#issuecomment-6386286893)의687e206a5e836e54314313b948d71a10aefec86b는 상대 검토 후보이며 우리 수신/배포 완료가 아니다. secret 변경 버전만으로 현재 runtime/최종 UI의 바이트 일치를 입증하지 못한다.

## 다음과 미발신 회신

새 고정 전달본·전체SHA·검토 결과 수신 → runtime 대응/발행 단일키·절대만료 고정 → 승인된 창의 발행 회수·안내·양측 연결시험 순서다. 팀원 코드는 접근·변경하지 않았고 새 외부 발신은 하지 않았다.

> 본인 시험 서버에서 로그인200 → 같은 세션 홈200 → 관람 코드 회수 후 같은 세션401을 확인했고, 첫 실패1건을 포함한4요청을 실제 저장 로그와 대조했어. 자료읽기/업로드는OFF야. 발행 토큰 회수와 최신 UI 일치는 아직 남아 있어. 새v7/v4.5·전체SHA·검토 결과를 받으면 runtime/발행 범위·만료부터 맞출게. 이번 결과는 본인 호스트 점검이며 공동시험 완료는 아니야.

문안은 미발신이다. 상대 이슈에 게시하려면 새 발신 승인이 필요하다.

## 기록 검사

기존 `python -B -m pytest tests/test_checklist_model.py -q -p no:cacheprovider` 8 passed. 영수증 SHA·4건 상태/서버 대조·허용목록·현재 구역 상대파일 링크·git diff 검사를 통과했다. 운영 소스 변경이 없어 전체 모델 학습/CPU 테스트를 반복하지 않았다.
