"""u3 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 예측 — 어느 것이 함정인가
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")

# (A)
fa = [lambda: n for n in range(3)]
print("  A:", [f() for f in fa], "  예측:__")

# (B)
fb = [lambda n=n: n for n in range(3)]
print("  B:", [f() for f in fb], "  예측:__")

# (C)
def mk(n):
    return lambda: n
fc = [mk(n) for n in range(3)]
print("  C:", [f() for f in fc], "  예측:__")

# (D) — 즉시 호출
fd = [(lambda: n)() for n in range(3)]
print("  D:", fd, "  예측:__")

# (E) — 루프 변수를 안 쓰는 경우
fe = [lambda: 99 for n in range(3)]
print("  E:", [f() for f in fe], "  예측:__")

# 함정인 것과 아닌 것을 나누고, 기준을 한 문장으로:
#   →


# ═══════════════════════════════════════════════════
# 유제 2. cell 확인
# ═══════════════════════════════════════════════════
# 아래 두 방식의 __closure__와 __defaults__를 비교하라.
print("\n=== 유제2 ===")

late = [lambda: n for n in range(3)]
early = [lambda n=n: n for n in range(3)]

print("  late  __closure__ :", late[0].__closure__)
print("  late  __defaults__:", late[0].__defaults__)
print("  early __closure__ :", early[0].__closure__)
print("  early __defaults__:", early[0].__defaults__)

# (a) early 쪽이 __closure__가 None인 이유:
#   →
# (b) 이 차이가 "이른 바인딩 vs 늦은 바인딩"과 어떻게 대응하나:
#   →


# ═══════════════════════════════════════════════════
# 유제 3. 버그 수정 — 재시도 핸들러
# ═══════════════════════════════════════════════════
# API 엔드포인트별로 재시도 함수를 만드는 코드. 전부 마지막 것만 호출한다.

def make_retriers_buggy():
    retriers = {}
    for name, url in [("users", "/api/users"),
                      ("posts", "/api/posts"),
                      ("tags",  "/api/tags")]:
        def retry(times=3):
            return f"{name}: {url}를 {times}회 재시도"
        retriers[name] = retry
    return retriers

print("\n=== 유제3 ===")
for k, fn in make_retriers_buggy().items():
    print(f"  {k:<6} → {fn()}")

# (a) 캡처된 변수가 몇 개이고 cell이 몇 개인가:
#   →
# (b) 팩토리 함수 방식으로 고쳐라 (코드 작성):
#   →
# (c) 기본값 인자 방식으로도 고쳐라. 이 경우 times=3과 충돌하지 않게
#     매개변수 순서를 어떻게 해야 하나:
#   →


# ═══════════════════════════════════════════════════
# 유제 4. 판단 문제 — 이건 안전한가
# ═══════════════════════════════════════════════════
# 아래 네 코드 중 늦은 바인딩 함정이 있는 것을 고르고 이유를 쓰라.
print("\n=== 유제4 ===")

# (1)
results1 = []
for x in [1, 2, 3]:
    results1.append(x * 2)

# (2)
tasks2 = []
for x in [1, 2, 3]:
    tasks2.append(lambda: x * 2)

# (3)
def double(v):
    return v * 2
tasks3 = []
for x in [1, 2, 3]:
    tasks3.append(lambda v=x: double(v))

# (4)
from functools import partial
tasks4 = []
for x in [1, 2, 3]:
    tasks4.append(partial(double, x))

print("  1:", results1)
print("  2:", [t() for t in tasks2])
print("  3:", [t() for t in tasks3])
print("  4:", [t() for t in tasks4])

# 함정이 있는 것: __
# 각각의 이유:
#   1 →
#   2 →
#   3 →
#   4 →
#
# (심화) 1번이 안전한 근본 이유는 무엇인가? (함수를 만들지 않는다는 점에서)
#   →