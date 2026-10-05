"""Render the offline human review page; never supply a human judgment."""

from __future__ import annotations

import html
import json


def render_review_page(manifest, response, instructions):
    """Embed only the source manifest and blank response, without executable JSON."""
    data = json.dumps(
        {"manifest": manifest, "response": response}, ensure_ascii=False, allow_nan=False
    ).replace("<", "\\u003c")
    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self';
style-src 'unsafe-inline'; script-src 'self'">
<title>미트 관측 개발 재검토</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1320px;margin:24px auto;padding:12px}
p{line-height:1.6}button,input,select,textarea{font:inherit;padding:6px;margin:4px}
label{display:inline-block;margin-right:12px}fieldset{margin:12px 0}textarea{width:90%}
#canvas{position:relative;display:inline-block;max-width:100%;line-height:0;cursor:crosshair}
#frame{display:block;max-width:100%;height:auto}#marker{position:absolute;width:14px;height:14px;
border:2px solid #ffdc00;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;
box-shadow:0 0 0 1px #000}#message{white-space:pre-wrap;color:#9c2100;min-height:1.6em}
#caption,#coordinates{font-family:monospace}#warning{background:#fff5cc;padding:12px}
</style><script src="review_ui.js" defer></script></head><body>
<h1>미트 관측 개발 재검토</h1><p>__INSTRUCTIONS__</p>
<p id="warning">자동 저장하지 않습니다. 닫기 전에 JSON 내보내기를 하세요.
이 페이지는 사람이 직접 표시하는 개발 재검토 도구이며 AI 판정을 생성하지 않습니다.</p>
<label>검토자 ID <input id="reviewer" autocomplete="off"></label>
<button id="export" type="button">JSON 내보내기</button>
<label>저장한 응답 불러오기 <input id="import" type="file" accept="application/json,.json"></label>
<div id="message" role="alert"></div>
<nav><button id="prev" type="button">이전</button>
<label>프레임 <input id="index" type="number" min="1" value="1" style="width:5em"></label>
<span id="total"></span><button id="next" type="button">다음</button></nav>
<p id="caption"></p><div id="canvas"><img id="frame" alt="검토할 원본 프레임">
<span id="marker" hidden></span></div><p id="coordinates">미트 좌표 없음</p>
<fieldset><legend>현재 프레임의 사람 판정</legend>
<label>상태 <select id="status"><option>unreviewed</option><option>marked</option>
<option>unavailable</option><option>unknown</option></select></label>
<label>미트 가시성 <select id="visibility"><option>unknown</option><option>full</option>
<option>partial</option><option>hidden</option></select></label>
<label>자세 <select id="pose"><option>unknown</option><option>presented_target</option>
<option>resting</option><option>moving</option></select></label>
<p>미트 중심을 클릭하면 원본 픽셀 좌표를 기록합니다. marked 상태는 가시성 full 또는
partial을 직접 선택해야 합니다. unavailable·unknown 상태에는 이유를 입력하세요.
unreviewed로 바꾸면 현재 행의 판정을 모두 초기화합니다.</p>
<label for="reason">이유 / 메모</label><br><textarea id="reason" rows="2"></textarea>
</fieldset><script type="application/json" id="review-data">__DATA__</script>
</body></html>""".replace("__INSTRUCTIONS__", html.escape(instructions)).replace("__DATA__", data)
