#!/usr/bin/env python3
"""Drive a running virtual T1 through QEMU's QMP socket (headless automation).

  dap-qmp.py screenshot FILE.png       capture the display
  dap-qmp.py press BUTTON [ms]         action | vol-up | vol-down | power
  dap-qmp.py tap X Y                   touch at display pixel (320 x 480 portrait)
  dap-qmp.py raw COMMAND [JSON-ARGS]   any QMP command
"""
import json, os, socket, sys, time

SOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run", "qmp.sock")
WIDTH, HEIGHT = 320, 480  # touch faceplate display (faceplate-touch ADR 0001)
# Virtual T1 button mapping (QEMU key codes → Linux input keys).
BUTTONS = {"action": "audioplay", "vol-up": "volumeup", "vol-down": "volumedown", "power": "power"}

class QMP:
    def __init__(self, path=SOCK):
        self.s = socket.socket(socket.AF_UNIX); self.s.connect(path); self.f = self.s.makefile("rw")
        self._read(); self.cmd("qmp_capabilities")
    def _read(self):
        while True:
            msg = json.loads(self.f.readline())
            if "event" not in msg:
                return msg
    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args}) + "\n"); self.f.flush()
        r = self._read()
        if "error" in r:
            raise SystemExit(f"QMP {name}: {r['error']['desc']}")
        return r.get("return")

def key(q, qcode, down):
    q.cmd("input-send-event", events=[{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": qcode}}}])

def main(a):
    if not a:
        raise SystemExit(__doc__)
    q = QMP()
    if a[0] == "screenshot":
        q.cmd("screendump", filename=os.path.abspath(a[1]), format="png"); print(a[1])
    elif a[0] == "press":
        hold = int(a[2]) if len(a) > 2 else 100
        key(q, BUTTONS[a[1]], True); time.sleep(hold / 1000); key(q, BUTTONS[a[1]], False)
    elif a[0] == "tap":
        x, y = int(a[1]), int(a[2]); sx, sy = x * 0x7FFF // (WIDTH - 1), y * 0x7FFF // (HEIGHT - 1)
        ev = lambda down: [{"type": "abs", "data": {"axis": "x", "value": sx}},
                           {"type": "abs", "data": {"axis": "y", "value": sy}},
                           {"type": "btn", "data": {"down": down, "button": "touch"}}]
        q.cmd("input-send-event", events=ev(True)); time.sleep(0.05); q.cmd("input-send-event", events=ev(False))
    elif a[0] == "raw":
        print(json.dumps(q.cmd(a[1], **(json.loads(a[2]) if len(a) > 2 else {})), indent=2))
    else:
        raise SystemExit(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:])
