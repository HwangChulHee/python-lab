"""
run.py — pvmlab 유일한 진입점 (CLI)

  python run.py                 # demos/ 전체 → pvm_trace.html
  python run.py ch00            # 'ch00'로 시작하는 데모 모듈만
  python run.py -o custom.html  # 출력 경로 지정

각 데모를 미니 PVM으로 실행한 뒤, 진짜 CPython으로 같은 걸 실행해 결과를 assert로
대조한다("검증 OK"). 그 다음 전체 트레이스를 단일 HTML로 내보낸다.

엔진 모듈을 직접 실행하지 말고 반드시 이 파일로 실행할 것. (진입점과 라이브러리
분리 — engine/__init__.py의 설명 참조.)
"""

import argparse
import copy
import importlib
import pkgutil
import sys
import types
from pathlib import Path

# 이 파일이 있는 디렉터리를 import 경로에 올려 engine / demos 패키지를 찾게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import MiniPVM          # noqa: E402
from viewer import build_html       # noqa: E402
import demos                        # noqa: E402


def load_demos(chapter):
    """chapter(예: 'ch00')로 시작하는 데모 모듈을 import한다. None이면 전체."""
    demos.DEMOS.clear()
    names = [m.name for m in pkgutil.iter_modules(demos.__path__)
             if not m.name.startswith("_")]
    if chapter:
        names = [n for n in names if n.startswith(chapter)]
        if not names:
            sys.exit(f"'{chapter}'로 시작하는 데모 모듈이 demos/ 에 없습니다. "
                     f"(있는 것: {', '.join(m.name for m in pkgutil.iter_modules(demos.__path__))})")
    for n in sorted(names):
        importlib.import_module(f"demos.{n}")
    return list(demos.DEMOS)


def fresh_copy(func, pristine_defaults):
    """진짜 CPython 대조용으로, 오염되지 않은 기본값을 가진 함수 객체 복제.

    미니 PVM이 원본 함수의 __defaults__를 이미 변형시켰을 수 있으므로(데모 ⑤),
    실행 전에 떠 둔 pristine 기본값으로 새 함수 객체를 만들어 대조한다. 같은 함수
    객체를 재사용하면 기본값 리스트가 계속 자라 오염된다."""
    return types.FunctionType(func.__code__, func.__globals__, func.__name__,
                              pristine_defaults, func.__closure__)


def run_demo(spec):
    """데모 하나를 실행해 (트레이스 dict, 미니 PVM 결과, 진짜 CPython 결과) 반환."""
    func, args, title, calls = spec["func"], spec["args"], spec["title"], spec["calls"]

    # 실행 전에 원본 기본값을 pristine으로 떠 둔다 (미니 PVM이 변형하기 전).
    pristine = copy.deepcopy(func.__defaults__)

    pvm = MiniPVM()
    call_list = calls if calls is not None else [args]
    result = None
    for cargs in call_list:                    # calls면 같은 트레이스에 이어 기록
        result = pvm.call(func, list(cargs))

    # 진짜 CPython 대조: 오염 없는 새 함수 객체로 같은 호출 시퀀스 재현.
    ref = fresh_copy(func, pristine)
    expected = None
    for cargs in call_list:
        expected = ref(*cargs)

    trace = {"title": title, "steps": pvm.steps, "listings": pvm.listings,
             "sources": pvm.sources, "code_attrs": pvm.code_attrs, "names": pvm.names}
    return trace, result, expected


def main():
    parser = argparse.ArgumentParser(description="pvmlab — CPython 실행 모델 미니 재현")
    parser.add_argument("chapter", nargs="?", default=None,
                        help="데모 장 접두어 (예: ch00). 생략하면 demos/ 전체")
    parser.add_argument("-o", "--out", default="pvm_trace.html", help="출력 HTML 경로")
    ns = parser.parse_args()

    specs = load_demos(ns.chapter)
    if not specs:
        sys.exit("등록된 데모가 없습니다.")

    traces = []
    for spec in specs:
        trace, result, expected = run_demo(spec)
        status = "OK" if result == expected else "MISMATCH!"
        print(spec["title"])
        print(f"  미니 PVM: {result!r}  |  진짜 CPython: {expected!r}  → 검증 {status}")
        assert result == expected, \
            f"미니 PVM이 CPython과 다른 결과를 냈습니다: {result!r} != {expected!r}"
        traces.append(trace)

    build_html(traces, ns.out)
    print(f"\n생성 완료 → {ns.out}  (브라우저로 열기, 데모 {len(traces)}개)")


if __name__ == "__main__":
    main()
