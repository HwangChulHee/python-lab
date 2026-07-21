"""
engine — pvmlab 실행 엔진 (라이브러리)

진입점은 tools/pvmlab/run.py 하나뿐이다. 이 패키지의 모듈을 python -m 이나 직접
실행하지 말 것 — 이전 버전에서 같은 파일이 __main__과 일반 모듈로 이중 로드되어
데코레이터 등록이 증발하는 버그가 있었다. 진입점(run.py)과 라이브러리(engine/)를
분리해 그 문제를 구조적으로 없앴다.

네 층 중 아래 두 층이 여기 산다:
  Frame     — frame.py   (호출마다 1개: 지역 변수 + 값 스택 + 명령 포인터)
  평가 루프  — pvm.py     (코드 객체를 읽고, 프레임에 쓴다)
"""

from .frame import Frame, fmt
from .pvm import MiniPVM
from .opcodes import opcode, OPCODE_HANDLERS, OPCODE_DOCS

__all__ = ["Frame", "fmt", "MiniPVM", "opcode", "OPCODE_HANDLERS", "OPCODE_DOCS"]
