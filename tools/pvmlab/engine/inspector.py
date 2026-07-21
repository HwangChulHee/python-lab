"""
inspector.py — 코드 객체 / 함수 객체 속성 인스펙터

이 도구의 핵심 교육 장치 중 하나. "네 층" 중 위의 두 층을 눈에 보이게 한다.

  코드 객체 (func.__code__) — 불변. 컴파일 시점에 확정돼 절대 안 변한다.
                              → 함수마다 한 번만 스냅샷.
  함수 객체 (func 그 자체)   — 가변. __defaults__ 같은 건 실행 중에 자랄 수 있다.
                              → 매 스텝 스냅샷하고, 직전 스텝과 diff를 잡는다.

diff의 검증 케이스가 데모 ⑤(가변 기본값 함정)다. 같은 함수 객체를 여러 번
호출하면 __defaults__ 안의 리스트가 호출마다 자라나는 것이 changed=True로 잡힌다.
"""

import dis

from .frame import scrub_addr


# ------------------------------------------------------------------ 값 포맷
def _short(text, limit=48):
    """긴 repr은 말줄임. (뷰어가 좁아 값이 넘치는 것 방지)"""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _interpret_flags(flags):
    """co_flags(비트마스크)를 사람이 읽는 플래그명 리스트로. (OPTIMIZED, NEWLOCALS ...)"""
    return [f.strip() for f in dis.pretty_flags(flags).split(",")]


# ------------------------------------------------------------------ 코드 객체 (불변)
CODE_ATTR_DOCS = {
    "co_name":
        "이 코드 객체의 이름(대개 함수 이름). 트레이스백·디버깅에 쓰인다.",
    "co_argcount":
        "위치 매개변수의 개수. co_varnames의 앞쪽 이만큼이 매개변수 이름이다.",
    "co_varnames":
        "지역 변수 이름 배열. LOAD_FAST/STORE_FAST의 인덱스가 이 배열을 가리킨다. "
        "앞쪽 co_argcount개가 매개변수.",
    "co_names":
        "전역/속성 접근에 쓰는 이름 튜플. LOAD_GLOBAL이 참조한다. 여기엔 함수 "
        "'이름'만 있고 함수 코드는 없다는 게 핵심 — 코드는 호출 시점에 함수 객체를 "
        "통해 찾아간다.",
    "co_consts":
        "이 코드가 쓰는 상수 튜플. LOAD_CONST가 여기서 인덱스로 꺼낸다. 함수 안에 "
        "def가 있으면 그 코드 객체도 여기 상수로 들어 있다.",
    "co_freevars":
        "클로저로 바깥 스코프에서 캡처한 자유 변수 이름들. P1 데모엔 없음(빈 튜플).",
    "co_cellvars":
        "안쪽 함수가 캡처해 갈, 셀에 담기는 지역 변수 이름들. P1 데모엔 없음(빈 튜플).",
    "co_stacksize":
        "값 스택이 최대 몇 칸 필요한지 컴파일러가 미리 계산해 둔 값.",
    "co_flags":
        "코드 객체의 성질을 담은 비트플래그를 해석한 목록(OPTIMIZED, NEWLOCALS 등).",
    "co_firstlineno":
        "이 코드가 소스에서 시작하는 줄 번호.",
}


def code_attr_snapshot(func):
    """코드 객체 속성 스냅샷. 함수마다 1회(불변이므로). → [{name, value, doc}]"""
    code = func.__code__
    raw = [
        ("co_name", repr(code.co_name)),
        ("co_argcount", str(code.co_argcount)),
        ("co_varnames", repr(code.co_varnames)),
        ("co_names", repr(code.co_names)),
        ("co_consts", repr(code.co_consts)),
        ("co_freevars", repr(code.co_freevars)),
        ("co_cellvars", repr(code.co_cellvars)),
        ("co_stacksize", str(code.co_stacksize)),
        ("co_flags", ", ".join(_interpret_flags(code.co_flags))),
        ("co_firstlineno", str(code.co_firstlineno)),
    ]
    return [{"name": n, "value": _short(scrub_addr(v), 64), "doc": CODE_ATTR_DOCS[n]}
            for n, v in raw]


# ------------------------------------------------------------------ 함수 객체 (가변)
FUNC_ATTR_DOCS = {
    "__defaults__":
        "위치 매개변수의 기본값 튜플. 함수 '정의' 시점에 딱 한 번 만들어져 함수 "
        "객체에 붙는다. 기본값이 가변 객체(리스트 등)면 호출마다 그 하나를 공유해 "
        "이 튜플 안에서 자라난다 — 이것이 '가변 기본값 함정'.",
    "__kwdefaults__":
        "키워드 전용 매개변수의 기본값 딕셔너리. 없으면 None.",
    "__closure__":
        "클로저 셀들의 튜플. 각 셀이 바깥 스코프 변수 하나를 가리킨다. "
        "P1 데모엔 클로저가 없어 대부분 None.",
    "__dict__":
        "함수 객체에 임의로 붙일 수 있는 속성 딕셔너리(함수도 객체다).",
    "__globals__":
        "이 함수가 LOAD_GLOBAL로 뒤질 전역 이름공간. '정의된 모듈'의 전역 "
        "딕셔너리를 그대로 가리킨다. (값 전체는 너무 커서 키 목록만 표시)",
}


def _cell_contents_repr(cell):
    try:
        return repr(cell.cell_contents)
    except ValueError:                         # 아직 값이 안 채워진 셀
        return "빈 셀"


def _closure_repr(closure):
    if closure is None:
        return "None"
    return "(" + ", ".join(_cell_contents_repr(c) for c in closure) + ")"


def func_attr_values(func):
    """함수 객체 속성의 현재 값을 {이름: 문자열}로. diff 계산의 원천."""
    return {
        "__defaults__": repr(func.__defaults__),
        "__kwdefaults__": repr(func.__kwdefaults__),
        "__closure__": _closure_repr(func.__closure__),
        "__dict__": repr(func.__dict__),
        "__globals__": "[" + ", ".join(sorted(func.__globals__)) + "]",
    }


def build_func_attrs(values, changed_keys):
    """{이름:값} + 바뀐 키 집합 → 뷰어용 [{name, value, doc, changed}]"""
    order = ["__defaults__", "__kwdefaults__", "__closure__", "__dict__", "__globals__"]
    return [
        {"name": n, "value": _short(scrub_addr(values[n]), 48),
         "doc": FUNC_ATTR_DOCS[n], "changed": n in changed_keys}
        for n in order
    ]
