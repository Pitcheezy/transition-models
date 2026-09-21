"""Build a standalone, offline demonstration using only completed validation artifacts."""

import argparse
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartPitch · 검증 결과와 구종 추천</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#183044;background:#f3f6f8}
body{margin:0}main{max-width:1180px;margin:auto;padding:42px 28px 70px}h1{font-size:36px;letter-spacing:-1.8px;margin:10px 0}h2{font-size:22px;margin:0 0 16px}p{line-height:1.7}small,.muted{color:#637687}.eyebrow{color:#14786d;font-weight:750;letter-spacing:2px;font-size:13px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:26px 0}.card,section{background:white;border:1px solid #dce5eb;border-radius:15px;padding:22px;box-shadow:0 3px 12px #102c4206}.card b{display:block;font-size:27px;margin:9px 0}.card span{font-size:13px;color:#637687}section{margin-top:20px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px 10px;border-bottom:1px solid #e7edf1;text-align:right;white-space:nowrap}td:first-child,th:first-child{text-align:left}th{color:#65798b;font-size:12px}.table-wrap{overflow:auto}.selected{background:#eaf6f2}.unsupported{color:#a0acb5}.note{padding:16px 20px;border-left:4px solid #dfaa43;background:#fff8e9;border-radius:4px;color:#735220}select{padding:10px;border:1px solid #cbd8e2;border-radius:8px;background:white;max-width:100%;font:inherit}.demo-head{display:flex;gap:25px;justify-content:space-between;align-items:center;flex-wrap:wrap}.pills{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0}.pill{background:#edf3f7;padding:10px 14px;border-radius:8px;font-size:14px}.green{color:#087964}.bar{height:8px;border-radius:8px;background:#d8e8e5;width:120px;display:inline-block;text-align:left}.bar i{display:block;background:#128c7a;height:100%;border-radius:8px}footer{margin-top:25px;color:#637687;font-size:13px}@media(max-width:700px){main{padding:25px 15px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:28px}.card{padding:16px}.card b{font-size:22px}}
</style><main>
<div class="eyebrow">SMARTPITCH / VALIDATION · 2026.09.21</div>
<h1>투구 전에 아는 정보로, 구종 추천을 검증하다</h1>
<p class="muted">2022년 고정 프로필 → 2023년 학습 → 2024년 1–5월 선택 → 6월 확률 보정 → 7–9월 최종 평가</p>
<div class="cards" id="cards"></div>
<section><h2>확률 예측 성능</h2><p class="muted">같은 평가 투구에서 비교했습니다. CE와 Brier는 낮을수록 좋습니다. 모델 선택에는 1–5월 데이터만 사용했습니다.</p><div class="table-wrap"><table><thead><tr><th>모델</th><th>정확도</th><th>CE</th><th>Brier</th><th>ECE</th></tr></thead><tbody id="models"></tbody></table></div><p class="muted">MLP 행은 세 시드의 확률 평균입니다. 운영 135차원의 과거 프로필은 기존 UMAP/Arsenal 특징과 다른 버전입니다.</p></section>
<section><h2>추천이 기대 실점에 도움이 되었는가</h2><div id="policy"></div><p class="note">관측자료의 조건부 교환가능성 등 가정에 의존하는 한 번의 구종 선택 평가입니다. 시즌 전체 실점 감소나 실제 경기의 인과효과를 확정하지 않습니다. 평가 신뢰구간은 학습된 정책을 고정하고 경기를 재표집했습니다.</p></section>
<section><div class="demo-head"><h2>검증 사례에서 추천 확인</h2><select id="case" aria-label="검증 사례 선택"></select></div><p class="muted">평가셋의 앞쪽 30개 적격 사례를 순서대로 재생합니다. 각 구종의 물리량과 위치 분포는 2022년 이력으로 추정했습니다.</p><div class="pills" id="state"></div><p id="recommend"></p><div class="table-wrap"><table><thead><tr><th>구종</th><th>지원 여부</th><th>학습 모델 예상 비용</th><th>경험적 예상 비용</th><th>홈런 확률</th><th>삼진 확률</th></tr></thead><tbody id="actions"></tbody></table></div><p class="muted">비용 = 해당 투구 득점 + 다음 상태의 기대 실점 − 현재 상태의 기대 실점. 낮을수록 좋습니다. 위 값은 추천용 예측값이며, 정책 효용은 별도의 실제 결과로 평가했습니다.</p></section>
<section><h2>희소 사건: 최다 예측과 확률을 구분</h2><div class="table-wrap"><table><thead><tr><th>사건</th><th>평균 예측 확률</th><th>실제 발생률</th><th>정답 수</th><th>최대 확률로 선택한 수</th></tr></thead><tbody id="rare"></tbody></table></div><p class="muted">최대 확률로 선택한 횟수가 0이어도 해당 사건의 예측 확률이 0이라는 뜻은 아닙니다.</p></section>
<footer>저장된 검증 산출물만 사용 · 외부 네트워크 불필요 · 전체 설정·경기 신뢰구간·상황별 결과는 함께 제공된 JSON과 보고서에서 확인할 수 있습니다.</footer>
</main><script>
const DATA=__DATA__;
const p=DATA.probability, r=DATA.policy, d=DATA.demo, chosen=p.selection.selected;
const fmt=(v,n=4)=>Number(v).toFixed(n), pct=v=>fmt(v*100,2)+'%';
const dr=r.estimators.unclipped.dr;
document.querySelector('#cards').innerHTML=[['최종 평가 투구',p.models[chosen].calibrated_test.n.toLocaleString(),'독립된 2024년 7–9월'],['선택 모델',chosen,'검증 기간 CE 기준'],['정책 평가 투구',r.eligible_n.toLocaleString(),'1–8회 · 지원 행동 ≥ 2'],['추천 변경률',pct(r.recommendation_change_fraction),'경험적 기준선과 비교']].map(x=>`<div class="card"><small>${x[0]}</small><b>${x[1]}</b><span>${x[2]}</span></div>`).join('');
document.querySelector('#models').innerHTML=Object.entries(p.models).map(([name,m])=>{const s=m.calibrated_test;return `<tr class="${name===chosen?'selected':''}"><td>${name}${name===chosen?' · 선택':''}</td><td>${pct(s.top1)}</td><td>${fmt(s.ce)}</td><td>${fmt(s.brier)}</td><td>${fmt(s.ece_15)}</td></tr>`}).join('');
document.querySelector('#policy').innerHTML=`<p><strong>${r.improvement_supported_under_assumptions?'관측자료 평가의 가정 아래 개선을 지지합니다.':'통계적으로 명확한 개선을 확인하지 못했습니다.'}</strong></p><p>학습 정책 − 경험적 정책: <strong>${fmt(dr.mean[2],3)} 실점 / 100회 결정</strong><br>경기 단위 95% 신뢰구간: ${fmt(dr.ci95[2][0],3)} ~ ${fmt(dr.ci95[2][1],3)}<br>전체 최종 평가 투구 중 정책 평가 비율: ${pct(r.eligible_fraction)}</p><p class="muted">9개 구종의 특징 생성과 예측 시간 중앙값: ${fmt(r.latency.nine_actions_p50_ms,1)} ms (CPU, ${r.latency.threads} threads). 최소 예상 비용 구종 90% + 지원 후보 균등 10% 정책을 비교했습니다.</p>`;
document.querySelector('#rare').innerHTML=['Single','Double','Triple','HomeRun'].map(c=>{const x=p.models[chosen].calibrated_test.per_class[c];return `<tr><td>${c}</td><td>${pct(x.mean_probability)}</td><td>${pct(x.observed_frequency)}</td><td>${x.support.toLocaleString()}</td><td>${x.predicted_count.toLocaleString()}</td></tr>`}).join('');
const sel=document.querySelector('#case');
d.examples.forEach((e,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`사례 ${i+1} · 투수 ${e.state.pitcher} · ${e.state.balls}-${e.state.strikes} 카운트`;sel.append(o)});
function render(){const e=d.examples[Number(sel.value)],s=e.state;const runners=[1,2,3].filter(b=>s[`on_${b}b`]!=null).join('·')||'없음';document.querySelector('#state').innerHTML=[`${s.inning}회`,`${s.balls}볼 ${s.strikes}스트라이크`,`${s.outs_when_up}아웃`,`주자 ${runners}`,`타자 ${s.stand} / 투수 ${s.p_throws}`].map(t=>`<span class="pill">${t}</span>`).join('');document.querySelector('#recommend').innerHTML=`학습 모델 추천 <strong class="green">${e.learned_choice}</strong> · 경험적 기준선 <strong>${e.empirical_choice}</strong>`;document.querySelector('#actions').innerHTML=d.actions.map((a,i)=>`<tr class="${!e.available[i]?'unsupported':a===e.learned_choice?'selected':''}"><td>${a}</td><td>${e.available[i]?'지원':'제외'}</td><td>${fmt(e.learned_cost[i])}</td><td>${fmt(e.empirical_cost[i])}</td><td>${pct(e.probabilities[i][5])}</td><td>${pct(e.probabilities[i][7])}</td></tr>`).join('')}
sel.addEventListener('change',render);render();
</script></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--policy-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    probability = json.loads((args.evaluation_dir / "probability_report.json").read_text())
    compact = {
        "selection": probability["selection"],
        "models": {
            name: {"calibrated_test": row["calibrated_test"]}
            for name, row in probability["models"].items()
        },
    }
    payload = {
        "probability": compact,
        "policy": json.loads((args.policy_dir / "policy_report.json").read_text()),
        "demo": json.loads((args.policy_dir / "demo_examples.json").read_text()),
    }
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(TEMPLATE.replace("__DATA__", encoded), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
