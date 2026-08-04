"""24 u1 예제: 이벤트 루프의 원리를 관측한다.

실행: python examples.py
"""
import asyncio
import heapq
import inspect
import time

# ── 예제 1: 코루틴도 호출만으로는 안 돈다 ────────────
print("=== 코루틴 객체 ===")

async def hello():
    print("    실행됨!")
    return 42

h = hello()
print("  호출 결과:", h)
print("  아직 실행 안 됨 — 제너레이터와 동일")
print("  iscoroutine:", inspect.iscoroutine(h))
print("  CO_COROUTINE 플래그:", bool(hello.__code__.co_flags & 0x80))

try:
    h.send(None)
except StopIteration as e:
    print("  send(None) →", "StopIteration, value =", e.value)


# ── 예제 2: 손으로 만든 이벤트 루프 ──────────────────
print("\n=== 미니 이벤트 루프 ===")

class MiniLoop:
    def __init__(self):
        self.ready = []
        self.sleeping = []
        self._counter = 0

    def create_task(self, coro):
        self.ready.append(coro)

    def _call_later(self, delay, coro):
        self._counter += 1
        heapq.heappush(self.sleeping, (time.time() + delay, self._counter, coro))

    def run(self):
        while self.ready or self.sleeping:
            now = time.time()
            while self.sleeping and self.sleeping[0][0] <= now:
                _, _, coro = heapq.heappop(self.sleeping)
                self.ready.append(coro)

            if not self.ready and self.sleeping:
                time.sleep(max(0, self.sleeping[0][0] - time.time()))
                continue

            coro = self.ready.pop(0)
            try:
                delay = coro.send(None)       # 한 스텝 진행
                if delay is None:
                    self.ready.append(coro)
                else:
                    self._call_later(delay, coro)
            except StopIteration:
                pass


# 우리 루프용 sleep — 제너레이터로 구현
class Sleep:
    """await 가능한 객체. yield로 대기 시간을 루프에 알린다."""
    def __init__(self, delay):
        self.delay = delay
    def __await__(self):
        yield self.delay          # 루프가 이 값을 받는다


async def worker(name, count, delay):
    for i in range(count):
        print(f"    [{time.strftime('%S')}s] {name} 스텝 {i}")
        await Sleep(delay)
    print(f"    [{time.strftime('%S')}s] {name} 완료")


loop = MiniLoop()
loop.create_task(worker("A", 3, 0.3))
loop.create_task(worker("B", 2, 0.5))
print("  실행 (A와 B가 번갈아 진행):")
loop.run()


# ── 예제 3: 진짜 asyncio로 같은 일 ───────────────────
print("\n=== 진짜 asyncio ===")

async def real_worker(name, count, delay):
    for i in range(count):
        print(f"    {name} 스텝 {i}")
        await asyncio.sleep(delay)
    return f"{name} 완료"

async def main():
    results = await asyncio.gather(
        real_worker("X", 3, 0.1),
        real_worker("Y", 2, 0.15),
    )
    print("  결과:", results)

asyncio.run(main())


# ── 예제 4: await가 항상 양보하지는 않는다 ───────────
print("\n=== 양보 지점 ===")

order = []

async def no_yield():
    order.append("no_yield 시작")
    return 1                      # 대기 없음

async def with_yield():
    order.append("with_yield 시작")
    await asyncio.sleep(0)        # 강제 양보
    order.append("with_yield 재개")

async def other():
    order.append("other 실행")

async def demo():
    t1 = asyncio.create_task(with_yield())
    t2 = asyncio.create_task(other())
    await asyncio.gather(t1, t2)

asyncio.run(demo())
print("  실행 순서:", order)
print("  → sleep(0)에서 양보하여 other가 끼어들었다")


# ── 예제 5: 동시성 vs 순차 ───────────────────────────
print("\n=== 동시성 효과 ===")

async def fetch(name, delay):
    await asyncio.sleep(delay)
    return f"{name}({delay}s)"

async def sequential():
    start = time.perf_counter()
    r1 = await fetch("A", 0.3)
    r2 = await fetch("B", 0.3)
    r3 = await fetch("C", 0.3)
    return time.perf_counter() - start

async def concurrent():
    start = time.perf_counter()
    results = await asyncio.gather(
        fetch("A", 0.3), fetch("B", 0.3), fetch("C", 0.3)
    )
    return time.perf_counter() - start

seq = asyncio.run(sequential())
con = asyncio.run(concurrent())
print(f"  순차 await : {seq:.2f}초")
print(f"  gather     : {con:.2f}초")
print(f"  → 대기 시간이 합산이 아니라 최댓값이 된다")