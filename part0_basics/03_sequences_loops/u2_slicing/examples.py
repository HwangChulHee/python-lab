"""u2 예제: 슬라이싱을 관측한다.

실행: python examples.py
"""

s = [0, 1, 2, 3, 4, 5]

# ── 예제 1: 기본 슬라이싱 ────────────────────────────
print("=== 기본 ===")
print("  s        :", s)
print("  s[1:3]   :", s[1:3], "  ← 3은 제외")
print("  s[:3]    :", s[:3])
print("  s[3:]    :", s[3:])
print("  s[:]     :", s[:])
print("  s[-2:]   :", s[-2:], "  ← 음수는 뒤에서")
print("  s[:-2]   :", s[:-2])
print("  len(s[1:4]) == 4-1 :", len(s[1:4]) == 4 - 1)
print("  s[:2]+s[2:] == s   :", s[:2] + s[2:] == s)


# ── 예제 2: step ─────────────────────────────────────
print("\n=== step ===")
print("  s[::2]   :", s[::2])
print("  s[1::2]  :", s[1::2])
print("  s[::-1]  :", s[::-1], "  ← 뒤집기")
print("  s[::-2]  :", s[::-2])
print("  s[2:5:2] :", s[2:5:2], "  ← 읽기 어렵다")


# ── 예제 3: 범위 초과 ────────────────────────────────
print("\n=== 범위 초과 ===")
short = [1, 2, 3]
print("  short[1:100]:", short[1:100], "  ← 에러 없음")
print("  short[10:20]:", short[10:20], "  ← 빈 리스트")
try:
    short[10]
except IndexError as e:
    print("  short[10]   : IndexError —", e)


# ── 예제 4: 슬라이스는 새 객체 ───────────────────────
print("\n=== 얕은 복사 ===")
a = [1, 2, 3]
b = a[:]
print("  b is a      :", b is a)
b.append(4)
print("  b.append 후 a:", a, "| b:", b)

nested = [[1, 2], [3, 4]]
copy_n = nested[:]
copy_n[0].append(99)
print("  중첩: 안쪽 수정 후 원본:", nested, "  ← 안쪽은 공유")


# ── 예제 5: 슬라이스 대입 ────────────────────────────
print("\n=== 슬라이스 대입 ===")
a = [1, 2, 3, 4, 5]
a[1:3] = ["x"]
print("  a[1:3]=['x'] :", a, "  ← 길이 줄어듦")

a = [1, 2, 3]
a[1:2] = ["a", "b", "c"]
print("  a[1:2]=3개   :", a, "  ← 길이 늘어남")

print("\n  변경 vs 재대입:")
a = [1, 2, 3]; b = a
a[:] = [9, 9, 9]
print("    a[:] = ... (변경) → b:", b)
a = [1, 2, 3]; b = a
a = [9, 9, 9]
print("    a = ...   (재대입) → b:", b)


# ── 예제 6: slice 객체 ───────────────────────────────
print("\n=== slice 객체 ===")
sl = slice(1, 4)
print("  slice(1,4)   :", sl)
print("  s[sl]        :", s[sl])
print("  start/stop/step:", sl.start, sl.stop, sl.step)

class MyList:
    def __init__(self, data): self.data = data
    def __getitem__(self, key):
        print(f"    __getitem__({key!r}) 호출됨")
        return self.data[key]

m = MyList([10, 20, 30, 40])
print("  m[1]  :", m[1])
print("  m[1:3]:", m[1:3])


# ── 예제 7: __getitem__만으로 for가 돈다 ─────────────
print("\n=== 구형 이터레이션 프로토콜 ===")
class OldStyle:
    def __getitem__(self, i):
        if i >= 3:
            raise IndexError
        return i * 10

print("  for 결과:", [x for x in OldStyle()])
print("  __iter__ 있나?:", hasattr(OldStyle(), "__iter__"))