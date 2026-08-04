"""u1 유제"""
import inspect
import sys
from itertools import islice

# ═══════════════════════════════════════════════════
# 유제 1. 실행 순서 예측
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")

def trace_gen():
    print("    [1]")
    yield "a"
    print("    [2]")
    yield "b"
    print("    [3]")

# 아래 각 줄에서 무엇이 출력될지 예측한 뒤 실행
print("  g = trace_gen()")
g = trace_gen()                  # 예측:__아무것도 안나오제

print("  next(g) 1회:")
print("   →", next(g))           # 예측:__ [1] -> a

print("  next(g) 2회:")
print("   →", next(g))           # 예측:__ [2] -> b

print("  next(g) 3회:")
try:
    next(g)
except StopIteration:
    print("   → StopIteration")  # 예측:__ 3 -> StopIteration

# (a) 생성 시점에 [1]이 출력되지 않는 이유:
#   → ? 그렇게 만들었으니까. 제너레이터 함수가 제너레이터 객체를 만들었을뿐.
# (b) [3]은 언제 출력되나:
#   → 맨 마지막에 3 출력하고 stopIteration을 출력하는거제


# ═══════════════════════════════════════════════════
# 유제 2. 프레임 관찰
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")

def counter_gen():
    total = 0
    for i in range(3):
        total += i
        yield total

c = counter_gen()
print("  상태:", inspect.getgeneratorstate(c))   # 예측:__GEN_CREATED
next(c)
print("  1회 후 f_locals:", c.gi_frame.f_locals) # 예측:__{'total' : 0, 'i' : 0}
next(c)
print("  2회 후 f_locals:", c.gi_frame.f_locals) # 예측:__{'total' : 1, 'i' : 1}

# (a) total과 i가 f_locals에 남아 있는 이유:
#   → ? 이터레이터 객체 내 프레임이 사라지지 않으니까. 제너레이터니까 그런거지
# (b) 일반 함수였다면 이 값들은 어디로 갔을까:
#   → 그냥 함수프레임에서 생성되었다가 소멸됐겠지
# (c) 제너레이터가 끝까지 소진되면 gi_frame은 어떻게 되나? 확인해보라:
#   → 사라지겠지. 예제에서 해봤잖


# ═══════════════════════════════════════════════════
# 유제 3. 클래스를 제너레이터로 바꾸기
# ═══════════════════════════════════════════════════
# 아래 이터레이터 클래스와 같은 일을 하는 제너레이터 함수를 작성하라.

class Chunker:
    """리스트를 n개씩 묶어서 내놓는다. [1,2,3,4,5], 2 → [1,2],[3,4],[5]"""
    def __init__(self, data, n):
        self.data = data
        self.n = n
        self.pos = 0
    def __iter__(self):
        return self
    def __next__(self):
        if self.pos >= len(self.data):
            raise StopIteration
        chunk = self.data[self.pos:self.pos + self.n]
        self.pos += self.n
        return chunk

def chunker_gen(data, n):
    for i in range(0, len(data), n):
        yield data[i:i+n]

print("\n=== 유제3 ===")
print("  클래스   :", list(Chunker([1,2,3,4,5], 2)))
print("  제너레이터:", list(chunker_gen([1,2,3,4,5], 2)))

# (a) 클래스에서 self.pos가 하던 역할을 제너레이터에서는 무엇이 대신하나:
#   → i, 즉 반복문에서의 인덱스가 하기로 함
# (b) StopIteration을 직접 raise 했나? 안 했다면 누가 하나:
#   → yield 쓰면 알아서 제너레이터 함수되고, 제너레이터 객체되니께


# ═══════════════════════════════════════════════════
# 유제 4. 버그 찾기 — 제너레이터 소진
# ═══════════════════════════════════════════════════
# 아래 함수는 통계를 계산한다. 제너레이터를 넘기면 결과가 이상하다.

def stats(numbers):
    total = sum(numbers)
    count = sum(1 for _ in numbers)
    maximum = max(numbers) if count else 0
    return {"total": total, "count": count, "max": maximum}

def stats2(numbers) :
    total = 0
    count = 0
    max = 0
    for num in numbers:
        total += num
        count += 1
        if(max < num) :
            max = num
    return {"total": total, "count": count, "max": max}

print("\n=== 유제4 ===")
print("  리스트   :", stats([1, 2, 3, 4, 5]))
try:
    print("  제너레이터:", stats(x for x in [1, 2, 3, 4, 5]))
    print("  제너레이터2:", stats2(x for x in [1, 2, 3, 4, 5]))
except ValueError as e:
    print("  제너레이터: ValueError —", e)

# (a) 무엇이 잘못됐나:
#   → x for ~ 이건 제너레이터이기 때문에 이터레이터 마냥 카운터가 소진된 문제가 있다.
# (b) 한 번만 순회하도록 고쳐라:
#   → stat2로 작성함
# (c) 방어적으로 실체화하는 방법도 써보고, 두 방법의 트레이드오프를 쓰라:
#   → list()로 묶으면 됨. 실체화 하는 방법은 메모리를 먹는거고 위 방법은 복잡한데, 메모리 안먹는거지

# ═══════════════════════════════════════════════════
# 유제 5. 파이프라인 작성
# ═══════════════════════════════════════════════════
# 아래 데이터를 제너레이터 체인으로 처리하라.
# 요구: 각 단계가 한 항목씩만 처리해야 한다 (list() 금지)

RAW = [
    "kim,30,seoul",
    "lee,25,busan",
    "invalid line",
    "park,40,seoul",
    "choi,17,daegu",
]

# 1단계: 쉼표 3개로 split 가능한 줄만 통과 (invalid line 제거)
def valid_lines(lines):
    for line in lines:
        if len(line.split(",")) == 3:
            yield line

# 2단계: dict로 변환 {"name":..., "age": int, "city":...}
def to_dict(lines):
    for line in lines:
        name, age, city = line.split(",")
        yield {"name": name, "age": int(age), "city": city}


# 3단계: 성인(19세 이상)만 통과
def adults(records):
    for r in records:
        if r["age"] >= 19:
            yield r

print("\n=== 유제5 ===")
for r in adults(to_dict(valid_lines(RAW))):
    print("  ", r)

# (a) 이 파이프라인이 100만 줄이어도 메모리가 일정한 이유:
#   → 제너레이터라 yield까지만 하고, 이후에는 갱신하니까
# (b) 만약 중간에 list()를 하나 끼우면 무엇이 달라지나:
#   → 데이터만큼 메모리가 만들어지겠지
# (c) 각 단계가 "필요할 때 윗단계에 요청"하는 구조를 확인하려면
#     어떻게 실험하겠나:
#   → 이건 모르겠네