"""
loop.py — MiniEventLoop: 준비큐 · 타이머 힙 · 셀렉터 장부를 노출한 미니 루프

이벤트 루프는 배경 데몬이 아니다. run_until_complete()가 콜 스택에 올려놓는
'상주 프레임'이고, 그 본문의 단일 while이 진실의 원천이다. while 한 바퀴는
반드시 이 순서로 읽힌다:

  SELECT — 준비된 콜백이 없으면 OS(셀렉터)에 맡기고 잠든다. CPU 0%.
  WAKE   — OS가 알려준 fd를 장부(watch)에서 찾아 콜백을 준비큐로 옮긴다.
  RUN    — 준비큐를 소진한다. 콜백 하나 = 코루틴 한 번 재개.

준비큐(ready)에 들어 있는 것은 코루틴이 아니라 콜백(task.step)이다.
"""

import heapq
from collections import deque

from .task import MiniTask


class MiniEventLoop:
    def __init__(self, selector, tracer):
        self.ready = deque()           # 콜백만 들어간다 (Task(...).step)
        self.timers = []               # 힙 [(깨울 시각, 순번, 콜백)]
        self.watch = {}                # 셀렉터 장부: fd → 콜백 ("이 fd가 되면 이걸 불러라")
        self.selector = selector       # ScriptedSelector — OS 역할
        self.tracer = tracer
        self.clock = 0                 # 가상 시계 (셀렉터가 진행시킨다)
        self.tasks = []                # 만들어진 순서대로 (트레이서가 힙 패널에 그림)
        self._seq = 0                  # 타이머 동시각 안정 정렬용

    # ---------------- 등록 API (asyncio와 같은 개념, 최소 형태) ----------------
    def call_soon(self, cb):
        self.ready.append(cb)

    def call_later(self, delay, cb):
        heapq.heappush(self.timers, (self.clock + delay, self._seq, cb))
        self._seq += 1

    def add_reader(self, fd, cb):
        self.watch[fd] = cb            # 장부 기입: fd가 읽기 가능해지면 cb를 깨워라

    def remove_reader(self, fd):
        self.watch.pop(fd, None)

    def start_task(self, coro, label):
        """코루틴을 MiniTask로 감싸 등록한다. 큐에 들어가는 건 task.step 콜백."""
        task = MiniTask(self, coro, label)
        self.tasks.append(task)
        self.call_soon(task.step)
        self.tracer.task_created(task)
        return task

    # ---------------- 단일 while — 진실의 원천 ----------------
    def run_until_complete(self, coro, label="serve"):
        self.tracer.loop_started()
        main = self.start_task(coro, label)

        while True:
            # ---- SELECT: 실행할 콜백이 없으면 OS에 맡기고 잠든다 ----
            if not self.ready:
                if main.done or (self.selector.exhausted() and not self.timers):
                    break              # 더는 어떤 사건도 올 수 없다 → 루프 종료
                self.tracer.select_phase()
                readable = self.selector.wait()          # 가상 시계가 여기서 점프
                self.clock = self.selector.clock

                # ---- WAKE: 장부를 보고 누굴 깨울지 안다 ----
                self.tracer.wake_phase(readable)         # 장부 행 강조 (옮기기 전 스냅샷)
                for fd in readable:
                    cb = self.watch.pop(fd, None)
                    if cb is not None:
                        self.ready.append(cb)            # 장부 → 준비큐
                while self.timers and self.timers[0][0] <= self.clock:
                    _, _, cb = heapq.heappop(self.timers)
                    self.ready.append(cb)                # 시각이 된 타이머도 준비큐로

            # ---- RUN: 준비큐를 소진한다 ----
            self.tracer.run_phase()
            while self.ready:
                cb = self.ready.popleft()
                cb()                                     # = task.step() — 코루틴 한 번 재개

        self.tracer.loop_finished(main)
        for t in self.tasks:                             # 못 끝낸 코루틴 정리 (serve 등)
            if not t.done:
                t.coro.close()
