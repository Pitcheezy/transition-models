"""Render the offline human review page; never supply a human judgment."""

from __future__ import annotations

import html
import json


def render_review_page(manifest, response, instructions):
    """Embed only the source manifest and blank response, without executable JSON."""
    data = json.dumps(
        {"manifest": manifest, "response": response}, ensure_ascii=False, allow_nan=False
    ).replace("<", "\\u003c")
    return (
        """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self';
style-src 'unsafe-inline'; script-src 'self'">
<title>미트 관측 개발 재검토</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1320px;margin:24px auto;padding:12px}
p,li{line-height:1.6}button,input,select,textarea{font:inherit;padding:6px;margin:4px}
label{display:inline-block;margin-right:12px}fieldset{margin:12px 0}textarea{width:90%}
#canvas{position:relative;display:inline-block;max-width:100%;line-height:0;cursor:crosshair}
#frame{display:block;max-width:100%;height:auto}#marker{position:absolute;width:14px;height:14px;
border:2px solid #ffdc00;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;
box-shadow:0 0 0 1px #000}#message{white-space:pre-wrap;color:#9c2100;min-height:1.6em}
#caption,#coordinates{font-family:monospace}#warning{background:#fff5cc;padding:12px}
.workspace{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px;align-items:start}
.workspace fieldset{margin:0;padding:12px;position:sticky;top:12px;min-width:0}
.workspace label{display:block;margin:8px 0}.workspace select{display:block;max-width:100%}
.workspace textarea{box-sizing:border-box;width:100%;margin:0}.hint{font-size:14px;color:#445}
details{padding:8px 12px;border:1px solid #ccd;border-radius:8px}summary{cursor:pointer}
@media(max-width:850px){.workspace{grid-template-columns:1fr}.workspace fieldset{position:static}}
</style><script src="review_ui.js" defer></script></head><body>
<h1>미트 __COUNT__장 직접 검토하기</h1>
<p>보이는 <strong>포수 미트 몸체의 중심</strong>만 표시하는 작업입니다.
투수가 어디로 던지려 했는지는 판단하지 않습니다.</p>
<ol><li>검토자 ID를 입력합니다. 이전 결과의 점을 참고하지 않고 원본을 읽습니다.</li>
<li>미트 중심을 클릭하고, 가시성·자세를 선택합니다. 가려졌거나 확신이 없으면 그 상태와 이유를 남깁니다.</li>
<li>다음 이미지로 이동합니다. 중간에도 JSON을 내보내 저장하고, 나중에 불러와 이어갈 수 있습니다.</li></ol>
<details><summary>검토 기준 자세히 보기</summary><p>__INSTRUCTIONS__</p></details>
<p id="warning">자동 저장하지 않습니다. 닫기 전에 JSON 내보내기를 하세요.
이 페이지는 사람이 직접 표시하는 개발 재검토 도구이며 AI 판정을 생성하지 않습니다.</p>
<label>검토자 ID <input id="reviewer" autocomplete="off"></label>
<button id="export" type="button">JSON 내보내기</button>
<label>저장한 응답 불러오기 <input id="import" type="file" accept="application/json,.json"></label>
<div id="message" role="alert"></div>
<nav><button id="prev" type="button">이전</button>
<label>프레임 <input id="index" type="number" min="1" value="1" style="width:5em"></label>
<span id="total"></span><button id="next" type="button">다음</button></nav>
<div class="workspace"><section><p id="caption"></p><div id="canvas"><img id="frame" alt="검토할 원본 프레임">
<span id="marker" hidden></span></div><p id="coordinates">미트 좌표 없음</p>
</section><fieldset><legend>현재 프레임의 사람 판정</legend>
<label>상태 <select id="status"><option value="unreviewed">아직 검토하지 않음</option>
<option value="marked">중심을 표시함</option><option value="unavailable">중심을 읽을 수 없음</option>
<option value="unknown">판단이 불확실함</option></select></label>
<label>미트 가시성 <select id="visibility"><option value="unknown">확신 없음 / 아직 선택 안 함</option>
<option value="full">전체가 보임</option><option value="partial">일부가 가려짐</option>
<option value="hidden">가려져 보이지 않음</option></select></label>
<label>자세 <select id="pose"><option value="unknown">확신 없음</option>
<option value="presented_target">공을 받기 위해 제시한 자세로 보임</option>
<option value="resting">내려놓거나 쉬는 자세로 보임</option>
<option value="moving">움직이는 자세로 보임</option></select></label>
<p class="hint">손목끈·팔·공이 아닌 미트 몸체의 가운데를 클릭하세요.
미트가 아래에 있어도 중심이 보이면 표시합니다. 가시성은 직접 선택해야 합니다.</p>
<p class="hint">일부 가림·판독 불가·불확실에는 이유를 적으세요.
보이지 않는 위치는 추측하지 않습니다. 한 장으로 자세를 구별하기 어려우면 확신 없음으로 둡니다.</p>
<p class="hint">아직 검토하지 않음으로 바꾸면 이 이미지의 점과 판정이 초기화됩니다.</p>
<label for="reason">이유 / 메모</label><br><textarea id="reason" rows="2"></textarea>
</fieldset></div><script type="application/json" id="review-data">__DATA__</script>
</body></html>""".replace("__COUNT__", str(len(manifest["frames"])))
        .replace("__INSTRUCTIONS__", html.escape(instructions))
        .replace("__DATA__", data)
    )
