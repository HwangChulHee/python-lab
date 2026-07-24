"""
mini_web.py — metric-lab mini_server + mini_framework의 축약판 (관찰 대상 코드)

이 파일의 코루틴들은 전부 진짜 async def다. 미니 루프에서도 돌고, 검증 단계에선
같은 코드가 진짜 asyncio(StreamReader) 위에서도 그대로 돈다 — 코루틴 코드는
자기가 어느 루프 위에서 도는지 모른다.
"""


async def serve(loop, app, listener):
    """접속을 기다렸다가, 손님마다 handle_connection 코루틴을 하나씩 만든다.
    손님 1명 = 코루틴 1개 = 프레임 1개."""
    while True:
        name, reader, writer = await listener.accept()
        loop.start_task(handle_connection(app, reader, writer),
                        label=f"client_{name}")


async def handle_connection(app, reader, writer):
    """연결 하나의 일생. await마다 프레임이 보관되고, 멈춘 줄이 곧 연결의 상태다."""
    request_line = await reader.readline()          # 예: b"GET /ping HTTP/1.1\r\n"
    method, target, _version = request_line.decode().rstrip("\r\n").split(" ", 2)
    path, _, query = target.partition("?")

    headers = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):           # 빈 줄 = 헤더 끝
            break
        name, _, value = line.decode().rstrip("\r\n").partition(":")
        headers[name.strip().lower()] = value.strip()

    length = int(headers.get("content-length", "0"))
    body = await reader.readexactly(length)
    scope = {"method": method, "path": path, "query": query, "headers": headers}

    async def receive():
        return {"body": body}

    async def send(message):
        head = (f"HTTP/1.1 {message['status']} OK\r\n"
                f"content-length: {len(message['body'])}\r\n\r\n")
        writer.write(head.encode() + message["body"])
        await writer.drain()

    await app(scope, receive, send)                 # 프레임 위에 app 프레임이 얹힌다


class MiniAPI:
    """라우팅 dict 하나가 전부인 미니 프레임워크."""

    def __init__(self):
        self.routes = {}

    def add_route(self, method, path, handler):
        self.routes[(method, path)] = handler

    async def __call__(self, scope, receive, send):
        handler = self.routes[(scope["method"], scope["path"])]
        status, body = await handler(scope, receive)
        await send({"status": status, "body": body})


async def ping(scope, receive):
    return 200, b"pong\n"


def make_app():
    app = MiniAPI()
    app.add_route("GET", "/ping", ping)
    return app
