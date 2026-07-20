"""u4 예제: 값 스택과 프레임을 직접 관찰한다.

실행: python examples.py
"""
import dis
import sys

# ── 예제 1: 손 트레이스 검증 ─────────────────────────
def calc(a, b):
    x = a + b
    return x * 2

print("=== calc의 바이트코드 — README의 손 트레이스와 대조할 것 ===")
dis.dis(calc)


# ── 예제 2: 실행 중인 프레임을 직접 꺼내기 ───────────
def inner():
    frame = sys._getframe()          # 지금 이 순간의 프레임
    print("\n=== 프레임 체인 ===")
    while frame is not None:
        print(f"  {frame.f_code.co_name:<10} line {frame.f_lineno}")
        frame = frame.f_back         # 호출자의 프레임으로 이동

def outer():
    inner()

outer()
# 출력이 inner → outer → <module> 순으로 나온다.
# 트레이스백이 보여주는 것과 같은 사슬을 우리가 직접 걸어 올라간 것.


# ── 예제 3: 프레임은 호출마다 새로 생긴다 ────────────
def whoami():
    return id(sys._getframe())

a, b = whoami(), whoami()
print("\n=== 프레임 id — 호출마다 다름 ===")
print(a, b, "→ 같은 함수라도 호출마다 새 프레임:", a != b)
# u2 정리: 코드 객체(컴파일 시 1회) / 함수 객체(def 실행 시) / 프레임(호출 시)


# ── 예제 4: 콜 스택의 한계 ───────────────────────────
print("\n=== 재귀 한계 ===")
print("recursion limit:", sys.getrecursionlimit())

def down(n):
    return down(n + 1)

try:
    down(0)
except RecursionError as e:
    print("RecursionError 발생 — 프레임이 한계까지 쌓임")