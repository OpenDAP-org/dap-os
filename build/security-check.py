#!/usr/bin/env python3
"""Check the last built Blackbird OS image against Debian's security, updates and backports archives.

Reads every built image's package manifest (image/mkosi.output/*.manifest), downloads the current
package indexes and lists every package with a newer version available. Records the run in
<workspace>/.state/security-check so the weekly reminder knows when it last ran.

Exit code: 0 = up to date, 1 = updates available, 2 = error.
"""
import glob, json, lzma, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORKSPACE = os.path.abspath(os.path.join(REPO, "..", ".."))
ARCH = "arm64"
INDEXES = [  # (label, base URL, suite)
    ("security", "https://security.debian.org/debian-security", "trixie-security"),
    ("updates", "https://mirrors.edge.kernel.org/debian", "trixie-updates"),
    ("backports", "https://mirrors.edge.kernel.org/debian", "trixie-backports"),
]

def _order(c):
    return 0 if c.isdigit() else (-1 if c == "~" else (ord(c) if c.isalpha() else ord(c) + 256)) if c else 0

def _cmp_part(a, b):
    while a or b:
        na = re.match(r"^[^0-9]*", a).group(); nb = re.match(r"^[^0-9]*", b).group()
        a, b = a[len(na):], b[len(nb):]
        for i in range(max(len(na), len(nb))):
            ca = _order(na[i]) if i < len(na) else 0; cb = _order(nb[i]) if i < len(nb) else 0
            if ca != cb:
                return (ca > cb) - (ca < cb)
        da = re.match(r"^[0-9]*", a).group(); db = re.match(r"^[0-9]*", b).group()
        a, b = a[len(da):], b[len(db):]
        if int(da or 0) != int(db or 0):
            return (int(da or 0) > int(db or 0)) - (int(da or 0) < int(db or 0))
    return 0

def vercmp(a, b):
    """Debian version comparison (epoch:upstream-revision), as dpkg does it."""
    def split(v):
        e, _, rest = v.rpartition(":") if ":" in v else ("0", "", v)
        u, _, r = rest.rpartition("-") if "-" in rest else (rest, "", "0")
        return int(e or 0), u, r
    ea, ua, ra = split(a); eb, ub, rb = split(b)
    if ea != eb:
        return (ea > eb) - (ea < eb)
    return _cmp_part(ua, ub) or _cmp_part(ra, rb)

def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()

def index(base, suite):
    path = f"main/binary-{ARCH}/Packages.xz"
    try:
        data = fetch(f"{base}/dists/{suite}/{path}")
    except urllib.error.HTTPError:
        # Some mirrors serve indexes only by hash, as apt fetches them (Acquire-By-Hash).
        release = fetch(f"{base}/dists/{suite}/Release").decode()
        sha = re.search(r"^ ([0-9a-f]{64}) +\d+ " + re.escape(path) + "$", release, re.M).group(1)
        data = fetch(f"{base}/dists/{suite}/main/binary-{ARCH}/by-hash/SHA256/{sha}")
    text = lzma.decompress(data).decode()
    pkgs = {}
    for stanza in text.split("\n\n"):
        f = dict(re.findall(r"^(Package|Version): (.+)$", stanza, re.M))
        if "Package" in f and (f["Package"] not in pkgs or vercmp(f["Version"], pkgs[f["Package"]]) > 0):
            pkgs[f["Package"]] = f["Version"]
    return pkgs

def main():
    manifests = sorted(glob.glob(os.path.join(REPO, "image", "mkosi.output", "*.manifest")), key=os.path.getmtime)
    if not manifests:
        print("No image manifest found: build an image first (build/dap-image.sh).", file=sys.stderr); return 2
    installed = {}  # union of every built output (qemu, oci, t1, …)
    for m in manifests:
        for p in json.load(open(m)).get("packages", []):
            if p.get("type") == "deb":
                installed[p["name"]] = p["version"]
    pinned_backports = {n for n in installed if n.startswith("linux-") or "+bpo" in installed[n] or "~bpo" in installed[n]}
    newer = []
    for label, base, suite in INDEXES:
        avail = index(base, suite)
        for name, have in installed.items():
            if label == "backports" and name not in pinned_backports:
                continue
            if name in avail and vercmp(avail[name], have) > 0:
                newer.append((label, name, have, avail[name]))
    os.makedirs(os.path.join(WORKSPACE, ".state"), exist_ok=True)
    with open(os.path.join(WORKSPACE, ".state", "security-check"), "w") as f:
        f.write(f"{int(time.time())}\n{len(newer)} updates\n{' '.join(os.path.basename(m) for m in manifests)}\n")
    print(f"Image manifests: {', '.join(os.path.basename(m) for m in manifests)} ({len(installed)} packages)")
    if not newer:
        print("Up to date with trixie-security, trixie-updates and the pinned backports."); return 0
    print(f"{len(newer)} package(s) with newer versions:")
    for label, name, have, new in sorted(newer):
        print(f"  [{label}] {name}: {have} -> {new}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
