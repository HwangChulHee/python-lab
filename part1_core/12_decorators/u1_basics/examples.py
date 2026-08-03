"""u1 예제: 데코레이터를 관측한다.

실행: python examples.py
"""
import functools
import inspect
import time

# ── 예제 1: 최소 데코레이터 ──────────────────────────
print("=== 최소 데코레이터 ===")

def logger(fn):
    def wrapper(*args, **kwargs):
        print(f"    [호출] {fn.__name__}({args}, {kwargs})")
        result = fn(*args, **kwargs)
        print(f"    [완료] 결과={result}")
        return result
    return wrapper

@logger
def add(x, y):
    return x + y

print("  add(2, 3) =", add(2, 3))


# ── 예제 2: 클로저로 원본을 기억한다 ─────────────────
print("\n=== 클로저 확인 ===")
print("  __closure__:", add.__closure__)
print("  cell 안의 원본:", add.__closure__[0].cell_contents)
print("  cell의 원본 이름:", add.__closure__[0].cell_contents.__name__)


# ── 예제 3: 메타데이터 소실 ──────────────────────────
print("\n=== @wraps 없을 때 ===")

def bad_deco(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@bad_deco
def greet(name: str) -> str:
    """인사를 반환한다."""
    return f"hi {name}"

print("  __name__ :", greet.__name__)
print("  __doc__  :", greet.__doc__)
print("  signature:", inspect.signature(greet))


print("\n=== @wraps 있을 때 ===")

def good_deco(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@good_deco
def greet2(name: str) -> str:
    """인사를 반환한다."""
    return f"hi {name}"

print("  __name__ :", greet2.__name__)
print("  __doc__  :", greet2.__doc__)
print("  signature:", inspect.signature(greet2))
print("  __wrapped__:", greet2.__wrapped__)


# ── 예제 4: 실행 시점 ────────────────────────────────
print("\n=== 실행 시점 ===")

def timing_deco(fn):
    print(f"  [A] 데코레이터 실행 — {fn.__name__} 장식 중")
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"  [C] wrapper 실행")
        return fn(*args, **kwargs)
    print(f"  [B] wrapper 생성 완료")
    return wrapper

@timing_deco
def task():
    print("  [D] 원본 실행")

print("  --- 여기까지가 정의 시점 ---")
print("  이제 호출:")
task()
task()      # C, D만 다시 출력 — A, B는 한 번뿐


# ── 예제 5: 파라미터 있는 데코레이터 ─────────────────
print("\n=== 파라미터 데코레이터 ===")

def retry(times):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except ValueError as e:
                    print(f"    시도 {i+1} 실패: {e}")
                    if i == times - 1:
                        raise
        return wrapper
    return decorator

counter = {"n": 0}

@retry(3)
def flaky():
    counter["n"] += 1
    if counter["n"] < 3:
        raise ValueError("일시 오류")
    return f"성공 (시도 {counter['n']}회)"

print("  결과:", flaky())


# ── 예제 6: 여러 개 쌓기 ─────────────────────────────
print("\n=== 데코레이터 쌓기 ===")

def outer_deco(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        print("    outer 진입")
        r = fn(*a, **kw)
        print("    outer 종료")
        return r
    return wrapper

def inner_deco(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        print("    inner 진입")
        r = fn(*a, **kw)
        print("    inner 종료")
        return r
    return wrapper

@outer_deco
@inner_deco
def core():
    print("    원본 실행")

core()
print("  = outer_deco(inner_deco(core)) 와 같다")


# ── 예제 7: 실전 — 실행 시간 측정 ────────────────────
print("\n=== 실전: 타이머 ===")

def timed(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            print(f"    {fn.__name__}: {elapsed*1000:.2f}ms")
    return wrapper

@timed
def slow_sum(n):
    return sum(range(n))

slow_sum(1_000_000)