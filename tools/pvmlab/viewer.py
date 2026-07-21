"""
viewer.py — 트레이스(dict) → 단일 자족 HTML 문자열

외부 리소스 0. 트레이스 리스트를 JSON으로 박아 하나의 HTML을 만든다. 브라우저에서
←/→로 한 스텝씩 넘기며 소스·바이트코드·프레임 스택·객체 인스펙터를 함께 관찰한다.

한 줄 요약(부제): 평가 루프가 코드 객체를 읽고, 프레임에 쓴다.

트레이스 스키마(입력):
  { title, listings, sources, code_attrs, steps }
  step: { action, frames[], exec, key, line, opname, func_attrs[] }
"""

import json
from pathlib import Path

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>pvmlab — CPython 실행 모델</title>
<style>
  :root { --bg:#faf9f5; --card:#ffffff; --line:#e3e1d9; --txt:#26251f;
          --mut:#8b897f; --sub:#5f5e56; --acc:#2f6fce; --accbg:#e9f1fc;
          --warn:#9a6b1a; --warnbg:#faf0da; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--txt); padding:26px 20px 60px;
         font:15px/1.6 system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }
  .wrap { max-width:1120px; margin:0 auto; }
  h1 { font-size:19px; font-weight:600; margin-bottom:4px; }
  .sub { font-size:14px; color:var(--sub); margin-bottom:16px; }
  select { font:inherit; padding:6px 10px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); margin-bottom:16px; }
  .cols { display:grid; grid-template-columns:1.05fr 1fr; gap:14px; align-items:start; }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:13px; margin-bottom:14px; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:9px; }
  .src-row, .bc-row { display:flex; gap:12px; padding:2.5px 9px; border-radius:6px;
            font:13px/1.65 ui-monospace,Consolas,monospace; color:var(--sub);
            white-space:pre; }
  .src-row .no, .bc-row .off { color:var(--mut); min-width:26px; text-align:right;
            user-select:none; }
  .src-row.on { background:var(--warnbg); color:var(--warn); }
  .bc-row { cursor:pointer; }
  .bc-row:hover { background:var(--bg); }
  .bc-row.on { background:var(--accbg); color:var(--acc); font-weight:600; }
  .fr { border:1px solid var(--line); border-radius:8px; padding:9px 12px;
        margin-bottom:8px; background:var(--card); }
  .fr.act { border-color:var(--acc); background:var(--accbg); }
  .fr.wait { opacity:.5; }
  .fr-name { font:600 14px ui-monospace,Consolas,monospace; margin-bottom:5px; }
  .fr.act .fr-name { color:var(--acc); }
  .fr-row { font:12.5px ui-monospace,Consolas,monospace; color:var(--sub); }
  .stack-cells { display:flex; gap:6px; flex-wrap:wrap; margin-top:3px; }
  .cell { padding:1px 9px; border-radius:6px; background:var(--warnbg);
          color:var(--warn); border:1px solid #ecd9ae;
          font:12.5px ui-monospace,monospace; }
  .cell.empty { background:none; border:1px dashed var(--line); color:var(--mut); }
  .desc { padding:12px 15px; border:1px solid #bcd3f0; background:var(--accbg);
          border-radius:10px; color:#1c4d94; min-height:48px; margin-bottom:10px; }
  .opdoc { padding:11px 15px; border:1px solid var(--line); background:var(--card);
           border-radius:10px; font-size:13.5px; color:var(--sub); min-height:44px;
           margin-bottom:14px; }
  .opdoc b { color:var(--txt); font-family:ui-monospace,Consolas,monospace; }
  details.ins { background:var(--card); border:1px solid var(--line);
                border-radius:10px; padding:6px 13px; margin-bottom:12px; }
  details.ins summary { font-size:12px; color:var(--mut); cursor:pointer;
                        padding:4px 0; user-select:none; }
  .badge { display:inline-block; font-size:10.5px; color:var(--sub);
           background:var(--bg); border:1px solid var(--line); border-radius:5px;
           padding:0 6px; margin-left:6px; }
  .attr { border-top:1px solid var(--line); padding:7px 4px; }
  .attr.chg { background:var(--warnbg); border-radius:6px; }
  .attr-hd { display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; }
  .attr-name { font:600 12.5px ui-monospace,Consolas,monospace; color:var(--txt);
               min-width:118px; }
  .attr.chg .attr-name { color:var(--warn); }
  .attr-val { font:12.5px ui-monospace,Consolas,monospace; color:var(--acc); }
  .attr.chg .attr-val { color:var(--warn); font-weight:600; }
  .attr-doc { font-size:12px; color:var(--mut); margin-top:2px; }
  .attr-chgtag { font-size:10.5px; color:var(--warn); margin-left:6px; }
  .nav { display:flex; align-items:center; gap:12px; margin-top:14px; }
  button { font:inherit; padding:8px 18px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  input[type=range] { flex:1; }
  .pos { font-size:13px; color:var(--mut); min-width:64px; text-align:right; }
  .hint { font-size:12px; color:var(--mut); margin-top:9px; }
  .muttxt { color:var(--mut); }
</style></head><body><div class="wrap">
<h1>pvmlab — CPython 실행 모델</h1>
<div class="sub">평가 루프가 코드 객체를 <b>읽고</b>, 프레임에 <b>쓴다</b>. 노란 줄 = 지금 실행 중인 소스, 파란 줄 = 지금 실행 중인 바이트코드.</div>
<select id="demo"></select>
<div class="cols">
  <div>
    <div class="panel"><h2 id="srcname"></h2><div id="src"></div></div>
    <div class="panel"><h2 id="cname"></h2><div id="bc"></div></div>
  </div>
  <div>
    <div class="panel"><h2>프레임 스택 · 호출마다 1개 (맨 위 = 실행 중)</h2><div id="stk"></div></div>
    <div class="desc" id="desc"></div>
    <div class="opdoc" id="opdoc">바이트코드 줄을 클릭하면 그 명령의 설명이 여기 고정 표시됩니다.</div>
    <details class="ins" open><summary>코드 객체 속성 <span class="badge">불변 · 컴파일 시점 확정</span></summary><div id="codeattrs"></div></details>
    <details class="ins" open><summary>함수 객체 속성 <span class="badge">가변 · 매 스텝 스냅샷</span></summary><div id="funcattrs"></div></details>
  </div>
</div>
<div class="nav">
  <button id="prev">← 이전</button>
  <button id="next">다음 →</button>
  <input type="range" id="slider" min="0" value="0">
  <span class="pos" id="pos"></span>
</div>
<div class="hint">키보드 ← → 로도 이동. 노란 칸이 값 스택(왼쪽이 바닥, 오른쪽이 맨 위). 함수 객체 속성이 노랗게 강조되면 직전 스텝에서 값이 바뀐 것.</div>
</div>
<script>
const DATA = __DATA__;
let d = 0, i = 0, pinnedDoc = null;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

const sel = $("demo");
DATA.forEach((t, n) => sel.add(new Option(t.title, n)));
sel.onchange = () => { d = +sel.value; i = 0; pinnedDoc = null; render(); };

function showDoc(op, doc) {
  $("opdoc").innerHTML = "<b>" + esc(op) + "</b> — " + esc(doc);
}

function attrRow(a) {
  const chg = a.changed ? " chg" : "";
  const tag = a.changed ? '<span class="attr-chgtag">← 변경됨</span>' : "";
  return `<div class="attr${chg}">
    <div class="attr-hd"><span class="attr-name">${esc(a.name)}</span>` +
    `<span class="attr-val">${esc(a.value)}</span>${tag}</div>` +
    `<div class="attr-doc">${esc(a.doc)}</div></div>`;
}

function render() {
  const t = DATA[d], s = t.steps[i];
  $("slider").max = t.steps.length - 1;
  $("slider").value = i;
  const key = s.key ?? t.steps[Math.max(0, i-1)].key;

  // -- 소스 --
  const src = t.sources[key] ?? {first: 1, lines: []};
  $("srcname").textContent = key.replace(".__code__", "") + " 소스 코드";
  $("src").innerHTML = src.lines.map((ln, n) => {
    const lineno = src.first + n;
    return `<div class="src-row ${s.key === key && lineno === s.line ? "on" : ""}">` +
           `<span class="no">${lineno}</span><span>${esc(ln) || " "}</span></div>`;
  }).join("");

  // -- 바이트코드 --
  $("cname").textContent = key + " 의 바이트코드 (진짜 CPython 출력)";
  $("bc").innerHTML = (t.listings[key] ?? []).map((r, n) =>
    `<div class="bc-row ${s.key === key && n === s.exec ? "on" : ""}" data-n="${n}">` +
    `<span class="off">${r.off}</span><span>${esc(r.op)} ${esc(r.arg)}</span></div>`).join("");
  document.querySelectorAll(".bc-row").forEach(el => {
    el.onclick = () => { const r = t.listings[key][+el.dataset.n];
                        pinnedDoc = [r.op, r.doc]; showDoc(r.op, r.doc); };
  });

  // -- 프레임 스택 --
  $("stk").innerHTML = s.frames.length === 0
    ? '<div class="muttxt" style="text-align:center;padding:24px 0">비어 있음 — 실행 종료</div>'
    : s.frames.slice().reverse().map(f => `
      <div class="fr ${f.active ? "act" : "wait"}">
        <div class="fr-name">${esc(f.name)} 프레임 ${f.active ? "· 실행 중" : "· 대기(값 스택 유지)"}</div>
        <div class="fr-row">지역 변수: ${Object.entries(f.locals).map(([k,v]) => esc(k)+" = "+esc(v)).join(", ") || "—"}</div>
        <div class="fr-row">값 스택:</div>
        <div class="stack-cells">${f.stack.length
          ? f.stack.map(v => `<span class="cell">${esc(v)}</span>`).join("")
          : '<span class="cell empty">비어 있음</span>'}</div>
      </div>`).join("");

  // -- 설명 --
  $("desc").textContent = s.action;
  if (pinnedDoc) showDoc(pinnedDoc[0], pinnedDoc[1]);
  else if (s.opname) {
    const r = (t.listings[s.key] ?? []).find(x => x.op === s.opname);
    if (r) showDoc(s.opname, r.doc);
  }

  // -- 인스펙터: 코드 객체(불변) / 함수 객체(가변, diff) --
  const ca = t.code_attrs[key] ?? [];
  $("codeattrs").innerHTML = ca.length ? ca.map(attrRow).join("")
    : '<div class="attr muttxt">—</div>';
  const fa = s.func_attrs ?? [];
  $("funcattrs").innerHTML = fa.length ? fa.map(attrRow).join("")
    : '<div class="attr muttxt">(활성 프레임 없음)</div>';

  $("pos").textContent = i + " / " + (t.steps.length - 1);
  $("prev").disabled = i === 0;
  $("next").disabled = i === t.steps.length - 1;
}
$("next").onclick = () => { if (i < DATA[d].steps.length - 1) { i++; pinnedDoc = null; render(); } };
$("prev").onclick = () => { if (i > 0) { i--; pinnedDoc = null; render(); } };
$("slider").oninput = e => { i = +e.target.value; pinnedDoc = null; render(); };
document.onkeydown = e => {
  if (e.key === "ArrowRight") $("next").click();
  if (e.key === "ArrowLeft") $("prev").click();
};
render();
</script></body></html>
"""


def build_html(traces, out_path):
    """트레이스 리스트를 단일 HTML로 저장. </ 이스케이프로 script 조기 종료를 막는다."""
    data = json.dumps(traces, ensure_ascii=False).replace("</", "<\\/")
    Path(out_path).write_text(HTML_TEMPLATE.replace("__DATA__", data), encoding="utf-8")


def render_html(traces):
    """트레이스 리스트 → HTML 문자열 (검사/테스트용)."""
    data = json.dumps(traces, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", data)
