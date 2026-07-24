"""
realtrace.py — 진짜 asyncio를 실제로 돌리고, 후킹으로 '관찰만' 한다

여기서 도는 것은 전부 진짜다:
  · 관찰 대상 코드 = demos/weblab의 3파일 그대로 (mini_server / mini_framework /
    verify의 app·hello·echo). 한 글자도 고치지 않았다.
  · 진짜 asyncio.SelectorEventLoop (CPython asyncio 코드 그대로)
  · 진짜 asyncio.Task — 순수 파이썬 구현(_PyTask)을 써서 C 가속판과 동작은
    동일하되 Task.__step이 파이썬 프레임이라 콜 스택에 '보인다'
  · 진짜 소켓 (127.0.0.1 — asyncio.start_server / open_connection)

후킹은 세 군데뿐, 전부 관찰용이다:
  1. task factory   — Task 생성을 가로채 라벨 부여 + __step 앞뒤 스냅샷
  2. selector 프록시 — loop._selector.select()를 감싸 SELECT(잠듦)/WAKE 포착.
                      timeout=0인 논블로킹 폴링은 기록하지 않는다(진짜 잠만 기록)
  3. driver 코루틴   — verify.py check()의 2-클라이언트 확장판. 진짜 소켓으로
                      각본을 수행하며 사건을 기록한다

그래서 이 트레이스의 콜 스택에는 Handle._run → BaseEventLoop._run_once →
run_forever 같은 '진짜 asyncio 프레임'이 실제 파일:줄번호와 함께 찍힌다.
주의: 진짜 OS(fd·포트·시간)를 쓰므로 트레이스 세부는 실행마다 다를 수 있다.
"""

import asyncio
import re
import socket
import sys
from asyncio import tasks as _tasks
from pathlib import Path

_LOCALS_PICK = ("method", "path", "body", "scope")

# 관찰 후킹 프레임은 콜 스택에서 원래 이름으로 표시한다
_RENAME = {"TracingTask._Task__step": "Task.__step",
           "TracingSelector.select": "selector.select"}


def _scrub(s):
    return re.sub(r" at 0x[0-9a-fA-F]+", "", str(s))


def _short(v, limit=46):
    r = _scrub(repr(v))
    return r if len(r) <= limit else r[: limit - 3] + "..."


class TracingTask(_tasks._PyTask):
    """진짜 Task 그대로 — __step 앞뒤에 스냅샷만 끼운다."""

    def _Task__step(self, exc=None):           # _PyTask의 사설 메서드를 감싼다
        tr = getattr(self, "_rt", None)
        if tr is None:
            return super()._Task__step(exc)
        tr.resume(self)
        try:
            return super()._Task__step(exc)
        finally:
            tr.after_step(self)


class TracingSelector:
    """loop._selector 프록시 — 진짜 epoll 대기(select)만 가로채 기록한다."""

    def __init__(self, wrapped, tracer):
        self._w = wrapped
        self._t = tracer

    def select(self, timeout=None):
        if timeout == 0:                        # 준비 콜백이 있을 때의 논블로킹 폴링
            return self._w.select(timeout)
        self._t.select_snap()
        events = self._w.select(timeout)
        self._t.wake_snap(events)
        return events

    def __getattr__(self, name):                # register/unregister/get_map 등 위임
        return getattr(self._w, name)


class RealTracer:
    def __init__(self, src_paths):
        self.src_paths = list(src_paths)        # 관찰 대상 3파일의 절대 경로
        self.loop = None
        self.steps = []
        self.tasks = []
        self.phase = "RUN"
        self.current = None
        self.clock = 0                          # = 완료된 각본 행동 수 (T)
        self.script_done = 0
        self.func_cards = []
        self._nclients = 0

    # ---------------- 소스 위치 헬퍼 ----------------
    def _fidx(self, filename):
        return self.src_paths.index(filename) if filename in self.src_paths else -1

    def _floc(self, fidx, line):
        return f"{Path(self.src_paths[fidx]).stem}:{line}"

    def _chain(self, coro):
        """cr_await 사슬 (진짜 코루틴 속성 관찰)."""
        frames, obj = [], coro
        while obj is not None and hasattr(obj, "cr_frame"):
            code, fr = obj.cr_code, obj.cr_frame
            frames.append({"name": code.co_qualname, "code": code,
                           "line": fr.f_lineno if fr else None,
                           "f": self._fidx(code.co_filename)})
            obj = obj.cr_await
        return frames

    def _mark(self, coro):
        """관찰 대상 파일 안의 가장 깊은 프레임 위치 → (파일 idx, 줄) 또는 None."""
        best = None
        for fr in self._chain(coro):
            if fr["f"] >= 0 and fr["line"]:
                best = (fr["f"], fr["line"])
        return best

    # ---------------- 라벨/표기 ----------------
    def label_for(self, coro):
        q = coro.cr_code.co_qualname
        if q == "handle_connection":
            self._nclients += 1
            return f"client_{chr(ord('A') + self._nclients - 1)}"
        return q.rsplit(".", 1)[-1]             # serve / check / …

    def _cb_label(self, cb):
        owner = getattr(cb, "__self__", None)
        if isinstance(owner, TracingTask):
            return f"Task({owner._label}).{cb.__name__.replace('_Task__', '__')}"
        return _scrub(getattr(cb, "__qualname__", repr(cb)))

    def _handle_label(self, handle):
        return self._cb_label(getattr(handle, "_callback", handle))

    # ---------------- 진짜 콜 스택 걷기 ----------------
    def _real_stack(self, skip, chain_codes):
        """지금 이 순간의 진짜 파이썬 프레임들(아래→위). asyncio 내부 프레임이
        파일:줄 그대로 잡힌다 — 이 모드의 존재 이유. 코루틴 프레임(chain으로
        따로 그리는 것)은 중복 방지를 위해 건너뛴다."""
        rows = []
        f = sys._getframe(skip)
        while f is not None and len(rows) < 14:
            code = f.f_code
            if code not in chain_codes:
                name = _RENAME.get(code.co_qualname, code.co_qualname)
                kind = "loop" if code.co_qualname in (
                    "BaseEventLoop.run_forever", "BaseEventLoop.run_until_complete") else "base"
                note = f"{Path(code.co_filename).name}:{f.f_lineno}"
                if code.co_qualname == "BaseEventLoop.run_forever":
                    note += " — 진짜 루프의 while (_run_once 반복)"
                if name in _RENAME.values():
                    note += " (관찰 후킹)"
                rows.append({"name": name, "kind": kind, "line": None, "note": note})
            f = f.f_back
        rows.reverse()                           # 바닥(모듈)부터
        return rows

    # ---------------- 스냅샷 ----------------
    def _snap(self, kind, narration, concept="", look=(), notified=(), hi=None, skip=3):
        loop = self.loop
        cur_chain = self._chain(self.current.get_coro()) if self.current else []
        stack = self._real_stack(skip, {fr["code"] for fr in cur_chain})
        for fr in cur_chain:
            stack.append({"name": fr["name"], "kind": "coro",
                          "floc": self._floc(fr["f"], fr["line"]) if fr["f"] >= 0 and fr["line"] else None,
                          "infra": fr["f"] < 0, "label": self.current._label})

        # 힙 카드: 관찰 대상 파일의 코루틴 태스크만 (serve, client_A/B)
        coros, codes = [], {}
        for t in self.tasks:
            coro = t.get_coro()
            code = coro.cr_code
            if self._fidx(code.co_filename) < 0:
                continue
            codes.setdefault(code.co_qualname, {
                "qualname": code.co_qualname, "firstlineno": code.co_firstlineno,
                "argcount": code.co_argcount, "shared": []})
            codes[code.co_qualname]["shared"].append(t._label)
            if t.done():
                state, loc, picked = "DONE", None, []
            else:
                state = "RUNNING" if t is self.current else (
                    "SUSPENDED" if coro.cr_suspended or coro.cr_running else "CREATED")
                mark = self._mark(coro)
                loc = self._floc(*mark) if mark else None
                fr = coro.cr_frame
                lo = fr.f_locals if fr is not None else {}
                picked = [[k, _short(lo[k])] for k in _LOCALS_PICK if k in lo][:3]
                waiter = getattr(t, "_fut_waiter", None)
                if waiter is not None and t is not self.current:
                    picked.append(["_fut_waiter", _short(waiter, 56)])
            coros.append({"label": t._label, "code": code.co_qualname,
                          "state": state, "loc": loc, "locals": picked})

        bookmarks = []
        for t in self.tasks:
            if t is self.current or t.done():
                continue
            mark = self._mark(t.get_coro())
            if mark:
                bookmarks.append({"label": t._label, "f": mark[0], "line": mark[1]})

        try:
            keys = sorted(loop._selector.get_map().values(), key=lambda k: k.fd)
            watch = [{"fd": k.fd, "name": "소켓",
                      "cb": " · ".join(self._handle_label(h) for h in k.data
                                       if h is not None) or "등록됨",
                      "notified": k.fd in notified} for k in keys]
        except Exception:
            watch = []

        self.steps.append({
            "kind": kind, "clock": self.clock, "phase": self.phase,
            "narration": narration,
            "detail": {"concept": concept, "look": list(look)},
            "running": self.current._label if self.current else None,
            "stack": stack,
            "heap": {"codes": list(codes.values()), "funcs": self.func_cards, "coros": coros},
            "loop": {"ready": [self._handle_label(h) for h in loop._ready],
                     "watch": watch,
                     "timers": [[round(h.when() - loop.time(), 2), self._handle_label(h)]
                                for h in loop._scheduled]},
            "net": {"consumed": self.script_done},
            "src": {"hi": {"f": hi[0], "line": hi[1]} if hi else None,
                    "bookmarks": bookmarks},
        })

    # ---------------- 후킹 지점들 ----------------
    def task_factory(self, loop, coro, **kwargs):
        task = TracingTask(coro, loop=loop, **kwargs)
        task._label = self.label_for(coro)
        task._rt = self
        self.tasks.append(task)
        fi = self._fidx(coro.cr_code.co_filename)
        hi = (fi, coro.cr_frame.f_lineno) if fi >= 0 and coro.cr_frame else None
        self._snap("created",
                   f"진짜 asyncio.Task 생성 — loop.create_task()가 코루틴 "
                   f"{coro.cr_code.co_qualname}(...)을 Task({task._label})로 감쌌다. "
                   f"Task.__init__이 곧바로 call_soon(self.__step)을 불러 준비큐에 등록했다.",
                   concept=(
                       "async def를 호출한 순간엔 코루틴 객체만 생겼고 본문은 한 줄도 "
                       "돌지 않았다. asyncio.Task(진짜)가 그 코루틴의 운전기사가 된다 — "
                       "Task.__step이라는 콜백이 준비큐(loop._ready)에 Handle로 싸여 "
                       "들어갔고, 루프가 꺼내 부르면 그때 coro.send()가 일어난다. "
                       "handle_connection 태스크는 우리가 만든 게 아니라 "
                       "asyncio.start_server(streams)가 접속을 받고 스스로 만든 것이다."),
                   look=(f"③ 준비큐 — Task({task._label}).__step이 들어왔다 (Handle 포장)",
                         f"④ 힙 — 카드 생성 (관찰 대상 코루틴만 카드로 표시)",
                         "② 콜 스택 — create_task를 부른 진짜 호출 경로"),
                   hi=hi, skip=4)
        return task

    def resume(self, task):
        self.phase = "RUN"
        self.current = task
        mark = self._mark(task.get_coro())
        loc = self._floc(*mark) if mark else None
        self._snap("resume",
                   f"루프가 준비큐의 Handle을 실행 → 진짜 Task({task._label}).__step이 "
                   f"coro.send()를 부른다"
                   + (f" — {loc}에서 재개." if loc else "."),
                   concept=(
                       "② 콜 스택이 이 모드의 핵심 증거다. 바닥부터: <module>(run.py) → "
                       "run_until_complete → run_forever(진짜 루프의 while) → _run_once → "
                       "Handle._run → Task.__step — 전부 실제로 지금 쌓여 있는 CPython "
                       "asyncio의 프레임이고, 파일:줄번호가 진짜다(base_events.py, "
                       "events.py, tasks.py를 열면 그 줄이 있다). 그 위에 코루틴 프레임 "
                       "사슬이 얹혀 다음 await까지 중단 없이 달린다."),
                   look=(f"② 콜 스택 — asyncio 내부 프레임들 + ↑ 얹힘 코루틴 프레임",
                         f"① 소스 — {loc} 하이라이트" if loc else "③ 준비큐 — 하나 꺼내짐",
                         f"④ 힙 — {task._label} RUNNING"),
                   hi=mark, skip=4)

    def after_step(self, task):
        self.current = None
        if task.done():
            if task.cancelled():
                self._snap("done",
                           f"Task({task._label}) 취소 완료 — cancel()이 CancelledError를 "
                           f"코루틴 안으로 던져 넣었고, 프레임이 정리됐다.",
                           concept=("취소는 밖에서 죽이는 게 아니라 '코루틴이 멈춘 await "
                                    "지점에서 CancelledError가 던져지는' 것이다. serve는 "
                                    "serve_forever에서 이 예외를 받고 async with를 빠져나오며 "
                                    "서버를 닫았다. 실무 asyncio 난이도의 절반이 이 취소 "
                                    "처리에 있다."),
                           look=(f"④ 힙 — {task._label} 카드 DONE",), skip=4)
                return
            earlier = [t._label for t in self.tasks
                       if t._label.startswith("client_") and not t.done()
                       and self.tasks.index(t) < self.tasks.index(task)]
            msg = (f"코루틴이 return까지 도달 — StopIteration을 Task.__step이 받아 "
                   f"Task({task._label})를 완료 처리했다.")
            concept = ("진짜 Task도 StopIteration으로 끝을 안다(제너레이터와 동일한 "
                       "규약). 결과는 Task(=Future)에 저장되고, 이 Task를 await하던 쪽이 "
                       "있다면 콜백으로 깨어난다.")
            if task._label.startswith("client_") and earlier:
                msg += f" 나중에 접속한 {task._label}가 먼저 끝났다."
                concept += (f" 그리고 이것이 핵심 장면: {earlier[0]}는 아직 요청을 다 "
                            f"보내지도 않았는데 {task._label}가 먼저 응답까지 끝냈다. "
                            f"진짜 asyncio에서도 손님 1명 = Task 1개 = 프레임 1개라 "
                            f"서로를 조금도 막지 않는다.")
            self._snap("done", msg, concept=concept,
                       look=(f"④ 힙 — {task._label} DONE (카드가 흐려짐)",
                             "③ 셀렉터 장부 — 이 연결의 소켓이 정리되면 행도 사라진다"),
                       skip=4)
        else:
            waiter = _short(getattr(task, "_fut_waiter", None), 60)
            mark = self._mark(task.get_coro())
            loc = self._floc(*mark) if mark else None
            self._snap("suspend",
                       f"Task({task._label})가 await 지점에서 프레임을 내려놓았다"
                       + (f" — 책갈피 {loc}" if loc else "") +
                       f". 지금 기다리는 것: {waiter}",
                       concept=(
                           "진짜 asyncio는 튜플 신호가 아니라 Future를 기다린다. "
                           "task._fut_waiter가 그 Future다. 소켓에 데이터가 도착하면 "
                           "transport의 _read_ready 콜백이 StreamReader에 바이트를 넣으며 "
                           "이 Future를 완료시키고, 그러면 Task.__wakeup → __step으로 "
                           "이어진다. 즉 '장부에 fd 기입'(미니 루프)이 진짜에서는 "
                           "'셀렉터의 transport 콜백 + Future 연결'로 한 겹 두꺼워진 것."),
                       look=(f"④ 힙 — {task._label} 카드의 _fut_waiter 값 (무엇을 기다리나)",
                             "③ 셀렉터 장부 — 소켓 fd마다 transport._read_ready가 등록돼 있다",
                             f"① 소스 — {loc}에 책갈피 📑" if loc else "② — 프레임이 내려갔다"),
                       hi=mark, skip=4)

    def select_snap(self):
        self.phase = "SELECT"
        n = len(self.loop._selector.get_map())
        timers = len(self.loop._scheduled)
        self._snap("phase",
                   "준비큐가 비었다 — 진짜 epoll 대기로 들어간다. 이 순간 파이썬 "
                   "프로세스는 커널 안에서 잠들어 있다(CPU 0%).",
                   concept=(
                       "② 콜 스택을 보면 _run_once가 selector.select()를 부른 채 멈춰 "
                       "있다. 미니 루프의 SELECT가 흉내였다면 지금 이것은 진짜 epoll_wait "
                       "시스템 콜이다. 등록된 소켓에 이벤트가 오거나 타이머 시각이 되어야 "
                       "커널이 프로세스를 깨운다."),
                   look=("② 콜 스택 — selector.select까지의 asyncio 프레임 (전부 실제)",
                         f"③ 셀렉터 장부 — 등록 소켓 {n}개" +
                         (f" · 타이머 {timers}개 — 이들이 깨울 수 있는 전부" if timers
                          else " — 이들이 깨울 수 있는 전부")),
                   skip=4)

    def wake_snap(self, events):
        self.phase = "WAKE"
        fds = [key.fd for key, _ in events]
        if fds:
            nar = (f"epoll이 깨어났다 — fd {fds}에 이벤트. 셀렉터에 등록된 "
                   f"transport 콜백이 준비큐로 들어간다.")
            concept = ("OS가 알려준 fd의 콜백이 준비큐로 옮겨진다. 미니 루프에서는 "
                       "장부의 콜백이 곧 Task.step이었지만, 진짜는 한 단계가 더 있다: "
                       "transport._read_ready가 먼저 소켓에서 바이트를 읽어 StreamReader에 "
                       "넣고, 거기서 기다리던 Future가 완료되면 그제야 Task.__wakeup이 "
                       "예약된다. WAKE → (transport) → Future → Task 순서의 릴레이다.")
            look = (f"③ 셀렉터 장부 — fd {fds} 행 강조 (OS 알림)",
                    "③ 준비큐 — transport 콜백(_read_ready 등)이 들어왔다")
        else:
            nar = "타이머 시각이 되어 깨어났다 (fd 이벤트 없음) — sleep(0.2) 만료."
            concept = ("이번 기상은 소켓이 아니라 타이머다. call_later로 등록된 "
                       "TimerHandle의 시각이 지나 select가 타임아웃으로 돌아왔고, "
                       "그 콜백(sleep의 Future 완료)이 준비큐로 들어간다.")
            look = ("③ 타이머 힙 — 방금 시각이 된 항목이 준비큐로 이동",)
        self._snap("phase", nar, concept=concept, look=look, notified=fds, skip=4)

    def net_event(self, desc):
        self.script_done += 1
        self.clock = self.script_done
        self._snap("net", f"클라이언트 행동 완료: {desc}",
                   concept=("driver(verify.py check()의 확장판) 태스크가 각본의 다음 "
                            "행동을 마쳤다. 클라이언트도 서버와 같은 루프에서 도는 "
                            "태스크 하나일 뿐이다 — open_connection/write/read 전부 진짜다."),
                   look=("⑤ 타임라인 — 방금 항목에 ✓",
                         "② 콜 스택 — driver(check) 코루틴이 실행 중"),
                   skip=4)


# ================================================================ 실행기
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def build_real_trace(weblab_pkg, req_a, req_b, expected_a, expected_b):
    """weblab 3파일 코드를 진짜 asyncio에서 돌리고 트레이스를 만든다."""
    from importlib import import_module
    mini_server = import_module(f"{weblab_pkg}.mini_server")
    verify = import_module(f"{weblab_pkg}.verify")   # app / hello / echo 정의를 그대로
    mini_framework = import_module(f"{weblab_pkg}.mini_framework")

    src_files = [mini_server.__file__, mini_framework.__file__, verify.__file__]
    tracer = RealTracer(src_files)
    tracer.func_cards = [
        {"name": "serve · handle_connection", "note": "mini_server.py — 그대로 실행 중"},
        {"name": "app (MiniAPI 인스턴스)", "note": "mini_framework.py — ASGI callable"},
        {"name": "hello · echo", "note": "verify.py의 데모 앱 핸들러"},
        {"name": "asyncio.start_server / Task / SelectorEventLoop", "note": "전부 진짜 asyncio"},
    ]
    responses = {}
    port = _free_port()

    async def check():
        """verify.py check()의 2-클라이언트 확장판 — 진짜 소켓으로 각본 수행."""
        server_task = asyncio.create_task(mini_server.serve(verify.app, port=port))
        await asyncio.sleep(0.2)                 # 서버가 뜰 시간 (verify.py 그대로)
        tracer.net_event("serve 태스크 기동 + sleep(0.2) — 서버가 listen 소켓을 열었다")

        ra, wa = await asyncio.open_connection("127.0.0.1", port)
        tracer.net_event("A 접속")
        wa.write(req_a[0]); await wa.drain()
        tracer.net_event("A 요청라인만 전송 (GET /hello …) — A는 여기서 굼뜨다")
        rb, wb = await asyncio.open_connection("127.0.0.1", port)
        tracer.net_event("B 접속")
        wb.write(req_b[0] + req_b[1]); await wb.drain()
        tracer.net_event("B 요청 전체 전송 (POST /echo + 바디 hello)")
        responses["B"] = await rb.read(-1)       # 서버가 연결을 닫을 때까지 전부 읽기
        tracer.net_event("B 응답 수신 완료 ← 나중에 온 B가 먼저 끝났다")
        wa.write(req_a[1]); await wa.drain()
        tracer.net_event("A 나머지(헤더+빈 줄) 전송")
        responses["A"] = await ra.read(-1)
        tracer.net_event("A 응답 수신 완료")
        wa.close(); wb.close()

        server_task.cancel()                     # verify.py와 동일한 마무리
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    loop = asyncio.new_event_loop()
    try:
        loop.set_task_factory(tracer.task_factory)
        loop._selector = TracingSelector(loop._selector, tracer)
        tracer.loop = loop
        loop.run_until_complete(check())
    finally:
        loop.close()

    assert responses["A"] == expected_a, f"A(/hello) 응답 불일치: {responses['A']!r}"
    assert responses["B"] == expected_b, f"B(/echo) 응답 불일치: {responses['B']!r}"

    files = [{"name": f"demos/weblab/{Path(p).name}",
              "lines": Path(p).read_text(encoding="utf-8").splitlines()}
             for p in src_files]
    return {
        "title": "asynclab — 진짜 asyncio 관찰 (weblab 3파일)",
        "subtitle": "mini_server·mini_framework·verify의 코드를 한 글자도 안 고치고 진짜 "
                    "SelectorEventLoop·진짜 Task·진짜 소켓 위에서 돌린다. 후킹은 관찰용뿐 — "
                    "콜 스택의 asyncio 프레임은 실제 파일:줄이다",
        "files": files,
        "boot": [
            "from demos.weblab.verify import app        # hello/echo 라우트까지 verify.py 그대로",
            f"server_task = asyncio.create_task(serve(app, port={port}))   # verify.check()와 동일",
            "await asyncio.sleep(0.2)                    # 서버가 뜰 시간 → 진짜 타이머 힙 등록",
            "클라이언트 A/B = open_connection(...)       # 같은 루프의 태스크가 각본 수행",
            "루프 = asyncio.SelectorEventLoop            # run_forever의 while이 _run_once 반복",
        ],
        "script": [{"t": i + 1, "desc": d} for i, d in enumerate([
            "T=1 서버 기동(listen)", "T=2 A 접속", "T=3 A 요청라인만 전송",
            "T=4 B 접속", "T=5 B 요청 전체 전송", "T=6 B 응답 완료(먼저!)",
            "T=7 A 나머지 전송", "T=8 A 응답 완료 → 서버 취소"])],
        "steps": tracer.steps,
    }, responses
