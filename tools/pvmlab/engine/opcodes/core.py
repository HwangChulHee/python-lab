"""
core.py — P1 opcode 핸들러 전부 (파이썬 3.12 기준)

각 핸들러는 @opcode(이름, doc="...")으로 레지스트리에 등록된다. 스택/지역 변수를
직접 조작하고, 그 스텝의 구체 설명 문자열을 반환한다(None이면 기록 생략).

여기 없는 opcode를 만나면 평가 루프가 NotImplementedError를 던지며 "어느 파일에
@opcode 핸들러를 추가하라"까지 안내한다. 그게 이 도구의 확장(=학습) 방식이다.
"""

import builtins
import operator

from . import opcode


# ================================================================ 프레임 시작 표식
@opcode("RESUME",
        "3.11+에서 프레임 실행을 시작/재개하는 지점을 표시하는 명령. 인터럽트 "
        "체크 정도만 하고 스택엔 아무 일도 안 한다. 스택효과 0")
def _resume(pvm, frame, ins):
    return None                                 # 기록 생략 (노이즈)


# ================================================================ 값 올리기 (push)
@opcode("LOAD_CONST",
        "코드 객체의 상수 목록 co_consts에서 값을 꺼내 스택에 push. 상수는 컴파일 "
        "시점에 이미 코드 객체 안에 저장돼 있다. 스택효과 +1")
def _load_const(pvm, frame, ins):
    frame.value_stack.append(ins.argval)
    return f"상수 {ins.argval!r}를 push (코드 객체 co_consts에 저장돼 있던 값)"


@opcode("LOAD_FAST",
        "지역 변수 배열에서 값을 꺼내 스택에 push. 이름을 문자열로 찾는 게 아니라 "
        "co_varnames 배열의 인덱스로 바로 접근해서 'FAST'. 스택효과 +1")
def _load_fast(pvm, frame, ins):
    frame.value_stack.append(frame.local_vars[ins.argval])
    return f"지역 변수 {ins.argval}의 값을 push (배열 인덱스 접근)"


@opcode("LOAD_GLOBAL",
        "함수 객체에 붙은 __globals__ 딕셔너리에서 이름을 찾아 push. 없으면 "
        "builtins까지 뒤진다. 지역과 달리 문자열 키 조회라 상대적으로 느리다. "
        "스택효과 +1 (3.11+에선 NULL도 함께 밀어 실제 +2일 수 있음)")
def _load_global(pvm, frame, ins):
    name = ins.argval
    if name in frame.globals:
        value = frame.globals[name]
    else:
        value = getattr(builtins, name)         # print, len 같은 내장
    frame.value_stack.append(value)
    where = "__globals__" if name in frame.globals else "builtins"
    return f"{where}에서 '{name}'을 찾아 push (함수 이름은 co_names 경유로 조회)"


@opcode("PUSH_NULL",
        "3.11+ 호출 규약: CALL이 나중에 참조할 NULL 자리표시자를 push. 메서드 호출 "
        "최적화의 흔적이다. 스택효과 +1")
def _push_null(pvm, frame, ins):
    frame.value_stack.append(None)
    return "호출 규약용 NULL 자리표시자 push"


# ================================================================ 값 내리기 (pop)
@opcode("STORE_FAST",
        "스택 맨 위를 pop해서 지역 변수 배열(co_varnames 인덱스)에 저장. 스택효과 -1")
def _store_fast(pvm, frame, ins):
    frame.local_vars[ins.argval] = frame.value_stack.pop()
    return f"pop → 지역 변수 {ins.argval}에 저장"


@opcode("POP_TOP",
        "스택 맨 위를 pop해서 버린다. 반환값을 안 쓰는 표현식문 뒤에 나온다. 스택효과 -1")
def _pop_top(pvm, frame, ins):
    frame.value_stack.pop()
    return "스택 맨 위 버림 (쓰지 않는 표현식 결과)"


# ================================================================ 컨테이너 만들기
@opcode("BUILD_LIST",
        "스택에서 값 N개를 pop해 리스트 하나로 묶어 push. 인자 N이 원소 개수. "
        "예: [item]은 BUILD_LIST 1. 스택효과 -(N-1)")
def _build_list(pvm, frame, ins):
    n = ins.arg
    items = [frame.value_stack.pop() for _ in range(n)][::-1]
    frame.value_stack.append(items)
    return f"값 {n}개를 pop → 리스트 {items!r}로 묶어 push"


# ================================================================ 연산
# 일반 이항 연산과 제자리(in-place, += 등) 연산을 한 핸들러로 처리한다.
# operator.iadd 등은 대상이 리스트면 __iadd__로 '같은 객체를 제자리에서' 늘린다 —
# 데모 ⑤에서 __defaults__ 안의 리스트가 자라나는 것이 바로 이 경로다.
_BIN_OPS = {
    "+": operator.add, "-": operator.sub, "*": operator.mul,
    "/": operator.truediv, "//": operator.floordiv, "%": operator.mod,
    "**": operator.pow,
    "+=": operator.iadd, "-=": operator.isub, "*=": operator.imul,
    "/=": operator.itruediv, "//=": operator.ifloordiv, "%=": operator.imod,
    "**=": operator.ipow,
}


@opcode("BINARY_OP",
        "스택에서 두 값을 pop, 이항 연산 후 결과를 push. 어떤 연산인지는 인자로 "
        "구분(+, -, *, ... 그리고 +=, *= 같은 제자리 연산). 실제로는 여기서 "
        "__add__/__iadd__ 등 특수 메서드가 불린다. 제자리 연산은 가변 객체를 "
        "새로 만들지 않고 그 자리에서 바꾼다. 스택효과 -1")
def _binary_op(pvm, frame, ins):
    b, a = frame.value_stack.pop(), frame.value_stack.pop()
    sym = ins.argrepr.strip()
    r = _BIN_OPS[sym](a, b)
    frame.value_stack.append(r)
    kind = "제자리 연산(같은 객체를 그 자리에서 변경)" if sym.endswith("=") else "연산"
    return f"{a!r}, {b!r} pop → {sym} {kind} → {r!r} push"


@opcode("COMPARE_OP",
        "스택에서 두 값을 pop, 비교 후 결과(bool)를 push. 실제로는 __lt__, __eq__ "
        "등이 불린다. 스택효과 -1")
def _compare_op(pvm, frame, ins):
    b, a = frame.value_stack.pop(), frame.value_stack.pop()
    # 3.12/3.13에서 argrepr가 "<=" 또는 "bool(<=)" 형태 — 기호만 추출한다.
    sym = ins.argrepr.strip("bool() ")
    comps = {"<": a < b, "<=": a <= b, ">": a > b,
             ">=": a >= b, "==": a == b, "!=": a != b}
    r = comps[sym]
    frame.value_stack.append(r)
    return f"{a!r} {sym} {b!r} → {r} push"


# ================================================================ 점프: 명령 포인터 이동
# 주의: 점프 대상은 offset 이므로 frame.offset_to_index로 인덱스로 바꿔 대입한다.
#       (offset을 ip에 직접 넣으면 안 된다 — ip는 instructions 리스트의 인덱스다.)
@opcode("POP_JUMP_IF_FALSE",
        "스택 맨 위를 pop해서 거짓이면 지정 offset으로 명령 포인터를 옮긴다. "
        "if문의 정체가 이것. 스택효과 -1")
def _pjif(pvm, frame, ins):
    cond = frame.value_stack.pop()
    if not cond:
        frame.ip = frame.offset_to_index[ins.argval]
        return f"조건 {cond} → offset {ins.argval}로 점프 (명령 포인터 이동)"
    return f"조건 {cond} → 점프 안 함 (다음 명령으로)"


@opcode("POP_JUMP_IF_TRUE",
        "스택 맨 위를 pop해서 참이면 지정 offset으로 점프. 스택효과 -1")
def _pjit(pvm, frame, ins):
    cond = frame.value_stack.pop()
    if cond:
        frame.ip = frame.offset_to_index[ins.argval]
        return f"조건 {cond} → offset {ins.argval}로 점프 (명령 포인터 이동)"
    return f"조건 {cond} → 점프 안 함 (다음 명령으로)"


@opcode("JUMP_FORWARD",
        "무조건 앞쪽 offset으로 점프. 스택효과 0")
def _jf(pvm, frame, ins):
    frame.ip = frame.offset_to_index[ins.argval]
    return f"offset {ins.argval}로 점프"


@opcode("JUMP_BACKWARD",
        "무조건 뒤쪽 offset으로 점프. 루프가 되감기는 지점이며, 이때 "
        "인터럽트/GIL 양보 체크도 일어난다. 스택효과 0")
def _jb(pvm, frame, ins):
    frame.ip = frame.offset_to_index[ins.argval]
    return f"offset {ins.argval}로 되감기 — 루프의 정체 (GIL 양보 체크 지점)"
