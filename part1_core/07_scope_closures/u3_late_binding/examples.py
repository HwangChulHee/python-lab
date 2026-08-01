"""u3 예제: 늦은 바인딩을 관측한다.

실행: python examples.py
"""

# ── 예제 1: 고전 함정 ────────────────────────────────
print("=== 늦은 바인딩 ===")
funcs = []
for i in range(3):
    funcs.append(lambda: i)

print("  결과:", [f() for f in funcs], "← [0,1,2]가 아니다")
print("  루프 후 i:", i)
print("  같은 cell?:", funcs[0].__closure__ is None or
      funcs[0].__closure__[0] is funcs[1].__closure__[0])


# ── 예제 2: 즉시 호출하면 문제없다 ───────────────────
print("\n=== 즉시 호출 ===")
results = []
for i in range(3):
    results.append((lambda: i)())     # 만들자마자 호출
print("  결과:", results, "← 정상")


# ── 예제 3: 해결 1 — 기본값 인자 ─────────────────────
print("\n=== 해결1: 기본값 ===")
funcs = []
for i in range(3):
    funcs.append(lambda i=i: i)
print("  결과:", [f() for f in funcs])
print("  __defaults__:", [f.__defaults__ for f in funcs])
print("  __closure__ :", [f.__closure__ for f in funcs], "← None! 클로저가 아님")


# ── 예제 4: 해결 2 — 팩토리 함수 ─────────────────────
print("\n=== 해결2: 팩토리 ===")
def make_func(i):
    return lambda: i

funcs = [make_func(i) for i in range(3)]
print("  결과:", [f() for f in funcs])
print("  각자 다른 cell:",
      funcs[0].__closure__[0] is not funcs[1].__closure__[0])
print("  cell 값들:", [f.__closure__[0].cell_contents for f in funcs])


# ── 예제 5: 해결 3 — partial ─────────────────────────
print("\n=== 해결3: partial ===")
from functools import partial

def identity(x):
    return x

funcs = [partial(identity, i) for i in range(3)]
print("  결과:", [f() for f in funcs])


# ── 예제 6: 컴프리헨션도 안전하지 않다 ───────────────
print("\n=== 컴프리헨션 ===")
funcs = [lambda: i for i in range(3)]
print("  결과:", [f() for f in funcs], "← 여전히 함정")


# ── 예제 7: 실무형 — 이벤트 핸들러 ───────────────────
print("\n=== 실무 형태 ===")

def register_bad():
    handlers = {}
    for event in ["click", "hover", "focus"]:
        handlers[event] = lambda e: f"{event} 처리: {e}"
    return handlers

def register_good():
    handlers = {}
    def make_handler(event):
        return lambda e: f"{event} 처리: {e}"
    for event in ["click", "hover", "focus"]:
        handlers[event] = make_handler(event)
    return handlers

print("  나쁨:")
for k, h in register_bad().items():
    print(f"    {k:<6} → {h('데이터')}")
print("  좋음:")
for k, h in register_good().items():
    print(f"    {k:<6} → {h('데이터')}")