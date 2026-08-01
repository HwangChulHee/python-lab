"""u2 유제"""
import dis

# ═══════════════════════════════════════════════════
# 유제 1. cell 예측
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")

def make(a, b):
    c = a + b
    def inner(d):
        return c + d          # c만 캡처
    return inner

f = make(1, 2)
print("  f(10)             :", f(10), "  예측:__13")
print("  __closure__ 길이  :", len(f.__closure__), "  예측:__? 모르겠누 1개아닐까 c만 반영되니")
print("  cell_contents     :", f.__closure__[0].cell_contents, "  예측:__3")
print("  make.co_cellvars  :", make.__code__.co_cellvars, "  예측:__3")
print("  inner.co_freevars :", f.__code__.co_freevars, "  예측:__3")

# a와 b는 왜 cell에 안 들어갔나:
#   → 내부함수인 inner가 a와 b를 사용 안하니까


# ═══════════════════════════════════════════════════
# 유제 2. 캡처 시점 — 값인가 변수인가
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")

# (A)
def case_a():
    msg = "처음"
    def show():
        return msg
    msg = "나중"
    return show
print("  A:", case_a()(), "  예측:__나중")

# (B)
def case_b():
    items = [1, 2]
    def show():
        return items
    items.append(3)           # 변경(mutation)
    return show
print("  B:", case_b()(), "  예측:__[1,2,3]")

# (C)
def case_c():
    items = [1, 2]
    def show():
        return items
    items = [9, 9]            # 재대입(rebinding)
    return show
print("  C:", case_c()(), "  예측:__[9,9]")

# B와 C가 같은 결과인가 다른 결과인가? 01장의 mutation/rebinding으로 설명:
#   → 모르겠네. 변수공유니까 이 결과 아닐까 싶기도하고 이건 헷갈리네


# ═══════════════════════════════════════════════════
# 유제 3. 버그 찾기 — 설정이 공유된다
# ═══════════════════════════════════════════════════
# 여러 개의 로거를 만드는 팩토리. 그런데 전부 같은 prefix를 쓴다.

def make_loggers():
    loggers = []
    prefix = ""
    for p in ["[INFO]", "[WARN]", "[ERROR]"]:
        prefix = p
        def log(msg):
            return f"{prefix} {msg}"
        loggers.append(log)
    return loggers

print("\n=== 유제3 ===")
for lg in make_loggers():
    print(" ", lg("테스트"))

# (a) 세 로거가 전부 같은 prefix를 쓰는 이유 (cell로 설명):
#   → 이거 헷갈리네;; prepix라는 변수를 공유해서 ERROR를 사용하게 되는건가? 구조를 모르겠네
# (b) cell이 몇 개 만들어졌나? 왜 그런가:
#   → 1개인가? prefix는 한개니까?
# (c) 각 로거가 자기 prefix를 갖게 하려면? (두 가지 방법)
#   방법1 (함수를 한 겹 더) → ? 모르겠누
#   방법2 (기본값 인자 활용) →


# ═══════════════════════════════════════════════════
# 유제 4. 직접 구현 — 상태를 가진 함수
# ═══════════════════════════════════════════════════
# 호출할 때마다 이전 값과의 차이를 반환하는 함수를 클로저로 만들어라.
#   d = make_delta()
#   d(10) → 10   (처음이므로 10 - 0)
#   d(15) → 5
#   d(12) → -3

def make_delta():
    # TODO
    previous_num = 0
    def delta(current_num):
        nonlocal previous_num
        result = current_num - previous_num
        previous_num = current_num           # 이 줄이 있어야 함
        return result
    return delta

print("\n=== 유제4 ===")
d = make_delta()
print("  ", d(10), d(15), d(12))
d2 = make_delta()
print("  독립:", d2(100))

# (a) nonlocal이 필요했나? 왜:
#   → 외부 값을 초기화하지 않고 쓰기 위해서
# (b) 이걸 클래스로 바꾸면 어떤 점이 나아지나:
#   → 이전값을 쉽게 조회할 수 있겠지
# (c) 만약 "지금까지의 최댓값"도 같이 추적해야 한다면
#     클로저와 클래스 중 무엇을 택하겠나 (EP Item 33 기준):
#   → 클래스 골라야지 따로 저장하는 메서드도 만들테고