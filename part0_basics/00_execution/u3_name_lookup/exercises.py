"""u3 유제"""
import dis
import timeit

# ═══════════════════════════════════════════════════
# 유제 1. 바이트코드 예측
# ═══════════════════════════════════════════════════
import math

TAX = 0.1

def total(items):
    result = 0
    for price in items:
        result += price * (1 + TAX)
    return math.floor(result)

# (a) dis 돌리기 전에 예측:
#     - 이 함수에서 LOAD_FAST로 읽히는 이름은?      →  result, price
#     - LOAD_GLOBAL로 읽히는 이름은?                → TAX, math
#     - LOAD_ATTR로 읽히는 이름은?                  → floor
#     - co_varnames에 들어갈 것 / co_names에 들어갈 것은?
#         co_varnames → result, price
#         co_names    → TAX, math, floor
#
# (b) 확인:
print("=== 유제1 ===")
print("co_varnames:", total.__code__.co_varnames)
print("co_names   :", total.__code__.co_names)
dis.dis(total)
#
# (c) 틀린 부분과 이유:
#   → items를 안했누.


# ═══════════════════════════════════════════════════
# 유제 2. 실측 — 예측을 먼저 쓸 것
# ═══════════════════════════════════════════════════
# measure.py를 실행하기 전에 예측:
#   실험 2에서 LOAD_GLOBAL은 LOAD_FAST의 몇 배 느릴까?
#     예측 → 아 미리 돌려봄. 근데 예상 가능한가? 몇 배 느린지...
#   실험 3에서 속성 조회는 LOAD_FAST의 몇 배일까?
#     예측 → 몰루
#
# 실행 후 실제 수치:
#   실험 2 → LOAD_GLOBAL : 0.114s, LOAD_FAST   : 0.103s, 배율        : 1.11배
#   실험 3 →OAD_GLOBAL+LOAD_ATTR : 0.134s, LOAD_FAST 대비        : 1.31배
#
# 예측과 크게 달랐다면 왜 그렇게 예측했는지, 무엇을 놓쳤는지:
#   →
#
# 이 수치를 보고, 실무에서 이 최적화를 언제 해야 한다고 생각하나:
#   → 속성이나 전역변수 미리 지역변수로 담아둬야겠지. 치명적이지는 않아서 실무에서는 근데 그렇게 하진 않을듯.


# ═══════════════════════════════════════════════════
# 유제 3. 함정 — 왜 이 코드는 에러가 날까
# ═══════════════════════════════════════════════════
count = 0

def broken():
    count += 1        # UnboundLocalError!
    return count

# (a) 실행해보기 전에 예측: 왜 전역 count를 못 읽을까?
#     힌트: 컴파일러가 co_varnames를 언제 어떻게 정하는지 생각할 것
#   예측 → 뭐지 모르겠다
#
# (b) 확인 (주석 해제):
print(broken())
#
# (c) dis로 확인 — count가 LOAD_GLOBAL인가 LOAD_FAST인가?
print("\n=== 유제3 ===")
dis.dis(broken)
#
# (d) 설명 (한 문장):
#   →