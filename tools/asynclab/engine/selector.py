"""
selector.py — ScriptedSelector: 각본(scripted) 네트워크 재생기

실제 셀렉터(epoll/kqueue)의 자리에 앉는 가짜 OS. "T=3에 fd 5로 바이트가 도착"
같은 사건 목록(각본)을 미리 받아 두고, 루프가 wait()로 잠들 때마다 가상 시계를
다음 사건 시각으로 점프시키며 그 시각의 사건을 전부 수거한다.

여기가 이 도구에서 'OS'를 연기하는 유일한 곳이다:
  recv_buf  — fd별 수신 버퍼 (커널이 소켓마다 들고 있는 그 버퍼)
  backlog   — listen fd에 쌓이는 미수락 연결 (accept 대기열)
  sent      — fd별로 전송된 응답 바이트 기록 (검증 대상)

실제 소켓은 없다. 같은 각본이면 트레이스가 바이트 단위로 동일하다(결정성).

각본 항목: (시각, 종류, fd, 페이로드, 표시문구)
  ("connect", listen_fd, (이름, 새 fd))  — 새 연결이 backlog에 도착
  ("data",    fd,        바이트)          — 수신 버퍼에 바이트 도착
"""

from collections import deque


class ScriptedSelector:
    def __init__(self, script, fd_names):
        self.script = list(script)     # [(t, kind, fd, payload, desc)]
        self.consumed = 0              # 소비된 각본 사건 수 (타임라인 표시용)
        self.clock = 0                 # 가상 시계 — wait()가 진행시킨다
        self.recv_buf = {}             # fd → bytearray  (OS 수신 버퍼)
        self.backlog = {}              # listen fd → deque[(이름, 새 fd)]
        self.sent = {}                 # fd → bytearray  (전송된 응답 기록)
        self.fd_names = dict(fd_names) # fd → 사람용 이름 ("listen", "A", "B")

    def exhausted(self):
        """각본이 다 소진됐는가 — 루프 종료 판단의 근거."""
        return self.consumed >= len(self.script)

    def wait(self):
        """OS 대기를 흉내낸다: 가상 시계를 다음 각본 시각으로 점프시키고, 그 시각의
        사건을 전부 수거해 '읽기 가능해진 fd 목록'을 돌려준다. (epoll_wait의 축약)"""
        t = self.script[self.consumed][0]
        self.clock = t
        readable = []
        while self.consumed < len(self.script) and self.script[self.consumed][0] == t:
            _, kind, fd, payload, _ = self.script[self.consumed]
            if kind == "connect":                       # 새 연결 → listen fd가 읽기 가능
                name, new_fd = payload
                self.backlog.setdefault(fd, deque()).append((name, new_fd))
                self.recv_buf.setdefault(new_fd, bytearray())
                self.sent.setdefault(new_fd, bytearray())
                self.fd_names[new_fd] = name
            else:                                       # 바이트 도착 → 수신 버퍼에 적재
                self.recv_buf.setdefault(fd, bytearray()).extend(payload)
            if fd not in readable:
                readable.append(fd)
            self.consumed += 1
        return readable

    def accept(self, listen_fd):
        """backlog에서 연결 하나를 꺼낸다. (accept(2)의 축약)"""
        return self.backlog[listen_fd].popleft()

    def transmit(self, fd, data):
        """응답 바이트 '전송' — 기록만 한다. 검증이 이 기록과 기대값을 대조한다."""
        self.sent.setdefault(fd, bytearray()).extend(data)
