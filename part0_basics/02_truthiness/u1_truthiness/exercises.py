"""u1 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 예측 — 참인가 거짓인가
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")
for expr in ['0', '0.0', '""', '" "', '[]', '[0]', '[None]', '{}', 
             '{0:0}', 'None', '-1', '"False"', 'range(0)', 'range(1)']:
    # 각각 예측한 뒤 실행 결과와 대조
    print(f"  bool({expr:<9}) = {bool(eval(expr))}")

# 헷갈렸던 것과 이유 (특히 " ", [0], [None], "False"):
#   → " ", [0], [None], {0:0}, -1, range(1)은 true. range(0)은 false라 생각하는데 헷갈리네


# ═══════════════════════════════════════════════════
# 유제 2. 버그 찾기 — 0을 잃어버리는 함수
# ═══════════════════════════════════════════════════
# 아래 함수는 사용자의 잔액을 포맷한다.
# 잔액이 0원인 유효한 계정에서 오작동한다.

def format_balance(account):
    balance = account.get("balance")
    if not balance:
        return "잔액 정보 없음"
    return f"잔액: {balance}원"

print("\n=== 유제2 ===")
print(" ", format_balance({"balance": 1000}))
print(" ", format_balance({"balance": 0}))      # 0원 계정 — 뭐가 나올까?
print(" ", format_balance({}))                  # 정보 없는 계정

# (a) balance=0에서 무엇이 잘못 나오나:
#   →  "잔액 정보 없음"
# (b) "정보 없음"과 "0원"을 구분하도록 고치면:
#   →  if balance is None:
# (c) 이 버그의 근본 원인을 한 문장으로 (0과 None의 공통점):
#   → 파이썬이 0과 None은 모두 false로 인식하기 때문


# ═══════════════════════════════════════════════════
# 유제 3. __bool__ 직접 만들기
# ═══════════════════════════════════════════════════
# 장바구니 클래스. 담긴 상품이 있으면 truthy, 없으면 falsy로 만들어라.

class Cart:
    def __init__(self):
        self.items = []        
    
    # def __bool__(self):
    #     if len(self.items) == 0 :
    #         return False
    #     else :
    #         return True
    
    def __len__(self):
        return len(self.items)
    
    # TODO: if cart: 가 동작하도록 메서드 하나를 추가하라
    #       (__bool__ 또는 __len__ 중 무엇이 더 적절할지 판단)

cart = Cart()
print("\n=== 유제3 ===")

# 아래가 의도대로 동작해야 한다:
print("  빈 카트:", "있음" if cart else "비어있음")   # 비어있음
cart.items.append("사과")
print("  담은 후:", "있음" if cart else "비어있음")   # 있음

# (a) __bool__과 __len__ 중 무엇을 선택했고 왜인가:
#   → len을 택했다. 0 이외의 값은 모두 True이기도 하고 len(cart)도 구현가능하다. 일석이조의 효과
# (b) len(cart)도 되게 하려면 어느 쪽이어야 하나:
#   → __len__이다 당연히