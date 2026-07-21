"""
ch12_decorators.py — 12장 '데코레이터' 데모

관찰 포인트:
  · @deco 는 문법설탕이다. `@identity def greet(): ...` 는
      MAKE_FUNCTION(greet 생성) → CALL(identity 적용) → STORE_FAST(이름에 다시 묶기)
    로 컴파일된다. 즉 greet = identity(greet). 데코레이션이 '실행 시점의 함수 치환'
    임을 스텝으로 확인.

  · 데코레이션은 함수 '정의 시점'에 일어나므로, 그 장면을 트레이스에 담으려면
    def를 데모 함수 '안'에서 해야 한다(모듈 로드 시점이 아니라 데모 실행 시점).
    여기 identity/greet는 아무 것도 캡처하지 않아 클로저 opcode가 생기지 않는다
    (MAKE_FUNCTION 플래그 0) — P1 §12의 '데모 함수 자체를 중첩 정의 금지'와는 다른,
    의도된 중첩이다.

  · deco는 클로저 없는 단순 치환 데코레이터로 유지. *args 래퍼는 CALL_FUNCTION_EX가
    필요(P3 범위 밖)하므로 쓰지 않는다.
"""

from demos import demo


@demo("④ 데코레이터는 문법설탕 — MAKE_FUNCTION → CALL(deco) → STORE")
def deco_demo():
    def identity(f):           # 단순 치환 데코레이터 (받은 함수를 그대로 돌려줌)
        return f

    @identity                  # greet = identity(greet)
    def greet():
        return 42

    return greet()             # 42
