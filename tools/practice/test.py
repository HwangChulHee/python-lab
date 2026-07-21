import sys

def f(a, b):
    c = a + b
    frame = sys._getframe()
    print("코드 객체 co_varnames:", frame.f_code.co_varnames)  # ('a','b','c','frame')
    print("프레임 f_locals      :", frame.f_locals)            # {'a':3,'b':5,'c':8,...}
    return c

f(3, 5)
f(10, 20)   # co_varnames는 그대로, f_locals만 달라짐