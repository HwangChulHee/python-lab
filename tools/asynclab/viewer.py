"""
viewer.py — 트레이스(dict) → 단일 자족 HTML 문자열

pvmlab viewer의 시각 언어를 따른다: 같은 CSS 변수, 카드형 패널, ←/→ 스테핑,
내레이션 문장. 6패널 그리드:

  ① 소스 코드      ② 콜 스택         ③ 이벤트 루프 내부 (심장)
  ④ 힙            ⑤ 네트워크 타임라인  ⑥ 내레이션

한 스텝 = 이벤트 루프의 사건 하나. 외부 리소스 0 — 트레이스 JSON을 __DATA__에
박아 하나의 HTML로 만든다.
"""

import json

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>asynclab — 코루틴·이벤트 루프</title>
<style>
  :root { --bg:#faf9f5; --card:#ffffff; --line:#e3e1d9; --txt:#26251f;
          --mut:#8b897f; --sub:#5f5e56; --acc:#2f6fce; --accbg:#e9f1fc;
          --warn:#9a6b1a; --warnbg:#faf0da; --run:#2f8f4e; --runbg:#e6f4ec;
          --sel:#5a7fb8; --selbg:#eef3fa; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--txt); padding:22px 18px 60px;
         font:14.5px/1.6 system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }
  .wrap { max-width:1560px; margin:0 auto; }
  h1 { font-size:19px; font-weight:600; margin-bottom:3px; }
  .sub { font-size:13.5px; color:var(--sub); margin-bottom:12px; }
  .progress { height:4px; background:var(--line); border-radius:2px; margin-bottom:14px; }
  .progress i { display:block; height:100%; background:var(--acc); border-radius:2px; }
  .grid { display:grid; grid-template-columns:1.05fr 0.95fr 1.15fr; gap:13px;
          align-items:start; }
  @media (max-width:1100px) { .grid { grid-template-columns:1fr; } }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:12px; min-width:0; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:8px; }
  .scroll { max-height:46vh; overflow:auto; }

  /* ① 소스 */
  .src-row { display:flex; gap:10px; padding:1.5px 8px; border-radius:6px;
             font:12.5px/1.6 ui-monospace,Consolas,monospace; color:var(--sub);
             white-space:pre; }
  .src-row .no { color:var(--mut); min-width:24px; text-align:right; user-select:none; }
  .src-row.on { background:var(--warnbg); color:var(--warn); font-weight:600; }
  .src-row.bmk { background:var(--selbg); }
  .bm { font:10.5px system-ui; color:var(--sel); background:#dfe9f6; border-radius:5px;
        padding:0 6px; margin-left:8px; align-self:center; white-space:nowrap; }
  .bm::before { content:"📑 "; }

  /* ② 콜 스택 */
  .stk-note { font-size:11px; color:var(--mut); margin-bottom:7px; }
  .frame { border:1px solid var(--line); border-radius:8px; padding:7px 11px;
           margin-bottom:7px; font:13px ui-monospace,Consolas,monospace; color:var(--sub); }
  .frame.coro { border-color:var(--acc); background:var(--accbg); color:#1c4d94; font-weight:600; }
  .frame.coro.infra { opacity:.62; font-weight:400; border-style:dashed; }
  .frame.loopfr { border:2px solid var(--warn); background:var(--warnbg); color:var(--warn); }
  .frame .tag { font:10.5px system-ui; border-radius:5px; padding:0 6px; margin-left:7px;
                font-weight:400; }
  .frame .tag.res { color:var(--warn); background:#f3e3bd; }
  .frame .tag.who { color:#1c4d94; background:#d7e5f8; }
  .frame .tag.ln { color:var(--mut); background:var(--bg); }
  .cpu0 { border:1px dashed var(--sel); background:var(--selbg); color:var(--sel);
          border-radius:8px; padding:7px 11px; margin-bottom:7px; font-size:12.5px;
          text-align:center; }

  /* ③ 이벤트 루프 내부 */
  .phases { display:flex; gap:7px; margin-bottom:11px; }
  .ph { flex:1; text-align:center; padding:5px 0; border-radius:8px; font-size:12px;
        border:1px solid var(--line); color:var(--mut); background:var(--bg); }
  .ph.on.SELECT { border-color:var(--sel); background:var(--selbg); color:var(--sel); font-weight:700; }
  .ph.on.WAKE { border-color:var(--warn); background:var(--warnbg); color:var(--warn); font-weight:700; }
  .ph.on.RUN { border-color:var(--run); background:var(--runbg); color:var(--run); font-weight:700; }
  .sec { font-size:11px; color:var(--mut); margin:10px 0 5px; font-weight:600; }
  .sec b { color:var(--sub); }
  .qrow { display:flex; gap:6px; flex-wrap:wrap; }
  .cb { padding:2px 9px; border-radius:6px; border:1px solid #bcd3f0; background:var(--accbg);
        color:#1c4d94; font:12px ui-monospace,monospace; }
  .cb.exec { border-color:var(--run); background:var(--runbg); color:var(--run); font-weight:700; }
  .empty { font-size:12px; color:var(--mut); padding:2px 0; }
  .wrow { display:grid; grid-template-columns:auto 1fr; gap:8px; padding:4px 9px;
          border:1px solid var(--line); border-radius:7px; margin-bottom:5px;
          font:12px ui-monospace,monospace; color:var(--sub); align-items:center; }
  .wrow.hot { border-color:var(--warn); background:var(--warnbg); color:var(--warn); font-weight:600; }
  .wrow .fd { font-weight:700; }

  /* ④ 힙 */
  .hcard { border:1px solid var(--line); border-radius:8px; padding:8px 11px; margin-bottom:7px; }
  .hcard.code { border-color:#c9b8e6; background:#f7f3fc; }
  .hcard.code .nm { color:#6a4bb0; }
  .hcard .nm { font:600 13px ui-monospace,Consolas,monospace; }
  .hcard .meta { font-size:11.5px; color:var(--mut); margin-top:2px; }
  .hcard .share { font-size:11.5px; color:#6a4bb0; margin-top:3px; }
  .fchip { display:inline-block; font:12px ui-monospace,monospace; border:1px solid var(--line);
           border-radius:6px; padding:1px 8px; margin:0 5px 5px 0; color:var(--sub);
           background:var(--card); cursor:help; }
  .hcard.coro { border-color:#c9a227; background:#fdf8ec; }
  .hcard.coro.RUNNING { border-color:var(--run); background:var(--runbg); }
  .hcard.coro.CREATED { border-color:#7ea3d6; background:#eef4fb; }
  .hcard.coro.DONE { opacity:.5; border-color:var(--line); background:var(--card); }
  .stbadge { font-size:10.5px; font-weight:600; border-radius:5px; padding:0 6px; margin-left:6px; }
  .stbadge.SUSPENDED { color:#8a6d18; background:#faf0da; }
  .stbadge.CREATED { color:#2f6fce; background:#e9f1fc; }
  .stbadge.RUNNING { color:#2f8f4e; background:#d9efe2; }
  .stbadge.DONE { color:#8b897f; background:#eeece5; }
  .codelink { font-size:11px; color:#6a4bb0; background:#f0e9fb; border-radius:5px;
              padding:0 6px; margin-left:6px; }
  .locals { font:11.5px ui-monospace,monospace; color:var(--sub); margin-top:4px; }
  .locals div { overflow-wrap:anywhere; }

  /* ⑤ 네트워크 타임라인 */
  .net { display:flex; flex-direction:column; gap:5px; }
  .ev { display:flex; align-items:center; gap:8px; padding:4px 10px; border-radius:7px;
        border:1px solid var(--line); font-size:12.5px; color:var(--mut); }
  .ev.used { color:var(--sub); background:var(--bg); }
  .ev.used .chk { color:var(--run); font-weight:700; }
  .ev.now { border-color:var(--acc); background:var(--accbg); color:#1c4d94; font-weight:600; }
  .clockbox { font-size:12.5px; color:var(--sub); margin-bottom:8px; }
  .clockbox b { font-family:ui-monospace,monospace; color:var(--acc); }

  /* ⑥ 내레이션 */
  .desc { padding:12px 14px; border:1px solid #bcd3f0; background:var(--accbg);
          border-radius:10px; color:#1c4d94; min-height:110px; font-size:14px; }
  .kbadge { display:inline-block; font-size:10.5px; font-weight:600; border-radius:5px;
            padding:1px 7px; margin-bottom:7px; }
  .kbadge.phase { color:var(--sel); background:var(--selbg); }
  .kbadge.resume { color:var(--run); background:var(--runbg); }
  .kbadge.suspend { color:var(--warn); background:var(--warnbg); }
  .kbadge.created { color:#6a4bb0; background:#f0e9fb; }
  .kbadge.done { color:#8b897f; background:#eeece5; }
  .kbadge.loop { color:#1c4d94; background:#d7e5f8; }

  .nav { display:flex; align-items:center; gap:12px; margin-top:14px; }
  button { font:inherit; padding:8px 18px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  input[type=range] { flex:1; }
  .pos { font-size:13px; color:var(--mut); min-width:70px; text-align:right; }
</style></head><body><div class="wrap">
<h1>asynclab — 코루틴·이벤트 루프</h1>
<div class="sub" id="subtitle"></div>
<div class="progress"><i id="prog"></i></div>
<div class="grid">
  <div class="panel"><h2>① 소스 — demos/mini_web.py (📑 = 보관된 프레임의 책갈피)</h2>
    <div class="scroll" id="src"></div></div>
  <div class="panel"><h2>② 콜 스택 (아래가 바닥 — 루프 프레임은 상주)</h2>
    <div id="stack"></div></div>
  <div class="panel"><h2>③ 이벤트 루프 내부</h2><div class="scroll" id="loop"></div></div>
  <div class="panel"><h2>④ 힙 — 코드 객체는 공유, 프레임(코루틴)은 각자</h2>
    <div class="scroll" id="heap"></div></div>
  <div class="panel"><h2>⑤ 네트워크 타임라인 (각본)</h2>
    <div class="clockbox">가상 시계 <b id="clock"></b></div><div class="net" id="net"></div></div>
  <div class="panel"><h2>⑥ 내레이션 — 이번 스텝에서 일어난 일</h2>
    <div id="kind"></div><div class="desc" id="desc"></div></div>
</div>
<div class="nav">
  <button id="prev">← 이전</button><button id="next">다음 →</button>
  <input type="range" id="slider" min="0" value="0"><span class="pos" id="pos"></span>
</div>
</div>
<script>
const T = __DATA__;
let i = 0;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
$("subtitle").textContent = T.subtitle;
$("slider").max = T.steps.length - 1;

const KIND_LABEL = { phase:"페이즈", resume:"코루틴 재개", suspend:"프레임 보관",
                     created:"코루틴 생성", done:"코루틴 종료", loop:"루프" };

function render() {
  const s = T.steps[i];
  $("prog").style.width = (i / (T.steps.length - 1) * 100) + "%";

  // ① 소스 — 하이라이트 + 책갈피
  const marks = {};                        // line → [labels]
  s.src.bookmarks.forEach(b => (marks[b.line] = marks[b.line] || []).push(b.label));
  $("src").innerHTML = T.src.map((ln, n0) => {
    const n = n0 + 1;
    const cls = n === s.src.hi ? "on" : (marks[n] ? "bmk" : "");
    const bms = (marks[n] || []).map(l => `<span class="bm">${esc(l)}</span>`).join("");
    return `<div class="src-row ${cls}"><span class="no">${n}</span><span>${esc(ln) || " "}</span>${bms}</div>`;
  }).join("");
  const hiEl = $("src").querySelector(".on") || $("src").querySelector(".bmk");
  if (hiEl) hiEl.scrollIntoView({ block:"center" });

  // ② 콜 스택 — 배열은 바닥→꼭대기, 표시는 꼭대기부터
  const frames = s.stack.slice().reverse().map(f => {
    if (f.kind === "loop")
      return `<div class="frame loopfr">${esc(f.name)}<span class="tag res">상주</span></div>`;
    if (f.kind === "coro") {
      const ln = f.line ? `<span class="tag ln">줄 ${f.line}</span>` : "";
      return `<div class="frame coro ${f.infra ? "infra" : ""}">${esc(f.name)}` +
             `<span class="tag who">${esc(f.label)}</span>${ln}</div>`;
    }
    return `<div class="frame">${esc(f.name)}</div>`;
  });
  const cpu = s.phase === "SELECT"
    ? `<div class="cpu0">💤 OS 대기 중 — CPU 0% (파이썬 코드는 돌지 않는다)</div>` : "";
  $("stack").innerHTML = `<div class="stk-note">↓ 스택 꼭대기</div>` + cpu + frames.join("");

  // ③ 루프 내부 — 페이즈 표시등 / 준비큐 / 장부 / 타이머 힙
  const phases = ["SELECT","WAKE","RUN"].map(p =>
    `<div class="ph ${p} ${p === s.phase ? "on " + p : ""}">${p}${
      p==="SELECT"?" · 잠듦":p==="WAKE"?" · 수거":" · 소진"}</div>`).join("");
  const running = s.running ? `<span class="cb exec">▶ Task(${esc(s.running)}).step 실행 중</span>` : "";
  const ready = s.loop.ready.map(c => `<span class="cb">${esc(c)}</span>`).join("");
  const watch = s.loop.watch.map(w =>
    `<div class="wrow ${w.notified ? "hot" : ""}"><span class="fd">fd ${w.fd} (${esc(w.name)})</span>` +
    `<span>→ ${esc(w.cb)} 깨우기${w.notified ? " ← OS 알림!" : ""}</span></div>`).join("");
  const timers = s.loop.timers.length
    ? s.loop.timers.map(t => `<div class="wrow"><span class="fd">T=${t[0]}</span><span>→ ${esc(t[1])}</span></div>`).join("")
    : `<div class="empty">비어 있음 — 이 시나리오엔 sleep이 없다 (구조만 봐 두자)</div>`;
  $("loop").innerHTML = `<div class="phases">${phases}</div>` +
    `<div class="sec">준비큐 <b>ready (deque)</b> — 콜백만 들어간다, 코루틴이 아니라</div>` +
    `<div class="qrow">${running}${ready || (s.running ? "" : `<span class="empty">비어 있음</span>`)}</div>` +
    `<div class="sec">셀렉터 장부 <b>watch</b> — "이 fd가 되면 이 콜백을 불러라"</div>` +
    (watch || `<div class="empty">비어 있음</div>`) +
    `<div class="sec">타이머 힙 <b>timers</b> — (깨울 시각, 콜백)</div>` + timers;

  // ④ 힙 — 코드 객체(공유) / 함수 객체 / 코루틴 객체(보관된 프레임)
  const codes = s.heap.codes.map(c =>
    `<div class="hcard code"><span class="nm">${esc(c.qualname)}</span>` +
    `<span class="codelink">코드 객체 · 줄 ${c.firstlineno}~</span>` +
    `<div class="share">↖ ${c.shared.map(esc).join(" · ")} ${c.shared.length > 1 ? "가 공유 — 악보는 하나, 무대는 각자" : ""}</div></div>`).join("");
  const funcs = s.heap.funcs.map(f =>
    `<span class="fchip" title="${esc(f.note)}">${esc(f.name)}</span>`).join("");
  const coros = s.heap.coros.map(c => {
    const fr = c.line !== null
      ? `cr_frame.f_lineno = <b>${c.line}</b> (멈춘 줄 = 이 손님의 상태)`
      : `cr_frame = <b>None</b> — 프레임 소멸`;
    const lo = c.locals.map(kv => `<div>${esc(kv[0])} = ${esc(kv[1])}</div>`).join("");
    return `<div class="hcard coro ${c.state}"><span class="nm">${esc(c.label)}</span>` +
      `<span class="stbadge ${c.state}">${c.state}</span>` +
      `<span class="codelink">코드 → ${esc(c.code)}</span>` +
      `<div class="meta">${fr}</div>` +
      (lo ? `<div class="locals">${lo}</div>` : "") + `</div>`;
  }).join("");
  $("heap").innerHTML =
    `<div class="sec">코드 객체 — 컴파일 산물, 불변, <b>공유</b></div>` + codes +
    `<div class="sec">함수 객체 — 호출하면 코루틴 객체가 나온다</div><div>${funcs}</div>` +
    `<div class="sec">코루틴 객체 — 보관된 프레임 (진짜 cr_frame을 읽는 중)</div>` + coros;

  // ⑤ 네트워크 타임라인
  $("clock").textContent = "T=" + s.clock;
  $("net").innerHTML = T.script.map(e => {
    const used = s.net.consumed > T.script.indexOf(e);
    const now = used && e.t === s.clock;
    return `<div class="ev ${used ? "used" : ""} ${now ? "now" : ""}">` +
      `<span class="chk">${used ? "✓" : "·"}</span><span>${esc(e.desc)}</span></div>`;
  }).join("");

  // ⑥ 내레이션
  $("kind").innerHTML = `<span class="kbadge ${s.kind}">${KIND_LABEL[s.kind] || s.kind}</span>` +
    ` <span style="font-size:11px;color:var(--mut)">T=${s.clock} · ${s.phase}</span>`;
  $("desc").textContent = s.narration;

  $("slider").value = i;
  $("pos").textContent = i + " / " + (T.steps.length - 1);
  $("prev").disabled = i === 0;
  $("next").disabled = i === T.steps.length - 1;
}
$("next").onclick = () => { if (i < T.steps.length - 1) { i++; render(); } };
$("prev").onclick = () => { if (i > 0) { i--; render(); } };
$("slider").oninput = e => { i = +e.target.value; render(); };
document.onkeydown = e => {
  if (e.key === "ArrowRight") $("next").click();
  if (e.key === "ArrowLeft") $("prev").click();
};
render();
</script></body></html>
"""


def build_html(trace):
    data = json.dumps(trace, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", data)
