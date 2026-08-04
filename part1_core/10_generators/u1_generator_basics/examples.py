"""u1 예제: 제너레이터를 관측한다.

실행: python examples.py
"""
import inspect
import sys
from itertools import islice

# ── 예제 1: 호출해도 본문이 안 돈다 ──────────────────
print("=== 생성과 실행 ===")

def gen():
    print("    A 실행")
    yield 1
    print("    B 실행")
    yield 2
    print("    C 실행")

g = gen()
print("  생성됨:", g)
print("  next 1회:", next(g))
print("  next 2회:", next(g))
try:
    next(g)
except StopIteration:
    print("  next 3회: StopIteration (C까지 실행 후 종료)")


# ── 예제 2: 프레임이 살아있다 ────────────────────────
print("\n=== 프레임 보존 ===")

def stateful():
    x = 10
    yield x
    x = 20
    y = "추가됨"
    yield x

s = stateful()
print("  시작 전 상태 :", inspect.getgeneratorstate(s))
next(s)
print("  첫 yield 후  :", inspect.getgeneratorstate(s))
print("  f_locals     :", s.gi_frame.f_locals)
print("  실행 위치    :", s.gi_frame.f_lasti)
next(s)
print("  둘째 yield 후:", s.gi_frame.f_locals)
try:
    next(s)
except StopIteration:
    pass
print("  종료 후 상태 :", inspect.getgeneratorstate(s))
print("  종료 후 frame:", s.gi_frame, "← 프레임이 사라졌다")


# ── 예제 3: 클래스 vs 제너레이터 ─────────────────────
print("\n=== 03장 Reverse 재구현 ===")

class ReverseIterator:
    def __init__(self, data):
        self.data = data
        self.index = len(data)
    def __iter__(self):
        return self
    def __next__(self):
        if self.index <= 0:
            raise StopIteration
        self.index -= 1
        return self.data[self.index]

def reverse_gen(data):
    for i in range(len(data) - 1, -1, -1):
        yield data[i]

print("  클래스   :", list(ReverseIterator([10, 20, 30])))
print("  제너레이터:", list(reverse_gen([10, 20, 30])))
print("  → 상태(index)를 수동 관리 vs 프레임이 자동 보존")


# ── 예제 4: 제너레이터는 이터레이터 (소진) ───────────
print("\n=== 소진 ===")
g = (x * 2 for x in range(3))
print("  iter(g) is g:", iter(g) is g)
print("  1회:", list(g))
print("  2회:", list(g), "← 비었다")


# ── 예제 5: 메모리 비교 ──────────────────────────────
print("\n=== 메모리 ===")
lst = [i * i for i in range(100_000)]
gen = (i * i for i in range(100_000))
print(f"  리스트    : {sys.getsizeof(lst):>10,} 바이트")
print(f"  제너레이터: {sys.getsizeof(gen):>10,} 바이트")


# ── 예제 6: 무한 시퀀스 ──────────────────────────────
print("\n=== 무한 시퀀스 ===")

def naturals():
    n = 0
    while True:
        yield n
        n += 1

def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

print("  자연수 5개:", list(islice(naturals(), 5)))
print("  피보나치 10개:", list(islice(fib(), 10)))
print("  → 무한 루프인데 프로그램이 안 멈춘다 (필요한 만큼만 계산)")


# ── 예제 7: 파이프라인 ───────────────────────────────
print("\n=== 파이프라인 ===")

# 테스트용 로그 데이터
LOGS = [
    "2026-01-01 INFO 서버 시작",
    "2026-01-02 ERROR DB 연결 실패",
    "2026-01-03 INFO 요청 처리",
    "2026-01-04 ERROR 타임아웃",
]

def source(lines):
    for line in lines:
        print(f"    [읽음] {line[:20]}")
        yield line

def filter_errors(lines):
    for line in lines:
        if "ERROR" in line:
            yield line

def parse(lines):
    for line in lines:
        d, lv, msg = line.split(" ", 2)
        yield {"date": d, "level": lv, "msg": msg}

print("  파이프라인 실행 (읽기가 필요할 때만 일어남):")
for rec in parse(filter_errors(source(LOGS))):
    print("    →", rec)


# ── 예제 8: yield from ───────────────────────────────
print("\n=== yield from ===")

def flatten(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)
        else:
            yield item

print("  중첩 평탄화:", list(flatten([1, [2, [3, [4, 5]]], 6])))