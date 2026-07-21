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

---

## P3 — 제너레이터 (10/12장)

### 구현 요약
- **새 파일**
  - `engine/generator.py` — MiniGenerator(보관된 Frame + 상태) + gsend 마커.
  - `engine/opcodes/generators.py` — RETURN_GENERATOR/YIELD_VALUE의 '설명'만 등록
    (핸들러는 구조상 pvm 루프 본체에 있음).
  - `demos/ch10_generators.py`, `demos/ch12_decorators.py`.
- **엔진 변경 (비재귀 루프의 보상)**
  - `Frame.generator` 필드 추가(이 프레임이 제너레이터의 것이면 그 MiniGenerator).
  - 루프 본체에 **RETURN_GENERATOR**(프레임을 실행하지 않고 보관한 객체를 반환),
    **YIELD_VALUE**(프레임을 소멸이 아니라 보관 — ip·값 스택 보존), 그리고 제너레이터
    **RETURN**(=COMPLETED/StopIteration) 처리를 추가. 모두 프레임 스택을 다루는
    '기계 구조'라 CALL/RETURN과 나란히 본체에 둠.
  - `MiniPVM._resume_generator(gen, sent, on_stop)`: 보관 프레임을 프레임 스택으로
    되돌리고 sent 값을 그 프레임 값 스택에 push해 이어 실행. next는 None, gsend는 준 값.
  - `record()`에 `held`(지금 스택에 없는 제너레이터 프레임) 스냅샷 추가 — 상태·보관된
    ip offset·값 스택 그대로.
- **뷰어**: '보관된 프레임' 패널 신설(상태 배지 CREATED/SUSPENDED/RUNNING/COMPLETED,
  보관된 ip 위치·값 스택 표시). 프레임이 스택↔보관 패널을 오가는 것이 P3 하이라이트.
- **run.py**: `@demo(..., ref=참조함수)` 지원. 데모가 gsend를 쓰면 stock CPython으로
  그대로 못 도니, 실제 `.send()`를 쓰는 ref 함수로 대조값을 계산.

### 내린 설계 판단과 이유
- **제너레이터 생성은 RETURN_GENERATOR 지점에서 처리(CALL 지점 특별대우 아님)**:
  제너레이터 함수 호출도 일반 CALL처럼 프레임을 push하고, 그 프레임의 첫 명령
  RETURN_GENERATOR가 스스로를 보관된 객체로 바꿔 호출자에게 돌려준다. CPython ceval과
  동일한 흐름이라, '함수를 호출해도 본문이 0줄 실행된다'는 장면이 공짜로 나온다.
- **YIELD는 "보관", RETURN은 "소멸"을 프레임 스택 조작으로 그대로 구현**: YIELD_VALUE는
  프레임을 스택에서 떼되 MiniGenerator 안에 그대로 보관(ip·값 스택 유지), RETURN은
  버린다. 비재귀 단일 루프이기에 프레임 수명이 우리 손에 남아 이게 가능하다 — P3가
  비재귀 구조의 '보상'인 이유.
- **send는 엔진 마커 gsend로 우회**: `gen.send(v)`는 LOAD_ATTR(P4)이 필요. P3 범위를
  지키려고 엔진이 CALL 지점에서 가로채는 마커 함수 gsend(gen, v)를 도입. 대조는 실제
  `.send()`를 쓰는 ref로 하여 진짜 CPython과의 동치를 그대로 검증.
- **⚠ CALL 호출 규약을 정확히 다시 구현(중요 수정)**: 3.12의 CALL은 스택
  `[콜러블, self_or_NULL, 인자...]` 를 쓴다. 일반 호출은 콜러블 아래 NULL이 깔리고,
  메서드/데코레이터(`identity(greet)` 등 PUSH_NULL 없는 형태)는 NULL 자리에 진짜 self가
  있고 그것이 arg0이 된다. P1의 CALL은 후자를 처리하지 못해 데코레이터에서 콜러블을
  잘못 집었다. "맨 위/그 아래 두 슬롯을 보고, 아래가 NULL이면 일반 호출, 아니면 아래가
  콜러블이고 위는 arg0" 규칙으로 교정.
- **⚠ LOAD_GLOBAL이 NULL 슬롯을 함께 밀도록 수정(중요 수정)**: 3.12는 곧 호출될
  전역을 읽을 때 LOAD_GLOBAL 인자 하위 비트를 켜서 콜러블 아래 NULL을 함께 민다
  (argrepr "NULL + 이름"). P1은 이를 무시해 값만 밀었고, 위의 새 CALL 규약과 만나
  슬롯 수가 어긋났다. `ins.arg & 1`일 때 NULL을 함께 밀도록 교정 — 이제 모든 호출이
  균일하게 `콜러블+NULL슬롯+인자` 형태가 된다.
- **NOP 추가**: `while True` 등에서 등장(no-op, 기록 생략).

### 실측에서 확정한 opcode (예상과 다른 점)
- 제너레이터 첫 명령은 `RETURN_GENERATOR; POP_TOP; RESUME`. 재개 시 보낸 값을 값
  스택에 push하면 첫 POP_TOP(첫 next의 None) 또는 STORE_FAST(=`x = yield`)가 그 값을 받음.
- `SEND`/`END_SEND`는 이 데모들엔 등장하지 않음(`yield from` 전용) → 미구현. 필요 시
  P3+에서 추가. 예상 목록엔 있었으나 실측 우선.
- 데코레이터 사용 지점은 `MAKE_FUNCTION → CALL → STORE`로 컴파일(스텝으로 확인됨).

### 검증 결과 (전부 통과)
- 데모 15개(P1 5 + P2 6 + P3 4) 전부 진짜 CPython과 assert 대조 OK, `python run.py` 무에러.
- 검증2: countdown 트레이스에 SUSPENDED 보관 프레임 스냅샷 존재(ip offset·locals·값 스택 보존).
- 검증3: countdown 프레임이 스택에서 사라졌다(보관) 다시 나타나기를 4회 반복.
- 검증4: ch12 데코레이터 데모 스텝에 MAKE_FUNCTION → CALL → STORE 순서 등장.

### 다음 페이즈(P4)에 넘긴 것
- CALL 규약이 이제 self/메서드 슬롯을 처리하므로, P4의 `d.bark()`(LOAD_ATTR 메서드
  변형이 method+self를 스택에 올림)와 자연히 맞물릴 것. LOAD_ATTR에서 method 형태를
  push하면 CALL이 그대로 소비한다.
- 값 스택 NULL=None 겸용은 P3까지 문제 없었음(gsend는 실제 None을 인자로 밀지 않음).

---

## P4 — 속성 접근과 클래스 (14/15/16장)

### 구현 요약
- **새 파일**
  - `engine/classes.py` — BUILD_CLASS 마커(__build_class__를 엔진이 가로채기 위한).
  - `engine/opcodes/attributes.py` — LOAD_BUILD_CLASS, STORE_NAME, LOAD_NAME,
    STORE_ATTR, LOAD_ATTR(일반 + 메서드 변형) + 조회 경로 서술 헬퍼.
  - `demos/ch14_classes.py`, `demos/ch15_attribute_lookup.py`, `demos/ch16_mro.py`.
- **엔진 변경**
  - `Frame.namespace`(클래스 본문의 이름 dict), `Frame.produces`(RETURN 시 특수 산출).
  - CALL에 두 가로채기 추가:
    · `__build_class__` → 클래스 본문을 새 네임스페이스 dict를 가진 프레임으로 실행,
      RETURN 시 `type(name, bases, ns)`로 클래스 객체 생성.
    · 우리가 만든 클래스 호출 → `__new__`로 인스턴스 만들고, 파이썬 `__init__`이 있으면
      `(obj, *args)`로 프레임 실행(self가 첫 지역 변수), RETURN 시 인스턴스 반환.
  - `MiniPVM.user_classes`(가로챌 클래스 집합), `instances`(만든 인스턴스), 인스턴스
    `__dict__` diff 계산(`_instance_snapshots`).
- **뷰어**: '인스턴스' 패널 신설(__dict__ + type().__mro__, STORE_ATTR 시 diff 강조).
  LOAD_ATTR 조회 경로는 스텝 설명에 화살표로 직접 서술.
- **fmt 확장**: 클래스는 "이름 클래스", 인스턴스는 "이름 인스턴스<objN>", 엔진 마커는
  `_pvm_label` 훅으로 표시.

### 내린 설계 판단과 이유
- **__build_class__를 C 위임하지 않고 엔진이 가로챈다**: 진짜 __build_class__는 C라서
  그대로 부르면 클래스 본문이 C 안에서 돌아 우리 루프에 안 잡힌다. LOAD_BUILD_CLASS가
  마커를 올리고 CALL이 그걸 알아봐 본문을 '우리 프레임'으로 실행 → "클래스 본문도
  프레임에서 실행되는 코드"라는 P4 하이라이트 1이 그대로 나온다. 클래스 객체 자체는
  표준 `type(name, bases, ns)`로 만든다(진짜 클래스).
- **인스턴스 생성도 가로채 __init__을 프레임으로 실행**: `Dog("초코")`를 C에 위임하면
  __init__이 C에서 돌아 안 보인다. `__new__`로 인스턴스만 만들고 파이썬 __init__을
  루프로 실행해 self·STORE_ATTR·__dict__ 성장을 눈에 보이게 했다. object.__init__(슬롯
  래퍼, __code__ 없음)만 있는 클래스는 인스턴스를 바로 반환.
- **LOAD_ATTR: 값은 getattr에 위임, 경로는 직접 서술**: 실제 값은 getattr로 정확히
  얻되(디스크립터/바인딩 정확), 조회 경로(인스턴스 __dict__ → MRO 각 클래스)는 별도로
  계산해 화살표로 그린다 — P4 하이라이트 2(15장 "속성 접근의 진실").
- **메서드 변형(arg & 1)은 (함수, self)를 push**: CALL 규약이 P3에서 이미 self 슬롯을
  처리하므로, 메서드 변형이 [함수, self]를 올리면 CALL이 self를 첫 인자로 그대로 소비한다.
  P3의 CALL 수정이 여기서 값을 한다.
- **super()/LOAD_SUPER_ATTR는 미구현(스트레치)**: 핸드오프대로 데모에서 제외. MRO는
  다이아몬드 상속 + 일반 메서드 조회로 충분히 보인다. 필요 시 P4+에서 추가.

### 실측에서 확정한 opcode (예상과 다른 점)
- 클래스 본문은 `LOAD_NAME __name__ → STORE_NAME __module__`, `STORE_NAME __qualname__`
  로 시작하고 속성들을 STORE_NAME으로 쌓은 뒤 `RETURN_CONST None`.
- `self.x = v`는 `STORE_ATTR`(TOS=obj, TOS1=value), `self.x` 읽기는 `LOAD_ATTR`(arg&1=0).
- 메서드 호출 `d.f()`는 `LOAD_ATTR (NULL|self + f)`(arg&1=1) + `CALL`.
- 예상에 있던 별도 LOAD_METHOD는 없음 — 3.12는 LOAD_ATTR 메서드 변형으로 통합.

### 검증 결과 (전부 통과)
- 데모 19개(P1 5 + P2 6 + P3 4 + P4 4) 전부 진짜 CPython과 assert 대조 OK, `run.py` 무에러.
- 검증2: ch14 class_stmt 트레이스에 클래스 본문 프레임(Point) 등장.
- 검증3: ch15 섀도잉에서 같은 c.tag의 조회 경로가 인스턴스 속성 유무로 달라짐
  (인스턴스 ✗ → C ✓  vs  인스턴스 ✓).
- 검증4: ch14 인스턴스 __dict__ diff가 __init__ 실행 중 잡힘({'name': '초코'}).

### 다음 페이즈(P5)에 넘긴 것
- P5는 스테퍼가 아닌 별도 계기판 2종(refcount, eventloop). 뷰어 껍데기(스텝 내비게이션·
  스타일 토큰)만 공유하고 패널 구성은 새로 짠다. run.py에 서브커맨드로 연결.
- eventloop는 P3의 MiniGenerator를 태스크로 재사용 — "이벤트 루프 = 보관된 프레임들을
  번갈아 재개하는 스케줄러"를 실물로 증명하는 것이 설계 의도.

---

## P5 — 별도 계기판 2종 (20/24/25장)

스테퍼 형식이 안 맞는 주제라, 독립 도구 2개로 만들었다. 뷰어의 스타일 토큰과 스텝
내비게이션(←/→·슬라이더·드롭다운) 패턴만 공유하고, 패널 구성은 각자 새로 짰다.
`python run.py refcount`, `python run.py eventloop` 서브커맨드로 연결.

### 5a. 참조 카운트 추적기 (`refcount.py`, 20장)
- **구성**: 시나리오를 '문장 단위'로 실행하며 관심 객체의 `sys.getrefcount` 변화를
  기록. 각 스텝에 실행 문장 + 객체별 참조 수 막대(변화량 +/- 강조) + 왜 변했는지 한국어.
- **시나리오 3개**: ① 별칭·del, ② 컨테이너·함수 인자, ③ 순환 참조와 GC.
- **설계 판단**
  - **getrefcount 왜곡 보정**: `getrefcount(obj)`는 obj를 인자로 받는 순간 임시 참조를
    하나 더 만들어 실제보다 1(로컬 바인딩까지 하면 2) 크게 나온다. 이름/컨테이너에 있는
    객체는 `getrefcount(getter())`로 재서 −1만(로컬 바인딩 안 함), 약참조로만 남은 객체는
    None 확인 때문에 로컬에 묶어야 해서 −2 보정. 이 사실을 뷰어 상단 note에 명시.
  - **순환 객체는 dict 대신 클래스(_Node)**: dict는 약참조가 안 걸린다. 약참조로만 들고
    관찰해야 강한 참조를 안 남기고 소멸을 감지할 수 있어 클래스로.
  - **③에서 gc.disable() 후 명시적 gc.collect()**: 자동 GC가 중간에 순환을 수거하지
    않도록 꺼서 결정적으로 관찰. del 뒤에도 refcount가 1(서로 물림)로 남아 안 죽고,
    collect()에서 비로소 소멸하는 분업을 마지막 스텝으로 보인다.
  - **컨테이너 시나리오 측정 버그 수정**: `del a` 뒤 객체가 lst에 남아 살아있는데 이름
    a로만 조회하면 '소멸'로 오판. getter가 이름 → 컨테이너 순으로 찾도록 고침(궤적
    1→2→3→4→3→2→1→소멸).
- **검증**: 시나리오 3개 HTML 생성. note에 getrefcount +1 왜곡 명시. 함수 인자 동안
  일시 +1(궤적에 4 피크 후 하강). 순환은 del 뒤에도 참조 1로 생존, gc.collect 후 소멸.

### 5b. 미니 이벤트 루프 (`eventloop.py`, 24/25장)
- **구성**: 태스크(제너레이터)를 ready 큐 + sleep용 시간 힙 + 가상 시계로 굴리는
  스케줄러. `yield ("sleep", n)`/`yield ("work", k)` 프로토콜로 제어를 반납. 출력은
  태스크별 간트 타임라인(가로=가상 시간) + 현재 시계 재생 헤드 + 스텝별 상태/서술.
- **시나리오 2개**: ① 협조적 3태스크(번갈아 보관·재개), ② 블로킹의 참사(양보 없는
  work(20)이 다른 태스크를 굶김).
- **설계 판단**
  - **네이티브 제너레이터를 태스크로(중요 판단)**: 핸드오프는 P3의 MiniGenerator 재사용을
    제안했지만, 네이티브 파이썬 제너레이터도 '보관됐다 재개되는 프레임'이며 `gi_frame`으로
    멈춘 줄까지 직접 들여다볼 수 있어 증명하려는 원리(이벤트 루프 = 보관된 프레임들의
    스케줄러)는 그대로다. MiniGenerator를 이벤트 루프에 물리려면 스케줄러가 값을 돌려받는
    경로(프레임이 아니라 스케줄러가 resumer)를 엔진에 새로 뚫어야 해서, P5의 재량 범위
    안에서 더 단순·결정적인 네이티브 경로를 택했다. '보관/재개' 어휘는 스테퍼와 공유.
  - **가상 시계(실시간 대기 없음)**: ready가 비면 시계를 다음 깨어남으로 점프. ready FIFO +
    sleep 힙(wake, seq) 타이브레이크로 실행 순서가 완전히 결정적 → assert로 검증 가능.
  - **work(k) = 블로킹 모델**: 한 번의 재개에서 시계를 k만큼 밀어 '양보 없는 긴 계산'을
    표현. 단일 스레드 협조형이라 그동안 다른 태스크가 한 발도 못 나가는 것이 25장의 핵심.
- **검증**: 협조 3태스크 시나리오의 재개 순서가 손으로 계산한 값
  `[A,B,C,A,B,A,C,B,A]`와 정확히 일치(코드에 assert). 블로킹 시나리오에서 B의 첫 실행이
  T=20으로 밀림(그 전까지 굶음)이 타임라인에 드러남.

### 전체 완료 조건 점검
- ✅ `python run.py`(스테퍼 19개) + `refcount` + `eventloop` 전부 무에러.
- ✅ REPORT.md에 P2~P5 섹션 완비.
- ✅ 페이즈별 커밋 이력 유지(스쿼시 없음): P1 → P2 → P3 → P4 → P5.
- ✅ demos/ 각 파일 상단에 장 번호·관찰 포인트 주석.

### 남은 것(선택)
- 스테퍼 미구현: `SEND`/`END_SEND`(yield from), `super()`/`LOAD_SUPER_ATTR`, 예외 기구
  (try/except, with), `CALL_FUNCTION_EX`(*args). 전부 만나면 NotImplementedError가 추가할
  파일을 안내한다 — 커리큘럼 진행 시 각 장에서 열어 보는 것이 학습 활동.
- eventloop를 실제 MiniGenerator로 구동하는 버전(스케줄러-resumer 경로 추가)은 후속 확장 여지.
