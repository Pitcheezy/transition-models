# pitcheezy.com 홈 한 페이지 — Cloudflare 정적 호스트

형 요구(SONG-REQ-1031 1항) "홈 한 페이지 + 서비스 열기"를 위한 배포 설정이다. 파일은 `web/pitch-studio-home/`
(index.html, home.js, product.css, 영상 1개, 미리보기 사진 1개, 로고 2개, `_headers`)뿐이며 Worker 코드가 없다.
기존 `web/pitch-studio/`의 watch·receiver·games·guide·report는 Git에 보존하고 공개에서만 뺀다.

"서비스 열기"는 `https://app.pitcheezy.com/?game=849843`을 가리킨다(도메인 A안). 다른 주소로 정하면 index.html의 세 링크를 바꾼다.

## 로컬 확인

~~~text
python -m http.server 8797 --bind 127.0.0.1 --directory web/pitch-studio-home
~~~

## 배포 (사용자 로그인 뒤, 단계마다 승인)

1. `cd ops/public-host && npx wrangler login` — 사용자가 직접 브라우저에서 승인한다.
2. `npx wrangler deploy --config ../public-home/wrangler.jsonc --dry-run` 으로 올릴 파일 목록을 확인한다.
3. `npx wrangler deploy --config ../public-home/wrangler.jsonc` — Worker `pitcheezy-home`가 생긴다. workers.dev·preview 주소는 꺼져 있어 아직 아무도 볼 수 없다.
4. **도메인 연결(④, 별도 승인):** 대시보드 Workers → pitcheezy-home → Settings → Domains & Routes → Custom domain `pitcheezy.com`.
   Cloudflare가 DNS 레코드를 자동으로 바꾸므로, 그 전에 현재 `pitcheezy.com` 레코드(종류·값·프록시 여부)를 적어 둔다.
   되돌리기: Custom domain을 지우고 적어 둔 레코드를 복구한다. Sites 쪽은 그대로 남아 있다.
5. 확인: `https://pitcheezy.com/` 200, 영상 재생, "서비스 열기" 링크, `/watch.html` 등 옛 주소는 404.

이 Worker에는 접근 코드·안내 스위치·업로드가 없다. 그런 기능은 `ops/public-host`(형 앱 호스트)에만 있다.
