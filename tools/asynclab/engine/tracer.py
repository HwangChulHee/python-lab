"""
tracer.py — 매 사건마다 전 계층을 스냅샷

한 스텝 = 이벤트 루프의 사건 하나(페이즈 전환 / 콜백 시작·끝 / 코루틴 재개·보관 /
힙 변화). 바이트코드 단위 스테핑은 하지 않는다 — 그건 pvmlab의 일이다.

핵심: 코루틴 쪽은 '재현'이 아니라 '관찰'이다. cr_frame.f_lineno(멈춘 줄),
cr_await(무엇을 기다리며 아래로 이어지는가), cr_suspended(보관 여부)를 진짜
코루틴 객체에서 실제로 읽어 기록한다. 재현한 것은 루프와 네트워크뿐이다.
"""

# 코루틴 카드에 보여줄 지역 변수 (앞에서부터 최대 3개 — 핵심만)
_LOCALS_PICK = ("method", "path", "headers", "length", "scope")


def _short(v, limit=46):
    r = repr(v)
    return r if len(r) <= limit else r[: limit - 3] + "..."


def _chain(coro, src_path=None):
    """cr_await 사슬을 따라 내려가며 (qualname, 멈춘 줄) 목록을 만든다.
    handle_connection → MiniAPI.__call__ → send 처럼 await가 겹친 만큼 깊어진다.
    infile = 이 프레임이 관찰 대상 소스(mini_web.py)의 것인가 — 아니면 엔진
    (channel.py의 readline/drain 등)이라 소스 패널에 줄 표시를 하지 않는다."""
    frames = []
    obj = coro
    while obj is not None and hasattr(obj, "cr_frame"):
        fr = obj.cr_frame
        frames.append({"name": obj.cr_code.co_qualname,
                       "line": fr.f_lineno if fr else None,
                       "infile": obj.cr_code.co_filename == src_path})
        obj = obj.cr_await
    return frames


def _mark_line(coro, src_path):
    """책갈피/하이라이트용: 관찰 대상 소스 안의 가장 깊은 프레임이 멈춘 줄."""
    lines = [f["line"] for f in _chain(coro, src_path) if f["infile"]]
    return lines[-1] if lines else None


class Tracer:
    def __init__(self, selector, src_path):
        self.selector = selector
        self.src_path = src_path       # 관찰 대상 소스 파일 (demos/mini_web.py)
        self.loop = None               # run.py가 루프 생성 후 연결
        self.steps = []
        self.phase = "RUN"             # SELECT / WAKE / RUN 표시등
        self.current = None            # 지금 콜 스택에 프레임을 얹고 있는 MiniTask
        self.func_cards = []           # run.py가 등록하는 함수 객체 카드 (정적)

    # ---------------- 표기 헬퍼 ----------------
    def _cb_label(self, cb):
        """바운드 메서드 task.step → 'Task(client_A).step' 표기.
        repr(cb)를 쓰면 메모리 주소가 박혀 결정성이 깨진다 — 직접 조립한다."""
        owner = getattr(cb, "__self__", None)
        if owner is not None:
            return f"Task({owner.label}).step"
        return getattr(cb, "__name__", "콜백")

    def _fd_name(self, fd):
        return self.selector.fd_names.get(fd, str(fd))

    # ---------------- 스냅샷 ----------------
    def _snap(self, kind, narration, notified=(), hi=None):
        loop = self.loop
        stack = [{"name": "<module> — run.py", "kind": "base", "line": None,
                  "note": "app·listener를 만들고 loop.run_until_complete(serve(...))를 호출한 곳"},
                 {"name": "MiniEventLoop.run_until_complete", "kind": "loop", "line": None,
                  "note": "단일 while: SELECT → WAKE → RUN — 위에 얹히는 프레임들을 구동"}]
        if self.current is not None:
            for f in _chain(self.current.coro, self.src_path):
                stack.append({"name": f["name"], "kind": "coro",
                              "line": f["line"] if f["infile"] else None,
                              "infra": not f["infile"], "label": self.current.label})

        coros, codes = [], {}
        for t in loop.tasks:
            info = t._code_info
            codes.setdefault(info["qualname"], {**info, "shared": []})
            codes[info["qualname"]]["shared"].append(t.label)
            state = "RUNNING" if t is self.current else t.state()
            fr = t.coro.cr_frame
            picked = []
            if fr is not None:
                lo = fr.f_locals
                picked = [[k, _short(lo[k])] for k in _LOCALS_PICK if k in lo][:3]
            coros.append({"label": t.label, "code": info["qualname"], "state": state,
                          "line": fr.f_lineno if fr else None, "locals": picked})

        bookmarks = [{"label": t.label, "line": _mark_line(t.coro, self.src_path)}
                     for t in loop.tasks
                     if t is not self.current and not t.done
                     and t.coro.cr_frame is not None
                     and _mark_line(t.coro, self.src_path) is not None]

        self.steps.append({
            "kind": kind, "clock": loop.clock, "phase": self.phase,
            "narration": narration,
            "running": self.current.label if self.current else None,
            "stack": stack,
            "heap": {"codes": list(codes.values()), "funcs": self.func_cards, "coros": coros},
            "loop": {"ready": [self._cb_label(cb) for cb in loop.ready],
                     "watch": [{"fd": fd, "name": self._fd_name(fd),
                                "cb": self._cb_label(cb), "notified": fd in notified}
                               for fd, cb in sorted(loop.watch.items())],
                     "timers": [[t, self._cb_label(cb)] for t, _, cb in sorted(loop.timers)]},
            "net": {"consumed": self.selector.consumed},
            "src": {"hi": hi, "bookmarks": bookmarks},
        })

    # ---------------- 사건들 (루프가 부른다) ----------------
    def loop_started(self):
        self._snap("loop", "run.py의 <module>이 selector(각본 네트워크)·loop·app·listener를 "
                   "만든 뒤 loop.run_until_complete(serve(loop, app, listener))를 호출했다 — "
                   "asyncio.run(main())에 해당하는 순간. 이 호출로 run_until_complete()가 "
                   "콜 스택에 눌러앉는다. 루프는 배경 데몬이 아니라 이 '상주 프레임'이고, "
                   "끝날 때까지 내려가지 않는다.")

    def task_created(self, task):
        code = task.coro.cr_code
        task._code_info = {"qualname": code.co_qualname,
                           "firstlineno": code.co_firstlineno,
                           "argcount": code.co_argcount}
        self._snap("created",
                   f"코루틴 {code.co_qualname}(...) 생성 → Task({task.label})로 감싸 "
                   f"call_soon. 준비큐에 들어간 것은 코루틴이 아니라 콜백 "
                   f"Task({task.label}).step — Task가 코루틴을 콜백으로 번역한다.",
                   hi=task.coro.cr_frame.f_lineno)

    def select_phase(self):
        self.phase = "SELECT"
        self._snap("phase", "준비큐가 비었다 — 루프는 OS(셀렉터)에 맡기고 잠든다. "
                   "파이썬 코드는 한 줄도 돌지 않는다(CPU 0%). 콜 스택에는 루프 "
                   "프레임만 남아 있다.")

    def wake_phase(self, readable):
        self.phase = "WAKE"
        descs = [e[4] for e in self.selector.script[:self.selector.consumed]
                 if e[0] == self.selector.clock]
        waking = [self._cb_label(self.loop.watch[fd]) for fd in readable
                  if fd in self.loop.watch]
        self._snap("phase",
                   f"OS 알림: {' · '.join(descs)}. 루프가 깬다 — 장부(watch)를 보고 "
                   f"누굴 깨울지 안다: {', '.join(waking) if waking else '(대상 없음)'}"
                   f"을(를) 준비큐로 옮긴다.", notified=readable)

    def run_phase(self):
        self.phase = "RUN"
        n = len(self.loop.ready)
        self._snap("phase", f"RUN — 준비큐의 콜백 {n}개를 차례로 호출한다. "
                   "콜백 하나 = 보관된 프레임 한 번 재개.")

    # ---------------- 사건들 (MiniTask가 부른다) ----------------
    def resume(self, task):
        first = task.coro.cr_frame is not None and not task.coro.cr_suspended
        self.current = task
        line = _mark_line(task.coro, self.src_path)
        if first:
            what = f"코루틴 본문이 처음 시작된다 (줄 {line}의 def부터)"
        else:
            what = f"줄 {line}의 책갈피에서 재개된다"
        self._snap("resume",
                   f"준비큐에서 Task({task.label}).step을 꺼내 호출 — coro.send(None)이 "
                   f"보관된 프레임을 콜 스택에 얹는다. {what}.", hi=line)

    def suspend(self, task, why, fd=None, nbytes=None, delay=None):
        self.current = None
        line = _mark_line(task.coro, self.src_path)
        if why == "read":
            msg = (f"기다릴 데이터가 아직 없다 — 장부에 'fd {fd} ({self._fd_name(fd)}) → "
                   f"Task({task.label}).step' 기입 후 프레임을 내려놓는다(SUSPENDED). "
                   f"책갈피는 줄 {line}.")
        elif why == "write":
            msg = (f"응답 {nbytes}바이트를 fd {fd} ({self._fd_name(fd)})로 전송. 쓰기는 "
                   f"늘 준비돼 있으니 call_soon으로 준비큐에 즉시 재예약 — 프레임은 "
                   f"잠깐만 내려간다(줄 {line}).")
        else:
            msg = (f"{delay} 뒤에 깨워 달라고 타이머 힙에 등록 — 프레임을 내려놓는다. "
                   f"책갈피는 줄 {line}.")
        self._snap("suspend", msg, hi=line)

    def finish(self, task):
        self.current = None
        msg = (f"coro.send()가 StopIteration을 던졌다 — 본문 끝. Task({task.label}) "
               f"DONE, 프레임 소멸(cr_frame=None).")
        earlier = [t.label for t in self.loop.tasks
                   if t.label.startswith("client_") and not t.done
                   and self.loop.tasks.index(t) < self.loop.tasks.index(task)]
        if task.label.startswith("client_") and earlier:
            msg += (f" 나중에 접속한 {task.label}가 먼저 끝났다 — "
                    f"{earlier[0]}의 요청이 늦어도 {task.label}는 막히지 않는다. "
                    f"손님 1명 = 코루틴 1개 = 프레임 1개이기 때문이다.")
        self._snap("done", msg)

    def loop_finished(self, main):
        self._snap("loop", "각본 종료 — 준비큐도 타이머도 비었고 더 올 사건이 없다. "
                   f"루프 종료. {main.label}는 여전히 fd 3을 지켜보는 SUSPENDED인 채로 "
                   "남아 있다 — 실제 서버라면 Ctrl-C로 닫는 순간이다.")
