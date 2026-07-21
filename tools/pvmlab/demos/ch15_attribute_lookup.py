"""
ch15_attribute_lookup.py — 15장 '속성 접근의 진실' 데모

관찰 포인트:
  · 섀도잉: 같은 이름의 인스턴스 속성이 생기면 같은 c.tag 접근의 조회 경로가 바뀐다.
    처음엔 인스턴스.__dict__ ✗ → C.__dict__ ✓ (클래스 속성), 인스턴스 속성을 만든
    뒤엔 인스턴스.__dict__ ✓ 에서 바로 잡힌다. LOAD_ATTR 스텝 설명의 화살표로 확인.
  · 인스턴스 __dict__ diff가 STORE_ATTR 순간 잡힌다.

★ 클래스를 데모 함수 안에 정의.
"""

from demos import demo


@demo("③ 섀도잉 — 같은 c.tag가 조회 경로를 바꾼다 (클래스 속성 ↔ 인스턴스 속성)")
def shadowing():
    class C:
        tag = "class-tag"                  # 클래스 속성
    c = C()
    a = c.tag                              # 조회: 인스턴스 ✗ → C ✓  → "class-tag"
    c.tag = "inst-tag"                     # 인스턴스 속성 생성 (STORE_ATTR)
    b = c.tag                              # 조회: 인스턴스 ✓        → "inst-tag"
    return (a, b)                          # ("class-tag", "inst-tag")
