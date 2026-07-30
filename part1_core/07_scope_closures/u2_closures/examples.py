"""u2 예제: 클로저와 cell 객체를 관측한다.

실행: python examples.py
"""
import dis
import sys

# ── 예제 1: 프레임은 죽었는데 변수는 산다 ────────────
print("=== 클로저 기본 ===")

def make_counter():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count
    return increment

c = make_counter()
print("  1회:", c(), " 2회:", c(), " 3회:", c())
print("  make_counter의 프레임은 이미 소멸했는데 count는 살아있다")


# ── 예제 2: cell 객체 들여다보기 ─────────────────────
print("\n=== cell 객체 ===")
print("  __closure__      :", c.__closure__)
print("  cell_contents    :", c.__closure__[0].cell_contents)
c()
print("  호출 후 cell     :", c.__closure__[0].cell_contents)

print("\n  일반 함수는 __closure__가 None:")
def plain(): return 1
print("  plain.__closure__:", plain.__closure__)


# ── 예제 3: cellvars vs freevars ─────────────────────
print("\n=== 세 가지 이름 목록 ===")

def outer():
    made_here = "cellvar"     # outer가 만들고 inner가 씀
    local_only = "일반 지역"   # outer만 씀
    def inner():
        used_here = "inner 지역"
        return made_here + used_here
    return inner

inner_fn = outer()
print("  outer.co_varnames :", outer.__code__.co_varnames)
print("  outer.co_cellvars :", outer.__code__.co_cellvars, "← 넘겨줄 것")
print("  inner.co_varnames :", inner_fn.__code__.co_varnames)
print("  inner.co_freevars :", inner_fn.__code__.co_freevars, "← 받아쓸 것")

print("\n  바이트코드:")
dis.dis(outer)
# MAKE_CELL made_here / LOAD_DEREF 확인


# ── 예제 4: 값이 아니라 변수를 캡처한다 ──────────────
print("\n=== 변수 캡처 (값 아님) ===")

def late_binding():
    x = 1
    def show():
        return x
    x = 99                    # 함수 만든 뒤 변경
    return show

print("  결과:", late_binding()(), "← 1이 아니라 99")


# ── 예제 5: 같은 코드 객체, 다른 cell ────────────────
print("\n=== factory 패턴 (01장 u2 회수) ===")

def factory(n):
    def multiply(x):
        return x * n
    return multiply

double = factory(2)
triple = factory(3)

print("  double(5), triple(5) :", double(5), triple(5))
print("  같은 코드 객체?       :", double.__code__ is triple.__code__)
print("  같은 함수 객체?       :", double is triple)
print("  double의 cell        :", double.__closure__[0].cell_contents)
print("  triple의 cell        :", triple.__closure__[0].cell_contents)


# ── 예제 6: cell이 객체를 붙잡는다 ───────────────────
print("\n=== cell과 refcount (20장 복선) ===")
big = [0] * 1000
print("  big의 refcount(캡처 전):", sys.getrefcount(big))

def capture():
    data = big               # 클로저가 캡처
    def use():
        return len(data)
    return use

holder = capture()
print("  캡처 후               :", sys.getrefcount(big))
print("  cell이 참조를 들고 있어 big은 해제되지 않는다")


# ── 예제 7: 클로저 vs 클래스 ─────────────────────────
print("\n=== 같은 일을 두 방법으로 ===")

def make_acc_closure():
    total = 0
    def add(n):
        nonlocal total
        total += n
        return total
    return add

class AccClass:
    def __init__(self):
        self.total = 0
    def __call__(self, n):
        self.total += n
        return self.total

a1 = make_acc_closure()
a2 = AccClass()
print("  클로저:", a1(10), a1(5))
print("  클래스:", a2(10), a2(5))
print("  클래스는 상태 조회 가능:", a2.total)
print("  클로저는 불편        :", a1.__closure__[0].cell_contents)