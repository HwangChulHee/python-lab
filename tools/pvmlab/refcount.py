"""
refcount.py — 참조 카운트 추적기 (커리큘럼 20장) · P5 별도 계기판 ①

스테퍼(바이트코드 관찰)와 다른 계기판이다. 짧은 시나리오를 '문장 단위'로 실행하며
관심 객체들의 sys.getrefcount 변화를 기록하고, 왜 변했는지(별칭 +1, 함수 인자 +1,
del -1, 컨테이너 삽입/제거 등)를 한국어로 붙여 단일 HTML로 낸다.

시나리오:
  ① 별칭과 del      — 이름/컨테이너가 참조를 늘리고 줄이는 기본
  ② 컨테이너·함수 인자 — 리스트에 넣기, 함수 호출 동안의 일시적 +1
  ③ 순환 참조와 GC  — refcount가 0이 안 되는데 gc.collect()가 수거하는 것
                       (참조 카운팅과 세대별 GC의 분업)

★ getrefcount 왜곡 보정: sys.getrefcount(obj)는 obj를 '인자로' 받는 순간 임시 참조를
  하나 더 만들어, 실제보다 항상 1(또는 로컬 바인딩까지 2) 크게 나온다. 아래 측정은
  그 보정을 뺀 값을 보여 준다 — 이 사실을 뷰어 상단에도 명시한다.
"""

import gc
import json
import sys
import weakref
from pathlib import Path


# ================================================================ 측정 헬퍼
def _rc_named(getter):
    """이름/컨테이너에 있는 객체의 참조 수. getrefcount의 인자 임시 참조(+1)만 보정."""
    try:
        return sys.getrefcount(getter()) - 1      # getter() 결과를 로컬에 묶지 않고 바로 측정
    except (KeyError, IndexError):
        return None                                # 더 이상 어디에도 없음 → 소멸


def _rc_weak(wref):
    """약참조로만 들고 있는 객체의 참조 수. obj 로컬(+1)과 인자(+1) 둘 다 보정."""
    obj = wref()
    if obj is None:
        return None                                # 수거됨
    return sys.getrefcount(obj) - 2


# ================================================================ 시나리오 빌더
class _Scenario:
    def __init__(self, title, note):
        self.title = title
        self.note = note
        self.watch = []       # (label, measure_fn)
        self.steps = []       # {src, explain, objects:[{label, rc, delta}]}
        self._prev = {}

    def track(self, label, measure_fn):
        self.watch.append((label, measure_fn))

    def snap(self, src, explain):
        objs = []
        for label, measure in self.watch:
            rc = measure()
            prev = self._prev.get(label)
            delta = (rc - prev) if (rc is not None and prev is not None) else None
            self._prev[label] = rc
            objs.append({"label": label, "rc": rc, "delta": delta})
        self.steps.append({"src": src, "explain": explain, "objects": objs})

    def to_dict(self):
        maxrc = max((o["rc"] or 0) for s in self.steps for o in s["objects"]) or 1
        return {"title": self.title, "note": self.note, "steps": self.steps,
                "lines": [s["src"] for s in self.steps], "maxrc": maxrc}


# ---------------------------------------------------------------- ① 별칭과 del
def scenario_aliasing():
    sc = _Scenario("① 별칭과 del — 이름·컨테이너가 참조를 늘리고 줄인다",
                   "표시값은 sys.getrefcount에서 인자 임시 참조(+1)를 뺀 '실제 참조 수'입니다.")
    env = {}
    sc.track("리스트 [10, 20]", lambda: _rc_named(lambda: env["a"]))

    env["a"] = [10, 20]
    sc.snap("a = [10, 20]", "새 리스트 객체 생성 — 이름 a 하나가 가리킴 (참조 1)")
    env["b"] = env["a"]
    sc.snap("b = a", "복사가 아니라 별칭 — b도 같은 객체를 가리킴 (참조 +1)")
    env["box"] = [env["a"]]
    sc.snap("box = [a]", "컨테이너(리스트)에 담김 — box[0]가 또 가리킴 (참조 +1)")
    del env["b"]
    sc.snap("del b", "이름 b 제거 — 그 참조 사라짐 (참조 -1)")
    env["box"].clear()
    sc.snap("box.clear()", "컨테이너에서 빠짐 — box[0] 참조 사라짐 (참조 -1)")
    del env["a"]
    sc.snap("del a", "마지막 이름 제거 — 참조 0 → 즉시 소멸 (참조 카운팅이 바로 회수)")
    return sc.to_dict()


# ---------------------------------------------------------------- ② 컨테이너·함수 인자
def scenario_container():
    sc = _Scenario("② 컨테이너·함수 인자 — 삽입은 유지, 호출은 일시적 +1",
                   "함수 호출 '동안'에만 매개변수가 참조를 하나 더 잡는다(끝나면 되돌아옴).")
    env = {}

    def _get():                                # 객체를 이름 a → 컨테이너 lst 순으로 찾는다
        if "a" in env:
            return env["a"]
        if env.get("lst"):
            return env["lst"][0]
        raise KeyError                         # 어디에도 없음 → 소멸

    sc.track("리스트 [1]", lambda: _rc_named(_get))

    env["a"] = [1]
    sc.snap("a = [1]", "새 리스트 — 이름 a (참조 1)")
    env["lst"] = []
    env["lst"].append(env["a"])
    sc.snap("lst.append(a)", "리스트에 삽입 — lst[0]가 가리킴 (참조 +1)")
    env["lst"].append(env["a"])
    sc.snap("lst.append(a)", "또 삽입 — 같은 객체가 lst에 두 번 (참조 +1)")

    def _probe(x):                                 # 함수 호출 동안 매개변수 x가 참조를 하나 더 잡음
        sc.snap("f(a) 실행 중", "매개변수 x가 같은 객체를 가리킴 → 호출 동안 참조 +1 (일시적)")
    _probe(env["a"])
    sc.snap("f 반환 후", "함수가 끝나 매개변수 x 소멸 → 참조 -1 (원래대로)")

    env["lst"].pop()
    sc.snap("lst.pop()", "컨테이너에서 하나 제거 (참조 -1)")
    del env["a"]
    sc.snap("del a", "이름 a 제거 — 아직 lst에 한 번 남음 (참조 -1, 0 아님)")
    env["lst"].clear()
    sc.snap("lst.clear()", "마지막 참조 제거 — 참조 0 → 소멸")
    return sc.to_dict()


# ---------------------------------------------------------------- ③ 순환 참조와 GC
class _Node:
    """순환을 만들 객체. 약참조가 가능해야 해서 dict 대신 클래스를 쓴다."""
    def __init__(self, name):
        self.name = name
        self.ref = None


def scenario_cycle():
    sc = _Scenario("③ 순환 참조와 GC — refcount는 0이 안 되는데 gc.collect()가 수거",
                   "참조 카운팅은 서로 물린 순환을 못 푼다 — 세대별 GC가 그 뒤를 맡는다.")
    gc.disable()                                   # 자동 GC를 꺼 결정적으로 관찰
    try:
        env = {}
        env["x"] = _Node("x")
        env["y"] = _Node("y")
        wx = weakref.ref(env["x"])
        wy = weakref.ref(env["y"])
        sc.track("객체 x", lambda: _rc_weak(wx))
        sc.track("객체 y", lambda: _rc_weak(wy))

        sc.snap("x = Node(); y = Node()", "두 객체 생성 — 각각 이름 하나가 가리킴 (참조 1)")
        env["x"].ref = env["y"]
        sc.snap("x.ref = y", "x가 y를 가리킴 — y의 참조 +1 (이제 이름 y + x.ref)")
        env["y"].ref = env["x"]
        sc.snap("y.ref = x", "y가 x를 가리킴 — 순환 완성 (x도 참조 +1)")
        del env["x"]
        sc.snap("del x", "이름 x 제거 — 하지만 y.ref가 여전히 x를 가리킴 → 참조 0 아님, 살아있음")
        del env["y"]
        sc.snap("del y", "이름 y 제거 — 그래도 x.ref↔y.ref가 서로 물려 둘 다 참조 1, 소멸 안 됨!")
        gc.collect()
        sc.snap("gc.collect()", "세대별 GC가 도달 불가능한 순환을 탐지해 수거 → 이제 소멸 "
                                "(참조 카운팅과 GC의 분업)")
    finally:
        gc.enable()
    return sc.to_dict()


SCENARIOS = [scenario_aliasing, scenario_container, scenario_cycle]


# ================================================================ HTML
_HTML = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>pvmlab — 참조 카운트 추적기</title>
<style>
  :root { --bg:#faf9f5; --card:#ffffff; --line:#e3e1d9; --txt:#26251f;
          --mut:#8b897f; --sub:#5f5e56; --acc:#2f6fce; --accbg:#e9f1fc;
          --warn:#9a6b1a; --warnbg:#faf0da; --up:#2f8f4e; --down:#c0392b; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--txt); padding:26px 20px 60px;
         font:15px/1.6 system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }
  .wrap { max-width:980px; margin:0 auto; }
  h1 { font-size:19px; font-weight:600; margin-bottom:4px; }
  .sub { font-size:14px; color:var(--sub); margin-bottom:14px; }
  select { font:inherit; padding:6px 10px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); margin-bottom:14px; }
  .note { font-size:12.5px; color:var(--warn); background:var(--warnbg);
          border:1px solid #ecd9ae; border-radius:8px; padding:8px 12px; margin-bottom:14px; }
  .cols { display:grid; grid-template-columns:1fr 1.1fr; gap:14px; align-items:start; }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:13px; margin-bottom:14px; }
  .panel h2 { font-size:12px; font-weight:500; color:var(--mut); margin-bottom:9px; }
  .ln { display:flex; gap:12px; padding:2.5px 9px; border-radius:6px;
        font:13px/1.65 ui-monospace,Consolas,monospace; color:var(--sub); white-space:pre; }
  .ln .no { color:var(--mut); min-width:22px; text-align:right; user-select:none; }
  .ln.on { background:var(--warnbg); color:var(--warn); font-weight:600; }
  .obj { margin-bottom:12px; }
  .obj-hd { display:flex; justify-content:space-between; align-items:baseline;
            font:12.5px ui-monospace,Consolas,monospace; margin-bottom:4px; }
  .obj-name { color:var(--txt); font-weight:600; }
  .rc { font-weight:700; }
  .delta { font-size:11.5px; margin-left:6px; }
  .delta.up { color:var(--up); } .delta.down { color:var(--down); }
  .bar-track { height:20px; background:var(--bg); border:1px solid var(--line);
               border-radius:6px; overflow:hidden; }
  .bar { height:100%; background:var(--acc); transition:width .12s;
         display:flex; align-items:center; justify-content:flex-end;
         color:#fff; font:11px ui-monospace,monospace; padding-right:6px; }
  .bar.gone { background:var(--mut); }
  .gone-txt { color:var(--down); font-weight:700; }
  .desc { padding:12px 15px; border:1px solid #bcd3f0; background:var(--accbg);
          border-radius:10px; color:#1c4d94; min-height:56px; }
  .nav { display:flex; align-items:center; gap:12px; margin-top:14px; }
  button { font:inherit; padding:8px 18px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  input[type=range] { flex:1; }
  .pos { font-size:13px; color:var(--mut); min-width:64px; text-align:right; }
</style></head><body><div class="wrap">
<h1>pvmlab — 참조 카운트 추적기</h1>
<div class="sub">문장 하나마다 객체의 참조 수가 어떻게·왜 변하는지 관찰한다. 참조 0이 되면 즉시 소멸, 순환은 GC가 맡는다.</div>
<select id="sc"></select>
<div class="note" id="note"></div>
<div class="cols">
  <div><div class="panel"><h2>시나리오 (현재 문장 노란 강조)</h2><div id="src"></div></div></div>
  <div>
    <div class="panel"><h2>객체별 참조 수 (변화량 강조)</h2><div id="objs"></div></div>
    <div class="desc" id="desc"></div>
  </div>
</div>
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
  const t = DATA[d], s = t.steps[i];
  $("note").textContent = t.note;
  $("slider").max = t.steps.length - 1; $("slider").value = i;
  $("src").innerHTML = t.lines.map((ln, n) =>
    `<div class="ln ${n===i?"on":""}"><span class="no">${n+1}</span><span>${esc(ln)}</span></div>`).join("");
  $("objs").innerHTML = s.objects.map(o => {
    const gone = o.rc === null;
    const w = gone ? 0 : Math.max(6, Math.round(o.rc / t.maxrc * 100));
    let dtag = "";
    if (o.delta !== null && o.delta !== undefined && o.delta !== 0)
      dtag = `<span class="delta ${o.delta>0?"up":"down"}">${o.delta>0?"+":""}${o.delta}</span>`;
    const rctxt = gone ? '<span class="gone-txt">소멸됨 (참조 0)</span>' : `<span class="rc">${o.rc}</span>${dtag}`;
    return `<div class="obj"><div class="obj-hd"><span class="obj-name">${esc(o.label)}</span>${rctxt}</div>
      <div class="bar-track"><div class="bar ${gone?"gone":""}" style="width:${w}%">${gone?"":o.rc}</div></div></div>`;
  }).join("");
  $("desc").textContent = s.explain;
  $("pos").textContent = i + " / " + (t.steps.length - 1);
  $("prev").disabled = i===0; $("next").disabled = i===t.steps.length-1;
}
$("next").onclick = () => { if (i<DATA[d].steps.length-1){i++;render();} };
$("prev").onclick = () => { if (i>0){i--;render();} };
$("slider").oninput = e => { i=+e.target.value; render(); };
document.onkeydown = e => { if(e.key==="ArrowRight")$("next").click(); if(e.key==="ArrowLeft")$("prev").click(); };
render();
</script></body></html>
"""


def build(out_path):
    traces = [fn() for fn in SCENARIOS]
    data = json.dumps(traces, ensure_ascii=False).replace("</", "<\\/")
    Path(out_path).write_text(_HTML.replace("__DATA__", data), encoding="utf-8")
    # 터미널 요약
    for t in traces:
        print(t["title"])
        last = t["steps"][-1]
        print("   마지막 상태:",
              ", ".join(f"{o['label']}={'소멸' if o['rc'] is None else o['rc']}" for o in last["objects"]))
    print(f"\n생성 완료 → {out_path}  (시나리오 {len(traces)}개)")
    return traces
