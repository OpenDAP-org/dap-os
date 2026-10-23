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
        key(q, BUTTONS[a[1]], True); time.sleep(hold / 1000)
        try:
            key(q, BUTTONS[a[1]], False)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the instance powered off while the button was held (a long press of power)
    elif a[0] == "tap":
        x, y = int(a[1]), int(a[2]); sx, sy = x * 0x7FFF // (WIDTH - 1), y * 0x7FFF // (HEIGHT - 1)
        # virtio-multitouch takes multi-touch ("mtt") events, not pointer "abs" events. Known limit (QEMU 11.1.2):
        # the guest receives only BTN_TOUCH, with no position, slot or tracking id (checked 2026-10-23), so this is
        # not a valid contact. For tests, inject in the guest: `dap-qemu.sh ssh dap-inject tap X Y` (system repo,
        # deployed in the development system extension).
        mtt = lambda kind, axis="x", value=0: {"type": "mtt", "data": {"type": kind, "slot": 0, "tracking-id": 1, "axis": axis, "value": value}}
        q.cmd("input-send-event", events=[mtt("begin", "x", sx), mtt("data", "x", sx), mtt("data", "y", sy),
                                          {"type": "btn", "data": {"down": True, "button": "touch"}}])
        time.sleep(0.05)
        q.cmd("input-send-event", events=[mtt("end", "x", sx), {"type": "btn", "data": {"down": False, "button": "touch"}}])
    elif a[0] == "raw":
        print(json.dumps(q.cmd(a[1], **(json.loads(a[2]) if len(a) > 2 else {})), indent=2))
    else:
        raise SystemExit(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:])
