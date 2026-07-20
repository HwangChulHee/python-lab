"""u2 예제: def가 실행문임을 바이트코드와 객체로 확인한다.

실행: python examples.py
"""
import dis

# ── 예제 1: def의 바이트코드 ────────────────────────
def outer():
    def inner():
        return 42
    return inner

print("=== outer의 바이트코드 ===")
dis.dis(outer)
# 관찰 포인트 3개:
#   LOAD_CONST  <code object inner>  ← inner 본문은 이미 컴파일된 "상수"
#   MAKE_FUNCTION                    ← 그 코드 객체로 함수 객체를 지금 만듦
#   STORE_FAST  inner                ← inner라는 이름에 할당
# → def 한 줄이 "상수 로드 + 객체 생성 + 이름 할당"으로 번역된다.


# ── 예제 2: 함수 객체는 매번 새로, 코드 객체는 공유 ──
a = outer()
b = outer()

print("\n=== 함수 객체 vs 코드 객체 ===")
print("a is b               :", a is b)                        # False
print("a.__code__ is b.__code__:", a.__code__ is b.__code__)   # True
print("id(a), id(b)         :", id(a), id(b))
print("코드 객체 id          :", id(a.__code__))
# outer()를 호출할 때마다 MAKE_FUNCTION이 다시 실행돼 새 함수 객체가 생긴다.
# 하지만 본문의 바이트코드는 하나뿐이므로 코드 객체는 공유된다.


# ── 예제 3: 함수 객체 안에 뭐가 들어 있나 ────────────
def greet(name, greeting="hello"):
    """인사한다."""
    return f"{greeting}, {name}"

print("\n=== 함수 객체의 속성 ===")
print("__name__     :", greet.__name__)
print("__defaults__ :", greet.__defaults__)      # ('hello',) ← 기본값은 함수 객체에
print("__doc__      :", greet.__doc__)
print("co_varnames  :", greet.__code__.co_varnames)  # 지역 이름 목록은 코드 객체에
print("co_consts    :", greet.__code__.co_consts)

# 함수 객체는 그냥 객체라서 속성을 붙일 수도 있다
greet.call_count = 0
print("붙인 속성     :", greet.call_count)


# ── 예제 4: 실행문이라서 가능한 것들 ────────────────
print("\n=== 조건부 정의 ===")
import sys

if sys.platform == "win32":
    def path_sep():
        return "\\"
else:
    def path_sep():
        return "/"

print("path_sep():", path_sep())

print("\n=== 재정의는 그냥 덮어쓰기 ===")
def hello():
    return "first"

def hello():
    return "second"

print("hello():", hello())   # second — 에러가 아니라 재할당