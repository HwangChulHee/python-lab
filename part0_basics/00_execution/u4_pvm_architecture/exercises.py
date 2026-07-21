"""u4 유제 — 예측 → 관측(pvmlab) → 오차 수정"""
import dis
import sys

# ═══════════════════════════════════════════════════
# 유제 1. 손 트레이스 → pvmlab 대조
# ═══════════════════════════════════════════════════
def mystery(a, b):
    c = a * b
    d = c + a
    return d

# (a) dis를 돌리지 말고, 바이트코드와 각 명령 후 스택 상태를 먼저 예상해서 쓸 것:
"""
내 예상:
RESUME 0

LOAD_FAST 0 (a)
LOAD_FAST 1 (b)
BINARY_OP 5 (*)
STORE_FAST 2 (c)

LOAD_FAST 2 (c)
LOAD_FAST 0 (a)
BINARY_OP 0 (+)
STORE_FAST 3 (d)

RETURN_VALUE
"""
# (b) dis로 명령 목록 확인:
print("=== dis 확인 ===")
dis.dis(mystery)

# (c) pvmlab으로 스택 상태까지 대조:
#     tools/pvmlab/demos/ch00_execution.py에 mystery를 데모로 추가하고
#     python run.py ch00 → HTML에서 한 스텝씩 넘기며 내 예상과 대조.
#     (데모 추가 방법은 기존 데모 형식을 그대로 따라하면 됨 — 모듈 레벨 def!)
#
# 예상과 달랐던 지점과 이유:
#   → 맞았음


# ═══════════════════════════════════════════════════
# 유제 2. manual_style을 스택으로 재해석
# ═══════════════════════════════════════════════════
# u2의 manual_style 바이트코드:
#   LOAD_CONST <code f> / MAKE_FUNCTION / STORE_FAST f
#   LOAD_GLOBAL (NULL + logger) / LOAD_FAST f / CALL 1 / STORE_FAST f
#
# 각 줄 실행 후 스택 상태를 쓰고 (NULL 슬롯 포함!),
# deco_style과 달리 "장식 전 f가 이름에 묶이는 순간"이 어디인지 짚어라:
"""
트레이스:
LOAD_CONST <code f> [f의 코드객체]
MAKE_FUNCTION [f의 함수객체]
STORE_FAST f []

LOAD_GLOBAL (NULL + logger) [NULL, logger]
LOAD_FAST f [NULL, logger, f]
CALL 1 []
STORE_FAST f [?]


장식 전 f가 이름에 묶이는 지점:
STORE_FAST f, 지역 변수 f에 f의 함수객체를 저장하라는 의미니까
"""


# ═══════════════════════════════════════════════════
# 유제 3. 트레이스백 = 프레임 체인 검증
# ═══════════════════════════════════════════════════
def level3():
    raise ValueError("바닥")

def level2():
    level3()

def level1():
    level2()

# (a) 예측: level1() 호출 시 트레이스백의 함수 이름 순서는?
#   예측 → l3, l2, l1, module
#
# (b) 실행해서 확인 (주석 해제):
level1()
#
# (c) examples.py 예제 2(프레임 체인을 f_back으로 걷기)의 출력 순서와
#     같은가 반대인가? 왜?
#   → 그러게 왜;; level1부터 실행됐지? level1이 스택 맨 아래에 있는거 아닌가