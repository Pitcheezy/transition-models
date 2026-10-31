# pitcheezy.com 홈 한 페이지 — Cloudflare 정적 호스트

형 요구(SONG-REQ-1031 1항) "홈 한 페이지 + 서비스 열기"를 위한 배포 설정이다. 파일은 `web/pitch-studio-home/`
(index.html, home.js, product.css, 영상 1개, 미리보기 사진 1개, 로고 2개, `_headers`)뿐이며 Worker 코드가 없다.
기존 `web/pitch-studio/`의 watch·receiver·games·guide·report는 Git에 보존하고 공개에서만 뺀다.

"서비스 열기"는 `https://app.pitcheezy.com/?game=849843`을 가리킨다(도메인 A안). 다른 주소로 정하면 index.html의 세 링크를 바꾼다.
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
5. **apex 전환 전 시험(필수):** 대시보드에서 pitcheezy-home에 **임시 시험 호스트명**(예: 홈 시험용 하위 도메인 custom domain)을 붙이거나 `preview_urls`를 잠깐 켠다. 그 주소로
   `curl.exe -s -D - -o NUL -H "Range: bytes=0-1" https://<시험호스트명>/media/hero-849843-four-pitches-v1.mp4` 를 실행해 **206**이 오는지 보고, iPhone Safari에서 페이지를 열어 영상이 재생되는지 본다.
   iOS Safari는 범위 요청(206)을 못 받는 서버의 영상을 재생하지 않는다. 로컬 Miniflare의 정적 파일 처리는 Range에 200·전체 파일로 답했고, **실제 Cloudflare edge에서는 미검증**이다.
   200이 오면 대안은 둘이다: mp4를 R2 버킷 custom domain에서 서비스하도록 index.html의 `<source src>`를 바꾸거나, 영상을 빼고 사진만 둔다(home.js는 재생 실패 시 미리보기 사진으로 자동 전환한다).
   확인이 끝나면 임시 호스트명/preview를 다시 끈다.
6. **도메인 연결(④, 별도 승인):** 대시보드 Workers → pitcheezy-home → Settings → Domains & Routes → Custom domain `pitcheezy.com`.
   apex에 레코드가 이미 있으면 Cloudflare가 거부하거나 기존 레코드를 바꿀지 묻는다. 그 전에 현재 `pitcheezy.com` 레코드(종류·값·프록시 여부, TXT 포함)를 전부 적어 둔다.
   **되돌리기는 Sites가 아직 공개돼 있는 동안만 된다:** Custom domain을 지우고 적어 둔 레코드를 복구하면 Sites가 다시 보인다. 그래서 Sites는 전시(11/24)가 끝난 뒤에 내리는 것을 권한다. Sites를 먼저 내리면 전시 중 되돌릴 곳이 없다.
7. 확인: `https://pitcheezy.com/` 200, 영상 재생(PC·Android·**iPhone Safari**), "서비스 열기" 링크, `/watch.html` 등 옛 주소는 404. 폰으로 QR → 홈 → 서비스 열기까지.

이 Worker에는 접근 코드·안내 스위치·업로드가 없다. 그런 기능은 `ops/public-host`(형 앱 호스트)에만 있다.
