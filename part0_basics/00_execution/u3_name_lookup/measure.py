"""u3 실측: 이름 조회 비용을 timeit으로 잰다.

실행: python measure.py
"""
import timeit
import math

N = 200_000

# ── 실험 1: 전역+속성 vs 지역 바인딩 ─────────────────
def f_global(nums):
    result = []
    for n in nums:
        result.append(math.sqrt(n))
    return result

def f_local(nums):
    sqrt = math.sqrt          # 루프 밖에서 한 번만 조회
    result = []
    ap = result.append
    for n in nums:
        ap(sqrt(n))
    return result

nums = list(range(N))
t1 = timeit.timeit(lambda: f_global(nums), number=20)
t2 = timeit.timeit(lambda: f_local(nums), number=20)

print("=== 실험 1: math.sqrt 조회 ===")
print(f"  전역+속성 조회 : {t1:.3f}s")
print(f"  지역 바인딩    : {t2:.3f}s")
print(f"  차이           : {(t1-t2)/t1*100:.1f}% 단축")


# ── 실험 2: 순수 이름 조회만 비교 ────────────────────
g_value = 1

def read_global():
    total = 0
    for _ in range(N):
        total += g_value
    return total

def read_local():
    local_value = 1
    total = 0
    for _ in range(N):
        total += local_value
    return total

t3 = timeit.timeit(read_global, number=20)
t4 = timeit.timeit(read_local, number=20)

print("\n=== 실험 2: 순수 이름 조회 ===")
print(f"  LOAD_GLOBAL : {t3:.3f}s")
print(f"  LOAD_FAST   : {t4:.3f}s")
print(f"  배율        : {t3/t4:.2f}배")


# ── 실험 3: 속성 조회 추가 비용 ──────────────────────
class Holder:
    def __init__(self):
        self.value = 1

h = Holder()

def read_attr():
    total = 0
    for _ in range(N):
        total += h.value       # LOAD_GLOBAL h + LOAD_ATTR value
    return total

t5 = timeit.timeit(read_attr, number=20)

print("\n=== 실험 3: 속성 조회 ===")
print(f"  LOAD_GLOBAL+LOAD_ATTR : {t5:.3f}s")
print(f"  LOAD_FAST 대비        : {t5/t4:.2f}배")