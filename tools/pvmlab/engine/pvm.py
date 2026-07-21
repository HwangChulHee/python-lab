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

from .frame import Frame, fmt, fmt_cell, reset_obj_labels, _obj_label, scrub_addr
from .generator import MiniGenerator, gsend
from .classes import BUILD_CLASS
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
        self.generators = []                   # 만들어진 MiniGenerator 전부 (보관 프레임 표시용)
        self.user_classes = set()              # 우리가 만든 클래스들 (인스턴스 생성 가로채기용)
        self.instances = []                    # 만들어진 인스턴스들 (인스턴스 패널 + __dict__ diff)
        self._last_func_snap = {}              # {id(func): {속성:값}} — diff 계산용
        self._last_inst_snap = {}              # {id(inst): __dict__ 문자열} — diff 계산용
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
                # 3.12 호출 규약: 스택은 [콜러블, self_or_NULL, 인자...] 모양이다.
                #  · 일반 호출 f(x): 콜러블 아래에 NULL 자리표시자가 깔려 있다.
                #  · 메서드/데코레이터 g@f: NULL 대신 진짜 self/피장식 함수가 있고, 그것이 arg0이 된다.
                top1 = frame.value_stack.pop()             # 맨 위: 콜러블 또는 self/arg0
                below = frame.value_stack.pop()            # 그 아래: NULL 또는 콜러블
                if below is None:                          # 일반 호출
                    target = top1
                else:                                      # 메서드/데코레이터 — self가 첫 인자
                    target = below
                    args = [top1] + args

                # 제너레이터 구동 가로채기: next(gen) / gsend(gen, value).
                # gsend는 파이썬 함수라 __code__가 있으니 아래 일반 분기보다 먼저 가로챈다.
                if args and isinstance(args[0], MiniGenerator) and (target is next or target is gsend):
                    gen = args[0]
                    sent = args[1] if target is gsend else None
                    drv = "gsend" if target is gsend else "next"
                    if gen.state == "COMPLETED":
                        raise StopIteration(f"{gen.label}은 이미 소진된 제너레이터")
                    self.record(f"CALL {drv}({gen.label}) — 보관된 제너레이터를 재개하라는 요청",
                                executed, ins)
                    self._resume_generator(gen, sent, ("next", frame))
                    continue

                # 클래스 짓기 가로채기: __build_class__(본문함수, 이름, 베이스...).
                # 클래스 본문을 '우리 프레임'으로 실행하려고 C 위임 대신 직접 태운다.
                if target is BUILD_CLASS:
                    body_func, name, bases = args[0], args[1], tuple(args[2:])
                    self.record(f"CALL __build_class__ — 클래스 '{name}'의 본문을 새 "
                                f"네임스페이스 dict에서 프레임으로 실행 (본문도 코드다)", executed, ins)
                    body_frame = Frame(body_func, [])
                    body_frame.namespace = {}
                    body_frame.produces = ("class", name, bases, body_frame.namespace)
                    self._capture_code(body_frame)
                    self.frame_stack.append(body_frame)
                    self.record(f"{name} 클래스 본문 프레임 push — STORE_NAME이 네임스페이스 "
                                f"dict를 채운다 (그 dict가 곧 클래스 __dict__)", None, None)
                    continue

                # 인스턴스 생성 가로채기: 우리가 만든 클래스를 호출하면 __init__을 프레임으로 실행.
                if target in self.user_classes:
                    obj = target.__new__(target)
                    self.instances.append(obj)
                    init = getattr(target, "__init__", None)
                    self.record(f"CALL {target.__name__}(...) — 인스턴스 생성(__new__). "
                                f"__init__이 있으면 프레임으로 실행", executed, ins)
                    if hasattr(init, "__code__"):                # 파이썬 정의 __init__ (object.__init__은 __code__ 없음)
                        init_frame = Frame(init, [obj] + args)   # self = obj가 첫 지역 변수
                        init_frame.produces = ("init", obj)
                        self._capture_code(init_frame)
                        self.frame_stack.append(init_frame)
                        self.record(f"{target.__name__}.__init__ 프레임 push — self가 "
                                    f"첫 지역 변수로 들어온다", None, None)
                    else:                                        # __init__ 없음 → 인스턴스 바로 반환
                        frame.value_stack.append(obj)
                        self.record(f"{target.__name__} 인스턴스를 호출자 스택에 push "
                                    f"(__init__ 없음)", None, None)
                    continue

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

            # -- RETURN_GENERATOR: 프레임을 '보관하는' 기계 구조 (제너레이터 생성) --
            # 제너레이터 함수의 첫 명령. 지금 프레임을 실행하지 않고, 이 프레임을 보관한
            # 제너레이터 객체를 만들어 호출자에게 돌려준다. (본문은 0줄 실행)
            if op == "RETURN_GENERATOR":
                gen = MiniGenerator(frame, f"{frame.func_name}#{len(self.generators) + 1}")
                frame.generator = gen
                self.generators.append(gen)
                self.frame_stack.pop()                     # 프레임 스택에서 떼어 보관(CREATED)
                self.record(
                    f"RETURN_GENERATOR — {gen.label} 제너레이터 객체 생성. 본문을 실행하지 "
                    f"않고 프레임을 보관(CREATED). 호출한 함수를 '호출'해도 본문은 0줄 실행", None, ins)
                if self.frame_stack:
                    self.frame_stack[-1].value_stack.append(gen)
                    self.record(f"제너레이터 객체 {gen.label}이 호출자 스택에 push", None, None)
                continue

            # -- YIELD_VALUE: 프레임을 '보관하되 소멸시키지 않는' 기계 구조 --
            if op == "YIELD_VALUE":
                value = frame.value_stack.pop()
                gen = frame.generator
                gen.state = "SUSPENDED"
                self.frame_stack.pop()                     # 프레임을 스택에서 떼어 보관 (ip·값 스택 보존)
                on_stop = gen.on_stop
                self.record(
                    f"YIELD_VALUE — 값 {value!r}을 내보내고 {gen.label} 프레임을 소멸시키지 "
                    f"않은 채 보관(SUSPENDED). RETURN과의 차이가 이것이다", None, ins)
                if self.frame_stack:                       # 재개를 요청한 프레임에게 값 전달
                    self.frame_stack[-1].value_stack.append(value)
                    self.record(f"yield된 값 {value!r}이 재개 요청 프레임의 값 스택에 올라옴", None, None)
                continue

            # -- RETURN: 프레임을 '부수는' 기계 구조 --
            if op in ("RETURN_VALUE", "RETURN_CONST"):
                value = frame.value_stack.pop() if op == "RETURN_VALUE" else ins.argval
                self.frame_stack.pop()                     # 프레임 소멸

                if frame.generator is not None:            # 제너레이터 본문 종료 = StopIteration
                    gen = frame.generator
                    gen.state = "COMPLETED"
                    self.record(f"{op} — 제너레이터 {gen.label} 본문 종료 → COMPLETED "
                                f"(StopIteration 의미)", None, ins)
                    info, gen.on_stop = gen.on_stop, None
                    if info and info[0] == "for":          # for 소비 중이었으면 루프 밖으로
                        _, for_frame, target = info
                        for_frame.ip = target
                        self.record("소진 감지 → for 루프를 빠져나감 (남은 제너레이터는 "
                                    "END_FOR가 정리)", None, None)
                    continue

                if frame.produces is not None:             # 클래스 본문 / __init__ 특수 산출 (P4)
                    kind = frame.produces[0]
                    if kind == "class":
                        _, name, bases, ns = frame.produces
                        cls = type(name, bases, dict(ns))  # 네임스페이스 dict → 클래스 객체
                        self.user_classes.add(cls)
                        self.record(f"클래스 본문 종료 → type('{name}', {tuple(b.__name__ for b in bases)}, "
                                    f"네임스페이스)로 클래스 객체 생성", None, ins)
                        produced = cls
                    else:                                  # ("init", obj)
                        produced = frame.produces[1]
                        self.record(f"__init__ 종료 → 초기화된 인스턴스를 호출자에게 반환", None, ins)
                    if self.frame_stack:
                        self.frame_stack[-1].value_stack.append(produced)
                        self.record(f"{fmt(produced)}이 호출자 스택에 push", None, None)
                    continue

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

    # ---------------------------------------------------------- 제너레이터 재개
    def _resume_generator(self, gen, sent, on_stop):
        """보관된 제너레이터 프레임을 프레임 스택으로 되돌리고 실행을 이어 간다.

        재개의 정체가 여기 다 들어 있다: 보관해 둔 프레임(ip·값 스택 그대로)을 다시
        스택 맨 위에 올리고, 보내진 값을 그 프레임의 값 스택에 push한다. 다음 루프
        반복부터 그 프레임이 멈췄던 자리에서 이어 실행된다. next는 None을, gsend는
        준 값을 보낸다 — yield 표현식의 결과가 바로 그 값이다."""
        gen.state = "RUNNING"
        gen.on_stop = on_stop
        gen.frame.value_stack.append(sent)             # 보낸 값을 보관 프레임의 스택에 push
        self.frame_stack.append(gen.frame)             # 보관 프레임을 스택으로 복귀
        self.record(f"resume — {gen.label} 보관 프레임을 프레임 스택으로 되돌림. 보낸 값 "
                    f"{sent!r}을 값 스택에 push하고 멈췄던 자리부터 이어 실행", None, None)

    # ---------------------------------------------------------- 코드 객체 캡처 (1회)
    def _capture_code(self, frame):
        """바이트코드 목록·소스·코드 객체 속성을 뷰어용으로 저장 (코드 객체당 1번)."""
        key = frame.listing_key
        if key in self.listings:
            return
        self.names[key] = frame.func_name      # 키는 co_qualname, 표시는 읽기 좋은 이름
        self.listings[key] = [
            {"off": i.offset, "op": i.opname, "arg": scrub_addr(i.argrepr),
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
        # 보관된 제너레이터 프레임(지금 스택에 없는 것) — '보관된 프레임' 패널용.
        # 프레임이 스택 ↔ 보관 패널을 오가는 것이 P3의 하이라이트 장면이다.
        on_stack = set(id(f) for f in self.frame_stack)
        held = [self._held_snapshot(g) for g in self.generators
                if id(g.frame) not in on_stack]

        top = self.frame_stack[-1] if self.frame_stack else None
        self.steps.append({
            "action": scrub_addr(action),      # 스텝 설명에 박힌 주소도 제거 (결정적 HTML)
            "frames": frames,                  # 아래(먼저 쌓인 것) → 위 순서
            "held": held,                      # 보관된 제너레이터 프레임들
            "instances": self._instance_snapshots(),   # 만들어진 인스턴스들 (__dict__ diff)
            "exec": executed_index,            # 하이라이트할 명령 인덱스 (None 가능)
            "key": top.listing_key if top else None,
            "line": (ins.positions.lineno if ins and ins.positions else None),
            "opname": ins.opname if ins else None,
            "func_attrs": self._func_attrs_with_diff(top.func) if top else [],
        })

    def _instance_snapshots(self):
        """만들어진 인스턴스들의 __dict__·MRO 스냅샷 + 직전 스텝과의 __dict__ diff."""
        out = []
        for obj in self.instances:
            d = repr(obj.__dict__)
            oid = id(obj)
            changed = oid in self._last_inst_snap and self._last_inst_snap[oid] != d
            self._last_inst_snap[oid] = d
            out.append({
                "label": f"{type(obj).__name__} 인스턴스<{_obj_label(obj)}>",
                "cls": type(obj).__name__,
                "mro": " → ".join(k.__name__ for k in type(obj).__mro__),
                "dict": d,
                "changed": changed,
            })
        return out

    def _held_snapshot(self, gen):
        """보관된 제너레이터 프레임 하나를 스냅샷(상태·보관된 ip·값 스택 그대로)."""
        fr = gen.frame
        cur = fr.instructions[fr.ip] if fr.ip < len(fr.instructions) else None
        return {
            "label": gen.label, "name": fr.func_name, "key": fr.listing_key,
            "state": gen.state,
            "locals": {k: fmt(v) for k, v in fr.local_vars.items()},
            "cells": {k: fmt_cell(c) for k, c in fr.cells.items()},
            "stack": [fmt(v) for v in fr.value_stack],
            "ip_off": cur.offset if cur else None,
            "line": (cur.positions.lineno if cur and cur.positions else None),
        }

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
