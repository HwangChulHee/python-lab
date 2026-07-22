"""u2 예제: 이름이 화살표임을 관측한다.

실행: python examples.py
"""
import sys

# ── 예제 1: b = a 는 복사가 아니다 ───────────────────
print("=== b = a ===")
a = [1, 2, 3]
b = a
print("  a is b       :", a is b)          # True
print("  refcount     :", sys.getrefcount(a))  # 화살표 개수 + 1
b.append(4)
print("  b.append(4) 후 a:", a)            # [1,2,3,4] — a도 바뀜


# ── 예제 2: 재대입 vs 변경 ───────────────────────────
print("\n=== 재대입 vs 변경 ===")

# 재대입: 화살표를 옮김
a = [1, 2, 3]
b = a
b = [9, 9]
print("  재대입 후 a  :", a, "| b:", b)    # a는 [1,2,3] 그대로

# 변경: 객체를 수정
a = [1, 2, 3]
b = a
b.append(4)
print("  변경 후 a    :", a, "| b:", b)    # a도 [1,2,3,4]

# 같은 코드처럼 보여도 왼쪽이 b냐 b[0]이냐가 갈림
a = [1, 2, 3]
b = a
b[0] = 100                                 # 변경!
print("  b[0]=100 후 a:", a)               # [100,2,3] — a도 바뀜


# ── 예제 3: 화살표를 옮기면 옛 객체는 버려진다 ───────
print("\n=== 재대입과 소멸 ===")
x = [1, 2, 3]
print("  리스트 refcount:", sys.getrefcount(x))
x = "hello"                                # 리스트를 아무도 안 가리킴 → 소멸
print("  x = 'hello' 후 x:", x)


# ── 예제 4: 네임스페이스는 dict ──────────────────────
print("\n=== 네임스페이스 = dict ===")
foo = 42
print("  globals()['foo']:", globals()["foo"])
globals()["bar"] = 99                      # dict에 직접 넣기
print("  bar (dict로 만든 이름):", bar)


# ── 예제 5: 여러 이름이 한 객체를 ────────────────────
print("\n=== 화살표 개수 = refcount ===")
obj = [1]
print("  1개:", sys.getrefcount(obj))
p = obj
print("  2개:", sys.getrefcount(obj))
q = obj
print("  3개:", sys.getrefcount(obj))
del p, q
print("  다시 1개:", sys.getrefcount(obj))