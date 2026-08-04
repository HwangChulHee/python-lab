"""u2 유제"""
import inspect

# ═══════════════════════════════════════════════════
# 유제 1. send 흐름 예측
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")

def tracer():
    print("    [시작]")
    a = yield "first"
    print(f"    [a={a}]")
    b = yield "second"
    print(f"    [b={b}]")
    return "끝"

t = tracer()
print("  next(t)      →", next(t))        # 예측:__next(t) -> [시작] first
print("  t.send('X')  →", t.send("X"))    # 예측:__t.send('X') -> [a=X] second
try:
    t.send("Y")                            # 예측:__[b=Y] 
except StopIteration as e:
    print("  t.send('Y')  → StopIteration, value =", e.value)

# (a) next(t)가 반환한 값과, a에 들어간 값을 구분해서 설명하라:
#   → next(t)가 반환한 값은 
# (b) return "끝"은 어디로 가나:
#   →


# ═══════════════════════════════════════════════════
# 유제 2. priming 실험
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")

def collector():
    items = []
    while True:
        item = yield items
        items.append(item)

c = collector()

# (a) 아래 두 줄 중 하나는 실패한다. 어느 쪽이고 왜인가:
#   예측 →
try:
    result = c.send("첫 항목")
    print("  send 먼저:", result)
except TypeError as e:
    print("  send 먼저: TypeError -", e)

c2 = collector()
print("  next 먼저:", next(c2))
print("  그 다음 send:", c2.send("첫 항목"))

# (b) next(g)와 g.send(None)의 관계:
#   →


# ═══════════════════════════════════════════════════
# 유제 3. 직접 작성 — 이동 평균 계산기
# ═══════════════════════════════════════════════════
# send로 숫자를 받아 지금까지의 평균을 반환하는 코루틴을 만들어라.
#   avg = averager()
#   next(avg)         # priming
#   avg.send(10)  → 10.0
#   avg.send(20)  → 15.0
#   avg.send(30)  → 20.0

def averager():
    # TODO
    pass

print("\n=== 유제3 ===")
# avg = averager()
# next(avg)
# print("  ", avg.send(10), avg.send(20), avg.send(30))

# (a) 상태(합계, 개수)를 어디에 저장했나:
#   →
# (b) 07장의 클로저 방식(nonlocal)과 비교하면 무엇이 다른가:
#   →


# ═══════════════════════════════════════════════════
# 유제 4. close와 정리 보장
# ═══════════════════════════════════════════════════
# 아래 제너레이터는 파일을 흉내낸다.
# 소비자가 중간에 멈춰도 정리가 되는지 확인하라.

def fake_file_reader(lines):
    print("    [열림]")
    try:
        for line in lines:
            yield line
    finally:
        print("    [닫힘]")

print("\n=== 유제4 ===")

# (A) 끝까지 소진
print("  A) 전부 읽기:")
for line in fake_file_reader(["a", "b", "c"]):
    print("    읽음:", line)

# (B) 중간에 break
print("  B) 중간에 break:")
for line in fake_file_reader(["a", "b", "c"]):
    print("    읽음:", line)
    if line == "b":
        break

# (a) B에서도 [닫힘]이 출력되나? 예측 후 확인:
#   예측 →
# (b) 출력됐다면 누가 close를 호출한 것인가:
#   →
# (c) 이 성질이 FastAPI의 `yield` 의존성(get_db)에서 어떻게 쓰이나:
#   →


# ═══════════════════════════════════════════════════
# 유제 5. 미니 스케줄러 확장
# ═══════════════════════════════════════════════════
# 예제 8의 스케줄러를 확장하라.
# 요구: 각 태스크가 "완료 메시지"를 return하고, 스케줄러가 그것을 수집한다.

def task(name, steps):
    for i in range(steps):
        yield
    return f"{name} 완료 ({steps}스텝)"

def scheduler(tasks):
    results = []
    # TODO: 모든 태스크를 한 스텝씩 돌아가며 실행하고,
    #       StopIteration의 value에서 반환값을 수집하라
    return results

print("\n=== 유제5 ===")
# print("  ", scheduler([task("A", 3), task("B", 1), task("C", 2)]))

# (a) 반환값을 어떻게 꺼냈나:
#   →
# (b) 이 스케줄러가 asyncio 이벤트 루프와 다른 점 하나:
#   →   (힌트: 지금은 무엇을 기다리는가? 실제 이벤트 루프는?)