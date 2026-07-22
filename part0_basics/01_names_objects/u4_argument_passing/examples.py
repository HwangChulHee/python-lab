"""u4 예제: 인자 전달을 관측한다.

실행: python examples.py
"""
import sys

# ── 예제 1: 변경은 반영, 재대입은 안 됨 ──────────────
print("=== 변경 vs 재대입 ===")

def mutate(x):
    x.append(99)

def rebind(x):
    x = [0, 0]

a = [1, 2, 3]
mutate(a)
print("  mutate 후 :", a)      # [1,2,3,99]

a = [1, 2, 3]
rebind(a)
print("  rebind 후 :", a)      # [1,2,3]


# ── 예제 2: 인자로 넘기면 refcount 증가 ──────────────
print("\n=== 인자 전달 = 화살표 하나 더 ===")
def check(x):
    return sys.getrefcount(x)
obj = [1, 2, 3]
print("  바깥에서   :", sys.getrefcount(obj))
print("  함수 안에서 :", check(obj))    # +1 (매개변수 x)


# ── 예제 3: 불변 객체 ────────────────────────────────
print("\n=== 불변은 재대입만 가능 ===")
def add_one(n):
    n += 1
    return n
x = 5
result = add_one(x)
print(f"  x={x}, 반환={result}")   # x=5 (안 바뀜), 반환=6


# ── 예제 4: 가변 기본 인자 함정 ──────────────────────
print("\n=== 가변 기본 인자 함정 ===")
def bad(item, target=[]):
    target.append(item)
    return target
print("  bad(1):", bad(1))        # [1]
print("  bad(2):", bad(2))        # [1, 2] — 누적!
print("  bad(3):", bad(3))        # [1, 2, 3]
print("  __defaults__:", bad.__defaults__)   # 같은 리스트가 자라 있음

def good(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
print("  good(1):", good(1))      # [1]
print("  good(2):", good(2))      # [2] — 매번 새로