"""u1 유제"""
import functools
import inspect

# ═══════════════════════════════════════════════════
# 유제 1. 버그 찾기 — 반환값이 사라진다
# ═══════════════════════════════════════════════════
def broken_deco(fn):
    def wrapper(*args, **kwargs):
        print(f"    호출: {fn.__name__}")
        fn(*args, **kwargs)          # ← 문제
    return wrapper

@broken_deco
def multiply(a, b):
    return a * b

print("=== 유제1 ===")
print("  multiply(3, 4) =", multiply(3, 4), "  예측:__")

# (a) 왜 None이 나오나:
#   → ? return값이 없으니까 그렇지
# (b) 고쳐라:
#   →
def broken_deco2(fn):
    def wrapper(*args, **kwargs):
        print(f"    호출: {fn.__name__}")
        result = fn(*args, **kwargs)
        return result           # ← 문제
    return wrapper

@broken_deco2
def multiply(a, b):
    return a * b

print("=== 유제1 수정 ===")
print("  multiply(3, 4) =", multiply(3, 4), "  예측:__")
# (c) 이 버그가 위험한 이유 (테스트에서 잘 안 잡히는 이유):
#   → wrapper로 함수를 인식해서. 원본함수를 몰라서...


# ═══════════════════════════════════════════════════
# 유제 2. 실행 시점 예측
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")

def deco(fn):
    print("    [1] deco 본체")
    def wrapper(*a, **kw):
        print("    [2] wrapper")
        return fn(*a, **kw)
    print("    [3] wrapper 만들어짐")
    return wrapper

print("  --- 데코레이트 시작 ---")
@deco
def target():
    print("    [4] target 본체")

print("  --- 데코레이트 끝 ---")
print("  --- 호출 1회 ---")
target()
print("  --- 호출 2회 ---")
target()

# (a) [1],[3]이 몇 번 출력됐나? 왜:
#   → 1번. 데코레이터에 의해 deco가 호출될때어 wrapper가 출력할때 한번만 출력하니께
# (b) 만약 target을 한 번도 호출 안 하면 무엇이 출력되나:
#   → 1,3만 출력되고 끝이겠지. 2,4는 영원히 호출 안됨
# (c) 이 성질이 FastAPI 라우팅에 어떻게 쓰이는지 한 문장으로:
#   → ? 그냥 이렇게 쓰이겠지. 특히 사용자가 정의한 함수들이 라우팅 목록에 자동으로 저장되겠지 데코레이터를 통해 저장하는 코드를 써놨을테니


# ═══════════════════════════════════════════════════
# 유제 3. 직접 작성 — 호출 횟수 세는 데코레이터
# ═══════════════════════════════════════════════════
# 요구사항:
#   - 함수가 몇 번 호출됐는지 센다
#   - fn.call_count 로 밖에서 조회 가능해야 한다
#   - @wraps로 메타데이터 보존
#   - 원본 반환값 유지

def count_calls(fn):
    # TODO
    @functools.wraps(fn)
    def wrapper (*args, **kwargs):
        fn.call_count += 1
        return fn(*args, **kwargs)
    return wrapper

@count_calls
def hello(name):
    """인사"""
    return f"hi {name}"

# print("\n=== 유제3 ===")
# print("  ", hello("a"), hello("b"), hello("c"))
# print("  call_count:", hello.call_count)
# print("  __name__  :", hello.__name__)

# (a) call_count를 어디에 저장했나? (클로저 변수 vs wrapper의 속성)
#   →  ? 모르겠다리;
# (b) 클로저 변수(nonlocal)에 저장했다면 밖에서 조회할 수 있나? 왜:
#   →
# (c) 07장 u2의 "클로저 vs 클래스" 기준으로, 이 데코레이터는
#     어느 쪽이 더 적절한가:
#   → 흠.. 일단 한개밖에 없으니 괜찮지 않나


# ═══════════════════════════════════════════════════
# 유제 4. 파라미터 데코레이터 작성
# ═══════════════════════════════════════════════════
# 결과에 접두사를 붙이는 데코레이터를 만들어라.
#   @prefix("[LOG]")
#   def msg(): return "테스트"
#   msg()  →  "[LOG] 테스트"

def prefix(text):
    # TODO
    def decorator (fn) :
        @functools.wraps(fn)
        def wrapper (*args, **kwargs) :
            result = fn(*args, **kwargs)
            return text + "" + result
        return wrapper
    return decorator
    

print("\n=== 유제4 ===")
@prefix("[LOG]")
def msg():
    return "테스트"
print("  ", msg())


print("\n=== 유제4 - c 실험 ===")
@prefix
def msg():
    return "테스트"
print("  ", msg())
# (a) 함수를 몇 겹으로 만들었고 각 겹의 역할은:
#   → 3겹. 첫번째는 인자 처리, 두번째는 원본 보존을 위한 계층, 세번째는 최종적인 출력을 위한 계층
# (b) text는 어디에 저장되나:
#   → wrapper의 클로저
# (c) @prefix 를 괄호 없이 쓰면 (@prefix("[X]") 대신 @prefix)
#     어떤 일이 벌어지나? 예측 후 확인:
#   → text 대신 인자로 msg 라는 함수가 들어가지 않을까... 아마 컴파일부터 실패할것 같은데.