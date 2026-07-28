"""u1 예제: 인자 전달 규칙을 관측한다.

실행: python examples.py
"""
import dis
import time

# ── 예제 1: 위치 vs 키워드 ───────────────────────────
print("=== 위치와 키워드 ===")
def show(a, b, c):
    return f"a={a} b={b} c={c}"

print("  show(1,2,3)      :", show(1, 2, 3))
print("  show(a=1,b=2,c=3):", show(a=1, b=2, c=3))
print("  show(1, c=3, b=2):", show(1, c=3, b=2))


# ── 예제 2: 기본값은 정의 시점에 한 번 ───────────────
print("\n=== 기본값 평가 시점 ===")
def log_bad(msg, when=time.time()):
    return f"{when:.6f}: {msg}"

print(" ", log_bad("첫 번째"))
time.sleep(0.1)
print(" ", log_bad("두 번째"), "← 시각이 같다!")
print("  __defaults__:", log_bad.__defaults__)

def log_good(msg, when=None):
    if when is None:
        when = time.time()
    return f"{when:.6f}: {msg}"

print(" ", log_good("첫 번째"))
time.sleep(0.1)
print(" ", log_good("두 번째"), "← 시각이 다르다")


# ── 예제 3: *args / **kwargs ─────────────────────────
print("\n=== 모으기 ===")
def collect(a, b=2, *args, **kwargs):
    return f"a={a} b={b} args={args} kwargs={kwargs}"

print(" ", collect(1))
print(" ", collect(1, 3))
print(" ", collect(1, 3, 4, 5))
print(" ", collect(1, 3, 4, 5, x=9, y=8))
print(" ", collect(1, x=9))


# ── 예제 4: 키워드 전용 / 위치 전용 ──────────────────
print("\n=== 키워드 전용 ===")
def kw_only(a, *, verbose=False):
    return f"a={a} verbose={verbose}"

print(" ", kw_only(1, verbose=True))
try:
    kw_only(1, True)
except TypeError as e:
    print("  kw_only(1, True) → TypeError:", e)

print("\n=== 위치 전용 ===")
def pos_only(a, b, /, c):
    return f"a={a} b={b} c={c}"

print(" ", pos_only(1, 2, 3))
print(" ", pos_only(1, 2, c=3))
try:
    pos_only(a=1, b=2, c=3)
except TypeError as e:
    print("  pos_only(a=1,...) → TypeError:", e)

# 내장 함수도 위치 전용이다
try:
    len(obj=[1, 2])
except TypeError as e:
    print("  len(obj=[1,2]) → TypeError:", e)


# ── 예제 5: 호출부의 * ** (펼치기) ───────────────────
print("\n=== 펼치기 ===")
def add(a, b, c):
    return a + b + c

args = [1, 2, 3]
kwargs = {"a": 10, "b": 20, "c": 30}
print("  add(*args)        :", add(*args))
print("  add(**kwargs)     :", add(**kwargs))
print("  add(*[1,2], **{'c':3}):", add(*[1, 2], **{"c": 3}))


# ── 예제 6: 바이트코드 차이 ──────────────────────────
print("\n=== 바이트코드 ===")
def normal_call(f):
    return f(1, 2)

def star_call(f, args):
    return f(*args)

def kw_call(f):
    return f(a=1)

print("  --- f(1, 2) ---")
dis.dis(normal_call)
print("  --- f(*args) ---")
dis.dis(star_call)
print("  --- f(a=1) ---")
dis.dis(kw_call)
# CALL vs CALL_FUNCTION_EX vs KW_NAMES+CALL