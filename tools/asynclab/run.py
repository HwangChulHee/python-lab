"""
run.py — asynclab 유일한 진입점: weblab 3파일을 '진짜 asyncio'로 돌려 관찰한다

    python run.py            # 검증 통과 → asynclab_trace.html 생성

관찰 대상 = demos/weblab/ (metric-lab tools/weblab에서 그대로 가져온 3파일):
    mini_server.py      handle_connection + serve — uvicorn의 자리
    mini_framework.py   MiniAPI — ASGI callable
    verify.py           app / hello / echo — 데모 앱 정의를 그대로 import

진짜 asyncio.SelectorEventLoop + 진짜 asyncio.Task + 진짜 소켓으로 실행하고,
후킹(관찰용)으로 매 사건의 콜 스택·루프 내부를 기록한다.

검증 (실패하면 HTML을 만들지 않는다):
  1. 응답 정합 — A(GET /hello)·B(POST /echo)의 응답 바이트 == 기대값
  2. B 선완료  — 나중에 접속한 B의 완료 스텝이 A보다 앞선다 (트레이스에서 확인)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.realtrace import build_real_trace
import viewer

# verify.py의 check()가 보내는 것과 같은 형식의 raw HTTP 요청
REQ_A = (b"GET /hello HTTP/1.1\r\n", b"host: local\r\n\r\n")
REQ_B = (b"POST /echo HTTP/1.1\r\n", b"content-length: 5\r\n\r\nhello")


def expected_response(body):
    """mini_server의 send() + mini_framework의 _respond()가 만드는 형식 그대로."""
    return (b"HTTP/1.1 200 X\r\n"
            b"content-type: text/plain; charset=utf-8\r\n"
            b"content-length: " + str(len(body)).encode() + b"\r\n"
            b"connection: close\r\n\r\n" + body)


EXPECTED_A = expected_response("안녕, weblab\n".encode())
EXPECTED_B = expected_response(b"hello")


def main():
    ap = argparse.ArgumentParser(description="asynclab — 진짜 asyncio 관찰 (weblab)")
    ap.add_argument("-o", "--out", default="asynclab_trace.html")
    args = ap.parse_args()

    trace, responses = build_real_trace("demos.weblab", REQ_A, REQ_B,
                                        EXPECTED_A, EXPECTED_B)
    print("검증 1 OK — 진짜 asyncio 응답 A(GET /hello)/B(POST /echo) == 기대값")

    done_order = [s["narration"] for s in trace["steps"] if s["kind"] == "done"]
    b_done = next(i for i, s in enumerate(trace["steps"])
                  if s["kind"] == "done" and "client_B" in s["narration"])
    a_done = next(i for i, s in enumerate(trace["steps"])
                  if s["kind"] == "done" and "client_A" in s["narration"])
    assert b_done < a_done, "B가 먼저 끝나야 하는데 순서가 다릅니다"
    print("검증 2 OK — 나중에 접속한 client_B가 client_A보다 먼저 완료")

    out = Path(args.out)
    out.write_text(viewer.build_html(trace), encoding="utf-8")
    print(f"\n생성 완료 → {out}  (스텝 {len(trace['steps'])}개, 완료 사건 {len(done_order)}건)")


if __name__ == "__main__":
    main()
