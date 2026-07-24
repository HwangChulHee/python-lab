"""
viewer.py — 트레이스(dict) → 단일 자족 HTML 문자열

pvmlab viewer의 시각 언어를 따른다: 같은 CSS 변수, 카드형 패널, ←/→ 스테핑.
가독성 장치 세 가지:
  · 내레이션은 상단 전폭 '스토리' 띠 — 키워드(Task/fd/줄/페이즈)를 자동 강조
  · 태스크별 고정 색 (serve=보라, client_A=파랑, client_B=초록) — 책갈피·콜 스택·
    준비큐·장부·힙 카드 어디서든 같은 색이면 같은 손님이다
  · 직전 스텝과 달라진 코루틴 카드에 플래시 표시

패널: ① 소스 ② 콜 스택 ③ 이벤트 루프 내부 / ④ 힙 ⑤ 네트워크 타임라인 ⑥ 읽는 법.
한 스텝 = 이벤트 루프의 사건 하나. 외부 리소스 0 — 트레이스 JSON을 __DATA__에 박는다.
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
  .progress { height:4px; background:var(--line); border-radius:2px; margin-bottom:12px; }
  .progress i { display:block; height:100%; background:var(--acc); border-radius:2px; }

  /* 스토리 띠 — 이번 스텝에서 일어난 일 (가장 먼저 읽는 곳) */
  .story { display:grid; grid-template-columns:auto 1fr auto; gap:14px; align-items:center;
           background:var(--card); border:1px solid var(--line); border-left:5px solid var(--acc);
           border-radius:10px; padding:13px 16px; margin-bottom:13px; }
  .story.k-phase   { border-left-color:var(--sel); }
  .story.k-resume  { border-left-color:var(--run); }
  .story.k-suspend { border-left-color:var(--warn); }
  .story.k-created { border-left-color:#8a63c9; }
  .story.k-done    { border-left-color:#8b897f; }
  .story-meta { text-align:center; min-width:86px; }
  .kbadge { display:block; font-size:11px; font-weight:700; border-radius:6px; padding:2px 8px; }
  .kbadge.phase { color:var(--sel); background:var(--selbg); }
  .kbadge.resume { color:var(--run); background:var(--runbg); }
  .kbadge.suspend { color:var(--warn); background:var(--warnbg); }
  .kbadge.created { color:#6a4bb0; background:#f0e9fb; }
  .kbadge.done { color:#8b897f; background:#eeece5; }
  .kbadge.loop { color:#1c4d94; background:#d7e5f8; }
  .story-meta .tp { font:11.5px ui-monospace,monospace; color:var(--mut); margin-top:4px; display:block; }
  .story-text { font-size:15px; line-height:1.75; }
  .story-text code { font:600 13px ui-monospace,Consolas,monospace; border-radius:5px;
                     padding:1px 6px; background:var(--bg); color:var(--sub); white-space:nowrap; }
  .story-text code.kw { color:#1c4d94; background:var(--accbg); }
  .keyhint { font-size:11.5px; color:var(--mut); white-space:nowrap; }

  .grid { display:grid; grid-template-columns:1.2fr 0.9fr 1.1fr; gap:13px; align-items:start; }
  /* 소스는 왼쪽 열 전체(2행)를 차지한다. sticky는 쓰지 않는다 — 떠 있는 패널이
     아래 내용을 가리는 문제. 현재 줄은 어차피 패널 안에서 자동 중앙 정렬된다. */
  .srcpanel { grid-row:1 / span 2; }
  .fullw { grid-column:1 / -1; }
  @media (max-width:1100px) { .grid { grid-template-columns:1fr; }
    .srcpanel { grid-row:auto; } .fullw { grid-column:auto; } }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:12px; min-width:0; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:8px; }
  .scroll { max-height:44vh; overflow:auto; }
  @keyframes flash { from { box-shadow:0 0 0 3px #e6c98a; } to { box-shadow:0 0 0 3px transparent; } }
  .chg { animation:flash .9s ease-out; }

  /* ① 소스 — 크게, 세로로 최대한 */
  #src { max-height:calc(100vh - 210px); overflow:auto; }
  .src-row { display:flex; gap:11px; padding:1.5px 8px; border-radius:6px;
             font:13.5px/1.62 ui-monospace,Consolas,monospace; color:var(--sub);
             white-space:pre; }
  .src-row .no { color:var(--mut); min-width:26px; text-align:right; user-select:none; }
  .src-row.doc { opacity:.5; }             /* 모듈 docstring은 옅게 — 코드에 집중 */
  .src-row.on { background:var(--warnbg); color:var(--warn); font-weight:600; }
  .bm { font:10.5px system-ui; border-radius:5px; padding:0 6px; margin-left:8px;
        align-self:center; white-space:nowrap; }
  .bm::before { content:"📑 "; }

  /* ② 콜 스택 */
  .stk-note { font-size:11px; color:var(--mut); margin-bottom:7px; }
  .frame { border:1px solid var(--line); border-radius:8px; padding:7px 11px;
           margin-bottom:7px; font:13px ui-monospace,Consolas,monospace; color:var(--sub); }
  .frame.coro { font-weight:600; }
  .frame.coro.infra { opacity:.62; font-weight:400; border-style:dashed; }
  .frame.loopfr { border:2px solid var(--warn); background:var(--warnbg); color:var(--warn); }
  .frame .tag { font:10.5px system-ui; border-radius:5px; padding:0 6px; margin-left:7px;
                font-weight:400; }
  .frame .tag.res { color:var(--warn); background:#f3e3bd; }
  .frame .tag.ln { color:var(--mut); background:rgba(255,255,255,.65); }
  .frame .tag.push { color:#2f8f4e; background:#d9efe2; font-weight:700; }
  .frame .tag.pop { color:#b3543a; background:#f9e5de; font-weight:700; }
  .frame.coro.ghost { opacity:.55; border-style:dashed; }
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
  .cb { padding:2px 9px; border-radius:6px; border:1px solid var(--line);
        font:12px ui-monospace,monospace; background:var(--card); color:var(--sub); }
  .cb.exec { font-weight:700; }
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
  .hcard.coro { border-left-width:5px; background:var(--card); }
  .hcard.coro.DONE { opacity:.5; }
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

  /* ⑥ 읽는 법 */
  .guide { font-size:12.5px; color:var(--sub); line-height:1.9;
           display:grid; grid-template-columns:1fr 1fr; gap:0 26px; }
  @media (max-width:1100px) { .guide { grid-template-columns:1fr; } }
  .guide .row { margin-bottom:2px; }
  .guide code { font:12px ui-monospace,monospace; background:var(--bg); border-radius:5px; padding:0 5px; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px;
         vertical-align:-1px; }

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
<div class="story" id="story">
  <div class="story-meta"><span class="kbadge" id="kind"></span><span class="tp" id="tp"></span></div>
  <div class="story-text" id="desc"></div>
  <div class="keyhint">←/→ 키로<br>한 사건씩</div>
</div>
<div class="grid">
  <div class="panel srcpanel"><h2>① 소스 — demos/mini_web.py (📑 = 보관된 프레임의 책갈피)</h2>
    <div id="src"></div></div>
  <div class="panel"><h2>② 콜 스택 (아래가 바닥 — 루프 프레임은 상주)</h2>
    <div id="stack"></div></div>
  <div class="panel"><h2>③ 이벤트 루프 내부</h2><div class="scroll" id="loop"></div></div>
  <div class="panel"><h2>④ 힙 — 코드 객체는 공유, 프레임(코루틴)은 각자</h2>
    <div class="scroll" id="heap"></div></div>
  <div class="panel"><h2>⑤ 네트워크 타임라인 (각본)</h2>
    <div class="clockbox">가상 시계 <b id="clock"></b></div><div class="net" id="net"></div></div>
  <div class="panel fullw"><h2>⑥ 읽는 법</h2><div class="guide" id="guide"></div></div>
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

/* 태스크별 고정 색 — 어느 패널에서든 같은 색 = 같은 손님 */
const LAB = {
  serve:    { fg:"#6a4bb0", bg:"#f0e9fb", bd:"#c9b8e6" },
  client_A: { fg:"#1c4d94", bg:"#e9f1fc", bd:"#9cc2ea" },
  client_B: { fg:"#2f7a4a", bg:"#e6f4ec", bd:"#a9cdb5" },
};
const lab = l => LAB[l] || { fg:"var(--sub)", bg:"var(--bg)", bd:"var(--line)" };
const labStyle = l => `color:${lab(l).fg};background:${lab(l).bg};border-color:${lab(l).bd}`;

/* 내레이션 키워드 강조 — 한 번의 정규식 패스로 겹침 없이 처리 */
const NARR_RE = /(Task\((?:serve|client_A|client_B)\)\.step)|(client_A|client_B)|(fd \d+ \([^)]+\)|fd \d+)|(줄 \d+)|(SELECT|WAKE|RUN(?=[ \s—,.]|$)|StopIteration|coro\.send\(None\)|call_soon|run_until_complete\(\)|cr_frame ?= ?None|CPU 0%|SUSPENDED|CREATED|DONE)/g;
function fmtNarr(text) {
  return esc(text).replace(NARR_RE, (m, task, label, fd, line, kw) => {
    if (task) {
      const l = task.slice(5, -6);                 // "Task(" ... ").step"
      return `<code style="${labStyle(l)}">${m}</code>`;
    }
    if (label) return `<code style="${labStyle(label)}">${m}</code>`;
    if (kw) return `<code class="kw">${m}</code>`;
    return `<code>${m}</code>`;                    // fd n / 줄 n
  });
}

/* 준비큐·장부 콜백 표기에서 태스크 라벨을 뽑아 색을 입힌다 */
const cbOwner = c => (c.match(/^Task\((.+)\)\.step$/) || [])[1];

/* 모듈 docstring 줄들(1행이 \"\"\"로 시작 ~ 닫는 \"\"\")은 옅게 표시한다 */
const DOC = new Set();
if ((T.src[0] || "").startsWith('\"\"\"')) {
  DOC.add(1);
  for (let n = 1; n < T.src.length; n++) {
    DOC.add(n + 1);
    if (T.src[n].includes('\"\"\"')) break;
  }
}

/* 컨테이너 안에서만 세로 스크롤 — 페이지 전체가 딸려 움직이지 않게 */
function centerIn(box, el) {
  if (!box || !el) return;
  box.scrollTop = el.offsetTop - box.clientHeight / 2 + el.clientHeight / 2;
}

function render() {
  const s = T.steps[i];
  const prev = i > 0 ? T.steps[i - 1] : null;
  $("prog").style.width = (i / (T.steps.length - 1) * 100) + "%";

  // 스토리 띠
  $("story").className = "story k-" + s.kind;
  $("kind").className = "kbadge " + s.kind;
  $("kind").textContent = KIND_LABEL[s.kind] || s.kind;
  $("tp").textContent = `T=${s.clock} · ${s.phase}`;
  $("desc").innerHTML = fmtNarr(s.narration);

  // ① 소스 — 하이라이트 + 책갈피(태스크 색)
  const marks = {};                                // line → [labels]
  s.src.bookmarks.forEach(b => (marks[b.line] = marks[b.line] || []).push(b.label));
  $("src").innerHTML = T.src.map((ln, n0) => {
    const n = n0 + 1;
    const bms = (marks[n] || []).map(l => `<span class="bm" style="${labStyle(l)}">${esc(l)}</span>`).join("");
    const bg = marks[n] ? `background:${lab(marks[n][0]).bg}` : "";
    const cls = (n === s.src.hi ? "on" : "") + (DOC.has(n) ? " doc" : "");
    return `<div class="src-row ${cls}" style="${n === s.src.hi ? "" : bg}">` +
           `<span class="no">${n}</span><span>${esc(ln) || " "}</span>${bms}</div>`;
  }).join("");
  centerIn($("src"), $("src").querySelector(".on") || $("src").querySelector(".bm"));

  // ② 콜 스택 — 배열은 바닥→꼭대기, 표시는 꼭대기부터.
  // 직전 스텝과 비교해: 방금 얹힌 프레임 ↑(초록 플래시), 방금 내려간 프레임은
  // 유령(점선·반투명)으로 남겨 ↓ 방향을 보여준다.
  const fkey = f => f.name + "|" + (f.label || "");
  const curKeys = s.stack.filter(f => f.kind === "coro").map(fkey);
  const prevKeys = prev ? prev.stack.filter(f => f.kind === "coro").map(fkey) : [];
  const pushed = new Set(curKeys.filter(k => !prevKeys.includes(k)));
  const popped = prev ? prev.stack.filter(f => f.kind === "coro" && !curKeys.includes(fkey(f))) : [];

  const coroFrame = (f, extraTag, ghost) => {
    const c = lab(f.label);
    const ln = f.line ? `<span class="tag ln">줄 ${f.line}</span>` : "";
    return `<div class="frame coro ${f.infra ? "infra" : ""} ${ghost ? "ghost" : ""}"` +
           ` style="border-color:${c.bd};background:${c.bg};color:${c.fg}">` +
           `${esc(f.name)}<span class="tag" style="${labStyle(f.label)}">${esc(f.label)}</span>${ln}${extraTag}</div>`;
  };
  const popTag = s.kind === "done"
    ? `<span class="tag pop">↓ 프레임 소멸</span>`
    : `<span class="tag pop">↓ 내려놓음 — 보관</span>`;
  const ghosts = popped.slice().reverse().map(f => coroFrame(f, popTag, true));
  const frames = s.stack.slice().reverse().map(f => {
    if (f.kind === "loop")
      return `<div class="frame loopfr">${esc(f.name)}<span class="tag res">상주</span></div>`;
    if (f.kind === "coro") {
      const up = pushed.has(fkey(f)) ? `<span class="tag push">↑ 얹힘</span>` : "";
      return coroFrame(f, up, false);
    }
    return `<div class="frame">${esc(f.name)}</div>`;
  });
  const cpu = s.phase === "SELECT"
    ? `<div class="cpu0">💤 OS 대기 중 — CPU 0% (파이썬 코드는 돌지 않는다)</div>` : "";
  $("stack").innerHTML = `<div class="stk-note">↓ 스택 꼭대기</div>` + cpu + ghosts.join("") + frames.join("");

  // ③ 루프 내부 — 페이즈 표시등 / 준비큐 / 장부 / 타이머 힙
  const phases = ["SELECT","WAKE","RUN"].map(p =>
    `<div class="ph ${p} ${p === s.phase ? "on " + p : ""}">${p}${
      p==="SELECT"?" · 잠듦":p==="WAKE"?" · 수거":" · 소진"}</div>`).join("");
  const cbChip = (c, extra) =>
    `<span class="cb ${extra || ""}" style="${labStyle(cbOwner(c))}">${esc(c)}</span>`;
  const running = s.running ? cbChip(`Task(${s.running}).step`, "exec").replace("</span>", " ▶ 실행 중</span>") : "";
  const ready = s.loop.ready.map(c => cbChip(c)).join("");
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
  const prevCoro = {};
  if (prev) prev.heap.coros.forEach(c => prevCoro[c.label] = c);
  const codes = s.heap.codes.map(c =>
    `<div class="hcard code"><span class="nm">${esc(c.qualname)}</span>` +
    `<span class="codelink">코드 객체 · 줄 ${c.firstlineno}~</span>` +
    `<div class="share">↖ ${c.shared.map(l => `<span style="color:${lab(l).fg}">${esc(l)}</span>`).join(" · ")}` +
    `${c.shared.length > 1 ? " 가 공유 — 악보는 하나, 무대는 각자" : ""}</div></div>`).join("");
  const funcs = s.heap.funcs.map(f =>
    `<span class="fchip" title="${esc(f.note)}">${esc(f.name)}</span>`).join("");
  const coros = s.heap.coros.map(c => {
    const p = prevCoro[c.label];
    const changed = p && (p.state !== c.state || p.line !== c.line);
    const fr = c.line !== null
      ? `cr_frame.f_lineno = <b>${c.line}</b> (멈춘 줄 = 이 손님의 상태)`
      : `cr_frame = <b>None</b> — 프레임 소멸`;
    const lo = c.locals.map(kv => `<div>${esc(kv[0])} = ${esc(kv[1])}</div>`).join("");
    return `<div class="hcard coro ${c.state} ${changed ? "chg" : ""}" style="border-left-color:${lab(c.label).fg}">` +
      `<span class="nm" style="color:${lab(c.label).fg}">${esc(c.label)}</span>` +
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
  $("net").innerHTML = T.script.map((e, n) => {
    const used = s.net.consumed > n;
    const now = used && e.t === s.clock;
    return `<div class="ev ${used ? "used" : ""} ${now ? "now" : ""}">` +
      `<span class="chk">${used ? "✓" : "·"}</span><span>${esc(e.desc)}</span></div>`;
  }).join("");

  $("slider").value = i;
  $("pos").textContent = i + " / " + (T.steps.length - 1);
  $("prev").disabled = i === 0;
  $("next").disabled = i === T.steps.length - 1;
}

$("guide").innerHTML = [
  `<div class="row"><span class="dot" style="background:${LAB.serve.bd}"></span>serve` +
  ` <span class="dot" style="background:${LAB.client_A.bd}"></span>client_A` +
  ` <span class="dot" style="background:${LAB.client_B.bd}"></span>client_B` +
  ` — 어느 패널에서든 같은 색 = 같은 태스크</div>`,
  `<div class="row"><b>SELECT → WAKE → RUN</b> — 루프 while 한 바퀴. 잠들고, 장부 보고 깨우고, 준비큐를 소진한다</div>`,
  `<div class="row">📑 책갈피 — 보관된 프레임이 멈춘 줄. 멈춘 줄이 곧 그 연결의 상태다</div>`,
  `<div class="row"><code>Task(x).step</code> — 준비큐에 들어가는 건 코루틴이 아니라 이 콜백(바운드 메서드)</div>`,
  `<div class="row">노란 테두리 플래시 — 직전 스텝과 달라진 코루틴 카드</div>`,
  `<div class="row">콜 스택 <b style="color:#2f8f4e">↑ 얹힘</b> = 방금 재개된 프레임 · ` +
  `<b style="color:#b3543a">↓ 내려놓음/소멸</b> = 방금 내려간 프레임(점선 유령으로 한 스텝 남는다)</div>`,
  `<div class="row">점선 프레임 — 엔진(channel.py) 내부라 소스 패널에 줄 표시가 없는 프레임</div>`,
].join("");

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
