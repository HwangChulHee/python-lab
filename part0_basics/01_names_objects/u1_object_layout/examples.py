"""u1 예제: 객체의 실제 모양을 관측한다.

실행: python examples.py
"""
import sys

# ── 예제 1: 모든 것이 객체다 ─────────────────────────
print("=== 모든 것이 객체 ===")
for v in [5, 3.14, "hi", [1], {"a":1}, None, True, print, int]:
    print(f"  {str(v)[:20]:<22} type={type(v).__name__:<10} isinstance(object)={isinstance(v, object)}")

print("\n정수에 메서드가 있다:", (255).bit_length(), (255).to_bytes(2, 'big'))


# ── 예제 2: 헤더가 차지하는 크기 ─────────────────────
print("\n=== sys.getsizeof (64비트 기준) ===")
print("  빈 객체 헤더만       :", sys.getsizeof(object()))
print("  int 0               :", sys.getsizeof(0))
print("  int 5               :", sys.getsizeof(5))
print("  int 2**100 (큰 수)   :", sys.getsizeof(2**100))   # 가변 길이!
print("  빈 문자열            :", sys.getsizeof(""))
print("  빈 리스트            :", sys.getsizeof([]))
print("  빈 dict             :", sys.getsizeof({}))
# 관찰: 값이 작아도 최소 크기가 있다 = 헤더 때문


# ── 예제 3: id는 주소 ────────────────────────────────
print("\n=== id() ===")
x = [1, 2]
y = x
z = [1, 2]
print("  x       :", hex(id(x)))
print("  y (= x) :", hex(id(y)), "← 같은 객체")
print("  z       :", hex(id(z)), "← 내용은 같지만 다른 객체")
print("  x is y  :", x is y)
print("  x is z  :", x is z)
print("  x == z  :", x == z)

print("\n  주소 재사용 함정:")
print("  id([1,2]) == id([3,4]) →", id([1,2]) == id([3,4]))
# 첫 리스트가 즉시 죽고 그 자리를 두 번째가 차지할 수 있다


# ── 예제 4: refcount 관측 ────────────────────────────
print("\n=== refcount ===")
a = [1, 2, 3]
print("  a 생성 후        :", sys.getrefcount(a))
b = a
print("  b = a 후         :", sys.getrefcount(a))
container = [a, a]
print("  리스트에 2번 담은 후:", sys.getrefcount(a))
del b
print("  del b 후         :", sys.getrefcount(a))
del container
print("  del container 후 :", sys.getrefcount(a))
# getrefcount는 항상 +1 (인자로 넘기는 참조)


# ── 예제 5: 타입 포인터 ──────────────────────────────
print("\n=== ob_type ===")
print("  type(5)          :", type(5))
print("  type(5) is int   :", type(5) is int)
print("  int도 객체다      :", type(int))
print("  type(type)       :", type(type))    # type의 타입은 type — 14장 복선