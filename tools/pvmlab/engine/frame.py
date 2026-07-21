"""
frame.py — Frame 클래스

Frame = 함수 호출 1번에 대응하는 작업 공간. CPython에서도 호출마다 프레임이
하나씩 만들어진다. 프레임이 담는 것은 딱 세 가지다:

  1) 지역 변수 (local_vars)   — LOAD_FAST/STORE_FAST가 읽고 쓰는 곳
  2) 값 스택   (value_stack)  — 계산 중간값이 잠깐 올라갔다 내려오는 곳
  3) 명령 포인터 (ip)          — 지금 코드 객체의 몇 번째 명령을 실행 중인가

코드 객체(func.__code__)는 '불변의 설계도'이고, Frame은 그 설계도를 따라
실제로 값이 흐르는 '가변의 현장'이다. 같은 코드 객체로 여러 프레임을 만들 수
있다(재귀가 그 예). 그래서 지역/스택/포인터는 코드 객체가 아니라 Frame에 있다.
"""

import dis


class Frame:
    """호출 1번 = Frame 1개. 지역 변수 + 값 스택 + 명령 포인터를 담는 작업 공간."""

    def __init__(self, func, args):
        code = func.__code__
        self.func = func                       # 함수 객체 (인스펙터가 __defaults__ 등을 스냅샷)
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

        self.value_stack = []                  # 계산용 스택 (리스트 끝이 맨 위)

        # 바이트코드를 미리 풀어 리스트로. offset→인덱스 표도 만들어 둔다(점프용).
        self.instructions = list(dis.get_instructions(code))
        self.offset_to_index = {ins.offset: i for i, ins in enumerate(self.instructions)}

        self.ip = 0                            # 명령 포인터 (instructions 리스트의 인덱스)
        self.listing_key = f"{func.__name__}.__code__"


def fmt(v):
    """값 스택/지역 변수의 값을 짧은 문자열로. (뷰어 표시용 공통 규칙)"""
    if callable(v) and hasattr(v, "__name__"):
        return f"{v.__name__} 함수객체"         # 함수 객체는 이름만
    if v is None:
        return "NULL"                          # PUSH_NULL이 깔아둔 자리표시자
    r = repr(v)
    return r if len(r) <= 40 else r[:37] + "..."
