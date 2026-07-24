"""
tracer.py — 매 사건마다 전 계층을 스냅샷 + 쉽고 자세한 해설 생성

한 스텝 = 이벤트 루프의 사건 하나(페이즈 전환 / 콜백 시작·끝 / 코루틴 재개·보관 /
힙 변화). 바이트코드 단위 스테핑은 하지 않는다 — 그건 pvmlab의 일이다.

각 스텝은 세 겹의 설명을 갖는다:
  narration — 한두 문장 요약 (스토리 띠 첫 줄)
  concept   — 개념을 쉬운 말로 풀어 쓴 문단
  look      — "지금 볼 곳": 어느 패널(①~⑥)의 어떤 데이터가 이 사건을 보여주는가

핵심: 코루틴 쪽은 '재현'이 아니라 '관찰'이다. cr_frame.f_lineno(멈춘 줄),
cr_await(무엇을 기다리며 아래로 이어지는가), cr_suspended(보관 여부)를 진짜
코루틴 객체에서 실제로 읽어 기록한다. 재현한 것은 루프와 네트워크뿐이다.
"""

# 코루틴 카드에 보여줄 지역 변수 (앞에서부터 최대 3개 — 핵심만)
_LOCALS_PICK = ("method", "path", "body", "scope")


def _short(v, limit=46):
    r = repr(v)
    return r if len(r) <= limit else r[: limit - 3] + "..."


def _chain(coro, src_path=None):
    """cr_await 사슬을 따라 내려가며 (qualname, 멈춘 줄) 목록을 만든다.
    handle_connection → MiniAPI.__call__ → _respond → send 처럼 await가 겹친
    만큼 깊어진다. infile = 이 프레임이 관찰 대상 소스(mini_web.py)의 것인가 —
    아니면 엔진(channel.py의 readline/drain 등)이라 소스 줄 표시를 하지 않는다."""
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
    def _snap(self, kind, narration, concept="", look=(), notified=(), hi=None):
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
            "detail": {"concept": concept, "look": list(look)},
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
        self._snap(
            "loop",
            "run.py의 <module>이 selector(각본 네트워크)·loop·app·listener를 만든 뒤 "
            "loop.run_until_complete(serve(loop, app, listener))를 호출했다 — "
            "asyncio.run(main())에 해당하는 순간.",
            concept=(
                "이벤트 루프의 정체부터 확인하자. 루프는 별도 스레드도, 백그라운드 데몬도 "
                "아니다. run.py가 부른 run_until_complete()라는 평범한 함수 호출 하나가 "
                "리턴하지 않고 안에서 while을 돌고 있는 것뿐이다. 그래서 콜 스택에 "
                "'상주 프레임'으로 눌러앉아 있고, 앞으로 일어나는 모든 일(코루틴 재개, "
                "OS 대기)은 이 프레임 위에서 벌어진다. 진짜 asyncio에서 asyncio.run()을 "
                "부른 뒤 그 줄 아래 코드가 실행되지 않는 이유가 정확히 이것이다."),
            look=(
                "② 콜 스택 — 맨 아래 <module>(run.py), 그 위 run_until_complete에 '상주' "
                "배지. 마지막 스텝까지 이 두 칸은 절대 내려가지 않는다",
                "① 소스 상단 보라 점선 박스 — 이 루프가 어떻게 만들어져 호출됐는지 (배선 5줄)",
                "③ 페이즈 표시등 — 앞으로 SELECT(잠듦) → WAKE(수거) → RUN(소진)이 반복된다"))

    def task_created(self, task):
        code = task.coro.cr_code
        task._code_info = {"qualname": code.co_qualname,
                           "firstlineno": code.co_firstlineno,
                           "argcount": code.co_argcount}
        line = task.coro.cr_frame.f_lineno
        look = [
            f"④ 힙 — {task.label} 카드가 CREATED로 새로 생겼다. cr_frame.f_lineno={line} "
            f"(아직 def 줄 — 본문은 한 줄도 안 돌았다)",
            f"③ 준비큐 — 맨 끝에 Task({task.label}).step이 추가됐다. 코루틴이 아니라 "
            f"'나중에 이걸 불러 달라'는 콜백(바운드 메서드)이다",
        ]
        if self.current is not None:
            look.append(f"② 콜 스택 — 이 생성을 실행한 것은 지금 얹혀 있는 "
                        f"{self.current.label}의 프레임(serve의 while 안)이다")
        self._snap(
            "created",
            f"코루틴 {code.co_qualname}(...) 생성 → Task({task.label})로 감싸 call_soon. "
            f"준비큐에 들어간 것은 코루틴이 아니라 콜백 Task({task.label}).step이다.",
            concept=(
                f"async def 함수는 '호출'해도 본문이 한 줄도 실행되지 않는다. "
                f"{code.co_qualname}(...)이라고 부르는 순간 생기는 건 코루틴 객체 — "
                f"'실행할 준비가 된 프레임의 보관함' — 뿐이다. 이걸 실제로 굴리려면 누군가 "
                f"coro.send()를 계속 불러 줘야 하는데, 그 운전기사 역할을 Task({task.label})가 "
                f"맡는다. Task는 자신의 step 메서드(평범한 콜백)를 준비큐에 넣어 두고, 루프가 "
                f"꺼내 부를 때마다 send()로 코루틴을 한 구간씩 전진시킨다. 이것이 '코루틴을 "
                f"콜백으로 번역한다'의 뜻이고, 진짜 asyncio.create_task()가 하는 일과 같다."),
            look=look,
            hi=line)

    def select_phase(self):
        self.phase = "SELECT"
        n = len(self.loop.watch)
        self._snap(
            "phase",
            "준비큐가 비었다 — 루프는 OS(셀렉터)에 맡기고 잠든다. 파이썬 코드는 한 줄도 "
            "돌지 않는다(CPU 0%).",
            concept=(
                "실행할 콜백이 하나도 없다. 이때 루프는 바쁘게 확인을 반복(폴링)하는 게 "
                "아니라, OS의 대기 호출(리눅스라면 epoll_wait) 안에서 정말로 잠든다. "
                "파이썬 코드는 한 줄도 실행되지 않고 CPU도 쓰지 않는다. 깨어날 조건은 딱 "
                "하나 — 장부에 적어 둔 fd 중 하나에 무슨 일이 생겼다고 OS가 알려주는 것. "
                "'수천 연결을 스레드 없이 감당한다'는 말의 실체가 이 잠이다: 연결마다 "
                "스레드가 기다리는 게 아니라, 보관된 프레임들만 힙에 두고 전부가 잠든다."),
            look=(
                "② 콜 스택 — 코루틴 프레임이 하나도 없다. 루프 프레임만 남고 'CPU 0%' 배지",
                f"③ 셀렉터 장부 — 지금 fd {n}개를 지켜보는 중. 이 목록이 '누가 이 잠을 깨울 "
                f"수 있는가'의 전부다",
                "④ 힙 — 멈춘 손님들은 SUSPENDED 카드(보관된 프레임)로만 존재한다",
                "⑤ 타임라인 — 다음 각본 이벤트 시각까지 가상 시계가 점프할 것"))

    def wake_phase(self, readable):
        self.phase = "WAKE"
        descs = [e[4] for e in self.selector.script[:self.selector.consumed]
                 if e[0] == self.selector.clock]
        waking = [self._cb_label(self.loop.watch[fd]) for fd in readable
                  if fd in self.loop.watch]
        fd_list = ", ".join(f"fd {fd}({self._fd_name(fd)})" for fd in readable)
        self._snap(
            "phase",
            f"OS 알림: {' · '.join(descs)}. 루프가 깬다 — 장부(watch)를 보고 누굴 깨울지 "
            f"안다: {', '.join(waking) if waking else '(대상 없음)'}을(를) 준비큐로 옮긴다.",
            concept=(
                "'데이터가 온 걸 아는' 주체는 파이썬이 아니라 OS다. OS는 도착한 바이트를 "
                "커널의 수신 버퍼에 넣어 두고 '이 fd에 뭔가 왔다'고만 알려준다. 루프가 "
                "하는 일은 조회뿐이다: 장부(watch)를 펼쳐 그 fd 줄에 적힌 콜백을 찾아 "
                "준비큐로 옮긴다. 아직 아무 코루틴도 실행되지 않았고, 바이트를 읽지도 "
                "않았다 — 읽는 건 다음 RUN에서 깨어난 코루틴 자신의 일이다."),
            look=(
                f"⑤ 타임라인 — {' · '.join(descs)}에 ✓가 붙고 가상 시계가 T={self.selector.clock}로 점프",
                f"③ 셀렉터 장부 — {fd_list} 행이 강조됐다(OS 알림). 거기 적힌 "
                f"{', '.join(waking) if waking else '없음'}이 다음 스텝에 준비큐로 이동한다",
                "③ 페이즈 표시등 — SELECT에서 WAKE로 넘어왔다"),
            notified=readable)

    def run_phase(self):
        self.phase = "RUN"
        n = len(self.loop.ready)
        labels = ", ".join(self._cb_label(cb) for cb in self.loop.ready)
        self._snap(
            "phase",
            f"RUN — 준비큐의 콜백 {n}개를 차례로 호출한다. 콜백 하나 = 보관된 프레임 한 번 재개.",
            concept=(
                "이제 준비큐를 앞에서부터 소진한다. 큐에 든 것은 인자 없이 부를 수 있는 "
                "평범한 콜백이라, 루프는 그저 cb()라고 호출할 뿐이다 — 루프는 그 안에서 "
                "코루틴이 재개되는지, HTTP를 파싱하는지 전혀 모른다. 이 무지(콜백이라는 "
                "균일한 포장) 덕분에 루프 코드가 단순해진다."),
            look=(
                f"③ 준비큐 — 대기 중: {labels or '없음'}. 왼쪽(앞)부터 하나씩 꺼내진다",
                "③ 페이즈 표시등 — RUN 점등"))

    # ---------------- 사건들 (MiniTask가 부른다) ----------------
    def resume(self, task):
        first = task.coro.cr_frame is not None and not task.coro.cr_suspended
        self.current = task
        chain = _chain(task.coro, self.src_path)
        line = _mark_line(task.coro, self.src_path)
        names = " → ".join(f["name"] for f in chain)
        if first:
            what = f"코루틴 본문이 처음 시작된다 (줄 {line}의 def부터)"
            concept = (
                f"준비큐에서 Task({task.label}).step이 꺼내져 호출됐고, step 안의 "
                f"coro.send(None)이 코루틴 본문을 비로소 처음 실행시킨다. 지금부터 코드는 "
                f"다음 await(기다려야 하는 지점)를 만날 때까지 중단 없이 달린다 — 이 구간 "
                f"안에서는 그 누구도 끼어들 수 없다(협조적 스케줄링).")
        else:
            what = f"줄 {line}의 책갈피에서 재개된다"
            concept = (
                f"send(None)이 보관돼 있던 프레임을 콜 스택에 도로 얹는다. 지역 변수도, "
                f"멈췄던 줄도 전부 그대로 복원된다 — 새 함수 호출이 아니라 '이어하기'다. "
                f"줄 {line}부터 다음 await까지 다시 중단 없이 달린다.")
            if len(chain) > 1:
                concept += (f" await가 겹쳐 있던 만큼 프레임 사슬 전체가 한 번에 얹힌다: "
                            f"{names}.")
        self._snap(
            "resume",
            f"준비큐에서 Task({task.label}).step을 꺼내 호출 — coro.send(None)이 보관된 "
            f"프레임을 콜 스택에 얹는다. {what}.",
            concept=concept,
            look=(
                f"② 콜 스택 — ↑ 얹힘 배지가 붙은 프레임 {len(chain)}개가 루프 위에 올라왔다",
                f"① 소스 — 줄 {line} 하이라이트(지금 실행이 이어지는 지점)",
                f"④ 힙 — {task.label} 카드가 RUNNING으로 바뀌었다"),
            hi=line)

    def suspend(self, task, why, fd=None, nbytes=None, delay=None):
        self.current = None
        line = _mark_line(task.coro, self.src_path)
        if why == "read":
            msg = (f"기다릴 데이터가 아직 없다 — 장부에 'fd {fd} ({self._fd_name(fd)}) → "
                   f"Task({task.label}).step' 기입 후 프레임을 내려놓는다(SUSPENDED). "
                   f"책갈피는 줄 {line}.")
            concept = (
                f"reader가 버퍼를 확인했지만 원하는 데이터가 아직 없다. 동기 코드였다면 "
                f"여기서 블로킹 — 스레드 전체가 정지 — 했겠지만, 코루틴은 대신 "
                f"('read', fd {fd}) 신호를 yield하며 프레임을 통째로 내려놓는다. Task가 그 "
                f"신호를 받아 장부에 'fd {fd}에 데이터가 오면 나를 다시 불러라'라고 적고 "
                f"끝. 이 손님은 이제 힙에 보관된 프레임으로만 존재하고, 루프는 다른 일을 "
                f"하러 간다. await 한 줄이 '기다림'을 '자리 비움'으로 바꾸는 순간이다.")
            look = (
                f"② 콜 스택 — 방금 내려간 프레임이 점선 유령(↓ 내려놓음 — 보관)으로 보인다",
                f"③ 셀렉터 장부 — 'fd {fd} ({self._fd_name(fd)}) → Task({task.label}).step' "
                f"행이 새로 생겼다",
                f"④ 힙 — {task.label} 카드가 SUSPENDED, cr_frame.f_lineno={line} "
                f"(멈춘 줄 = 이 손님이 어디까지 진행했는가)",
                f"① 소스 — 줄 {line}에 책갈피 📑")
        elif why == "write":
            msg = (f"응답 {nbytes}바이트를 fd {fd} ({self._fd_name(fd)})로 전송. 쓰기는 "
                   f"늘 준비돼 있으니 call_soon으로 준비큐에 즉시 재예약 — 프레임은 "
                   f"잠깐만 내려간다(줄 {line}).")
            concept = (
                f"writer.write()는 소켓에 바로 쓰는 게 아니라 버퍼에 쌓기만 한다. 실제 "
                f"전송 신호는 await drain()이 yield하는 ('write', fd, {nbytes}바이트)다. "
                f"읽기와 달리 쓰기는 (버퍼가 차지 않는 한) 기다릴 이유가 없어서, Task는 "
                f"장부 대신 call_soon으로 자신을 준비큐에 곧장 재예약한다 — 같은 RUN "
                f"페이즈 안에서 바로 다음 순번에 이어진다.")
            look = (
                f"③ 준비큐 — Task({task.label}).step이 도로 들어와 있다 (장부가 아니라 큐!)",
                f"② 콜 스택 — 프레임 사슬이 유령으로 내려가 있다 (한 스텝만)",
                f"⑤ — 응답 {nbytes}바이트가 전송됐다 (run.py 검증 1이 이 바이트를 대조한다)")
        else:
            msg = (f"{delay} 뒤에 깨워 달라고 타이머 힙에 등록 — 프레임을 내려놓는다. "
                   f"책갈피는 줄 {line}.")
            concept = (f"asyncio.sleep에 해당하는 경로다. ('sleep', {delay}) 신호를 받은 "
                       f"Task가 타이머 힙에 (깨울 시각, 콜백)을 넣고 프레임을 내려놓는다.")
            look = (f"③ 타이머 힙 — (T={self.loop.clock + delay}, Task({task.label}).step) 등록",)
        self._snap("suspend", msg, concept=concept, look=look, hi=line)

    def finish(self, task):
        self.current = None
        msg = (f"coro.send()가 StopIteration을 던졌다 — 본문 끝. Task({task.label}) "
               f"DONE, 프레임 소멸(cr_frame=None).")
        concept = (
            f"재개된 코루틴이 이번엔 await에 멈추지 않고 본문 끝(return)까지 달렸다. "
            f"이때 send()는 값을 돌려주는 대신 StopIteration 예외를 던진다 — 제너레이터와 "
            f"똑같은, '더 재개할 것이 없다'는 신호다. Task는 DONE 처리하고, 프레임은 "
            f"소멸한다(cr_frame=None). 보관(suspend)과 소멸(done)은 다르다: 보관은 "
            f"이어할 수 있지만 소멸은 끝이다.")
        earlier = [t.label for t in self.loop.tasks
                   if t.label.startswith("client_") and not t.done
                   and self.loop.tasks.index(t) < self.loop.tasks.index(task)]
        if task.label.startswith("client_") and earlier:
            msg += (f" 나중에 접속한 {task.label}가 먼저 끝났다 — "
                    f"{earlier[0]}의 요청이 늦어도 {task.label}는 막히지 않는다. "
                    f"손님 1명 = 코루틴 1개 = 프레임 1개이기 때문이다.")
            concept += (
                f" 그리고 이 장면이 이 도구의 핵심이다: 먼저 접속한 {earlier[0]}는 아직 "
                f"SUSPENDED인데 나중에 온 {task.label}가 먼저 끝났다. {earlier[0]}가 느린 "
                f"것이 {task.label}를 조금도 막지 않았다 — 손님마다 프레임이 따로 있고, "
                f"루프는 준비된 쪽만 재개하기 때문이다. 스레드 없이 동시성이 성립하는 이유.")
        self._snap(
            "done", msg, concept=concept,
            look=(
                f"④ 힙 — {task.label} 카드가 흐려지고 cr_frame=None (지역 변수도 함께 사라졌다)",
                f"② 콜 스택 — 내려간 프레임들의 배지가 '↓ 프레임 소멸' (보관이 아니다)",
                f"③ 장부·준비큐 — {task.label} 관련 항목이 모두 사라졌다",
                f"① 소스 — {task.label}의 책갈피 📑가 사라졌다"))

    def loop_finished(self, main):
        self._snap(
            "loop",
            "각본 종료 — 준비큐도 타이머도 비었고 더 올 사건이 없다. 루프 종료. "
            f"{main.label}는 여전히 fd 3을 지켜보는 SUSPENDED인 채로 남아 있다 — "
            "실제 서버라면 Ctrl-C로 닫는 순간이다.",
            concept=(
                "루프의 종료 조건은 '더 이상 어떤 사건도 올 수 없음'이다: 준비큐가 비었고, "
                "타이머도 없고, 네트워크(각본)도 끝났다. serve는 아직 SUSPENDED로 accept를 "
                "기다리지만, 깨워 줄 수 있는 사건이 영영 없으므로 루프는 while을 빠져나온다. "
                "실제 서버에서는 이 '사건이 안 옴' 상태가 무한히 계속되고(계속 잠듦), "
                "Ctrl-C(시그널)가 와야 끝난다."),
            look=(
                "② 콜 스택 — 이제야 루프 프레임이 내려갈 수 있다 (run.py로 리턴)",
                f"④ 힙 — {main.label} 카드만 SUSPENDED로 남았다 (프레임은 이후 close()로 정리)",
                "⑤ 타임라인 — 모든 각본 이벤트에 ✓"))
