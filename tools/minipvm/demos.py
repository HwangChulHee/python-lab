"""
demos.py — minipvm 관찰 대상 목록. 이 파일만 편집하면 된다.

새 관찰 대상 추가:
    @demo("제목", args=[인자들])
    def my_func(...): ...

주의: 함수는 반드시 모듈 레벨에 정의한다.
함수 안에 def를 넣으면 클로저가 되어 COPY_FREE_VARS 같은 클로저용
opcode가 생긴다 (→ 07장 스코프와 클로저에서 그 opcode를 직접 구현해볼 것).

미구현 opcode를 만나면 NotImplementedError와 함께 opcode 이름이 뜬다.
그때 minipvm.py에 @opcode(...) 핸들러를 추가하는 것이 확장 방식이다.
앞으로 각 장에서 추가하게 될 것들:
    03장 시퀀스와 반복문  → FOR_ITER, GET_ITER, BUILD_LIST
    07장 스코프와 클로저  → LOAD_DEREF, COPY_FREE_VARS, MAKE_CELL
    10장 제너레이터      → YIELD_VALUE (run 루프 구조 변경 필요 — 프레임 보존!)
    14장 클래스          → LOAD_ATTR, STORE_ATTR
"""

from minipvm import demo


@demo("① 수식 하나 — 스택 머신의 기본 동작")
def calc():
    a = 3
    b = 4
    result = a + b * 2
    return result


def double(x):
    return x * 2


@demo("② 함수 호출 — CALL이 프레임을 쌓는 순간")
def caller():
    a = 3
    return double(a) + 1


@demo("③ 재귀 — 프레임이 3층까지 쌓였다 벗겨지는 과정", args=[3])
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)