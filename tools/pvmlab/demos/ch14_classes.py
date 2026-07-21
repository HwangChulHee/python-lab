"""
ch14_classes.py — 14장 '클래스' 데모

관찰 포인트:
  · class 문 = __build_class__(본문함수, 이름, 베이스) 호출. 클래스 '본문'도 하나의
    코드 객체이고 프레임에서 실행된다 — 함수 본문과 달리 STORE_NAME으로 네임스페이스
    dict를 채우고, 그 dict가 그대로 클래스의 __dict__가 된다.
  · 인스턴스 생성 Dog("초코") → __new__로 인스턴스를 만들고 __init__을 프레임으로
    실행한다. self가 __init__의 첫 지역 변수로 들어오는 것을 확인.
  · 메서드 호출 d.bark() → LOAD_ATTR 메서드 변형이 (함수, self)를 올리고 CALL이
    self를 첫 인자로 받는다.

★ 클래스를 데모 함수 '안'에 정의해 그 생성 과정을 트레이스에 담는다.
"""

from demos import demo


@demo("① 클래스 문 해부 — 본문이 프레임에서 실행되고 네임스페이스를 채운다")
def class_stmt():
    class Point:
        kind = "point"
        origin = 0
    return Point.kind                      # 클래스 속성 읽기 → "point"


@demo("② 인스턴스 생성과 메서드 호출 — __init__ 프레임, self, LOAD_ATTR 메서드")
def instance_method():
    class Dog:
        def __init__(self, name):
            self.name = name               # STORE_ATTR → 인스턴스 __dict__
        def bark(self):
            return self.name + " 멍"        # LOAD_ATTR name (인스턴스 __dict__ 조회)
    d = Dog("초코")
    return d.bark()                        # "초코 멍"
