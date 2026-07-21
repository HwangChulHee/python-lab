"""
iteration.py — 이터레이션 관련 opcode (커리큘럼 03장)

for 루프·리스트 컴프리헨션·첨자 접근·언패킹이 여기서 처리된다.

── for 루프의 뼈대 (3.12 실측) ─────────────────────────────────
    GET_ITER      반복 대상 → 이터레이터로 변환
  ┌ FOR_ITER      이터레이터에서 다음 값을 뽑아 push. 소진되면 루프 밖으로 점프
  │ ...루프 몸통...
  └ JUMP_BACKWARD  FOR_ITER로 되감기
    END_FOR       (소진 후) 스택에 남은 이터레이터를 정리

  주의: 3.12의 FOR_ITER는 소진돼도 이터레이터를 pop하지 않는다. 밖으로 점프한
  자리의 END_FOR가 그 이터레이터를 pop한다. (버전마다 다르니 실측이 기준.)

── 컴프리헨션 (PEP 709, 3.12) ──────────────────────────────────
  3.12부터 리스트/딕트/셋 컴프리헨션은 '인라인' 실행된다 — 별도 코드 객체나
  프레임을 만들지 않고 바깥 프레임에서 바로 돈다. LOAD_FAST_AND_CLEAR / SWAP은
  루프 변수(x)의 바깥 값을 잠시 치워 뒀다가 끝나고 복원하는 장치다. (3.11 이하의
  '컴프리헨션마다 프레임 생성' 설명은 여기 해당 없음.)
"""

from . import opcode
from ..generator import MiniGenerator


# ================================================================ 이터레이터
@opcode("GET_ITER",
        "스택 맨 위의 반복 대상을 pop해서 그 이터레이터를 push. iter(obj)에 해당. "
        "for 루프의 준비 단계. 스택효과 0")
def _get_iter(pvm, frame, ins):
    obj = frame.value_stack.pop()
    if isinstance(obj, MiniGenerator):         # 제너레이터는 자기 자신이 이터레이터
        frame.value_stack.append(obj)
        return f"{obj!r}은 이미 이터레이터 — 그대로 push (FOR_ITER가 resume으로 소비)"
    frame.value_stack.append(iter(obj))
    return f"{obj!r}의 이터레이터를 만들어 push (iter 호출)"


@opcode("FOR_ITER",
        "스택 맨 위의 이터레이터(그대로 둔 채)에서 다음 값을 뽑아 push. 소진되면 "
        "값을 밀지 않고 지정 offset으로 점프해 루프를 빠져나간다. 3.12에선 이터레이터를 "
        "여기서 pop하지 않고, 점프한 자리의 END_FOR가 정리한다. 스택효과 +1 (또는 점프)")
def _for_iter(pvm, frame, ins):
    it = frame.value_stack[-1]                 # 이터레이터는 pop하지 않고 들여다본다
    target = frame.offset_to_index[ins.argval]

    # 대상이 MiniGenerator면 next()를 인라인 호출할 수 없다(재개는 프레임 스택을 태워야
    # 한다). 소진 시 이 for가 빠져나갈 자리를 on_stop으로 알려주고 재개를 맡긴다.
    if isinstance(it, MiniGenerator):
        if it.state == "COMPLETED":
            frame.ip = target
            return "제너레이터 이미 소진 → 루프 밖으로 점프"
        pvm._resume_generator(it, None, ("for", frame, target))
        return None                            # resume이 프레임을 push하고 자체 기록

    try:
        value = next(it)
    except StopIteration:
        frame.ip = target
        return "이터레이터 소진 → 루프 밖으로 점프 (이터레이터는 END_FOR가 정리)"
    frame.value_stack.append(value)
    return f"다음 값 {value!r}을 push (이터레이터는 스택에 그대로 남는다)"


@opcode("END_FOR",
        "소진된 for 루프 뒤처리: 스택에 남은 이터레이터를 pop해 버린다. 스택효과 -1")
def _end_for(pvm, frame, ins):
    frame.value_stack.pop()
    return "루프 종료 — 남은 이터레이터를 스택에서 정리"


# ================================================================ 컨테이너 만들기/추가
@opcode("BUILD_TUPLE",
        "스택에서 값 N개를 pop해 튜플 하나로 묶어 push. 인자 N이 원소 개수. 스택효과 -(N-1)")
def _build_tuple(pvm, frame, ins):
    n = ins.arg
    items = tuple(frame.value_stack.pop() for _ in range(n))[::-1]
    frame.value_stack.append(items)
    return f"값 {n}개를 pop → 튜플 {items!r}로 묶어 push"


@opcode("LIST_APPEND",
        "스택 맨 위 값을 pop해서, 스택 아래쪽 i번째에 있는 리스트에 append한다. "
        "컴프리헨션 전용 — 일반 list.append(LOAD_ATTR+CALL)보다 빠른 지름길. 스택효과 -1")
def _list_append(pvm, frame, ins):
    item = frame.value_stack.pop()
    target = frame.value_stack[-ins.arg]       # pop 뒤 기준으로 i칸 아래의 리스트
    target.append(item)
    return f"{item!r}을 pop → 컴프리헨션 결과 리스트에 append (누적: {target!r})"


# ================================================================ 컴프리헨션 인라인 장치
@opcode("LOAD_FAST_AND_CLEAR",
        "지역 변수를 push하면서 그 슬롯을 비운다(없던 변수면 NULL을 push). 3.12 인라인 "
        "컴프리헨션이 루프 변수의 바깥 값을 잠시 치워 뒀다가 끝나고 복원하려고 쓴다. 스택효과 +1")
def _load_fast_and_clear(pvm, frame, ins):
    name = ins.argval
    value = frame.local_vars.pop(name, None)   # 없으면 None(=NULL 자리표시자)
    frame.value_stack.append(value)
    return f"지역 변수 {name}의 값을 push하고 슬롯을 비움 (컴프리헨션이 바깥 값 보관)"


@opcode("SWAP",
        "스택 맨 위와 아래에서 N번째 값을 맞바꾼다. 컴프리헨션이 이터레이터·결과 "
        "리스트·보관값의 순서를 정리할 때 쓴다. 스택효과 0")
def _swap(pvm, frame, ins):
    n = ins.arg
    s = frame.value_stack
    s[-1], s[-n] = s[-n], s[-1]
    return f"스택 맨 위와 {n}번째 값을 맞바꿈"


# ================================================================ 첨자 접근 / 언패킹
@opcode("BINARY_SUBSCR",
        "obj[key]. 스택에서 key와 obj를 pop, obj[key]를 push. 실제로는 __getitem__ "
        "호출. 스택효과 -1")
def _binary_subscr(pvm, frame, ins):
    key = frame.value_stack.pop()
    obj = frame.value_stack.pop()
    frame.value_stack.append(obj[key])
    return f"{obj!r}[{key!r}] → {obj[key]!r} push (__getitem__)"


@opcode("STORE_SUBSCR",
        "obj[key] = value. 스택에서 key, obj, value를 pop해 대입. __setitem__ 호출. 스택효과 -3")
def _store_subscr(pvm, frame, ins):
    key = frame.value_stack.pop()
    obj = frame.value_stack.pop()
    value = frame.value_stack.pop()
    obj[key] = value
    return f"{obj!r}[{key!r}] = {value!r} (__setitem__)"


@opcode("UNPACK_SEQUENCE",
        "스택 맨 위의 시퀀스를 pop해 원소 N개를 '역순으로' push한다(맨 왼쪽 원소가 맨 위에 오게). "
        "a, b = pair 같은 다중 대입의 정체. 스택효과 -1+N")
def _unpack_sequence(pvm, frame, ins):
    seq = frame.value_stack.pop()
    for v in reversed(list(seq)[: ins.arg]):
        frame.value_stack.append(v)
    return f"{seq!r}를 원소 {ins.arg}개로 펼쳐 push (다중 대입)"
