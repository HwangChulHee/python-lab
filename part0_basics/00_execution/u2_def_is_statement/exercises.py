"""u2 유제

실행: python exercises.py
"""
import dis

# ═══════════════════════════════════════════════════
# 유제 1. 출력 예측 (실행 전에 먼저 예측할 것)
# ═══════════════════════════════════════════════════
def make():
    def target():
        return "A"
    if True:
        def target():
            return "B"
    return target

# 실행 전 내 예측:
#   →
#
# 실제 출력:
print("유제1:", make()())
#
# 예측과 달랐다면 왜? 맞았다면 근거는?
#   →


# ═══════════════════════════════════════════════════
# 유제 2. 함수 객체 / 코드 객체 구분
# ═══════════════════════════════════════════════════
def factory(n):
    def multiply(x):
        return x * n
    return multiply

double = factory(2)
triple = factory(3)

print("\n유제2:")
print("  double(5)               :", double(5))
print("  triple(5)               :", triple(5))
print("  double is triple        :", double is triple)
print("  같은 코드 객체?          :", double.__code__ is triple.__code__)

# Q1. double과 triple은 동작이 다른데 코드 객체는 같다.
#     그렇다면 n=2와 n=3의 차이는 "어디에" 저장되어 있는가?
#     (힌트: double.__closure__ 를 출력해 볼 것 — 07장 선행 맛보기)
#   →
#
# Q2. 위 사실로부터, 함수 객체와 코드 객체의 역할 분담을 한 문장으로:
#   →


# ═══════════════════════════════════════════════════
# 유제 3. 데코레이터는 문법 설탕이다
# ═══════════════════════════════════════════════════
def logger(fn):
    def wrapper(*args, **kwargs):
        print(f"    [log] {fn.__name__} 호출됨")
        return fn(*args, **kwargs)
    return wrapper

# (A) 데코레이터 문법
@logger
def add(x, y):
    return x + y

# (B) 데코레이터 없이 손으로
def sub(x, y):
    return x - y
sub = logger(sub)          # ← 이 줄이 @logger와 같은 일을 한다

print("\n유제3:")
print("  add(1, 2) =", add(1, 2))
print("  sub(5, 3) =", sub(5, 3))

# Q1. (A)와 (B)가 정말 같은지 dis로 확인해 보자.
#     아래 두 함수의 바이트코드를 비교하고, 차이가 있는지 없는지 관찰:
def deco_style():
    @logger
    def f():
        pass
    return f

def manual_style():
    def f():
        pass
    f = logger(f)
    return f

print("\n  === deco_style ===")
dis.dis(deco_style)
print("\n  === manual_style ===")
dis.dis(manual_style)

# 관찰 결과 (두 바이트코드의 공통점과 차이점):
#   →
#
# Q2. add.__name__ 을 출력하면 뭐가 나올까? 예측 후 확인하고, 왜 그런지 설명:
#   예측 →
print("\n  add.__name__ :", add.__name__)
#   실제 이유 →
#
# Q3. 데코레이터가 "def가 실행문이기 때문에" 가능한 이유를 한 문장으로:
#   →