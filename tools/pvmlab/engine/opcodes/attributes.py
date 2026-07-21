"""
attributes.py — 속성 접근과 클래스 (커리큘럼 14/15/16장)

여기서 두 개의 하이라이트가 나온다.

  1) 클래스 본문도 '프레임에서 실행되는 코드'다.
     class 문은 (1) 본문을 코드 객체로 만든 함수 → (2) __build_class__(본문, 이름, 베이스)
     호출 로 컴파일된다. 본문 프레임 안에서는 지역 슬롯(STORE_FAST)이 아니라
     네임스페이스 dict(STORE_NAME)에 이름이 쌓인다 — 그 dict가 그대로 클래스의 __dict__가 된다.

  2) 속성 접근의 진실 (LOAD_ATTR).
     obj.x 는 먼저 인스턴스 __dict__ 를 보고, 없으면 type(obj).__mro__ 를 순서대로 뒤진다.
     이 조회 경로를 스텝 설명에 화살표로 그려 준다.
"""

import types

from . import opcode
from ..classes import BUILD_CLASS


# ================================================================ 클래스 짓기
@opcode("LOAD_BUILD_CLASS",
        "클래스를 짓는 함수(__build_class__)를 스택에 push. 이어지는 CALL이 "
        "__build_class__(본문함수, 이름, 베이스...)를 불러 클래스를 만든다. class 문의 정체.")
def _load_build_class(pvm, frame, ins):
    frame.value_stack.append(BUILD_CLASS)
    return "클래스를 짓는 함수 __build_class__를 push (class 문 = 이 함수 호출)"


# ================================================================ 네임스페이스 (클래스 본문)
@opcode("STORE_NAME",
        "스택 맨 위를 pop해 '네임스페이스 dict'에 이름으로 저장. 함수 본문의 "
        "STORE_FAST(지역 배열)와 달리 dict 조회다 — 클래스 본문·모듈 최상위에서 쓰인다. "
        "여기 쌓인 것이 그대로 클래스의 __dict__가 된다. 스택효과 -1")
def _store_name(pvm, frame, ins):
    frame.namespace[ins.argval] = frame.value_stack.pop()
    return f"pop → 네임스페이스['{ins.argval}']에 저장 (지역 슬롯이 아니라 dict — 클래스 본문)"


@opcode("LOAD_NAME",
        "이름을 네임스페이스 dict → 전역 → builtins 순으로 찾아 push. 지역 배열 인덱스 "
        "접근이 아니라 문자열 조회다(클래스 본문·모듈 최상위). 스택효과 +1")
def _load_name(pvm, frame, ins):
    name = ins.argval
    if frame.namespace is not None and name in frame.namespace:
        value = frame.namespace[name]
        where = "네임스페이스"
    elif name in frame.globals:
        value = frame.globals[name]
        where = "전역"
    else:
        import builtins
        value = getattr(builtins, name)
        where = "builtins"
    frame.value_stack.append(value)
    return f"{where}에서 '{name}'을 찾아 push"


# ================================================================ 속성 읽기/쓰기
@opcode("STORE_ATTR",
        "obj.attr = value. 스택에서 obj(위)와 value(아래)를 pop해 setattr. 인스턴스 "
        "__dict__에 키가 생긴다(대개). self.x = ... 의 정체. 스택효과 -2")
def _store_attr(pvm, frame, ins):
    obj = frame.value_stack.pop()
    value = frame.value_stack.pop()
    setattr(obj, ins.argval, value)
    return f"{_who(obj)}.{ins.argval} = {value!r} 설정 (인스턴스 __dict__에 기록)"


@opcode("LOAD_ATTR",
        "obj.attr 를 읽어 push. 조회 순서: 인스턴스 __dict__ → type(obj).__mro__의 각 "
        "클래스 __dict__. 3.12의 메서드 변형(argrepr에 'NULL|self')은 곧 호출할 메서드를 "
        "위해 (함수, self)를 함께 올려 CALL이 self를 첫 인자로 받게 한다. 스택효과 +1 또는 +2")
def _load_attr(pvm, frame, ins):
    obj = frame.value_stack.pop()
    name = ins.argval
    path = _describe_lookup(obj, name)

    if ins.arg & 1:                            # 메서드 변형: (함수, self)를 올린다
        func = _find_in_mro(obj, name)
        if isinstance(func, types.FunctionType):
            frame.value_stack.append(func)     # 콜러블(함수) — 아래
            frame.value_stack.append(obj)      # self — 위 (CALL이 첫 인자로 받음)
            return f"{_who(obj)}.{name} 메서드 로드 → (함수, self) push. 조회: {path}"
        # 메서드가 아니면 일반 값 + NULL 자리표시자
        value = getattr(obj, name)
        frame.value_stack.append(None)
        frame.value_stack.append(value)
        return f"{_who(obj)}.{name} → 값 push (+NULL). 조회: {path}"

    value = getattr(obj, name)                 # 일반 속성 읽기
    frame.value_stack.append(value)
    return f"{_who(obj)}.{name} → {value!r} push. 조회: {path}"


# ================================================================ 조회 경로 서술 헬퍼
def _who(obj):
    if isinstance(obj, type):
        return f"{obj.__name__}(클래스)"
    return f"{type(obj).__name__} 인스턴스"


def _find_in_mro(obj, name):
    """type(obj).__mro__ 에서 name을 찾아 그 원본 값(함수 등)을 반환. 없으면 None."""
    for klass in type(obj).__mro__:
        if name in klass.__dict__:
            return klass.__dict__[name]
    return None


def _describe_lookup(obj, name):
    """속성 조회 경로를 화살표 문자열로. 예: 인스턴스.__dict__ ✗ → Dog.__dict__ ✓"""
    steps = []
    if not isinstance(obj, type):
        inst_dict = getattr(obj, "__dict__", {})
        if name in inst_dict:
            return f"인스턴스.__dict__ ✓ ('{name}' 발견)"
        steps.append("인스턴스.__dict__ ✗")
        mro = type(obj).__mro__
    else:
        mro = obj.__mro__                      # 클래스 자체의 속성 조회
    for klass in mro:
        if name in klass.__dict__:
            steps.append(f"{klass.__name__}.__dict__ ✓")
            return " → ".join(steps)
        steps.append(f"{klass.__name__}.__dict__ ✗")
    return " → ".join(steps) + " → (못 찾음)"
