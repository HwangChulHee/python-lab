"""u3 예제: is/== 와 인터닝을 관측한다.

실행: python examples.py
"""

# ── 예제 1: is 와 == ─────────────────────────────────
print("=== is vs == ===")
a = [1, 2, 3]
b = a
c = [1, 2, 3]
print("  a is b:", a is b, " | a is c:", a is c, " | a == c:", a == c)


# ── 예제 2: 작은 정수 캐시 ───────────────────────────
print("\n=== 작은 정수 캐시 (-5 ~ 256) ===")
for n in [5, 256, 257, -5, -6, 1000]:
    x = n
    y = n
    print(f"  {n:>5}: x is y = {x is y}")
# 256까지 True, 257부터 False


# ── 예제 3: 캐시 경계 확인 ───────────────────────────
print("\n=== 경계 ===")
print("  256 is 256:", 256 is 256)     # 같은 리터럴이라 특수, SyntaxWarning 날 수 있음
a, b = 256, 256
print("  a,b=256   :", a is b)          # True
a, b = 257, 257
print("  a,b=257   :", a is b)          # False


# ── 예제 4: 문자열 인터닝 ────────────────────────────
print("\n=== 문자열 인터닝 ===")
a = "hello"
b = "hello"
print("  'hello'     :", a is b)        # 보통 True
a = "hello world!"
b = "hello world!"
print("  'hello world!':", a is b)      # 특수문자 있으면 다를 수 있음
import sys
a = sys.intern("hello world!")          # 강제 인터닝
b = sys.intern("hello world!")
print("  intern 강제 :", a is b)         # True


# ── 예제 5: 싱글턴 None ──────────────────────────────
print("\n=== 싱글턴 ===")
import sys
x = None
print("  x is None      :", x is None)
print("  None refcount  :", sys.getrefcount(None))   # 매우 큼 — 어디서나 씀
print("  True refcount  :", sys.getrefcount(True))