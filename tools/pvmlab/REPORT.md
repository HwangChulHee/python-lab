# pvmlab P2–P5 구현 리포트

각 페이즈의 구현 요약·설계 판단·검증 결과를 코드를 다시 읽지 않고도 검토할 수
있도록 기록한다. (P1은 `pvm_trace.html` 뷰어와 §1 네 층 모델로 완료된 상태에서 출발.)

---

## P2 — 이터레이션 + 클로저 (03/06/07장)

### 구현 요약
- **새 opcode 파일 2개**
  - `engine/opcodes/iteration.py` — GET_ITER, FOR_ITER, END_FOR, BUILD_TUPLE,
    LIST_APPEND, LOAD_FAST_AND_CLEAR, SWAP, BINARY_SUBSCR, STORE_SUBSCR, UNPACK_SEQUENCE
  - `engine/opcodes/closures.py` — MAKE_CELL, COPY_FREE_VARS, LOAD_CLOSURE,
    LOAD_DEREF, STORE_DEREF, MAKE_FUNCTION
- **엔진 변경**
  - `Frame.cells` 추가: `{이름: types.CellType}`. 셀 변수(클로저)를 지역 변수와 분리 보관.
  - `Frame.listing_key`를 `이름.__code__` → `code.co_qualname`으로 변경(유일성 보장).
    `MiniPVM.names[key]=func_name`으로 표시용 이름을 따로 들고, 뷰어가 그걸로 렌더.
  - 값 표시 헬퍼 `fmt`에 가변 컨테이너용 `<objN>` 라벨 추가(별칭=같은 객체 시각화),
    `fmt_cell`로 셀 내용 표시(빈 셀 처리 포함). 라벨은 트레이스마다 초기화.
- **인스펙터/뷰어**
  - 함수 객체 `__closure__` 스냅샷이 셀 내용 repr(빈 셀은 "빈 셀")을 표시, diff로 강조.
  - 프레임 패널에 "셀 변수" 행 신설(지역 변수와 색으로 구분).

### 내린 설계 판단과 이유
- **`bucket.append` 대신 `+=`는 P1 선례, 여기선 컴프리헨션이 이미 LIST_APPEND를 씀**:
  `.append`(LOAD_ATTR)는 여전히 P4로 미룸. 컴프리헨션의 LIST_APPEND는 attribute
  경로가 아닌 전용 opcode라 P2 범위 안에서 자연히 등장.
- **셀은 자체 클래스 대신 `types.CellType` 사용**: cell_contents가 인스펙터에
  그대로 보이고, 무엇보다 MAKE_FUNCTION이 만드는 함수 객체의 `__closure__`에 진짜
  셀을 그대로 꽂을 수 있어 `types.FunctionType(code, globals, name, defaults, closure)`가
  실제 CPython 경로와 동일하게 동작한다.
- **listing_key = co_qualname**: `make_adder(1)`·`make_adder(5)`가 만든 add1/add5는
  함수 객체는 둘이지만 코드 객체는 하나 → 같은 co_qualname → 같은 키로 묶임(정확).
  서로 다른 코드 객체는 qualname이 달라 충돌 없음. 표시는 `names` 맵으로 짧은 이름 유지.
- **컴프리헨션 인라인(PEP 709) 실측 반영**: 3.12는 컴프리헨션마다 프레임을 만들지
  않고 바깥 프레임에서 인라인 실행한다. LOAD_FAST_AND_CLEAR/SWAP은 루프 변수의 바깥
  값을 잠시 치웠다 복원하는 장치. 정상 실행 경로는 예외 테이블(RERAISE/POP_TOP,
  offset 40~48)을 절대 건드리지 않으므로 예외 기구 없이 완전 동작 — P2 범위 준수.
- **FOR_ITER 소진 처리 실측**: 3.12의 FOR_ITER는 소진돼도 이터레이터를 pop하지 않고
  루프 밖(END_FOR)으로 점프하며, END_FOR가 이터레이터를 pop한다. 그대로 구현.
- **BUILD_LIST는 P1 core.py에 이미 있어 이동/중복 등록하지 않음**(핸드오프는
  iteration.py 소속으로 적었으나 재등록은 레지스트리 덮어쓰기라 그대로 둠).
- **추가 데모 ch06 ④(첨자·언패킹)**: 핸드오프가 iteration.py 소속으로 명시한
  BINARY_SUBSCR/STORE_SUBSCR/UNPACK_SEQUENCE를 실제로 실행·검증하기 위해 데모를
  하나 더 뒀다(죽은 코드 방지, §0.6 취지).

### 실측에서 확정한 opcode (예상과 다른 점)
- 컴프리헨션: `LOAD_FAST_AND_CLEAR`, `SWAP`, `END_FOR`, 그리고 예외 테이블
  (`RERAISE`) 등장 — 예상 목록엔 없던 것. 정상 경로는 앞의 둘 + END_FOR만 필요.
- for 루프: `END_FOR`가 소진 정리를 담당(예상의 "FOR_ITER가 pop" 아님).
- 클로저: `LOAD_CLOSURE`가 별도 opcode로 존재(LOAD_DEREF와 구분 — 값이 아니라 셀
  객체를 올린다). MAKE_CELL/COPY_FREE_VARS는 프레임 첫 명령(offset 0)으로 등장.

### 검증 결과 (전부 통과)
- 데모 11개(P1 5 + P2 6) 전부 진짜 CPython과 assert 대조 OK, `python run.py` 무에러.
- 검증2: ch07 클로저 데모에서 add1/add5가 단일 코드 객체 키(`make_adder.<locals>.add`)
  하나를 공유함을 트레이스로 확인.
- 검증3: nonlocal 데모에서 tick `__closure__` changed 스텝 3회, 셀 count 궤적 0→1→2→3.
- 검증4: ch06 별칭 데모에서 a·b가 같은 `<obj1>` 라벨을 공유(같은 객체)함을 확인.

### 다음 페이즈(P3)에 넘긴 것
- FOR_ITER 핸들러는 현재 실제 이터레이터(list_iterator 등)만 소비. P3에서
  MiniGenerator를 이터레이터로 소비하도록 분기 추가 필요.
- 값 스택의 NULL 표현은 P1대로 파이썬 `None`을 겸용(전용 센티넬 아님). 제너레이터
  send에서 실제 None 주입과 충돌 소지가 있는지 P3에서 점검할 것.
