# pvmlab — CPython 내부 동작을 눈으로 보는 학습 도구

**바이트코드는 진짜를 쓰고, 실행 엔진만 파이썬으로 재현한다.** 사용자가 정의한
함수를 `dis.get_instructions()`로 읽어, 직접 구현한 Frame·프레임 스택·평가 루프로
실행하며 모든 스텝을 기록하고, 단일 HTML로 내보낸다. 브라우저에서 ←/→로 한
명령씩 넘기며 관찰한다.

## 개념 모델 — 네 층

| 층 | 실체 | 성질 |
|---|---|---|
| 함수 객체 | 사용자가 `def`한 것 그대로 | `__code__`, `__globals__`, `__defaults__` 등 보유 (가변) |
| 코드 객체 | `func.__code__` 그대로 | 불변. 바이트코드·상수·이름·소스 위치 |
| Frame | 엔진이 구현 | 호출마다 1개. 지역 변수 + 값 스택 + 명령 포인터 |
| 평가 루프 | 엔진이 구현 | 코드 객체를 **읽고**, 프레임에 **쓴다** |

## 실행

```bash
cd tools/pvmlab
python run.py                 # demos/ 전체 → pvm_trace.html
python run.py ch00            # 'ch00'로 시작하는 데모 모듈만
python run.py -o out.html     # 출력 경로 지정
```

각 데모는 미니 PVM 실행 결과를 진짜 CPython과 `assert`로 대조한다("검증 OK").

## 구조

```
run.py              유일한 진입점 (엔진 모듈을 직접 실행하지 말 것)
engine/
  frame.py          Frame 클래스
  pvm.py            MiniPVM — 비재귀 평가 루프 + 트레이스 기록
  inspector.py      코드/함수 객체 속성 스냅샷 + 설명 사전 + diff
  opcodes/core.py   P1 opcode 핸들러 (@opcode 등록)
viewer.py           트레이스 → 단일 자족 HTML
demos/ch00_execution.py   데모 5개
```

## 확장 = 학습

미구현 opcode를 만나면 `NotImplementedError`가 어느 파일에 `@opcode` 핸들러를
추가할지 안내한다. 커리큘럼이 진행되며 `opcodes/iteration.py`(반복문),
`opcodes/closures.py`(클로저) 식으로 파일을 늘려 가는 것 자체가 학습 활동이다.
데모 함수는 반드시 **모듈 레벨**에 정의한다(함수 안 `def`는 클로저 opcode를 만든다).
