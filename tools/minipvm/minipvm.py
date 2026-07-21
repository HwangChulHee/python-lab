"""
minipvm — CPython 실행 모델을 눈으로 보는 미니 PVM (확장 가능 버전)

바이트코드는 진짜(CPython 컴파일러가 만든 것)를 쓰고,
실행 엔진(평가 루프, Frame, 프레임 스택)만 파이썬으로 재현한다.
실행하면 모든 스텝을 기록해 HTML 하나를 만든다. 브라우저로 열어
소스 코드 · 바이트코드 · 프레임 스택을 나란히 놓고 한 명령씩 관찰한다.

구조 = 네 층:
  함수 객체  → demos.py에 정의한 파이썬 함수 그대로 (__globals__ 포함)
  코드 객체  → func.__code__ 그대로 (불변, 바이트코드·상수·소스 위치 보관)
  Frame     → 이 파일에서 구현 (지역 변수 + 값 스택 + 명령 포인터)
  평가 루프  → 이 파일에서 구현 (run()의 while 루프)

확장 방법:
  1) 새 opcode 지원  → 아래 @opcode(...) 핸들러 하나 추가
  2) 새 관찰 대상    → demos.py에 @demo(...) 함수 추가
  CALL / RETURN_* 만은 레지스트리가 아니라 run() 본체에 있다.
  프레임을 만들고 부수는 명령은 개별 연산이 아니라 기계 구조이기 때문.

실행:
  python minipvm.py              # demos.py의 데모 전부 실행 → pvm_trace.html
  python minipvm.py -o out.html
"""

import builtins
import dis
import inspect
import json
import textwrap
import argparse
from pathlib import Path

# ================================================================ Frame

class Frame:
    """호출 1번 = Frame 1개. 지역 변수 + 값 스택 + 명령 포인터를 담는 작업 공간."""

    def __init__(self, func, args):
        code = func.__code__
        self.code = code                      # 코드 객체 (읽기 전용 참조)
        self.func_name = func.__name__
        self.globals = func.__globals__       # LOAD_GLOBAL이 뒤질 곳 — 함수 객체에 붙어 있다
        arg_names = code.co_varnames[: code.co_argcount]
        self.local_vars = dict(zip(arg_names, args))
        self.value_stack = []
        self.instructions = list(dis.get_instructions(code))
        self.offset_to_index = {ins.offset: i for i, ins in enumerate(self.instructions)}
        self.ip = 0                           # 명령 포인터 (instructions 인덱스)
        self.listing_key = f"{func.__name__}.__code__"


def fmt(v):
    """값 스택/지역 변수의 값을 짧은 문자열로."""
    if callable(v) and hasattr(v, "__name__"):
        return f"{v.__name__} 함수객체"
    if v is None:
        return "NULL"
    r = repr(v)
    return r if len(r) <= 40 else r[:37] + "..."

# ================================================================ opcode 레지스트리
#
# 새 opcode 지원 = 여기에 핸들러 하나 추가.
# 핸들러는 (pvm, frame, ins)를 받아 스택/변수를 조작하고 설명 문자열을 반환.
# doc은 HTML에서 그 명령을 클릭했을 때 보여줄 일반 설명.

OPCODE_HANDLERS = {}
OPCODE_DOCS = {}

def opcode(name, doc):
    def deco(fn):
        OPCODE_HANDLERS[name] = fn
        OPCODE_DOCS[name] = doc
        return fn
    return deco

# ---- 프레임 관리 표식 -------------------------------------------------

@opcode("RESUME", "3.11+에서 프레임 실행 시작/재개 지점을 표시하는 명령. "
                  "인터럽트 체크 정도만 하고 스택에는 아무 일도 안 한다. 스택효과 0")
def _resume(pvm, frame, ins):
    return None                               # 기록 생략 (노이즈)

# ---- 값 올리기 (push) ------------------------------------------------

@opcode("LOAD_CONST", "코드 객체의 상수 목록 co_consts에서 값을 꺼내 스택에 push. "
                      "상수는 컴파일 시점에 이미 코드 객체 안에 저장돼 있다. 스택효과 +1")
def _load_const(pvm, frame, ins):
    frame.value_stack.append(ins.argval)
    return f"상수 {ins.argval!r}를 push (코드 객체에 저장돼 있던 값)"

@opcode("LOAD_FAST", "지역 변수 배열에서 값을 꺼내 스택에 push. 이름을 문자열로 찾는 게 아니라 "
                     "배열 인덱스로 바로 접근해서 'FAST'. 스택효과 +1")
def _load_fast(pvm, frame, ins):
    frame.value_stack.append(frame.local_vars[ins.argval])
    return f"지역 변수 {ins.argval}의 값을 push"

@opcode("LOAD_GLOBAL", "함수 객체에 붙은 __globals__ 딕셔너리에서 이름을 찾아 push. "
                       "없으면 builtins까지 뒤진다. 지역과 달리 문자열 키 조회라 더 느리다. 스택효과 +1")
def _load_global(pvm, frame, ins):
    name = ins.argval
    if name in frame.globals:
        value = frame.globals[name]
    else:
        value = getattr(builtins, name)       # print, len 같은 내장
    frame.value_stack.append(value)
    return f"__globals__에서 '{name}'을 찾아 push — 올라간 건 함수 객체"

@opcode("PUSH_NULL", "3.11+ 호출 규약: CALL이 나중에 참조할 NULL 자리표시자를 push. "
                     "메서드 호출 최적화의 흔적이다. 스택효과 +1")
def _push_null(pvm, frame, ins):
    frame.value_stack.append(None)
    return "호출 규약용 NULL 자리표시자 push"

# ---- 값 내리기 (pop) -------------------------------------------------

@opcode("STORE_FAST", "스택 맨 위를 pop해서 지역 변수 배열에 저장. 스택효과 -1")
def _store_fast(pvm, frame, ins):
    frame.local_vars[ins.argval] = frame.value_stack.pop()
    return f"pop → 지역 변수 {ins.argval}에 저장"

@opcode("POP_TOP", "스택 맨 위를 pop해서 버린다. 반환값을 안 쓰는 표현식문 뒤에 나온다. 스택효과 -1")
def _pop_top(pvm, frame, ins):
    frame.value_stack.pop()
    return "스택 맨 위 버림"

# ---- 연산 ------------------------------------------------------------

@opcode("BINARY_OP", "스택에서 두 값을 pop, 이항 연산 후 결과를 push. 어떤 연산인지는 "
                     "인자로 구분(+, -, *, ...). 실제로는 여기서 __add__ 등 특수 메서드가 불린다. 스택효과 -1")
def _binary_op(pvm, frame, ins):
    b, a = frame.value_stack.pop(), frame.value_stack.pop()
    sym = ins.argrepr.strip()
    ops = {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b,
           "/": lambda: a / b, "//": lambda: a // b, "%": lambda: a % b,
           "**": lambda: a ** b}
    r = ops[sym]()
    frame.value_stack.append(r)
    return f"{a!r}, {b!r} pop → {sym} 연산 → {r!r} push"

@opcode("COMPARE_OP", "스택에서 두 값을 pop, 비교 후 결과(bool)를 push. "
                      "실제로는 __lt__, __eq__ 등이 불린다. 스택효과 -1")
def _compare_op(pvm, frame, ins):
    b, a = frame.value_stack.pop(), frame.value_stack.pop()
    sym = ins.argrepr.strip("() bol")
    comps = {"<": a < b, "<=": a <= b, ">": a > b,
             ">=": a >= b, "==": a == b, "!=": a != b}
    r = comps[sym]
    frame.value_stack.append(r)
    return f"{a!r} {sym} {b!r} → {r} push"

# ---- 점프: 명령 포인터를 직접 옮긴다 ------------------------------------

@opcode("POP_JUMP_IF_FALSE", "스택 맨 위를 pop해서 거짓이면 지정 offset으로 명령 포인터를 옮긴다. "
                             "if문의 정체가 이것. 스택효과 -1")
def _pjif(pvm, frame, ins):
    cond = frame.value_stack.pop()
    if not cond:
        frame.ip = frame.offset_to_index[ins.argval]
        return f"조건 {cond} → offset {ins.argval}로 점프 (명령 포인터 이동)"
    return f"조건 {cond} → 점프 안 함"

@opcode("POP_JUMP_IF_TRUE", "스택 맨 위를 pop해서 참이면 지정 offset으로 점프. 스택효과 -1")
def _pjit(pvm, frame, ins):
    cond = frame.value_stack.pop()
    if cond:
        frame.ip = frame.offset_to_index[ins.argval]
        return f"조건 {cond} → offset {ins.argval}로 점프"
    return f"조건 {cond} → 점프 안 함"

@opcode("JUMP_FORWARD", "무조건 앞쪽 offset으로 점프. 스택효과 0")
def _jf(pvm, frame, ins):
    frame.ip = frame.offset_to_index[ins.argval]
    return f"offset {ins.argval}로 점프"

@opcode("JUMP_BACKWARD", "무조건 뒤쪽 offset으로 점프. 루프가 되감기는 지점이며, "
                         "이때 인터럽트/GIL 양보 체크도 일어난다. 스택효과 0")
def _jb(pvm, frame, ins):
    frame.ip = frame.offset_to_index[ins.argval]
    return f"offset {ins.argval}로 되감기 — 루프의 정체"

# CALL / RETURN_VALUE / RETURN_CONST 문서 (핸들러는 run() 본체에 있음)
OPCODE_DOCS["CALL"] = (
    "스택에서 인자들과 함수 객체를 pop → 함수 객체의 __code__로 새 Frame을 만들어 "
    "프레임 스택에 push → 명령 포인터가 새 코드 객체로 넘어간다. "
    "네 층(함수 객체·코드 객체·프레임·평가 루프)이 전부 맞물리는 명령. 스택효과 -(인자수+2)+1")
OPCODE_DOCS["RETURN_VALUE"] = (
    "스택 맨 위를 반환값으로 들고 현재 프레임을 통째로 소멸시킨다. "
    "반환값은 아래(호출자) 프레임의 값 스택에 올라가고, 호출자는 멈췄던 지점부터 재개.")
OPCODE_DOCS["RETURN_CONST"] = (
    "RETURN_VALUE의 최적화판(3.12+): 상수를 스택에 올렸다 내리는 대신 바로 반환.")

# ================================================================ 미니 PVM

class MiniPVM:
    """평가 루프 + 프레임 스택. CPython ceval의 뼈대만 재현. 매 스텝을 기록한다."""

    def __init__(self):
        self.frame_stack = []                 # 프레임 스택 (리스트 끝이 맨 위)
        self.listings = {}                    # {코드key: 바이트코드 목록}  (HTML용)
        self.sources = {}                     # {코드key: 소스 줄들}       (HTML용)
        self.steps = []                       # 스텝 스냅샷               (HTML용)

    # ---- 진입점: CALL의 정체 ----------------------------------------

    def call_function(self, func, args):
        """함수 객체에서 __code__를 꺼내 Frame을 만들어 쌓는다."""
        frame = Frame(func, args)
        self.capture_code(func, frame)
        self.frame_stack.append(frame)
        arg_str = ", ".join(repr(a) for a in args)
        self.record(f"CALL → {func.__name__}({arg_str}) 프레임 생성, 프레임 스택에 push",
                    None, None)
        return self.run(frame)

    def capture_code(self, func, frame):
        """코드 객체의 바이트코드 목록과 소스를 HTML용으로 저장 (코드 객체당 1번)."""
        key = frame.listing_key
        if key in self.listings:
            return
        self.listings[key] = [
            {"off": i.offset, "op": i.opname, "arg": i.argrepr,
             "line": i.positions.lineno if i.positions else None,
             "doc": OPCODE_DOCS.get(i.opname, "(설명 미등록 opcode)")}
            for i in frame.instructions]
        try:
            src = textwrap.dedent(inspect.getsource(func))
            self.sources[key] = {"first": func.__code__.co_firstlineno,
                                 "lines": src.rstrip().splitlines()}
        except OSError:                        # REPL 등 소스를 못 찾는 경우
            self.sources[key] = {"first": 1, "lines": ["(소스를 찾을 수 없음)"]}

    # ---- 평가 루프 --------------------------------------------------

    def run(self, frame):
        """ceval.c의 _PyEval_EvalFrameDefault에 해당. 명령 하나 꺼내 → 실행 → 반복."""
        while True:
            ins = frame.instructions[frame.ip]
            executed = frame.ip
            op = ins.opname
            frame.ip += 1                     # 기본: 다음 명령 (점프 핸들러가 덮어쓸 수 있음)

            # -- 프레임을 만들고 부수는 명령: 레지스트리가 아니라 기계 본체 --
            if op == "CALL":
                n = ins.arg
                args = [frame.value_stack.pop() for _ in range(n)][::-1]
                target = frame.value_stack.pop()
                if frame.value_stack and frame.value_stack[-1] is None:
                    frame.value_stack.pop()   # PUSH_NULL이 깔아둔 자리표시자 제거
                self.record(f"CALL — 스택에서 함수 객체와 인자 {args} pop. "
                            f"그 함수 객체의 __code__로 새 프레임을 만든다", executed, ins)
                if hasattr(target, "__code__"):
                    result = self.call_function(target, args)   # 우리 루프로 재귀 진입
                else:
                    result = target(*args)                      # 내장 함수는 C에 위임
                frame.value_stack.append(result)
                self.record(f"RETURN ← 반환값 {result!r}이 {frame.func_name} 스택에 "
                            f"올라옴. 멈췄던 지점부터 재개", executed, ins)
                continue

            if op in ("RETURN_VALUE", "RETURN_CONST"):
                value = frame.value_stack.pop() if op == "RETURN_VALUE" else ins.argval
                self.frame_stack.pop()
                self.record(f"{op} — {frame.func_name} 프레임 통째로 소멸, "
                            f"{value!r} 반환", None, ins)
                return value

            # -- 나머지 전부: 레지스트리에서 핸들러를 찾아 실행 --
            handler = OPCODE_HANDLERS.get(op)
            if handler is None:
                raise NotImplementedError(
                    f"미구현 opcode: {op}\n"
                    f"→ minipvm.py에 @opcode(\"{op}\", doc=...) 핸들러를 추가하면 된다. "
                    f"(파이썬 버전에 따라 바이트코드가 다를 수 있음)")
            note = handler(self, frame, ins)
            if note is not None:              # None 반환 = 기록 생략 (RESUME 등)
                self.record(f"{op} — {note}", executed, ins)

    # ---- 스텝 기록 --------------------------------------------------

    def record(self, action, executed_index, ins):
        """현재 프레임 스택 전체를 스냅샷으로 저장."""
        frames = []
        for i, fr in enumerate(self.frame_stack):
            frames.append({
                "name": fr.func_name,
                "key": fr.listing_key,
                "locals": {k: fmt(v) for k, v in fr.local_vars.items()},
                "stack": [fmt(v) for v in fr.value_stack],
                "active": i == len(self.frame_stack) - 1,
            })
        top = self.frame_stack[-1] if self.frame_stack else None
        self.steps.append({
            "action": action,
            "frames": frames,                 # 아래(먼저 쌓인 것) → 위 순서
            "exec": executed_index,           # 하이라이트할 명령 인덱스 (None 가능)
            "key": top.listing_key if top else None,
            "line": (ins.positions.lineno if ins and ins.positions else None),
            "opname": ins.opname if ins else None,
        })

# ================================================================ 데모 등록

DEMOS = []

def demo(title, args=()):
    """demos.py에서 관찰 대상 함수를 등록하는 데코레이터."""
    def deco(fn):
        DEMOS.append((fn, list(args), title))
        return fn
    return deco

# ================================================================ HTML 생성

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>minipvm — CPython 실행 모델</title>
<style>
  :root { --bg:#faf9f5; --card:#ffffff; --line:#e3e1d9; --txt:#26251f;
          --mut:#8b897f; --sub:#5f5e56; --acc:#2f6fce; --accbg:#e9f1fc;
          --warn:#9a6b1a; --warnbg:#faf0da; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--txt); padding:26px 20px 60px;
         font:15px/1.6 system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; }
  .wrap { max-width:1060px; margin:0 auto; }
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
  .fr.wait { opacity:.45; }
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
           border-radius:10px; font-size:13.5px; color:var(--sub); min-height:44px; }
  .opdoc b { color:var(--txt); font-family:ui-monospace,Consolas,monospace; }
  .nav { display:flex; align-items:center; gap:12px; margin-top:14px; }
  button { font:inherit; padding:8px 18px; border:1px solid var(--line);
           border-radius:8px; background:var(--card); cursor:pointer; }
  button:disabled { opacity:.35; cursor:default; }
  input[type=range] { flex:1; }
  .pos { font-size:13px; color:var(--mut); min-width:64px; text-align:right; }
  .hint { font-size:12px; color:var(--mut); margin-top:9px; }
</style></head><body><div class="wrap">
<h1>minipvm — CPython 실행 모델</h1>
<div class="sub">평가 루프가 코드 객체를 읽고, 프레임에 쓴다. 노란 줄 = 지금 실행 중인 소스, 파란 줄 = 지금 실행 중인 바이트코드.</div>
<select id="demo"></select>
<div class="cols">
  <div>
    <div class="panel"><h2 id="srcname"></h2><div id="src"></div></div>
    <div class="panel"><h2 id="cname"></h2><div id="bc"></div></div>
  </div>
  <div>
    <div class="panel"><h2>프레임 스택 · 호출마다 1개</h2><div id="stk"></div></div>
    <div class="desc" id="desc"></div>
    <div class="opdoc" id="opdoc">바이트코드 줄을 클릭하면 그 명령의 설명이 여기 표시됩니다.</div>
  </div>
</div>
<div class="nav">
  <button id="prev">← 이전</button>
  <button id="next">다음 →</button>
  <input type="range" id="slider" min="0" value="0">
  <span class="pos" id="pos"></span>
</div>
<div class="hint">키보드 ← → 로도 이동. 노란 칸이 값 스택(왼쪽이 바닥, 오른쪽이 맨 위).</div>
</div>
<script>
const DATA = __DATA__;
let d = 0, i = 0, pinnedDoc = null;
const $ = id => document.getElementById(id);

const sel = $("demo");
DATA.forEach((t, n) => sel.add(new Option(t.title, n)));
sel.onchange = () => { d = +sel.value; i = 0; pinnedDoc = null; render(); };

function showDoc(op, doc) {
  $("opdoc").innerHTML = "<b>" + op + "</b> — " + doc;
}

function render() {
  const t = DATA[d], s = t.steps[i];
  $("slider").max = t.steps.length - 1;
  $("slider").value = i;
  const key = s.key ?? t.steps[Math.max(0, i-1)].key;

  const src = t.sources[key] ?? {first: 1, lines: []};
  $("srcname").textContent = key.replace(".__code__", "") + " 소스 코드";
  $("src").innerHTML = src.lines.map((ln, n) => {
    const lineno = src.first + n;
    return `<div class="src-row ${s.key === key && lineno === s.line ? "on" : ""}">` +
           `<span class="no">${lineno}</span><span>${(ln.replace(/&/g,"&amp;").replace(/</g,"&lt;")) || " "}</span></div>`;
  }).join("");

  $("cname").textContent = key + " 의 바이트코드 (진짜 CPython 출력)";
  $("bc").innerHTML = (t.listings[key] ?? []).map((r, n) =>
    `<div class="bc-row ${s.key === key && n === s.exec ? "on" : ""}" data-n="${n}">` +
    `<span class="off">${r.off}</span><span>${r.op} ${r.arg}</span></div>`).join("");
  document.querySelectorAll(".bc-row").forEach(el => {
    el.onclick = () => { const r = t.listings[key][+el.dataset.n];
                        pinnedDoc = [r.op, r.doc]; showDoc(r.op, r.doc); };
  });

  $("stk").innerHTML = s.frames.length === 0
    ? '<div style="color:var(--mut);text-align:center;padding:24px 0">비어 있음 — 실행 종료</div>'
    : s.frames.slice().reverse().map(f => `
      <div class="fr ${f.active ? "act" : "wait"}">
        <div class="fr-name">${f.name} 프레임 ${f.active ? "· 실행 중" : "· 대기"}</div>
        <div class="fr-row">지역 변수: ${Object.entries(f.locals).map(([k,v]) => k+" = "+v).join(", ") || "—"}</div>
        <div class="fr-row">값 스택:</div>
        <div class="stack-cells">${f.stack.length
          ? f.stack.map(v => `<span class="cell">${v}</span>`).join("")
          : '<span class="cell empty">비어 있음</span>'}</div>
      </div>`).join("");

  $("desc").textContent = s.action;
  if (pinnedDoc) showDoc(pinnedDoc[0], pinnedDoc[1]);
  else if (s.opname) {
    const r = (t.listings[s.key] ?? []).find(x => x.op === s.opname);
    if (r) showDoc(s.opname, r.doc);
  }
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
    data = json.dumps(traces, ensure_ascii=False).replace("</", "<\\/")
    Path(out_path).write_text(HTML_TEMPLATE.replace("__DATA__", data), encoding="utf-8")

# ================================================================ main

def main():
    import demos                              # noqa: F401 — @demo 등록이 일어나는 곳
    # 주의: python minipvm.py로 실행하면 이 파일은 __main__으로 로드되고,
    # demos.py의 `from minipvm import demo`는 같은 파일을 minipvm이라는
    # 별개 모듈로 한 번 더 로드한다 (이중 임포트 — 31장 모듈과 임포트).
    # 데모는 그쪽 DEMOS에 등록되므로 그 모듈의 리스트를 읽어야 한다.
    import minipvm as engine
    demo_list = engine.DEMOS or DEMOS

    parser = argparse.ArgumentParser(description="CPython 실행 모델 미니 재현")
    parser.add_argument("-o", "--out", default="pvm_trace.html", help="출력 HTML 경로")
    args = parser.parse_args()

    traces = []
    for func, fargs, title in demo_list:
        pvm = MiniPVM()
        result = pvm.call_function(func, fargs)
        expected = func(*fargs)               # 진짜 파이썬으로 같은 걸 실행해 대조
        status = "OK" if result == expected else "MISMATCH!"
        print(f"{title}")
        print(f"  미니 PVM: {result!r}  |  진짜 CPython: {expected!r}  → 검증 {status}")
        assert result == expected, "미니 PVM이 CPython과 다른 결과를 냈습니다"
        traces.append({"title": title, "steps": pvm.steps,
                       "listings": pvm.listings, "sources": pvm.sources})

    build_html(traces, args.out)
    print(f"\n생성 완료 → {args.out}  (브라우저로 열기)")

if __name__ == "__main__":
    main()