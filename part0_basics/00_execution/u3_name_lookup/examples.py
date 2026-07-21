"""u3 예제: 세 가지 이름 조회를 바이트코드로 구분한다.

실행: python examples.py
"""
import dis

# ── 예제 1: 지역 vs 전역 ─────────────────────────────
x = 10

def use_global():
    return x

def use_local():
    y = 10
    return y

print("=== use_global ===")
dis.dis(use_global)      # LOAD_GLOBAL — 이름 문자열로 dict 조회
print("\n=== use_local ===")
dis.dis(use_local)       # LOAD_FAST — 배열 인덱스


# ── 예제 2: co_varnames vs co_names ──────────────────
import math

def mixed(a):
    b = a * 2
    return math.sqrt(b)

print("\n=== 이름이 어디에 저장되나 ===")
print("co_varnames (지역, 인덱스로 접근):", mixed.__code__.co_varnames)
print("co_names    (전역·속성, 문자열로 조회):", mixed.__code__.co_names)
print()
dis.dis(mixed)
# 관찰: LOAD_GLOBAL math → LOAD_ATTR sqrt 두 단계를 매번 거친다


# ── 예제 3: 내장 함수는 두 번 뒤진다 ─────────────────
def use_builtin(items):
    return len(items)

print("\n=== 내장 함수 ===")
dis.dis(use_builtin)
# LOAD_GLOBAL len — 모듈 전역에 없으면 builtins에서 다시 찾는다
print("len이 모듈 전역에 있나?:", "len" in globals())
import builtins
print("builtins에 있나?      :", "len" in vars(builtins))


# ── 예제 4: 전역은 실행 중에 바뀔 수 있다 ────────────
print("\n=== 왜 전역은 인덱스로 못 바꾸나 ===")
globals()["동적이름"] = 42
print("실행 중 추가된 전역:", 동적이름)
# 컴파일 시점에 이 이름의 존재를 알 수 없다 → 위치 확정 불가