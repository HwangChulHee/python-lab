"""
eventloop.py — 미니 이벤트 루프 (커리큘럼 24/25장) · P5 별도 계기판 ②

P3의 통찰을 그대로 잇는다: '이벤트 루프 = 보관된 프레임들을 번갈아 재개하는
스케줄러'. 태스크는 파이썬 제너레이터다(= 보관됐다 재개되는 프레임 그 자체 —
gi_frame으로 멈춘 줄까지 들여다본다). 스케줄러가 그 프레임들을 가상 시계에 맞춰
번갈아 깨운다. asyncio API를 흉내내지 않는다 — 원리만 드러낸다.

프로토콜 (태스크가 제어를 반납하는 방법):
  yield ("sleep", n)  — n 가상시간 뒤에 깨워 달라며 프레임을 보관(양보).
  yield ("work", k)   — 지금 k 가상시간만큼 '계산으로 점유'(양보 없음). 협조형
                        스케줄러에선 이 동안 다른 태스크가 한 발도 못 나간다 —
                        25장 '블로킹의 참사'의 정체.

설계 판단: P3의 MiniGenerator를 직접 태우지 않고 '네이티브 제너레이터'를 태스크로
쓴다. 네이티브 제너레이터도 '보관된 프레임'(gi_frame)이므로 증명하려는 원리는
그대로다. 반면 MiniGenerator를 이벤트 루프에 물리려면 스케줄러가 값을 돌려받는
경로(프레임이 아니라 스케줄러가 resumer)를 엔진에 새로 뚫어야 해서, P5의 재량 범위
안에서 더 단순하고 결정적인 네이티브 경로를 택했다. (REPORT.md 참조)
"""

import heapq
import json
from collections import deque
from pathlib import Path


class _Task:
    def __init__(self, name, gen):
        self.name = name
        self.gen = gen
        self.state = "READY"       # READY / RUNNING / SLEEPING / DONE
        self.wake = None           # SLEEPING이면 깨어날 가상시간
        self.line = None           # 보관된 프레임이 멈춘 소스 줄 (gi_frame)


def run_scenario(title, subtitle, task_defs):
    """태스크들을 가상 시계로 돌리고 (트레이스 dict, 재개 순서)를 반환."""
    tasks = [_Task(n, g) for n, g in task_defs]
    ready = deque(tasks)
    sleeping = []                  # 힙 (wake, seq, task)
    clock = 0
    seq = 0
    order = []                     # 재개된 태스크 이름 순서 (결정적 — assert 대상)
    steps = []
    segments = []                  # 간트용 [{task, start, end, kind}]

    def snap(action):
        steps.append({
            "clock": clock, "action": action,
            "states": [{"task": t.name, "state": t.state, "wake": t.wake, "line": t.line}
                       for t in tasks],
        })

    snap("시작 — 모든 태스크 READY (가상 시계 0). 스케줄러가 하나씩 재개한다.")
    while ready or sleeping:
        if not ready:                          # 실행할 게 없으면 시계를 다음 깨어남으로
            clock = sleeping[0][0]
            woken = []
            while sleeping and sleeping[0][0] <= clock:
                _, _, t = heapq.heappop(sleeping)
                t.state = "READY"; t.wake = None
                ready.append(t); woken.append(t.name)
            snap(f"⏰ 실행할 태스크 없음 → 가상 시계를 {clock}로 진행. 깨어남: {', '.join(woken)}")

        t = ready.popleft()
        order.append(t.name)
        t.state = "RUNNING"
        try:
            cmd = t.gen.send(None)             # 보관된 프레임을 재개 (첫 재개는 None 프라이밍)
        except StopIteration:
            t.state = "DONE"; t.line = None
            segments.append({"task": t.name, "start": clock, "end": clock, "kind": "done"})
            snap(f"T={clock} · {t.name} 재개 → 본문 종료(DONE). 프레임 소멸")
            continue

        t.line = t.gen.gi_frame.f_lineno if t.gen.gi_frame else None
        kind, amt = cmd
        if kind == "sleep":
            t.state = "SLEEPING"; t.wake = clock + amt
            heapq.heappush(sleeping, (clock + amt, seq, t)); seq += 1
            segments.append({"task": t.name, "start": clock, "end": clock + amt, "kind": "sleep"})
            snap(f"T={clock} · {t.name} 재개 → yield sleep({amt}). 프레임을 보관(SLEEPING), "
                 f"{clock + amt}에 깨우도록 예약")
        elif kind == "work":
            segments.append({"task": t.name, "start": clock, "end": clock + amt, "kind": "work"})
            started = clock
            clock += amt                        # 계산이 시계를 점유 — 그동안 아무도 못 뜀
            t.state = "READY"; ready.append(t)
            snap(f"T={started} · {t.name} 재개 → yield work({amt}). {amt}단위 계산으로 시계를 "
                 f"{clock}까지 밀어붙임 — 이 동안 다른 태스크는 한 발도 못 나간다(굶음)")

    snap(f"모두 DONE — 이벤트 루프 종료 (가상 시계 {clock})")
    end = max((s["end"] for s in segments), default=0)
    return ({"title": title, "subtitle": subtitle, "tasks": [t.name for t in tasks],
             "segments": segments, "end": end or 1, "steps": steps, "order": order}, order)


# ================================================================ 시나리오
def _ping(times, interval):
    """interval마다 한 번씩 깨어나는 협조적 태스크(순수 sleeper)."""
    for _ in range(times):
        yield ("sleep", interval)


def _greedy():
    """양보 없이 오래 계산하는 태스크 — 다른 태스크를 굶긴다."""
    yield ("work", 20)


def _beeper(times):
    for _ in range(times):
        yield ("sleep", 4)


def scenario_cooperative():
    return run_scenario(
        "① 협조적 3태스크 — 프레임들이 번갈아 보관·재개된다",
        "세 태스크가 서로 다른 주기로 sleep. 스케줄러가 가상 시계를 진행하며 깨어난 프레임을 재개한다.",
        [("A", _ping(3, 10)), ("B", _ping(2, 15)), ("C", _ping(1, 25))])


def scenario_blocking():
    return run_scenario(
        "② 블로킹의 참사 — 한 태스크가 양보 안 하면 나머지가 굶는다",
        "G가 work(20)으로 시계를 20까지 점유하는 동안 B는 한 번도 실행되지 못한다.",
        [("G", _greedy()), ("B", _beeper(3))])


SCENARIOS = [scenario_cooperative, scenario_blocking]

# 협조적 시나리오의 재개 순서는 결정적이다 — 손으로 계산한 값과 대조한다.
COOP_EXPECTED_ORDER = ["A", "B", "C", "A", "B", "A", "C", "B", "A"]


# ================================================================ HTML (간트 타임라인)
_HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>pvmlab — 미니 이벤트 루프</title>
<style>
  :root { --bg:#faf9f5; --card:#ffffff; --line:#e3e1d9; --txt:#26251f;
          --mut:#8b897f; --sub:#5f5e56; --acc:#2f6fce; --accbg:#e9f1fc;
          --sleep:#cfe3f7; --work:#e0876f; --run:#2f8f4e; --done:#c8c6bd; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--txt); padding:26px 20px 60px;
         font:15px/1.6 system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }
  .wrap { max-width:1000px; margin:0 auto; }
  h1 { font-size:19px; font-weight:600; margin-bottom:4px; }
  .sub { font-size:14px; color:var(--sub); margin-bottom:14px; }
  select { font:inherit; padding:6px 10px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); margin-bottom:14px; }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:14px; margin-bottom:14px; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:11px; }
  .gantt { position:relative; }
  .grow { display:grid; grid-template-columns:44px 1fr; gap:8px; align-items:center;
          margin-bottom:7px; }
  .gname { font:600 13px ui-monospace,Consolas,monospace; text-align:right; color:var(--sub); }
  .track { position:relative; height:22px; background:var(--bg); border:1px solid var(--line);
           border-radius:5px; overflow:hidden; }
  .seg { position:absolute; top:0; height:100%; border-radius:4px; font:10.5px ui-monospace,monospace;
         color:#3a3a34; display:flex; align-items:center; justify-content:center; overflow:hidden; }
  .seg.sleep { background:var(--sleep); }
  .seg.work { background:var(--work); color:#fff; }
  .seg.done { background:var(--done); width:3px!important; }
  .playhead { position:absolute; top:0; bottom:0; width:2px; background:var(--acc); z-index:5; }
  .axis { position:relative; height:16px; margin-left:52px; margin-top:2px; color:var(--mut);
          font:10.5px ui-monospace,monospace; }
  .tick { position:absolute; transform:translateX(-50%); }
  .states { display:flex; gap:8px; flex-wrap:wrap; }
  .st { border:1px solid var(--line); border-radius:8px; padding:6px 10px; font:12.5px ui-monospace,monospace; }
  .st .nm { font-weight:600; }
  .st.RUNNING { border-color:var(--run); background:#e9f6ee; }
  .st.SLEEPING { border-color:#9cc2ea; background:var(--accbg); }
  .st.READY { background:var(--card); }
  .st.DONE { opacity:.5; }
  .badge { font-size:10.5px; margin-left:5px; }
  .desc { padding:12px 15px; border:1px solid #bcd3f0; background:var(--accbg);
          border-radius:10px; color:#1c4d94; min-height:52px; margin-top:12px; }
  .nav { display:flex; align-items:center; gap:12px; margin-top:14px; }
  button { font:inherit; padding:8px 18px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  input[type=range] { flex:1; }
  .pos { font-size:13px; color:var(--mut); min-width:64px; text-align:right; }
  .legend { font-size:12px; color:var(--mut); margin-top:8px; }
  .sw { display:inline-block; width:11px; height:11px; border-radius:3px; vertical-align:-1px; margin:0 3px 0 10px; }
</style></head><body><div class="wrap">
<h1>pvmlab — 미니 이벤트 루프</h1>
<div class="sub">이벤트 루프 = 보관된 프레임(제너레이터)들을 가상 시계에 맞춰 번갈아 재개하는 스케줄러.</div>
<select id="sc"></select>
<div class="panel">
  <h2 id="gtitle">타임라인 (가로 = 가상 시간, 파란 선 = 현재 시계)</h2>
  <div class="gantt" id="gantt"></div>
  <div class="axis" id="axis"></div>
  <div class="legend"><span class="sw" style="background:var(--sleep)"></span>sleep(대기)<span class="sw" style="background:var(--work)"></span>work(계산 점유)<span class="sw" style="background:var(--done)"></span>done</div>
</div>
<div class="panel"><h2>태스크 상태 (현재 스텝)</h2><div class="states" id="states"></div></div>
<div class="desc" id="desc"></div>
<div class="nav">
  <button id="prev">← 이전</button><button id="next">다음 →</button>
  <input type="range" id="slider" min="0" value="0"><span class="pos" id="pos"></span>
</div>
</div>
<script>
const DATA = __DATA__;
let d = 0, i = 0;
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const sel = $("sc");
DATA.forEach((t, n) => sel.add(new Option(t.title, n)));
sel.onchange = () => { d = +sel.value; i = 0; render(); };

function render() {
  const t = DATA[d], s = t.steps[i], end = t.end;
  $("slider").max = t.steps.length - 1; $("slider").value = i;
  const pct = v => (v / end * 100);
  // 간트
  $("gantt").innerHTML = t.tasks.map(name => {
    const segs = t.segments.filter(g => g.task === name).map(g => {
      const w = Math.max(g.kind==="done"?0:1.2, pct(g.end - g.start));
      const label = g.kind==="sleep" ? "sleep" : (g.kind==="work" ? "work "+(g.end-g.start) : "");
      return `<div class="seg ${g.kind}" style="left:${pct(g.start)}%;width:${w}%">${label}</div>`;
    }).join("");
    return `<div class="grow"><div class="gname">${esc(name)}</div>
      <div class="track">${segs}</div></div>`;
  }).join("") + `<div class="playhead"></div>`;   // 위치는 아래 positionPlayhead가 픽셀로 설정
  // 축
  const ticks = [];
  const stepv = Math.max(1, Math.round(end/8));
  for (let v=0; v<=end; v+=stepv) ticks.push(`<span class="tick" style="left:${pct(v)}%">${v}</span>`);
  $("axis").innerHTML = ticks.join("");
  // 상태
  $("states").innerHTML = s.states.map(st => {
    let extra = "";
    if (st.state === "SLEEPING") extra = `<span class="badge">→ ${st.wake}에 깨어남</span>`;
    else if (st.state === "RUNNING" && st.line) extra = `<span class="badge">줄 ${st.line}에서</span>`;
    return `<div class="st ${st.state}"><span class="nm">${esc(st.task)}</span> <span class="badge">${st.state}</span>${extra}</div>`;
  }).join("");
  $("gtitle").textContent = `타임라인 · ${t.subtitle}  (현재 시계 T=${s.clock})`;
  $("desc").textContent = s.action;
  $("pos").textContent = i + " / " + (t.steps.length - 1);
  $("prev").disabled = i===0; $("next").disabled = i===t.steps.length-1;
  // 재생 헤드 위치 보정 (트랙 시작 오프셋 52px 안에서)
  positionPlayhead(pct(s.clock));
}
function positionPlayhead(p) {
  const ph = document.querySelector(".playhead");
  if (!ph) return;
  const gantt = $("gantt");
  const track = gantt.querySelector(".track");
  if (!track) return;
  const gRect = gantt.getBoundingClientRect(), tRect = track.getBoundingClientRect();
  const x = (tRect.left - gRect.left) + tRect.width * p / 100;
  ph.style.left = x + "px";
}
$("next").onclick = () => { if (i<DATA[d].steps.length-1){i++;render();} };
$("prev").onclick = () => { if (i>0){i--;render();} };
$("slider").oninput = e => { i=+e.target.value; render(); };
document.onkeydown = e => { if(e.key==="ArrowRight")$("next").click(); if(e.key==="ArrowLeft")$("prev").click(); };
window.addEventListener("resize", () => render());
render();
</script></body></html>
"""


def build(out_path):
    traces = []
    coop_order = None
    for fn in SCENARIOS:
        trace, order = fn()
        traces.append(trace)
        if trace["title"].startswith("①"):
            coop_order = order

    # 결정적 실행 순서 검증 (손으로 계산한 값과 대조)
    assert coop_order == COOP_EXPECTED_ORDER, \
        f"이벤트 루프 재개 순서가 예상과 다릅니다: {coop_order} != {COOP_EXPECTED_ORDER}"

    data = json.dumps(traces, ensure_ascii=False).replace("</", "<\\/")
    Path(out_path).write_text(_HTML.replace("__DATA__", data), encoding="utf-8")
    for t in traces:
        print(t["title"])
        print(f"   재개 순서: {' → '.join(t['order'])}  (총 {t['end']} 가상시간)")
    print(f"   협조 시나리오 순서 검증 OK: {coop_order}")
    print(f"\n생성 완료 → {out_path}  (시나리오 {len(traces)}개)")
    return traces
