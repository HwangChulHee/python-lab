"""
pvm.py — MiniPVM: 비재귀 평가 루프 + 트레이스 기록

CPython ceval의 뼈대만 재현한다. 핵심 설계는 '프레임 스택 리스트를 유일한
진실로 삼는 단일 while 루프'다.

── 왜 비재귀인가 ────────────────────────────────────────────────
  재귀 구현(CALL을 만나면 파이썬 함수 재귀로 하위 프레임을 실행)은 우리 프레임이
  파이썬 콜스택에 갇혀 버린다. 그러면 나중에 YIELD_VALUE(프레임을 소멸시키지 않고
  보관했다가 재개하는 명령)를 구현할 수 없다. 프레임 스택을 명시적 리스트로 두고
  '항상 맨 위 프레임을 한 스텝 실행'하는 단일 루프로 만들면, 프레임의 수명이 우리
  손 안에 남는다. 이게 실제 CPython ceval의 구조이기도 하다. P1에서 제너레이터를
  구현하진 않지만, '나중에 가능하도록' 지금 이 구조로 만들어 둔다.

── 왜 CALL/RETURN은 레지스트리가 아니라 루프 본체에 있나 ─────────────
  프레임을 만들고(CALL) 부수는(RETURN) 명령은 값 하나를 밀고 당기는 '개별 연산'이
  아니라, 기계가 프레임 스택을 조작하는 '구조' 그 자체다. 그래서 opcode 핸들러
  레지스트리가 아니라 평가 루프 안에 직접 박아 둔다.
"""

import inspect
import textwrap

from .frame import Frame, fmt, fmt_cell, reset_obj_labels
from .inspector import code_attr_snapshot, func_attr_values, build_func_attrs
from .opcodes import OPCODE_HANDLERS, OPCODE_DOCS


class MiniPVM:
    """평가 루프 + 프레임 스택. 매 스텝을 스냅샷으로 기록해 HTML용 트레이스를 만든다."""

    def __init__(self):
        self.frame_stack = []                  # 프레임 스택 (리스트 끝이 맨 위) — 유일한 진실
        self.listings = {}                     # {코드key: 바이트코드 목록}    (뷰어용)
        self.sources = {}                      # {코드key: 소스 줄들}          (뷰어용)
        self.code_attrs = {}                   # {코드key: 코드 객체 속성}     (뷰어용, 불변)
        self.names = {}                        # {코드key: 사람이 읽는 함수 이름} (뷰어 표시용)
        self.steps = []                        # 스텝 스냅샷 목록              (뷰어용)
        self._last_func_snap = {}              # {id(func): {속성:값}} — diff 계산용
        reset_obj_labels()                     # <objN> 라벨을 트레이스마다 초기화

    # ---------------------------------------------------------- 진입점: CALL의 최초 형태
    def call(self, func, args):
        """최초 진입. 프레임 하나를 쌓고 평가 루프를 돌린다.

        같은 MiniPVM 인스턴스에 call을 여러 번 하면 트레이스가 이어서 쌓인다
        (데모 ⑤: 같은 함수 객체를 3회 호출하며 __defaults__ diff를 관찰)."""
        frame = Frame(func, args)
        self._capture_code(frame)
        self.frame_stack.append(frame)
        arg_str = ", ".join(repr(a) for a in args)
        self.record(f"CALL → {func.__name__}({arg_str}) 프레임 생성, 프레임 스택에 push",
                    None, None)
        return self._loop()

    # ---------------------------------------------------------- 평가 루프 (단일 while)
    def _loop(self):
        """ceval.c의 _PyEval_EvalFrameDefault에 해당. 항상 맨 위 프레임을 한 스텝 실행."""
        result = None
        while self.frame_stack:
            frame = self.frame_stack[-1]       # 항상 맨 위 프레임을 실행
            ins = frame.instructions[frame.ip]
            executed = frame.ip
            op = ins.opname
            frame.ip += 1                      # 기본: 다음 명령 (점프 핸들러가 덮어쓸 수 있음)

            # -- CALL: 프레임을 '만드는' 기계 구조 (재귀 호출 아님 — 스택에 쌓을 뿐) --
            if op == "CALL":
                n = ins.arg
                args = [frame.value_stack.pop() for _ in range(n)][::-1]
                target = frame.value_stack.pop()
                if frame.value_stack and frame.value_stack[-1] is None:
                    frame.value_stack.pop()    # PUSH_NULL이 깔아둔 자리표시자 제거
                self.record(
                    f"CALL — 스택에서 함수 객체와 인자 {args} pop. 그 함수 객체의 "
                    f"__code__로 새 프레임을 만든다", executed, ins)

                if hasattr(target, "__code__"):            # 파이썬 함수
                    new_frame = Frame(target, args)
                    self._capture_code(new_frame)
                    self.frame_stack.append(new_frame)     # 재귀 없이 스택에 push
                    self.record(
                        f"{target.__name__} 프레임 생성 → 프레임 스택에 push. 명령 "
                        f"포인터가 새 코드 객체로 넘어간다 (다음 스텝부터 이 프레임 실행)",
                        None, None)
                    continue                               # 다음 반복에서 새 프레임이 맨 위
                else:                                       # 내장/C 함수는 C에 위임
                    r = target(*args)
                    frame.value_stack.append(r)
                    name = getattr(target, "__name__", repr(target))
                    self.record(
                        f"내장/C 함수 {name}(...) 실행 → {r!r} push (프레임을 만들지 "
                        f"않고 C에 위임)", None, None)
                    continue

            # -- RETURN: 프레임을 '부수는' 기계 구조 --
            if op in ("RETURN_VALUE", "RETURN_CONST"):
                value = frame.value_stack.pop() if op == "RETURN_VALUE" else ins.argval
                self.frame_stack.pop()                     # 프레임 소멸
                self.record(f"{op} — {frame.func_name} 프레임 통째로 소멸, {value!r} 반환",
                            None, ins)
                if self.frame_stack:                       # 호출자가 있으면
                    self.frame_stack[-1].value_stack.append(value)
                    self.record(
                        f"RETURN ← 반환값 {value!r}이 {self.frame_stack[-1].func_name} "
                        f"프레임의 값 스택에 올라옴. 멈췄던 지점부터 재개", None, None)
                    continue
                result = value                             # 최상위 반환 → 루프 종료
                continue

            # -- 나머지 전부: 레지스트리에서 핸들러를 찾아 실행 --
            handler = OPCODE_HANDLERS.get(op)
            if handler is None:
                raise NotImplementedError(
                    f"미구현 opcode: {op}\n"
                    f"→ tools/pvmlab/engine/opcodes/core.py 에 "
                    f"@opcode(\"{op}\", doc=...) 핸들러를 추가하세요.\n"
                    f"  (해당 장 전용 파일을 새로 만들어 등록해도 됩니다 — 예: "
                    f"engine/opcodes/iteration.py)\n"
                    f"  파이썬 버전에 따라 바이트코드가 다를 수 있습니다(3.12 기준 개발).")
            note = handler(self, frame, ins)
            if note is not None:                           # None = 기록 생략 (RESUME 등)
                self.record(f"{op} — {note}", executed, ins)
        return result

    # ---------------------------------------------------------- 코드 객체 캡처 (1회)
    def _capture_code(self, frame):
        """바이트코드 목록·소스·코드 객체 속성을 뷰어용으로 저장 (코드 객체당 1번)."""
        key = frame.listing_key
        if key in self.listings:
            return
        self.names[key] = frame.func_name      # 키는 co_qualname, 표시는 읽기 좋은 이름
        self.listings[key] = [
            {"off": i.offset, "op": i.opname, "arg": i.argrepr,
             "line": i.positions.lineno if i.positions else None,
             "doc": OPCODE_DOCS.get(i.opname, "(설명 미등록 opcode)")}
            for i in frame.instructions]
        try:
            src = textwrap.dedent(inspect.getsource(frame.func))
            self.sources[key] = {"first": frame.code.co_firstlineno,
                                 "lines": src.rstrip().splitlines()}
        except OSError:                        # REPL 등 소스를 못 찾는 경우
            self.sources[key] = {"first": 1, "lines": ["(소스를 찾을 수 없음)"]}
        self.code_attrs[key] = code_attr_snapshot(frame.func)

    # ---------------------------------------------------------- 스텝 기록 (스냅샷)
    def record(self, action, executed_index, ins):
        """현재 프레임 스택 전체 + 맨 위 함수 객체 속성을 한 스텝으로 스냅샷."""
        frames = []
        for i, fr in enumerate(self.frame_stack):
            frames.append({
                "name": fr.func_name,
                "key": fr.listing_key,
                "locals": {k: fmt(v) for k, v in fr.local_vars.items()},
                "cells": {k: fmt_cell(c) for k, c in fr.cells.items()},
                "stack": [fmt(v) for v in fr.value_stack],
                "active": i == len(self.frame_stack) - 1,
            })
        top = self.frame_stack[-1] if self.frame_stack else None
        self.steps.append({
            "action": action,
            "frames": frames,                  # 아래(먼저 쌓인 것) → 위 순서
            "exec": executed_index,            # 하이라이트할 명령 인덱스 (None 가능)
            "key": top.listing_key if top else None,
            "line": (ins.positions.lineno if ins and ins.positions else None),
            "opname": ins.opname if ins else None,
            "func_attrs": self._func_attrs_with_diff(top.func) if top else [],
        })

    def _func_attrs_with_diff(self, func):
        """맨 위 프레임 함수 객체의 속성 스냅샷 + 직전 스냅샷과의 diff(changed 키)."""
        values = func_attr_values(func)
        fid = id(func)
        if fid in self._last_func_snap:        # 이 함수가 전에도 활성이었으면 비교
            prev = self._last_func_snap[fid]
            changed = {n for n, v in values.items() if prev.get(n) != v}
        else:                                  # 첫 등장 → 전부 changed로 보지 않는다(노이즈 방지)
            changed = set()
        self._last_func_snap[fid] = values
        return build_func_attrs(values, changed)
