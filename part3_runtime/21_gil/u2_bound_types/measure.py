"""u2 실측: IO/CPU bound를 스레드/프로세스로 비교한다.

실행: python measure.py
※ ProcessPoolExecutor 때문에 함수가 모듈 최상위에 있어야 한다.
"""
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

WORKERS = 4

# ── 작업 정의 (모듈 최상위 — pickle 가능해야 함) ─────
def io_task(n):
    """IO 흉내 — 대기 중 GIL 해제"""
    time.sleep(0.3)
    return n

def cpu_task_pure(n):
    """순수 파이썬 CPU 작업"""
    total = 0
    for i in range(3_000_000):
        total += i * i
    return total

def cpu_task_c(n):
    """C 구현 CPU 작업 — hashlib은 GIL을 놓는다"""
    data = b"x" * 5_000_000
    for _ in range(20):
        hashlib.sha256(data).hexdigest()
    return n


def bench(label, fn, executor_cls=None):
    items = list(range(WORKERS))
    start = time.perf_counter()
    if executor_cls is None:
        results = [fn(i) for i in items]          # 순차
    else:
        with executor_cls(max_workers=WORKERS) as ex:
            results = list(ex.map(fn, items))
    elapsed = time.perf_counter() - start
    print(f"  {label:<24} {elapsed:6.2f}초")
    return elapsed


def compare(name, fn):
    print(f"\n=== {name} ===")
    seq = bench("순차", fn)
    thr = bench("ThreadPoolExecutor", fn, ThreadPoolExecutor)
    prc = bench("ProcessPoolExecutor", fn, ProcessPoolExecutor)
    print(f"  → 스레드 배속: {seq/thr:.2f}x   프로세스 배속: {seq/prc:.2f}x")


if __name__ == "__main__":
    print(f"작업 {WORKERS}개를 순차/스레드/프로세스로 실행")

    compare("IO-bound (sleep 0.3s)", io_task)
    compare("CPU-bound 순수 파이썬", cpu_task_pure)
    compare("CPU-bound C 구현 (hashlib)", cpu_task_c)

    print("\n예상:")
    print("  IO-bound        : 스레드 O, 프로세스 O (오버헤드만큼 손해)")
    print("  CPU 순수 파이썬  : 스레드 X, 프로세스 O")
    print("  CPU C 구현      : 스레드 O (GIL 해제), 프로세스 O")