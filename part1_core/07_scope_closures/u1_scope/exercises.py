"""u1 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 어느 스코프에서 찾는가
# ═══════════════════════════════════════════════════
v = "global"

def case_a():
    return v

def case_b():
    v = "local"
    return v

def case_c():
    v = "enclosing"
    def inner():
        return v
    return inner()

def case_d():
    def inner():
        v = "inner-local"
        return v
    return inner()

print("=== 유제1 ===")
for name, fn in [("a", case_a), ("b", case_b), ("c", case_c), ("d", case_d)]:
    print(f"  case_{name}: {fn()}    예측:__")

# 각 케이스가 L/E/G 중 어디서 찾았는지:
#   a → G   b → L   c → E   d → L


# ═══════════════════════════════════════════════════
# 유제 2. 에러 예측
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")
n = 100

def f1():
    print(n)                    # A
def f2():
    n = 5
    print(n)                    # B
def f3():
    print(n)
    n = 5                       # C
def f4():
    global n
    n += 1
    return n                    # D

for name, fn in [("f1", f1), ("f2", f2), ("f3", f3), ("f4", f4)]:
    try:
        r = fn()
        print(f"  {name}: OK {r if r is not None else ''}    예측:__")
    except Exception as e:
        print(f"  {name}: {type(e).__name__}    예측:__")
""" 
A : Ok, 100
B : Ok, 5
C : 실패
D : Ok, 101
"""
# f3만 실패하는 이유를 "컴파일 시점"이라는 말을 써서 설명:
#   → 컴파일 시점에 f3은 지역변수를 사용하기로 되어있는데 print 하기 전에 n이 정의가 안되어있으니 오류가 뜨는거지


# ═══════════════════════════════════════════════════
# 유제 3. 버그 찾기 — 카운터가 안 늘어난다
# ═══════════════════════════════════════════════════
# 아래 코드는 호출 횟수를 세려 한다. 두 버전 모두 문제가 있다.

def make_counter_v1():
    count = 0
    def increment():
        count = count + 1       # 문제 1
        return count
    return increment

def make_counter_v2():
    count = 0
    def increment():
        return count + 1        # 문제 2
    return increment

print("\n=== 유제3 ===")
c1 = make_counter_v1()
try:
    print("  v1:", c1())
except Exception as e:
    print("  v1:", type(e).__name__)

c2 = make_counter_v2()
print("  v2:", c2(), c2(), c2())

# (a) v1이 실패하는 이유:
#   → count를 지역변수로 인식했는데, 정의가 없으므로 에러
# (b) v2가 에러는 안 나는데 뭐가 잘못됐나:
#   → count 값 자체를 올리지 못하지. 반복해서 호출해도.
# (c) 올바른 구현을 작성하라:
#   →
""" 
def make_counter_v3():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count       
    return increment
"""


# ═══════════════════════════════════════════════════
# 유제 4. global vs nonlocal 선택
# ═══════════════════════════════════════════════════
# 아래 두 요구사항 각각에 맞는 코드를 작성하라.

print("\n=== 유제4 ===")

# 요구 A: 모듈 전역 로그 카운트를 늘리는 함수
log_count = 0
def write_log(msg):
    # TODO
    global log_count
    log_count += 1
    return log_count

# 요구 B: 각 호출마다 독립적으로 상태를 유지하는 누적기 팩토리
#         acc = make_accumulator()
#         acc(10) → 10,  acc(5) → 15,  acc(3) → 18
def make_accumulator():
    # TODO
    total = 0
    def acc (num):
        nonlocal total
        total += num
        return total
    return acc

acc = make_accumulator()
print("  ", acc(10), acc(5), acc(3))
acc2 = make_accumulator()
print("  새 누적기:", acc2(100))

# (a) A에는 global, B에는 nonlocal을 쓴 이유:
#   → a는 뭐 계속 log_count를 어딘가 저장하고 있어야되서. 지역변수로 쓰면 사라지니. b도 마찬가지인데, 팩토리 패턴으로 작성했으니 상태관리를 enclosing 변수를 통해 할수있는거고
# (b) B를 클래스로 바꾼다면 어떤 모습일까 (코드 말고 설명으로): 
#   → 그냥 속성값을 total로 해놓으면 되지
# (c) 실무에서 A 같은 전역 카운터가 위험한 이유 하나를 들어라:
#   → 다른 연산이나 함수를 통해 count가 변경될수있으니 위험하지