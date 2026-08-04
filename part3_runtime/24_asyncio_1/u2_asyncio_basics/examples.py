"""24 u2 예제: asyncio 실전 API를 관측한다.

실행: python examples.py
"""
import asyncio
import time

async def fetch(name, delay):
    await asyncio.sleep(delay)
    return f"{name}"


# ── 예제 1: 코루틴 vs 태스크 ─────────────────────────
async def ex1():
    print("=== 코루틴 vs 태스크 ===")

    start = time.perf_counter()
    await fetch("A", 0.2)
    await fetch("B", 0.2)
    print(f"  순차 await     : {time.perf_counter()-start:.2f}초")

    start = time.perf_counter()
    t1 = asyncio.create_task(fetch("A", 0.2))
    t2 = asyncio.create_task(fetch("B", 0.2))
    await t1
    await t2
    print(f"  create_task 후 : {time.perf_counter()-start:.2f}초")
    print("  → create_task는 즉시 실행을 시작한다")


# ── 예제 2: gather ───────────────────────────────────
async def ex2():
    print("\n=== gather ===")
    start = time.perf_counter()
    results = await asyncio.gather(
        fetch("A", 0.3), fetch("B", 0.1), fetch("C", 0.2)
    )
    print(f"  결과: {results}")
    print(f"  시간: {time.perf_counter()-start:.2f}초 (최댓값)")
    print("  → 완료 순서와 무관하게 입력 순서로 정렬된다")


# ── 예제 3: gather 예외 처리 ─────────────────────────
async def failing():
    await asyncio.sleep(0.1)
    raise ValueError("실패!")

async def ex3():
    print("\n=== gather 예외 ===")

    try:
        await asyncio.gather(fetch("A", 0.1), failing(), fetch("C", 0.1))
    except ValueError as e:
        print(f"  기본 동작: 예외 전파 — {e}")

    results = await asyncio.gather(
        fetch("A", 0.1), failing(), fetch("C", 0.1),
        return_exceptions=True
    )
    print(f"  return_exceptions=True: {results}")


# ── 예제 4: TaskGroup (3.11+) ────────────────────────
async def ex4():
    print("\n=== TaskGroup ===")
    try:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(fetch("A", 0.1))
            t2 = tg.create_task(fetch("B", 0.2))
        print(f"  결과: {t1.result()}, {t2.result()}")
    except* Exception as eg:
        print(f"  예외 그룹: {eg}")

    print("  실패 시 자동 취소:")
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fetch("정상", 0.5))
            tg.create_task(failing())
    except* ValueError as eg:
        print(f"  → {eg.exceptions[0]} 발생, 나머지 자동 취소됨")


# ── 예제 5: 흔한 실수 — 루프에서 순차 await ──────────
async def ex5():
    print("\n=== 루프 순차 vs gather ===")
    urls = list(range(5))

    start = time.perf_counter()
    results = []
    for u in urls:
        results.append(await fetch(f"url{u}", 0.1))
    seq = time.perf_counter() - start

    start = time.perf_counter()
    results = await asyncio.gather(*[fetch(f"url{u}", 0.1) for u in urls])
    con = time.perf_counter() - start

    print(f"  루프 안 await: {seq:.2f}초")
    print(f"  gather       : {con:.2f}초")
    print("  → asyncio를 쓰면서도 효과를 못 보는 가장 흔한 실수")


# ── 예제 6: Semaphore로 동시성 제한 ──────────────────
async def ex6():
    print("\n=== Semaphore ===")
    active = 0
    peak = 0

    async def limited(sem, n):
        nonlocal active, peak
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1
        return n

    sem = asyncio.Semaphore(3)
    await asyncio.gather(*[limited(sem, i) for i in range(10)])
    print(f"  10개 작업, 제한 3 → 최대 동시 실행: {peak}")


# ── 예제 7: 동기 함수 밀어내기 ───────────────────────
def blocking_task(n):
    time.sleep(0.2)          # 동기 블로킹
    return n * 2

async def ex7():
    print("\n=== to_thread ===")
    start = time.perf_counter()
    results = await asyncio.gather(
        asyncio.to_thread(blocking_task, 1),
        asyncio.to_thread(blocking_task, 2),
        asyncio.to_thread(blocking_task, 3),
    )
    print(f"  결과: {results}")
    print(f"  시간: {time.perf_counter()-start:.2f}초 (0.6초가 아님)")
    print("  → 동기 함수를 스레드로 밀어내 이벤트 루프를 막지 않는다")


async def main():
    await ex1(); await ex2(); await ex3()
    await ex4(); await ex5(); await ex6(); await ex7()

asyncio.run(main())