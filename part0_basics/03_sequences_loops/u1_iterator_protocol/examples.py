"""u1 예제: 이터레이터 프로토콜을 관측한다.

실행: python examples.py
"""
import dis
import sys

# ── 예제 1: for를 손으로 풀어쓰기 ────────────────────
print("=== for의 실체 ===")
items = ["a", "b", "c"]

print("  for문:")
for x in items:
    print("   ", x)

print("  손으로 푼 것:")
it = iter(items)
while True:
    try:
        x = next(it)
    except StopIteration:
        break
    print("   ", x)


# ── 예제 2: 이터러블 vs 이터레이터 ───────────────────
print("\n=== 이터러블 vs 이터레이터 ===")
lst = [1, 2, 3]
it = iter(lst)

print("  lst 타입      :", type(lst).__name__)
print("  iter(lst) 타입:", type(it).__name__)
print("  lst is it     :", lst is it)          # False — 다른 객체
print("  __next__ 있나? lst:", hasattr(lst, "__next__"))
print("  __next__ 있나? it :", hasattr(it, "__next__"))
print("  iter(it) is it    :", iter(it) is it)  # True — 이터레이터는 자기 자신 반환


# ── 예제 3: 소진 ─────────────────────────────────────
print("\n=== 소진 ===")
it = iter([1, 2, 3])
print("  next:", next(it), next(it), next(it))
try:
    next(it)
except StopIteration:
    print("  네 번째 → StopIteration")

it2 = iter([1, 2, 3])
print("  list(it2) 1회:", list(it2))
print("  list(it2) 2회:", list(it2), "← 비었다")

# 리스트는 소진되지 않는다
print("  list 두 번 순회:", list(lst), list(lst))


# ── 예제 4: 제너레이터도 이터레이터 ──────────────────
print("\n=== 제너레이터 소진 함정 ===")
gen = (x * 2 for x in range(3))
print("  1회 list:", list(gen))
print("  2회 list:", list(gen), "← 비었다")
print("  sum     :", sum(gen), "← 0")


# ── 예제 5: range는 이터러블이지 이터레이터가 아니다 ─
print("\n=== range ===")
r = range(3)
print("  list(r) 1회:", list(r))
print("  list(r) 2회:", list(r), "← 다시 나온다")
print("  __next__ 있나?:", hasattr(r, "__next__"))
print("  len(r)      :", len(r))
print("  r[2]        :", r[2])
print("  메모리 비교:")
print("    range(1_000_000)      :", sys.getsizeof(range(1_000_000)), "바이트")
print("    list(range(1_000_000)):", sys.getsizeof(list(range(1_000_000))), "바이트")


# ── 예제 6: 직접 만든 클래스도 for에 넣기 ────────────
print("\n=== 프로토콜만 있으면 된다 ===")

class Countdown:
    def __init__(self, start):
        self.start = start
    def __iter__(self):                 # 이터러블: 새 이터레이터를 반환
        return CountdownIterator(self.start)

class CountdownIterator:
    def __init__(self, current):
        self.current = current
    def __iter__(self):                 # 이터레이터: 자기 자신
        return self
    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

c = Countdown(3)
print("  1회:", list(c))
print("  2회:", list(c), "← 이터러블이라 재사용 가능")


# ── 예제 7: 바이트코드 ───────────────────────────────
print("\n=== 바이트코드 ===")
def loop(items):
    for x in items:
        pass
dis.dis(loop)
# GET_ITER → FOR_ITER → STORE_FAST → JUMP_BACKWARD → END_FOR