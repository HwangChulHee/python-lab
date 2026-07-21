"""
frame.py — Frame 클래스 + 값 표시 헬퍼

Frame = 함수 호출 1번에 대응하는 작업 공간. CPython에서도 호출마다 프레임이
하나씩 만들어진다. 프레임이 담는 것:

  1) 지역 변수 (local_vars)   — LOAD_FAST/STORE_FAST가 읽고 쓰는 곳
  2) 셀 변수   (cells)        — LOAD_DEREF/STORE_DEREF가 읽고 쓰는 곳 (클로저 P2)
  3) 값 스택   (value_stack)  — 계산 중간값이 잠깐 올라갔다 내려오는 곳
  4) 명령 포인터 (ip)          — 지금 코드 객체의 몇 번째 명령을 실행 중인가

코드 객체(func.__code__)는 '불변의 설계도'이고, Frame은 그 설계도를 따라 실제로
값이 흐르는 '가변의 현장'이다. 같은 코드 객체로 여러 프레임을 만들 수 있다(재귀,
그리고 make_adder가 만든 add1/add5처럼 코드 객체를 공유하는 함수들).
"""

import dis
import types


class Frame:
    """호출 1번 = Frame 1개. 지역 변수 + 셀 변수 + 값 스택 + 명령 포인터."""

    def __init__(self, func, args):
        code = func.__code__
        self.func = func                       # 함수 객체 (인스펙터가 __defaults__/__closure__ 스냅샷)
        self.code = code                       # 코드 객체 (읽기 전용 참조 — 불변)
        self.func_name = func.__name__
        self.globals = func.__globals__        # LOAD_GLOBAL이 뒤질 곳 — 함수 객체에 붙어 있다

        # 매개변수 = co_varnames의 앞쪽 co_argcount개. 인자를 그 이름에 묶어 지역 변수로.
        arg_names = code.co_varnames[: code.co_argcount]
        self.local_vars = dict(zip(arg_names, args))

        # 넘겨받지 못한 뒤쪽 매개변수는 __defaults__로 채운다. 기본값은 '복사하지 않고'
        # 그대로 참조한다 — 가변 기본값(리스트 등)이 공유되는 것이 CPython 그대로이고,
        # 데모 ⑤(가변 기본값 함정)가 성립하는 이유다.
        defaults = func.__defaults__ or ()
        first_default = len(arg_names) - len(defaults)   # 기본값이 붙는 첫 매개변수 인덱스
        for idx in range(len(args), len(arg_names)):
            self.local_vars[arg_names[idx]] = defaults[idx - first_default]

        self.cells = {}                        # {이름: types.CellType} — 셀 변수 (클로저)
        self.value_stack = []                  # 계산용 스택 (리스트 끝이 맨 위)

        # 바이트코드를 미리 풀어 리스트로. offset→인덱스 표도 만들어 둔다(점프용).
        self.instructions = list(dis.get_instructions(code))
        self.offset_to_index = {ins.offset: i for i, ins in enumerate(self.instructions)}

        self.ip = 0                            # 명령 포인터 (instructions 리스트의 인덱스)
        self.generator = None                  # 이 프레임이 제너레이터의 것이면 그 MiniGenerator (P3)
        self.namespace = None                  # 클래스 본문 프레임의 이름 dict (STORE_NAME/LOAD_NAME) (P4)
        self.produces = None                   # RETURN 시 특수 산출: ("class",...) / ("init", obj) (P4)

        # 코드 객체를 유일하게 식별하는 키. co_qualname을 쓰면 같은 코드 객체를 공유하는
        # 함수(add1/add5)는 같은 키로 묶이고(정확), 서로 다른 코드 객체는 다른 키가 된다.
        self.listing_key = code.co_qualname


# ================================================================ 값 표시 헬퍼
#
# 가변 컨테이너(list/dict/set)에는 짧은 객체 라벨 <objN>을 붙인다. 같은 객체가
# 두 이름으로 실리면 같은 라벨이 붙어 '별칭(같은 객체)'임이 눈에 보인다 (데모 ch06).
# 라벨은 트레이스마다 초기화한다(reset_obj_labels).

_OBJ_LABELS = {}


def reset_obj_labels():
    _OBJ_LABELS.clear()


def _obj_label(v):
    key = id(v)
    if key not in _OBJ_LABELS:
        _OBJ_LABELS[key] = f"obj{len(_OBJ_LABELS) + 1}"
    return _OBJ_LABELS[key]


def _short_repr(v):
    r = repr(v)
    return r if len(r) <= 34 else r[:31] + "..."


def fmt(v):
    """값 스택/지역 변수의 값을 짧은 문자열로. (뷰어 표시용 공통 규칙)"""
    lbl = getattr(v, "_pvm_label", None)       # 엔진 마커용 표시 훅 (예: __build_class__)
    if lbl:
        return lbl
    if isinstance(v, types.CellType):
        return f"셀({fmt_cell(v)})"
    if isinstance(v, (list, dict, set)):
        return f"{_short_repr(v)} <{_obj_label(v)}>"   # 가변 객체 → 객체 라벨 부착
    if isinstance(v, type):
        return f"{v.__name__} 클래스"          # 클래스(type)도 콜러블이지만 함수 아님
    if callable(v) and hasattr(v, "__name__"):
        return f"{v.__name__} 함수객체"         # 함수 객체는 이름만
    if v is None:
        return "NULL"                          # PUSH_NULL이 깔아둔 자리표시자
    # 사용자 정의 클래스의 인스턴스 — 짧게 (상세 __dict__는 인스턴스 패널에서)
    if hasattr(v, "__dict__") and not isinstance(v, types.ModuleType) and not callable(v):
        return f"{type(v).__name__} 인스턴스<{_obj_label(v)}>"
    return _short_repr(v)


def fmt_cell(cell):
    """셀 객체의 내용을 짧은 문자열로. 빈 셀(아직 값이 없는 셀)은 '빈 셀'."""
    try:
        contents = cell.cell_contents
    except ValueError:                         # 아직 값이 안 채워진 셀
        return "빈 셀"
    if isinstance(contents, (list, dict, set)):
        return f"{_short_repr(contents)} <{_obj_label(contents)}>"
    return _short_repr(contents)
