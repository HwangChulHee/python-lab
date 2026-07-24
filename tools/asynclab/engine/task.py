"""
task.py — MiniTask: 코루틴을 콜백으로 번역하는 어댑터

이벤트 루프의 준비큐에는 코루틴이 못 들어간다 — 큐가 아는 건 "인자 없이 호출
가능한 것"뿐이다. MiniTask가 그 사이를 잇는다: step()이라는 평범한 바운드
메서드가 coro.send(None)을 불러 보관된 프레임을 재개하고, 코루틴이 yield한
튜플 신호를 보고 다음에 어디에 등록될지(셀렉터 장부 / 준비큐 / 타이머 힙)를
결정한다. asyncio.Task.__step의 축약판이다.

큐·장부·힙 어디에 들어가든, 들어가는 것은 항상 `task.step` — 콜백이다.
"""


class MiniTask:
    def __init__(self, loop, coro, label):
        self.loop = loop
        self.coro = coro                        # 진짜 네이티브 코루틴 객체
        self.label = label                      # "serve", "client_A", ...
        self.done = False

    def state(self):
        """코루틴 객체의 실제 속성을 읽어 상태를 판정한다 (재현이 아니라 관찰)."""
        if self.coro.cr_frame is None:          # 본문 종료 → 프레임 소멸
            return "DONE"
        if self.coro.cr_running:
            return "RUNNING"
        if self.coro.cr_suspended:              # 3.12+: await에서 멈춰 보관된 상태
            return "SUSPENDED"
        return "CREATED"                        # 만들어졌지만 아직 첫 재개 전

    def step(self):
        """준비큐에서 꺼내져 호출되는 콜백. 보관된 프레임을 얹고(send), 다음
        yield에서 내려놓고(신호 수신), 신호에 따라 자신을 재등록한다."""
        tracer = self.loop.tracer
        tracer.resume(self)
        try:
            signal = self.coro.send(None)       # 프레임을 콜 스택에 얹는다
        except StopIteration:
            self.done = True                    # 본문 끝 — cr_frame은 이미 None
            tracer.finish(self)
            return

        kind = signal[0]
        if kind == "read":                      # ("read", fd) — 셀렉터 장부에 등록
            fd = signal[1]
            self.loop.add_reader(fd, self.step)
            tracer.suspend(self, "read", fd=fd)
        elif kind == "write":                   # ("write", fd, data) — 전송 후 즉시 재예약
            _, fd, data = signal
            self.loop.selector.transmit(fd, data)
            self.loop.call_soon(self.step)
            tracer.suspend(self, "write", fd=fd, nbytes=len(data))
        elif kind == "sleep":                   # ("sleep", n) — 타이머 힙에 등록
            self.loop.call_later(signal[1], self.step)
            tracer.suspend(self, "sleep", delay=signal[1])
        else:
            raise RuntimeError(f"알 수 없는 신호: {signal!r}")
