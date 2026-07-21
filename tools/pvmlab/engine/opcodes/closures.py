"""
closures.py — 클로저 관련 opcode (커리큘럼 07장) + MAKE_FUNCTION (u2 "def는 실행문")

── 셀(cell)이란 ────────────────────────────────────────────────
  안쪽 함수가 바깥 함수의 지역 변수를 계속 붙들려면, 그 변수를 '셀'이라는 상자에
  넣고 상자를 공유한다. 바깥 프레임이 사라져도 셀은 살아남아 클로저가 참조한다.
  여기선 진짜 types.CellType을 쓴다 — cell_contents가 인스펙터에 그대로 보이고,
  MAKE_FUNCTION이 만드는 함수 객체의 __closure__에도 그대로 꽂을 수 있다.

  MAKE_CELL       프레임 시작 시 셀 변수용 셀을 만든다 (인자면 그 값으로 채워서)
  LOAD_CLOSURE    셀 '객체 자체'를 스택에 push (클로저 튜플 재료)
  COPY_FREE_VARS  안쪽 프레임 시작 시 함수 객체의 __closure__ 셀들을 프레임에 복사
  LOAD_DEREF      셀의 내용(cell_contents)을 push
  STORE_DEREF     셀의 내용을 pop한 값으로 교체 (nonlocal 대입의 정체)

── MAKE_FUNCTION: "def는 실행문이다"의 물증 ────────────────────
  def는 컴파일 시점에 함수를 '만드는' 게 아니다. 실행 시점에 MAKE_FUNCTION이
  코드 객체(이미 co_consts에 상수로 들어 있던)를 꺼내 런타임에 함수 객체를 '생성'
  한다. 같은 make_adder를 두 번 실행하면 코드 객체는 하나인데 함수 객체는 둘이
  만들어지는 이유가 이것이다.
"""

import types

from . import opcode


# ================================================================ 셀 만들기/읽기/쓰기
@opcode("MAKE_CELL",
        "프레임 시작 시 셀 변수 하나를 위한 셀(상자)을 만든다. 그 이름이 매개변수였다면 "
        "받은 인자 값으로 셀을 채우고, 아니면 빈 셀로 둔다. 스택효과 0")
def _make_cell(pvm, frame, ins):
    name = ins.argval
    if name in frame.local_vars:               # 인자이면서 셀 변수 → 그 값으로 채운다
        frame.cells[name] = types.CellType(frame.local_vars.pop(name))
        return f"셀 변수 {name}을 인자 값으로 채운 셀 생성 (지역 슬롯 → 셀로 이동)"
    frame.cells[name] = types.CellType()       # 빈 셀 (STORE_DEREF가 나중에 채움)
    return f"셀 변수 {name}을 위한 빈 셀 생성"


@opcode("COPY_FREE_VARS",
        "안쪽(클로저) 프레임 시작 시, 함수 객체의 __closure__에 담긴 셀들을 이 프레임의 "
        "자유 변수 슬롯으로 복사한다. 이 순간 바깥 함수의 셀과 안쪽 프레임이 '같은 셀'을 "
        "공유하게 된다. 스택효과 0")
def _copy_free_vars(pvm, frame, ins):
    closure = frame.func.__closure__ or ()
    for i, name in enumerate(frame.code.co_freevars):
        frame.cells[name] = closure[i]         # 같은 셀 객체를 공유 (복사 아님)
    names = ", ".join(frame.code.co_freevars)
    return f"함수 객체의 __closure__ 셀을 프레임으로 가져옴: {names} (바깥과 같은 셀 공유)"


@opcode("LOAD_CLOSURE",
        "셀 '객체 자체'를 스택에 push. 값이 아니라 상자를 올린다 — 이어지는 BUILD_TUPLE + "
        "MAKE_FUNCTION이 이 셀들을 새 함수의 __closure__로 묶기 위해서다. 스택효과 +1")
def _load_closure(pvm, frame, ins):
    frame.value_stack.append(frame.cells[ins.argval])
    return f"셀 변수 {ins.argval}의 '셀 객체'를 push (값이 아니라 상자)"


@opcode("LOAD_DEREF",
        "셀의 내용(cell_contents)을 꺼내 push. 클로저가 바깥 변수의 현재 값을 읽는 통로. "
        "스택효과 +1")
def _load_deref(pvm, frame, ins):
    cell = frame.cells[ins.argval]
    frame.value_stack.append(cell.cell_contents)
    return f"셀 {ins.argval}의 내용 {cell.cell_contents!r}을 push"


@opcode("STORE_DEREF",
        "스택 맨 위를 pop해 셀의 내용을 교체한다. nonlocal 대입의 정체 — 바깥 프레임과 "
        "공유하는 셀을 고쳐 쓰므로 바깥에서도 바뀐 값이 보인다. 스택효과 -1")
def _store_deref(pvm, frame, ins):
    value = frame.value_stack.pop()
    frame.cells[ins.argval].cell_contents = value
    return f"pop → 셀 {ins.argval}의 내용을 {value!r}로 교체 (nonlocal, 바깥과 공유하는 셀)"


# ================================================================ 함수 객체 런타임 생성
@opcode("MAKE_FUNCTION",
        "스택의 코드 객체로 런타임에 '함수 객체'를 만들어 push. def는 컴파일이 아니라 "
        "실행 시점에 이 명령으로 함수를 생성한다('def는 실행문이다'). 인자 플래그에 따라 "
        "기본값·클로저 등을 함께 붙인다. 스택효과 (플래그에 따라)")
def _make_function(pvm, frame, ins):
    flags = ins.arg
    code = frame.value_stack.pop()             # 맨 위 = 코드 객체
    closure = frame.value_stack.pop() if flags & 0x08 else None    # 0x08: 클로저
    annotations = frame.value_stack.pop() if flags & 0x04 else None
    kwdefaults = frame.value_stack.pop() if flags & 0x02 else None
    defaults = frame.value_stack.pop() if flags & 0x01 else None

    func = types.FunctionType(code, frame.globals, code.co_name, defaults, closure)
    if kwdefaults:
        func.__kwdefaults__ = kwdefaults
    if annotations:
        func.__annotations__ = dict(annotations)

    extra = []
    if closure:
        extra.append(f"클로저 셀 {len(closure)}개 연결")
    if defaults:
        extra.append(f"기본값 {defaults!r}")
    tail = (" — " + ", ".join(extra)) if extra else ""
    frame.value_stack.append(func)
    return (f"코드 객체 {code.co_qualname!r}로 함수 객체 {code.co_name!r}를 런타임 "
            f"생성해 push{tail} (def는 실행문)")
