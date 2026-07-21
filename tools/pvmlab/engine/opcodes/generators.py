"""
generators.py — 제너레이터 관련 opcode의 '설명'만 등록 (커리큘럼 10장)

RETURN_GENERATOR / YIELD_VALUE 의 핸들러는 여기 없다. 프레임을 만들고·보관하고·
재개하는 명령은 CALL/RETURN과 마찬가지로 '개별 연산'이 아니라 프레임 스택을 다루는
'기계 구조'이므로 평가 루프(pvm.py) 본체에 직접 박혀 있다. 여기서는 뷰어가 바이트코드
목록에 표시할 doc만 등록한다.
"""

from . import OPCODE_DOCS

OPCODE_DOCS["RETURN_GENERATOR"] = (
    "제너레이터 함수의 첫 명령. 지금 프레임을 실행하는 대신, 그 프레임을 보관한 "
    "제너레이터 객체를 만들어 호출자에게 돌려준다. 그래서 제너레이터 함수를 '호출'해도 "
    "본문은 한 줄도 실행되지 않는다 — 객체만 손에 들어온다.")
OPCODE_DOCS["YIELD_VALUE"] = (
    "스택 맨 위 값을 '내보내되' 프레임을 소멸시키지 않고 보관한다. RETURN과의 핵심 "
    "차이가 이것 — ip와 값 스택이 그대로 살아 있어 다음 재개 때 멈춘 자리부터 이어진다. "
    "재개 시 보내진 값(next는 None, send는 그 값)이 값 스택에 다시 올라온다.")
OPCODE_DOCS["RESUME"] = OPCODE_DOCS.get("RESUME",
    "실행을 시작/재개하는 지점 표식. yield 뒤의 RESUME은 '여기서부터 다시 시작'을 뜻한다.")
