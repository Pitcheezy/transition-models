# pitcheezy.com 홈 한 페이지 — Cloudflare 정적 호스트

형 요구(SONG-REQ-1031 1항) "홈 한 페이지 + 서비스 열기"를 위한 배포 설정이다. 파일은 `web/pitch-studio-home/`
(index.html, home.js, product.css, 영상 1개, 미리보기 사진 1개, 로고 2개, `_headers`)뿐이며 Worker 코드가 없다.
기존 `web/pitch-studio/`의 watch·receiver·games·guide·report는 Git에 보존하고 공개에서만 뺀다.

"서비스 열기"는 `https://app.pitcheezy.com/?game=849843`을 가리킨다(도메인 A안). 다른 주소로 정하면 index.html의 세 링크를 바꾼다.

**2026-11-01 실행 결과:** `pitcheezy-home` Worker 배포 완료, 임시 호스트에서 홈·헤더·404 확인. **Workers 정적 호스트는 영상 Range 요청에 206이 아니라 200 전체로 답해**(아래 5단계의 우려가 실제 엣지에서 확인됨) iPhone Safari가 재생하지 못하므로, 영상(`hero-849843-four-pitches-v1.mp4`)과 포스터는 전용 R2 버킷 + custom domain **`media.pitcheezy.com`**(Range 206, `Cache-Control: public, max-age=31536000, immutable`)에서 내보내고 index.html의 `<source src>`만 그 주소로 바꿨다. iPhone Safari 재생 확인. 영상을 바꿀 때는 **새 파일명**으로 R2에 올리고 HTML 주소를 바꾼다(immutable 캐시). 도메인은 대시보드 Route(`pitcheezy.com/*`)로 붙인다 — 설정 파일 `routes`는 설정 검사 대상 밖이라 쓰지 않는다. 상세는 [③ 문서 "④ 진행"](../../docs/EXHIBIT_HOST_DEPLOY_STEPS_20261101.md).
**apex 주의(11/1 발견):** `pitcheezy.com`은 OpenAI Sites가 Cloudflare for SaaS custom hostname으로 잡고 있어 A 레코드를 Proxied로 바꾸고 Route를 걸어도 우리 Worker가 돌지 않는다(O2O는 Proxied CNAME일 때만). 아래 6단계의 "레코드 교체"만으로는 부족하고, Sites에서 도메인 연결을 해제하거나 OpenAI의 CNAME 대상으로 Proxied CNAME을 써야 한다. `www.pitcheezy.com`은 Route만으로 새 홈이 나온다.
**QR 경로:** 포스터 QR → `pitcheezy.com` 홈 → "서비스 열기" 한 번 → 앱. 기존 QR이 그대로 유효하다. 형이 원하면 최종 포스터에 앱 직행 QR을 넣을 수 있다(결정 전에는 홈 경유가 기준).

## 로컬 확인

~~~text
python -m http.server 8797 --bind 127.0.0.1 --directory web/pitch-studio-home
~~~

## 배포 (사용자 로그인 뒤, 단계마다 승인)

Wrangler는 `ops/public-host-tooling`에 lockfile로 고정한 **4.151.0**만 쓴다(`ops/public-host`에는 Wrangler가 없고, `npx wrangler`는 최신판을 받아 온다).
명령은 저장소 루트의 Windows PowerShell 5.1 기준이다(`&&` 없음).

1. 고정 도구 설치(최초 1회, 네트워크): `Set-Location ops/public-host-tooling; npm ci --ignore-scripts --no-fund --no-audit; Set-Location ../..`
2. `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js login` — 사용자가 직접 브라우저에서 승인한다.
3. `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --dry-run --config ops/public-home/wrangler.jsonc --outdir <비공개>/dry-run-home`
   출력은 파일 이름이 아니라 개수다: `Read 9 files`(올라가는 7개 + `media` 폴더 + 업로드에서 제외되는 `_headers`). 이름까지 보려면 `$env:WRANGLER_LOG = "debug"`.
   dry-run이 설정 파일 옆에 `.wrangler/`를 만들면 지운다.
4. `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js deploy --config ops/public-home/wrangler.jsonc` — Worker `pitcheezy-home`가 생긴다. workers.dev·preview 주소는 꺼져 있어 아직 아무도 볼 수 없다.
5. **apex 전환 전 읽기 확인:** 새 홈은 `https://www.pitcheezy.com/`에서 확인한다. 실제 HTML이 사용하는 영상 주소는 `https://media.pitcheezy.com/hero-849843-four-pitches-v1.mp4`다. 이 주소에 `Range: bytes=0-1` 요청을 보내 206·Content-Range를 확인한다. 11/1 Claude의 실제 엣지 검사·사용자 iPhone 재생 기록과 Codex의 206 재조회가 있다. 홈 Worker의 옛 `/media/...` 경로는 검사 대상이 아니다. 새 임시 호스트나 preview를 다시 켤 필요가 없다.
6. **apex 전환(④, 별도 승인):** 현재 방식은 대시보드의 정확한 Route `pitcheezy.com/*`다. 설정 파일에 routes나 `*.pitcheezy.com/*`를 추가하지 않는다. 실행 직전에 Route 대상·DNS Proxied·TLS 상태를 읽기 확인한다. 사용자가 기존 Sites의 **pitcheezy.com 도메인 연결만 해제**하고 사이트·배포는 보존한다. 연결 해제 후 응답으로 전환을 판정하며 수 분 내 완료를 보장하지 않는다.
   **복구안:** 기존 Sites에 pitcheezy.com을 다시 연결하고 검증/TLS 활성 상태를 확인한 뒤 홈 Worker의 정확한 apex Route만 해제한다. 재연결은 재검증·전파가 필요할 수 있으며 실제 복구 시간은 미측정이다. 앱 Worker·앱 접근 코드·media는 이 복구의 대상이 아니다. 기존 Sites는 전시 이후 별도 결정 전까지 보존한다.
7. 확인: `https://pitcheezy.com/` 200, 영상 재생(PC·Android·**iPhone Safari**), "서비스 열기" 링크, `/watch.html` 등 옛 주소는 404. 폰으로 QR → 홈 → 서비스 열기까지.

이 Worker에는 접근 코드·안내 스위치·업로드가 없다. 그런 기능은 `ops/public-host`(형 앱 호스트)에만 있다.
