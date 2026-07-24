"""
channel.py — await 가능한 바이트 통로 (MiniListener / MiniReader / MiniWriter)

코루틴이 루프에 제어를 반납하는 통로가 여기 다 모여 있다. asyncio의 Future를
흉내내지 않는다 — 커스텀 awaitable의 __await__가 튜플 신호 하나를 yield하면,
그 튜플이 코루틴 사슬을 타고 올라가 MiniTask.step의 send() 반환값으로 떨어진다.

  yield ("read", fd)          — fd가 읽기 가능해지면 깨워 달라 (셀렉터 장부 등록)
  yield ("write", fd, bytes)  — 이 바이트를 전송해 달라 (쓰기는 늘 준비 → 즉시 재예약)

MiniReader는 자기 버퍼를 따로 두지 않고 셀렉터의 recv_buf(=OS 수신 버퍼)에서
직접 꺼낸다. "데이터는 파이썬이 아니라 OS가 들고 있다"가 구조에 드러난다.
"""


class _WaitReadable:
    """await하면 ("read", fd)를 yield하고 프레임을 보관하는 awaitable."""

    def __init__(self, fd):
        self.fd = fd

    def __await__(self):
        yield ("read", self.fd)                 # 여기서 프레임이 멈춘다(책갈피)


class _Flush:
    """await하면 ("write", fd, data)를 yield하는 awaitable — drain의 정체."""

    def __init__(self, fd, data):
        self.fd = fd
        self.data = data

    def __await__(self):
        yield ("write", self.fd, self.data)


class MiniListener:
    """listen 소켓의 축약. accept()가 연결 도착까지 await한다."""

    def __init__(self, selector, fd):
        self.selector = selector
        self.fd = fd

    async def accept(self):
        await _WaitReadable(self.fd)            # 연결이 올 때까지 프레임 보관
        name, fd = self.selector.accept(self.fd)
        return name, MiniReader(self.selector, fd), MiniWriter(self.selector, fd)


class MiniReader:
    """asyncio.StreamReader의 축약 — readline/readexactly만. OS 수신 버퍼에서 읽는다."""

    def __init__(self, selector, fd):
        self.selector = selector
        self.fd = fd

    def _buf(self):
        return self.selector.recv_buf[self.fd]

    async def readline(self):
        """개행까지 한 줄(개행 포함). 버퍼에 없으면 도착할 때까지 await."""
        while b"\n" not in self._buf():
            await _WaitReadable(self.fd)        # 없으면 OS에 맡기고 프레임 보관
        buf = self._buf()
        idx = buf.index(b"\n") + 1
        line = bytes(buf[:idx])
        del buf[:idx]
        return line

    async def readexactly(self, n):
        """정확히 n바이트. n=0이면 await 없이 즉시 반환(빈 바디)."""
        while len(self._buf()) < n:
            await _WaitReadable(self.fd)
        buf = self._buf()
        data = bytes(buf[:n])
        del buf[:n]
        return data


class MiniWriter:
    """asyncio.StreamWriter의 축약 — write는 쌓기만, drain이 실제 전송 신호."""

    def __init__(self, selector, fd):
        self.selector = selector
        self.fd = fd
        self._pending = bytearray()

    def write(self, data):
        self._pending.extend(data)              # 동기: 쌓아만 둔다 (진짜와 동일)

    async def drain(self):
        data = bytes(self._pending)
        self._pending.clear()
        await _Flush(self.fd, data)             # ("write", fd, data) 신호로 루프에 위임
