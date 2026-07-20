"""u1 예제: 컴파일 파이프라인을 단계별로 직접 실행해 본다.

실행: python examples.py
각 단계의 출력을 눈으로 확인할 것.
"""
import ast
import dis

source = "x = 1 + 2"

# ── ② 파싱: 소스 → AST ──────────────────────────────
tree = ast.parse(source)
print("=== AST ===")
print(ast.dump(tree, indent=2))
# Assign(targets=[Name(id='x')], value=BinOp(Constant(1), Add(), Constant(2)))
# → "x에 (1+2)를 할당"이라는 구조가 트리로 표현됨

# ── ③ 컴파일: AST → 코드 객체 ───────────────────────
code = compile(tree, filename="<demo>", mode="exec")
print("\n=== 코드 객체 ===")
print(type(code))                # <class 'code'>

print("\n=== 바이트코드 ===")
dis.dis(code)
# 관찰 포인트: LOAD_CONST 3
# 소스에는 1 + 2인데 바이트코드에는 이미 3이 들어 있다.
# 컴파일러가 상수 계산을 미리 해버린 것 (constant folding).
# "컴파일러가 없다"면 이런 최적화도 없어야 한다 → 컴파일러 존재의 직접 증거.

# ── ④ 실행: PVM에 코드 객체를 넘김 ──────────────────
namespace = {}
exec(code, namespace)
print("\n=== 실행 결과 ===")
print(namespace["x"])            # 3