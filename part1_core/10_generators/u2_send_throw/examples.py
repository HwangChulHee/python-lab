"""u2 예제: send/throw/close와 코루틴의 원형을 관측한다.

실행: python examples.py
"""
import inspect

# ── 예제 1: yield는 값을 받는다 ──────────────────────
print("=== send 기본 ===")

def echo():
    while True:
        received = yield
        print(f"    받음: {received}")

g = echo()
next(g)                    # priming
g.send("hello")
g.send("world")


# ── 예제 2: priming 없이 send하면 ────────────────────
print("\n=== priming 필요성 ===")
g2 = echo()
try:
    g2.send("바로 전송")
except TypeError as e:
    print("  TypeError:", e)
print("  → next(g) 또는 g.send(None)으로 첫 yield까지 진행해야 함")


# ── 예제 3: 양방향 — 주고받기 ────────────────────────
print("\n=== 양방향 통신 ===")

def accumulator():
    total = 0
    while True:
        n = yield total        # total 내보내고 n 받음
        total += n

acc = accumulator()
print("  초기값 :", next(acc))
print("  send(10):", acc.send(10))
print("  send(5) :", acc.send(5))
print("  send(3) :", acc.send(3))


# ── 예제 4: throw ────────────────────────────────────
print("\n=== throw ===")

def resilient_worker():
    while True:
        try:
            item = yield
            print(f"    처리: {item}")
        except ValueError as e:
            print(f"    오류 잡음: {e} — 계속 진행")

w = resilient_worker()
next(w)
w.send("작업1")
w.throw(ValueError("일시 오류"))
w.send("작업2")
print("  → 예외를 던져도 제너레이터가 살아있다")


# ── 예제 5: close와 finally ──────────────────────────
print("\n=== close ===")

def resource_holder():
    print("    자원 획득")
    try:
        while True:
            yield "데이터"
    finally:
        print("    자원 해제")

r = resource_holder()
print("  first:", next(r))
r.close()
print("  상태:", inspect.getgeneratorstate(r))


# ── 예제 6: yield from의 위임 ────────────────────────
print("\n=== yield from 위임 ===")

def inner():
    while True:
        x = yield
        if x is None:
            break
        print(f"    inner가 받음: {x}")

def outer():
    print("    outer 시작")
    yield from inner()          # send가 inner까지 전달됨
    print("    outer 끝")

o = outer()
next(o)
o.send("A")
o.send("B")
print("  → send가 outer를 통과해 inner에 도달한다")


# ── 예제 7: 제너레이터의 return 값 ───────────────────
print("\n=== return 값 회수 ===")

def counted():
    count = 0
    for x in [1, 2, 3]:
        yield x
        count += 1
    return f"총 {count}개 생성"

def wrapper():
    result = yield from counted()
    print(f"    하위 반환값: {result}")

print("  값들:", end=" ")
for v in wrapper():
    print(v, end=" ")
print()


# ── 예제 8: 손으로 만든 스케줄러 (이벤트 루프 원형) ──
print("\n=== 협조적 멀티태스킹 ===")

def task(name, steps):
    for i in range(steps):
        print(f"    {name}: 스텝 {i}")
        yield                   # 여기서 양보

tasks = [task("A", 3), task("B", 2), task("C", 4)]

print("  스케줄러 실행:")
while tasks:
    for t in list(tasks):
        try:
            next(t)             # 한 스텝씩 진행
        except StopIteration:
            tasks.remove(t)
print("  → 이게 이벤트 루프의 원형이다 (24장)")