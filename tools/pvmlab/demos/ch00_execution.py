"""
ch00_execution.py — 00장 '실행 모델' 데모 5개

★ 모든 데모 함수는 반드시 '모듈 레벨'에 정의한다 ★
   함수 안에 def를 넣으면 그 안쪽 함수가 클로저가 되어 P1 미지원 opcode
   (COPY_FREE_VARS 등)가 생긴다. 그래서 서로 호출하는 함수들도 전부 모듈 레벨에
   나란히 둔다. (클로저 opcode는 커리큘럼 07장에서 직접 구현하며 열어 볼 것.)

데모 목록:
   ① 수식 하나        — 스택 머신의 기본 동작
   ② 함수 호출        — CALL이 프레임을 쌓는 순간 (바이트코드 패널 전환)
   ③ 재귀             — 프레임 3층, 대기 프레임이 값 스택을 유지
   ④ 이름 조회 대결   — LOAD_GLOBAL(co_names) vs LOAD_FAST(co_varnames)
   ⑤ 가변 기본값 함정 — __defaults__가 호출마다 자라는 diff (인스펙터 검증 케이스)
"""

from demos import demo


# ============================================================ ① 수식 하나
@demo("① 수식 하나 — 스택 머신의 기본 동작")
def calc():
    a = 3
    b = 4
    result = a + b * 2
    return result


# ============================================================ ② 함수 호출
def double(x):
    return x * 2


@demo("② 함수 호출 — CALL이 프레임을 쌓는 순간")
def caller():
    a = 3
    return double(a) + 1


# ============================================================ ③ 재귀
@demo("③ 재귀 — 프레임이 3층까지 쌓였다 벗겨지는 과정", args=(3,))
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)


# ============================================================ ④ 이름 조회 대결
# 전역을 읽는 함수와 지역을 읽는 함수를 한 트레이스에서 나란히 실행한다.
#   read_global → LOAD_GLOBAL CONFIG (co_names 경유, 문자열 키 조회)
#   read_local  → LOAD_FAST config  (co_varnames 인덱스, 배열 접근)
# 인스펙터의 code_attrs에서 각 함수의 co_names / co_varnames를 비교해 보라.
CONFIG = 42   # 모듈 전역 변수


def read_global():
    return CONFIG * 2      # CONFIG는 지역에 없으니 LOAD_GLOBAL


def read_local(config):
    return config * 2      # config는 매개변수 → LOAD_FAST


@demo("④ 이름 조회 대결 — LOAD_GLOBAL(co_names) vs LOAD_FAST(co_varnames)")
def name_lookup():
    return read_global() + read_local(10)


# ============================================================ ⑤ 가변 기본값 함정
# bucket의 기본값 []는 '함수 정의 시점'에 딱 한 번 만들어져 __defaults__에 붙는다.
# 호출마다 그 하나를 공유하므로, 제자리 연산 += 로 늘리면 __defaults__ 안의 리스트가
# 호출을 거듭할수록 자라난다. 인스펙터 diff가 이 성장을 changed=True로 잡는다.
#
# 참고: 흔한 형태 bucket.append(item) 는 LOAD_ATTR(속성 접근, P2)을 만든다.
#       P1 범위 안에서 '같은 객체를 제자리에서 늘리는' 동일한 함정을 보이려고
#       += 를 썼다 (BUILD_LIST + BINARY_OP(+=), 둘 다 P1 opcode).
@demo("⑤ 가변 기본값 함정 — __defaults__가 호출마다 자란다",
      calls=[(1,), (2,), (3,)])
def append_to(item, bucket=[]):
    bucket += [item]
    return bucket

@demo("⑥ u2 유제3 — @deco 와 손수 f=deco(f) 는 같은가 (deco_style)")
def deco_style():
    def logger(fn):            # 고정 인자 래퍼 (*args는 CALL_FUNCTION_EX 필요 — 미구현)
        def wrapper(x, y):
            return fn(x, y)
        return wrapper

    @logger
    def add(x, y):
        return x + y

    return add(1, 2)           # 3


@demo("⑦ u2 유제3 — 손수 치환 (manual_style): STORE 가 한 번 더 있다")
def manual_style():
    def logger(fn):
        def wrapper(x, y):
            return fn(x, y)
        return wrapper

    def sub(x, y):
        return x - y
    sub = logger(sub)          # ← @logger 와 같은 일

    return sub(5, 3)           # 2

@demo("8 u4 유제1")
def mystery(a, b):
    c = a * b
    d = c + a
    return d