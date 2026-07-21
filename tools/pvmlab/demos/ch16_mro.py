"""
ch16_mro.py — 16장 'MRO(메서드 결정 순서)' 데모

관찰 포인트:
  · 다이아몬드 상속 D(B, C) — B와 C가 각각 A를 상속. d.who()가 어느 클래스의 who를
    잡는지 MRO 순서(D → B → C → A → object)를 조회 경로로 확인한다.
  · 인스턴스 패널에 type(d).__mro__가 그대로 표시된다.

super()는 스트레치라 P4에서 구현하지 않음 → 데모에서 제외 (REPORT.md 참조).

★ 클래스를 데모 함수 안에 정의.
"""

from demos import demo


@demo("④ MRO — 다이아몬드 상속에서 who()는 D→B에서 잡힌다")
def mro_demo():
    class A:
        def who(self):
            return "A"
    class B(A):
        def who(self):
            return "B"
    class C(A):
        def who(self):
            return "C"
    class D(B, C):
        pass
    d = D()
    return d.who()                         # MRO: D→B→C→A → "B"
