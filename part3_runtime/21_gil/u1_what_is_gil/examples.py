"""u1 예제: GIL의 동작과 한계를 관측한다.

실행: python examples.py
"""
import dis
import sys
import threading
import time

# ── 예제 1: GIL 관련 설정 확인 ───────────────────────
print("=== 환경 ===")
print("  파이썬 버전     :", sys.version.split()[0])
print("  스위치 인터벌   :", sys.getswitchinterval(), "초")
print("  CPU 코어 수     :", __import__("os").cpu_count())
# 3.13+ free-threading 빌드면 False가 나온다
if hasattr(sys, "_is_gil_enabled"):
    print("  GIL 활성화됨    :", sys._is_gil_enabled())
else:
    print("  GIL 활성화됨    : True (이 빌드는 GIL 고정)")


# ── 예제 2: count += 1 은 여러 명령이다 ──────────────
print("\n=== += 는 원자적이지 않다 ===")
count = 0

def increment_once():
    global count
    count += 1

dis.dis(increment_once)
print("  → LOAD, ADD, STORE 사이에서 스레드 전환 가능")


# ── 예제 3: race condition 재현 ──────────────────────
print("\n=== race condition ===")

counter = 0
N = 1_000_000

def worker_unsafe():
    global counter
    for _ in range(N):
        counter += 1

threads = [threading.Thread(target=worker_unsafe) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()

expected = N * 4
print(f"  기대값: {expected}")
print(f"  실제값: {counter}")
print(f"  손실  : {expected - counter} ({(expected-counter)/expected*100:.2f}%)")
print("  GIL이 있는데도 값이 유실된다")


# ── 예제 4: 락으로 해결 ──────────────────────────────
print("\n=== Lock으로 해결 ===")

counter = 0
lock = threading.Lock()

def worker_safe():
    global counter
    for _ in range(N):
        with lock:
            counter += 1

threads = [threading.Thread(target=worker_safe) for _ in range(4)]
start = time.perf_counter()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.perf_counter() - start

print(f"  기대값: {expected}")
print(f"  실제값: {counter}  ← 정확")
print(f"  소요  : {elapsed:.3f}초 (락 비용이 있다)")


# ── 예제 5: 원자적인 연산 vs 아닌 것 ─────────────────
print("\n=== 무엇이 원자적인가 ===")

shared_list = []
def append_worker():
    for i in range(10_000):
        shared_list.append(i)      # 원자적

threads = [threading.Thread(target=append_worker) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"  list.append 4x10000 → {len(shared_list)} (기대 40000)")
print("  append는 단일 C 호출이라 원자적")
print("  하지만 이런 세부사항에 의존하지 말 것")


# ── 예제 6: GIL 해제 확인 (sleep) ────────────────────
print("\n=== IO 중에는 GIL 해제 ===")

def io_task(name, results):
    time.sleep(0.5)                # GIL 놓음
    results.append(name)

results = []
start = time.perf_counter()
threads = [threading.Thread(target=io_task, args=(i, results)) for i in range(4)]
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.perf_counter() - start

print(f"  0.5초 대기 4개를 스레드로: {elapsed:.2f}초")
print("  순차 실행이면 2.0초 — 병렬로 처리됐다")