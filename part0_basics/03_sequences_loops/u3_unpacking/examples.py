"""u3 예제: 언패킹을 관측한다.

실행: python examples.py
"""
import dis

# ── 예제 1: 기본 언패킹 ──────────────────────────────
print("=== 기본 ===")
a, b = 1, 2
print("  a, b =", a, b)
a, b, c = [10, 20, 30]
print("  from list:", a, b, c)
a, b, c = "xyz"
print("  from str :", a, b, c)
(x, y), z = (1, 2), 3
print("  중첩:", x, y, z)


# ── 예제 2: 개수 불일치 ──────────────────────────────
print("\n=== 개수 불일치 ===")
for rhs in [[1, 2, 3], [1]]:
    try:
        a, b = rhs
    except ValueError as e:
        print(f"  a, b = {rhs}  → ValueError: {e}")


# ── 예제 3: swap ─────────────────────────────────────
print("\n=== swap ===")
a, b = 1, 2
a, b = b, a
print("  swap 후:", a, b)

print("\n  바이트코드 (오른쪽 먼저 튜플로):")
def swap(a, b):
    a, b = b, a
    return a, b
dis.dis(swap)
# 관찰: 오른쪽을 스택에 다 올린 뒤 언패킹한다


# ── 예제 4: *rest ────────────────────────────────────
print("\n=== *rest ===")
first, *rest = [1, 2, 3, 4]
print("  first, *rest:", first, rest)
*init, last = [1, 2, 3, 4]
print("  *init, last :", init, last)
a, *mid, z = [1, 2, 3, 4, 5]
print("  a, *mid, z  :", a, mid, z)
first, *rest = [1]
print("  나머지 없음 :", first, rest, "← 빈 리스트")
print("  *rest 타입  :", type(rest).__name__, "← 튜플 풀어도 list")


# ── 예제 5: 중첩 + for ───────────────────────────────
print("\n=== for에서 언패킹 ===")
data = [(("kim", 20), 90), (("lee", 25), 85)]
for (name, age), score in data:
    print(f"  {name}({age}): {score}")

d = {"a": 1, "b": 2}
for i, (k, v) in enumerate(d.items()):
    print(f"  [{i}] {k}={v}")


# ── 예제 6: 함수 호출의 * ** ─────────────────────────
print("\n=== 함수에서 펼치기 ===")
def add(a, b, c):
    return a + b + c

args = [1, 2, 3]
print("  f(*args)   :", add(*args))
kwargs = {"a": 10, "b": 20, "c": 30}
print("  f(**kwargs):", add(**kwargs))