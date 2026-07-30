"""u1 예제: 스코프 규칙을 관측한다.

실행: python examples.py
"""
import dis

# ── 예제 1: LEGB ─────────────────────────────────────
print("=== LEGB ===")
x = "global"

def outer():
    x = "enclosing"
    def inner():
        return x            # E에서 찾음
    return inner()

def only_global():
    return x                # G에서 찾음

print("  outer()      :", outer())
print("  only_global():", only_global())
print("  len (builtin):", len)


# ── 예제 2: 네 가지 명령 ─────────────────────────────
print("\n=== 명령 비교 ===")

def show_local():
    y = 1
    return y

def show_global():
    return x

def make_closure():
    z = 1
    def use():
        return z            # LOAD_DEREF!
    return use

print("  --- 지역 (LOAD_FAST) ---")
dis.dis(show_local)
print("  --- 전역 (LOAD_GLOBAL) ---")
dis.dis(show_global)
print("  --- 클로저 (LOAD_DEREF / MAKE_CELL) ---")
dis.dis(make_closure)


# ── 예제 3: 파이썬은 함수 스코프 ─────────────────────
print("\n=== if/for는 스코프를 안 만든다 ===")
if True:
    block_var = "if 안에서 만듦"
print("  if 밖에서:", block_var)

for i in range(3):
    pass
print("  루프 종료 후 i:", i, "← 살아있다")

# 자바라면 둘 다 컴파일 에러


# ── 예제 4: UnboundLocalError (00장 회수) ────────────
print("\n=== 대입이 지역을 만든다 ===")
counter = 10

def read_only():
    return counter          # 읽기만 — OK

def write_attempt():
    counter += 1            # 대입 있음 → 지역 확정 → 에러
    return counter

print("  read_only():", read_only())
try:
    write_attempt()
except UnboundLocalError as e:
    print("  write_attempt(): UnboundLocalError —", e)

print("  co_varnames:", write_attempt.__code__.co_varnames)


# ── 예제 5: global ───────────────────────────────────
print("\n=== global ===")
total = 0

def add_global(n):
    global total
    total += n

add_global(5); add_global(3)
print("  total:", total)


# ── 예제 6: nonlocal ─────────────────────────────────
print("\n=== nonlocal ===")

def make_counter():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count
    return increment

c = make_counter()
print("  1회:", c())
print("  2회:", c())
print("  3회:", c())

c2 = make_counter()
print("  새 카운터:", c2(), "← 독립된 count")


# ── 예제 7: nonlocal은 새로 만들지 않는다 ────────────
print("\n=== nonlocal vs global 차이 ===")
print("  global은 없으면 만든다:")
def create_global():
    global 새전역
    새전역 = 42
create_global()
print("    새전역 =", 새전역)

print("  nonlocal은 없으면 SyntaxError (주석 참고)")
# def outer():
#     def inner():
#         nonlocal missing    # SyntaxError
#         missing = 1