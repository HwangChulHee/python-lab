"""
opcodes/ — opcode 핸들러 레지스트리

이 패키지는 '평가 루프가 명령 하나를 만났을 때 무엇을 하는가'를 opcode별로
모아 둔 곳이다. 새 opcode 지원 = 어딘가에 @opcode 핸들러 하나 추가.

  P1        → core.py 한 파일에 전부.
  커리큘럼   → 장이 진행되며 파일을 늘려 간다. 예: iteration.py(반복문 opcode),
              closures.py(클로저 opcode). 파일을 쪼개는 것 자체가 학습 활동이다.

핸들러 시그니처: fn(pvm, frame, ins) -> str | None
  - 반환한 문자열 = 그 스텝의 구체 설명(뷰어 설명 박스에 표시).
  - None 반환 = 그 스텝 기록을 아예 생략(RESUME 같은 노이즈).

CALL / RETURN_VALUE / RETURN_CONST 은 여기 없다. 프레임을 만들고 부수는 명령은
'개별 연산'이 아니라 '기계 구조'라서, 평가 루프(pvm.py) 본체에 직접 박혀 있다.
그 doc만 여기 등록해 둔다.
"""

OPCODE_HANDLERS = {}   # {opname: fn(pvm, frame, ins) -> str | None}
OPCODE_DOCS = {}       # {opname: 일반 설명(한국어)}


def opcode(name, doc):
    """opcode 핸들러 등록 데코레이터. name=opcode 이름, doc=뷰어용 일반 설명."""
    def deco(fn):
        OPCODE_HANDLERS[name] = fn
        OPCODE_DOCS[name] = doc
        return fn
    return deco


# ---- 프레임을 만들고 부수는 명령 (핸들러는 pvm.py 루프 본체에 있음) --------------
OPCODE_DOCS["CALL"] = (
    "스택에서 인자들과 함수 객체를 pop → 그 함수 객체의 __code__로 새 Frame을 "
    "만들어 프레임 스택에 push → 명령 포인터가 새 코드 객체로 넘어간다. "
    "네 층(함수 객체·코드 객체·프레임·평가 루프)이 전부 맞물리는 명령. "
    "대상이 파이썬 함수면 프레임을 쌓고, 내장/C 함수면 C에 위임한다.")
OPCODE_DOCS["RETURN_VALUE"] = (
    "스택 맨 위를 반환값으로 들고 현재 프레임을 통째로 소멸시킨다. 반환값은 "
    "아래(호출자) 프레임의 값 스택에 올라가고, 호출자는 멈췄던 지점부터 재개한다.")
OPCODE_DOCS["RETURN_CONST"] = (
    "RETURN_VALUE의 최적화판(3.12+): 상수를 스택에 올렸다 도로 내리는 대신 "
    "co_consts의 값을 바로 반환한다. 프레임 소멸은 동일.")

# 각 opcode 모듈을 import해 @opcode 등록을 실제로 일으킨다. (레지스트리 정의 뒤에 와야 함)
# 새 장을 열 때 여기에 한 줄씩 추가한다.
from . import core        # noqa: E402,F401  P1: 스택 머신 기본
from . import iteration   # noqa: E402,F401  P2: for 루프·컴프리헨션·첨자·언패킹 (03장)
from . import closures    # noqa: E402,F401  P2: 셀·클로저·MAKE_FUNCTION (07장)
from . import generators  # noqa: E402,F401  P3: 제너레이터 opcode 설명 (10장)
