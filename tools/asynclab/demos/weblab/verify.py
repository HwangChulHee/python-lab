"""weblab 검증 — 미니 구현이 실제로 동작하는지, 그리고 진짜와 호환되는지.

검증 1 (자동): mini_server 위에 MiniAPI를 올리고 raw HTTP 요청을 보내
             응답이 올바른지 assert 한다.
검증 2 (수동): 같은 MiniAPI 앱을 "진짜 uvicorn"에 올려 본다.
             MiniAPI가 ASGI 규약을 지켰다면 그대로 돌아야 한다.

실행 (레포 루트에서):
    uv run python -m tools.weblab.verify          # 검증 1
    uv run uvicorn tools.weblab.verify:app        # 검증 2 → curl로 확인
"""
import asyncio

from .mini_framework import MiniAPI
from .mini_server import serve


# ── 데모 앱: 프레임워크 사용자의 코드는 이만큼만 ─────────────────────
app = MiniAPI()


async def hello(scope, body):
    return 200, "안녕, weblab\n".encode()


async def echo(scope, body):
    return 200, body if body else b"(empty)\n"


app.add_route("GET", "/hello", hello)
app.add_route("POST", "/echo", echo)


# ── 검증 1: mini_server + MiniAPI 조합을 코드로 확인 ─────────────────
async def check():
    server_task = asyncio.create_task(serve(app, port=8901))
    await asyncio.sleep(0.2)  # 서버가 뜰 시간

    reader, writer = await asyncio.open_connection("127.0.0.1", 8901)
    writer.write(
        b"POST /echo HTTP/1.1\r\n"
        b"content-length: 5\r\n"
        b"\r\n"
        b"hello"
    )
    await writer.drain()
    response = await reader.read(-1)  # 서버가 연결을 닫을 때까지 전부 읽기

    assert response.startswith(b"HTTP/1.1 200"), response
    assert response.endswith(b"hello"), response
    print("=" * 50)
    print("검증 1 OK: mini_server 위에서 MiniAPI 에코 동작")
    print("=" * 50)
    print("검증 2 (진짜와 대조):")
    print("  uv run uvicorn tools.weblab.verify:app")
    print("  curl -X POST http://127.0.0.1:8000/echo -d hello")
    print("  → 같은 앱이 진짜 서버에서도 돈다면, MiniAPI는 ASGI 규약을 지킨 것")

    server_task.cancel()


if __name__ == "__main__":
    asyncio.run(check())
