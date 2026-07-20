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
#   → B. target이라는 변수에 A를 출력하는 함수객체가 저장되었는데, 이후에 B를 출력하는 함수개체가 덮어씌여졌기 때문에
#   
# 실제 출력:
print("유제1:", make()())
#
# 예측과 달랐다면 왜? 맞았다면 근거는?
#   → B 출력됨. 근거는 위에서 말했던 것과 같다.


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
print("double.__closure__       :", double.__closure__[0].cell_contents)

# Q1. double과 triple은 동작이 다른데 코드 객체는 같다.
#     그렇다면 n=2와 n=3의 차이는 "어디에" 저장되어 있는가?
#     (힌트: double.__closure__ 를 출력해 볼 것 — 07장 선행 맛보기)
#   → 함수 객체 안에 있는 closure에 저장되어있다.
#
# Q2. 위 사실로부터, 함수 객체와 코드 객체의 역할 분담을 한 문장으로:
#   → 코드객체는 변하지 않는 함수의 로직을 저장하고, 함수객체는 정의될떼(def가 실행될때) 변하는 정보들을 저장한다.


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
#   → 이건 잘 모르겠음;
'''
 === deco_style ===
 80           0 RESUME                   0

 81           2 LOAD_GLOBAL              0 (logger)

 82          12 LOAD_CONST               1 (<code object f at 0x7f9b4611e0b0, file "/home/hch/python-lab/part0_basics/00_execution/u2_def_is_statement/exercises.py", line 81>)
             14 MAKE_FUNCTION            0

 81          16 CALL                     0

 82          24 STORE_FAST               0 (f)

 84          26 LOAD_FAST                0 (f)
             28 RETURN_VALUE

Disassembly of <code object f at 0x7f9b4611e0b0, file "/home/hch/python-lab/part0_basics/00_execution/u2_def_is_statement/exercises.py", line 81>:
 81           0 RESUME                   0

 83           2 RETURN_CONST             0 (None)




  === manual_style ===
 86           0 RESUME                   0

 87           2 LOAD_CONST               1 (<code object f at 0x7f9b4611e180, file "/home/hch/python-lab/part0_basics/00_execution/u2_def_is_statement/exercises.py", line 87>)
              4 MAKE_FUNCTION            0
              6 STORE_FAST               0 (f)

 89           8 LOAD_GLOBAL              1 (NULL + logger)
             18 LOAD_FAST                0 (f)
             20 CALL                     1
             28 STORE_FAST               0 (f)

 90          30 LOAD_FAST                0 (f)
             32 RETURN_VALUE

Disassembly of <code object f at 0x7f9b4611e180, file "/home/hch/python-lab/part0_basics/00_execution/u2_def_is_statement/exercises.py", line 87>:
 87           0 RESUME                   0

 88           2 RETURN_CONST             0 (None)

==============================deco_style==============================
LOAD_GLOBAL logger      ← logger를 스택에 올림 (호출 준비를 먼저!)
LOAD_CONST <code f>     ← f의 악보를 올림
MAKE_FUNCTION           ← f 함수 객체 생성
CALL 0                  ← logger(f) 호출
STORE_FAST f            ← 그 결과를 f에 저장

==============================manual_style==============================
LOAD_CONST <code f>     ← f의 악보를 올림
MAKE_FUNCTION           ← f 함수 객체 생성
STORE_FAST f            ← f에 저장 (1번째 저장!)
LOAD_GLOBAL logger      ← logger를 올림
LOAD_FAST f             ← f를 다시 꺼냄
CALL 1                  ← logger(f) 호출
STORE_FAST f            ← 결과를 f에 저장 (2번째 저장!)


LOAD_* — 뭔가를 스택에 올림 (_CONST 상수, _FAST 지역, _GLOBAL 전역, _ATTR 속성)
STORE_* — 스택 맨 위 값을 이름에 저장
CALL — 스택에 올려둔 함수를 인자와 함께 호출
MAKE_FUNCTION — 코드 객체로 함수 객체 생성 (u2에서 본 것)
RETURN_* — 반환
BINARY_OP — 이항 연산 (+, *, ** 등)
JUMP_* / POP_JUMP_* — 분기 (if, 루프)
'''
#
# Q2. add.__name__ 을 출력하면 뭐가 나올까? 예측 후 확인하고, 왜 그런지 설명:
#   예측 → 예측했어야되는데 안함..
print("\n  add.__name__ :", add.__name__)
#   실제 이유 → wrapper가 나옴. logger 자체는 wrapper를 출력하기 때문이다.
#
# Q3. 데코레이터가 "def가 실행문이기 때문에" 가능한 이유를 한 문장으로:
#   → 문제 의도를 잘 모르겠는데, def가 실행문이기 때문에 데코레이터가 아래 정의된 함수를 인자로 받은뒤, wrapping 함수에 넣은뒤에 
#   원래 정의된 함수 이름으로 다시 할당이 가능한거지