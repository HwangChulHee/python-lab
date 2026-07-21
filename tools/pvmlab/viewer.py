"""
viewer.py — 트레이스(dict) → 단일 자족 HTML 문자열

외부 리소스 0. 트레이스 리스트를 JSON으로 박아 하나의 HTML을 만든다. 브라우저에서
←/→로 한 스텝씩 넘기며 소스·바이트코드·프레임 스택·객체 인스펙터를 함께 관찰한다.

한 줄 요약(부제): 평가 루프가 코드 객체를 읽고, 프레임에 쓴다.

트레이스 스키마(입력):
  { title, listings, sources, code_attrs, names, steps }
  step: { action, frames[], held[], instances[], exec, key, line, opname, func_attrs[] }
  frame: { name, key, active, fast[], cellvars[], freevars[], namespace, stack[],
           ip_off, ip_op, line }   ← CPython localsplus 배치 그대로
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
  .cols { display:grid; grid-template-columns:1.02fr 1fr; gap:14px; align-items:start; }
  .colL { position:sticky; top:14px; }         /* 코드 열은 위에 고정 — 스크롤해도 항상 보임 */
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:13px; margin-bottom:14px; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:9px; }
  /* 소스·바이트코드가 길어도 열 자체는 안 늘어나도록 각 패널 내부를 스크롤한다.
     그래야 프레임 스택·코드 객체 속성이 옆에서 밀려나지 않는다. */
  #src { position:relative; max-height:30vh; overflow:auto; }
  #bc  { position:relative; max-height:44vh; overflow:auto; }
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
  .fr.wait { opacity:.78; }              /* 호출한(대기) 프레임의 변수도 또렷이 읽히게 */
  .fr-name { font:600 14px ui-monospace,Consolas,monospace; margin-bottom:5px; }
  .fr.act .fr-name { color:var(--acc); }
  .fr-row { font:12.5px ui-monospace,Consolas,monospace; color:var(--sub); }
  .frtag { font-size:11px; color:var(--mut); font-weight:400; }
  .fr.act .frtag { color:var(--acc); }
  .ipinfo { font:11px ui-monospace,monospace; color:var(--mut); font-weight:400; float:right; }
  .lp-line { display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin:4px 0; }
  .lp-tag { min-width:82px; font-size:11px; color:var(--mut); flex-shrink:0; }
  .lpchip { padding:1px 8px; border-radius:6px; border:1px solid var(--line);
            background:var(--card); font:12px ui-monospace,Consolas,monospace; color:var(--sub); }
  .lpchip.param { border-color:#c9a9e6; background:#f5eefc; color:#6a3ea0; }
  .lpchip.unset { color:var(--mut); border-style:dashed; background:none; }
  .lpchip.cellref { color:#6a4bb0; border-style:dashed; background:none; }
  .lpchip.cellv { border-color:#c9b8e6; background:#f4effb; color:#5a3ea0; }
  .lpchip.freev { border-color:#a9cdb5; background:#eff8f2; color:#2f7a4a; }
  .lpchip.nsv { border-color:#bcd3f0; background:var(--accbg); color:#1c4d94; }
  .fr-legend { font-size:11px; color:var(--mut); margin-top:6px; }
  .fr-legend .sw { display:inline-block; padding:0 6px; border-radius:5px; margin:0 2px;
                   border:1px solid var(--line); }
  .panel.held { border-color:#c9b8e6; background:#f7f3fc; }
  .panel.held h2 { color:#6a4bb0; }
  .heldfr { border-style:dashed; }
  .heldfr.st-SUSPENDED { border-color:#c9a227; background:#fdf8ec; }
  .heldfr.st-CREATED { border-color:#7ea3d6; background:#eef4fb; }
  .heldfr.st-COMPLETED { opacity:.5; }
  .stbadge { font-size:10.5px; font-weight:600; border-radius:5px; padding:0 6px;
             margin-left:4px; }
  .stbadge.st-SUSPENDED { color:#8a6d18; background:#faf0da; }
  .stbadge.st-CREATED { color:#2f6fce; background:#e9f1fc; }
  .stbadge.st-RUNNING { color:#2f8f4e; background:#e6f4ec; }
  .stbadge.st-COMPLETED { color:#8b897f; background:#eeece5; }
  .panel.inst { border-color:#a9cdb5; background:#f3faf5; }
  .panel.inst h2 { color:#2f8f4e; }
  .instfr { border-color:#a9cdb5; }
  .instfr.chg { background:var(--warnbg); border-color:#ecd9ae; }
  .instfr b { font-family:ui-monospace,Consolas,monospace; }
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
  <div class="colL">
    <div class="panel"><h2 id="srcname"></h2><div id="src"></div></div>
    <div class="panel"><h2 id="cname"></h2><div id="bc"></div></div>
  </div>
  <div>
    <div class="panel"><h2>프레임 스택 · 호출마다 1개 (맨 위 = 실행 중, 아래 = 호출한 프레임)</h2><div id="stk"></div>
      <div class="fr-legend">한 프레임의 <b>localsplus</b> = 지역(fast) · 셀(cell) · 자유(free) 를 한 배열에 두고 그 뒤에 값 스택.
        <span class="lpchip param">매개변수</span> <span class="lpchip cellv">셀</span> <span class="lpchip freev">자유</span> <span class="lpchip unset">미설정</span></div>
    </div>
    <div class="panel held" id="heldpanel" style="display:none"><h2>보관된 프레임 · 제너레이터 (소멸 아님, ip·값 스택 보존)</h2><div id="held"></div></div>
    <div class="panel inst" id="instpanel" style="display:none"><h2>인스턴스 · __dict__와 type().__mro__ (STORE_ATTR 시 diff 강조)</h2><div id="inst"></div></div>
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
<div class="hint">키보드 ← → 로도 이동. 프레임마다 그 프레임의 <b>모든 실제 변수</b>(localsplus: 지역·셀·자유·값 스택)를 보여 준다 — 호출한(대기) 프레임의 변수도 함께. 소스·바이트코드 패널은 길어지면 안에서 스크롤되고 현재 줄로 자동 이동한다.</div>
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

// localsplus 한 줄(라벨 + 칩들) 렌더
function lpLine(tag, chipsHtml) {
  return `<div class="lp-line"><span class="lp-tag">${tag}</span>${chipsHtml || '<span class="muttxt">—</span>'}</div>`;
}

// 프레임 하나의 '실제 변수 전부'를 localsplus 순서(지역·셀·자유·[네임스페이스]·값 스택)로
function frameBody(f) {
  let h = "";
  // 지역(fast) — 미설정 슬롯·셀로 옮겨간 슬롯까지 그대로
  const fast = (f.fast || []).map(v => {
    if (v.slot === "unset") return `<span class="lpchip unset">${esc(v.name)} = (미설정)</span>`;
    if (v.slot === "cell")  return `<span class="lpchip cellref">${esc(v.name)} → 셀 슬롯</span>`;
    return `<span class="lpchip ${v.param ? "param" : ""}">${esc(v.name)} = ${esc(v.val)}</span>`;
  }).join("");
  h += lpLine("지역(fast)", fast);
  if (f.cellvars && f.cellvars.length)
    h += lpLine("셀(cell)", f.cellvars.map(v => `<span class="lpchip cellv">${esc(v.name)} ▸ ${esc(v.val)}</span>`).join(""));
  if (f.freevars && f.freevars.length)
    h += lpLine("자유(free)", f.freevars.map(v => `<span class="lpchip freev">${esc(v.name)} ▸ ${esc(v.val)}</span>`).join(""));
  if (f.namespace)   // 클래스 본문 프레임 — 네임스페이스 dict가 실제 변수
    h += lpLine("네임스페이스", Object.entries(f.namespace).map(([k,v]) => `<span class="lpchip nsv">${esc(k)} = ${esc(v)}</span>`).join(""));
  h += lpLine("값 스택", (f.stack && f.stack.length)
      ? f.stack.map(v => `<span class="cell">${esc(v)}</span>`).join("")
      : '<span class="cell empty">비어 있음</span>');
  return h;
}

function ipInfo(f) {
  if (f.ip_off == null) return "";
  return `<span class="ipinfo">IP → offset ${f.ip_off}${f.ip_op ? " · " + esc(f.ip_op) : ""}</span>`;
}

function render() {
  const t = DATA[d], s = t.steps[i];
  $("slider").max = t.steps.length - 1;
  $("slider").value = i;
  const key = s.key ?? t.steps[Math.max(0, i-1)].key;
  const dispName = (t.names && t.names[key]) ? t.names[key] : key;

  // -- 소스 --
  const src = t.sources[key] ?? {first: 1, lines: []};
  $("srcname").textContent = dispName + " 소스 코드";
  $("src").innerHTML = src.lines.map((ln, n) => {
    const lineno = src.first + n;
    return `<div class="src-row ${s.key === key && lineno === s.line ? "on" : ""}">` +
           `<span class="no">${lineno}</span><span>${esc(ln) || " "}</span></div>`;
  }).join("");

  // -- 바이트코드 --
  $("cname").textContent = dispName + " 의 바이트코드 (진짜 CPython 출력)";
  $("bc").innerHTML = (t.listings[key] ?? []).map((r, n) =>
    `<div class="bc-row ${s.key === key && n === s.exec ? "on" : ""}" data-n="${n}">` +
    `<span class="off">${r.off}</span><span>${esc(r.op)} ${esc(r.arg)}</span></div>`).join("");
  document.querySelectorAll(".bc-row").forEach(el => {
    el.onclick = () => { const r = t.listings[key][+el.dataset.n];
                        pinnedDoc = [r.op, r.doc]; showDoc(r.op, r.doc); };
  });

  // -- 프레임 스택 (localsplus 전체) --
  $("stk").innerHTML = s.frames.length === 0
    ? '<div class="muttxt" style="text-align:center;padding:24px 0">비어 있음 — 실행 종료</div>'
    : s.frames.slice().reverse().map((f, ri) => {
      const depth = s.frames.length - ri;   // 위에서부터 1, 2, ...
      const role = f.active ? "· 실행 중" : "· 대기(호출한 프레임)";
      return `<div class="fr ${f.active ? "act" : "wait"}">
        <div class="fr-name">#${depth} ${esc(f.name)} 프레임 <span class="frtag">${role}</span>${ipInfo(f)}</div>
        ${frameBody(f)}</div>`;
    }).join("");

  // -- 보관된 프레임 (제너레이터) — 스택 프레임과 같은 localsplus 배치 --
  const held = s.held ?? [];
  $("heldpanel").style.display = held.length ? "" : "none";
  $("held").innerHTML = held.map(f => `
      <div class="fr heldfr st-${esc(f.state)}">
        <div class="fr-name">${esc(f.label)} <span class="stbadge st-${esc(f.state)}">${esc(f.state)}</span>${ipInfo(f)}</div>
        <div class="fr-row muttxt">보관된 위치: offset ${f.ip_off ?? "—"}${f.line ? " (소스 " + f.line + "줄)" : ""}</div>
        ${frameBody(f)}</div>`).join("");

  // -- 인스턴스 (__dict__ · MRO) --
  const insts = s.instances ?? [];
  $("instpanel").style.display = insts.length ? "" : "none";
  $("inst").innerHTML = insts.map(o => `
      <div class="fr instfr ${o.changed ? "chg" : ""}">
        <div class="fr-name">${esc(o.label)}</div>
        <div class="fr-row">__dict__: <b>${esc(o.dict)}</b>${o.changed ? ' <span class="attr-chgtag">← 변경됨</span>' : ""}</div>
        <div class="fr-row">MRO: ${esc(o.mro)}</div>
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

  // 활성 소스 줄·바이트코드 줄을 각 스크롤 패널 '안에서만' 보이게 (페이지는 안 움직임)
  centerInScroll("src", ".src-row.on");
  centerInScroll("bc", ".bc-row.on");
}

function centerInScroll(containerId, sel) {
  const c = $(containerId), el = c.querySelector(sel);
  if (!el) return;
  const target = el.offsetTop - c.clientHeight / 2 + el.clientHeight / 2;
  c.scrollTop = Math.max(0, target);
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
