"""
ch07_closures.py — 07장 '스코프와 클로저' 데모

관찰 포인트:
  · MAKE_FUNCTION: def는 실행문이다. make_adder를 두 번 실행하면 코드 객체는 하나인데
    (add1·add5의 listings가 같은 코드 객체를 가리킴) 함수 객체는 둘이 만들어진다.
    두 함수의 __closure__ 셀 내용(1 vs 5)이 다른 것을 인스펙터로 확인.
  · nonlocal: STORE_DEREF가 바깥과 공유하는 '셀'을 고쳐 쓴다. 카운터를 3회 호출하면
    셀 내용이 1→2→3으로 자라는 diff가 잡힌다.

★ 모든 함수 모듈 레벨. 안쪽 함수(add·tick)도 여기서 make_* 안에 정의되지만, 이는
  클로저를 '만드는' 것이 목적이므로 의도된 것 — P1에서 금지한 '데모 함수 자체를
  중첩 정의하는 것'과는 다르다. 관찰 대상(@demo)은 여전히 모듈 레벨이다.
"""

from demos import demo


def make_adder(n):
    def add(x):
        return x + n          # n은 자유 변수 → 셀에서 LOAD_DEREF
    return add


@demo("⑤ 클로저 생성 — MAKE_FUNCTION으로 add1·add5가 코드 객체를 공유")
def adder_demo():
    add1 = make_adder(1)
    add5 = make_adder(5)
    return add1(10) + add5(10)   # 11 + 15 = 26


def make_counter():
    count = 0
    def tick():
        nonlocal count           # 바깥 셀을 고쳐 쓴다 → STORE_DEREF
        count += 1
        return count
    return tick


@demo("⑥ nonlocal 카운터 — STORE_DEREF로 셀이 1→2→3")
def counter_demo():
    t = make_counter()
    return t() + t() + t()       # 1 + 2 + 3 = 6
