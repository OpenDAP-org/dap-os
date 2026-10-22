# DAP OS: image composition on Debian trixie (RK3566)

- **Date:** 2026-10-21
- **Status:** research, not a decision. Everything under "Recommendation" is a recommendation for the maintainers to decide on.
- **Scope:** which Debian components a trimmed DAP OS image for an RK3566 handheld keeps, replaces or drops. The image is built from Debian 13 *trixie* plus selected *trixie-backports* packages (kernel 7.2.x, Mesa, PipeWire).
- **Companion report:** [2026-10-base-distribution.md](2026-10-base-distribution.md) (choice of base distribution).

## 0. Inputs

### 0.1 Owner direction and constraints

1. Debian is the base. Components are trimmed or added from there.
2. **Use the most standard, open-source Linux option, without tricks.** A clever replacement for a Debian default (for example swapping out systemd or coreutils) is a cost. It needs a strong reason, backed by measurements.
3. Start from prebuilt Debian packages. Do not compile the OS (OS-005, OS-006). The system stays desktop-style, not embedded (OS-003).
4. A custom Rust orchestrator manages services. Services can be ephemeral (CLI-like) or persistent engines, in the foreground or background (SYS-003). They talk over a Rust-native bus (SYS-004).
5. The UI is a Rust/Slint runtime on Wayland. It shows *activities*, not windows (SYS-006).
6. **Audio is a top priority.** This is a DAP for audiophiles, so bit-perfect playback is required.
7. **Battery life (power management) is a top priority.**
8. Wi-Fi/BT, USB-C gadget modes, suspend-to-RAM with fast resume, and field updates are required.
9. Third-party capability packages are fetched over HTTP through the package endpoint, using a reverse-domain / well-known scheme (SYS-010, SYS-011). Signed HAT capability manifests are verified on the device (HCS-009..011).

### 0.2 Already decided (taken as given here)

- U-Boot is mainline, built locally, and boots through extlinux with `u-boot-menu`.
- The image is built with **mkosi**, with profiles `t1`, `qemu` and `oci`.
- The root filesystem is **A/B erofs + dm-verity**. The kernel and initrd ship in a **signed FIT**. Over-the-air updates use **RAUC**.
- Non-consumer developer tools come from a separate repository and are not installed by default.

### 0.3 How evidence is marked

- **Versions** were read on 2026-10-21 from Debian's archive metadata ([madison](https://qa.debian.org/madison.php), [packages.debian.org](https://packages.debian.org/trixie/), and the `Packages.xz` indices on `deb.debian.org`).
- **Sizes** marked "measured" come from real `mmdebstrap` builds run on that date. The builds ran natively on arm64 in a `debian:trixie` container, against the live trixie, trixie-updates, trixie-security and trixie-backports archives. Sizes are `du -sxm` of the resulting root tree, in MiB.
- **Kernel facts** come from `/usr/lib/modules/7.2.9+deb13-arm64/config`, extracted from the trixie-backports package `linux-base-7.2.9+deb13-arm64_7.2.9-1~bpo13+1_arm64.deb`.
- Anything marked **UNVERIFIED** comes from memory or from secondary knowledge and was not checked against a primary source in this session.
- No RK3566 hardware was available. Boot-time, power and resume numbers are estimates and are labelled as such.

---

## 1. Key findings (read this first)

1. **Most of the image is the GPU stack and the kernel, not the init system or the shell tools.** In the measured full DAP set (890 MiB raw), the largest packages are:

   | Package | Installed size |
   |---|---|
   | `libllvm19` | 120 MiB |
   | DTBs for every arm64 board (`linux-base-7.2.9`) | 114 MiB |
   | kernel modules | 85 MiB |
   | `mesa-libgallium` | 49 MiB |
   | uncompressed kernel `Image` | 48 MiB |
   | `libz3-4` (pulled in by LLVM) | 26 MiB |

   Against these, **coreutils is 21 MiB and the whole systemd init set is about 46 MiB.** Section 7 has the full budget.
2. **Replacing coreutils with BusyBox is a measured "no".** It saves about 20 MiB (about 3% of the trimmed image), and in our test it broke `apt` straight away:
   - After `dpkg --force-remove-essential` removed coreutils and BusyBox installed its applets, installing `openssh-server` failed.
   - The failure was in its maintainer script, which ran `cp -Z`. BusyBox prints `cp: invalid option -- 'Z'`.
   - The dpkg database stayed broken afterwards, so later `apt` installs failed too.

   This is exactly the kind of trick the maintainers wants to avoid (section 3).
3. **Replacing systemd saves about 18 MiB of RAM and 37 MiB of disk, and costs a lot.**
   - Measured in a container: systemd, journald, udevd, logind and dbus-broker together use about **24.6 MiB PSS**. sysvinit with elogind, seatd and dbus-daemon uses about **6.9 MiB**, but that figure does not include udev.
   - Disk: 151 MiB with systemd versus 114 MiB with sysvinit, both on top of minbase.
   - What would be lost: socket activation, cgroup-based supervision, `StartTransientUnit` for the orchestrator, the sandboxing directives, the user manager that PipeWire's Debian units expect, `systemd-sleep`/logind suspend inhibitors, and the default path that Debian actually tests.
   - **dinit and s6-rc are not packaged in Debian at all.**
   - Recommendation: keep systemd as PID 1 and run the orchestrator under it (section 2).
4. **The backports PipeWire 1.6.9 pulls in an ML runtime.** In trixie-backports, `libspa-0.2-modules` hard-depends on `libonnxruntime1.21` because of its `filter-graph` ONNX plugin. That drags in about **54 MiB** (onnxruntime, dnnl, onnx, abseil, protobuf, xnnpack). The trixie PipeWire 1.4.2 does not. It is worth filing a Debian bug asking for the plugin to be split into its own package (section 5).
5. **Mesa brings in LLVM even though Panfrost does not need it.** Debian's `mesa-libgallium` (26.1.6 in backports) links `libllvm19`, and LLVM needs `libz3-4`. Together that is about **195 MiB** for a GPU (Mali-G52) whose driver uses no LLVM. Without rebuilding Mesa, which the maintainers rules out, this cannot be removed. Accept it, or open a Debian discussion about a non-LLVM gallium flavour (open question Q3).
6. **The Debian kernel ships DTBs for RK3566 handhelds, but not the panel drivers they use.**
   - The DTBs `rk3566-anbernic-rg353*`, `rg503`, `rg-arc-*` and `powkiddy-*` are all present.
   - Only 13 DSI/eDP panel drivers are enabled. Among those that are off: `NEWVISION_NV3051D`, `HIMAX_HX8394`, `ILITEK_ILI9881C`, `ELIDA_KD35T133` and `MAGNACHIP_D53E6EA8966`, while 116 panel symbols in all are not set.
   - **The T1 panel has to be one whose driver Debian enables, or we file a Debian kernel config merge request** (as already proposed for i.MX8MP in the base-distribution report).
7. **The kernel config is otherwise good for a DAP.** Enabled:
   - Panfrost and VOP2/DSI;
   - RK817 codec and charger, I2S-TDM, SPDIF;
   - `SND_USB_AUDIO`;
   - DWC3 dual-role and the configfs gadget functions UAC2, NCM, mass storage, HID and FunctionFS;
   - Type-C TCPM/FUSB302;
   - `SUSPEND`, `ENERGY_MODEL`, schedutil by default, devfreq simple_ondemand;
   - Landlock, which is first in `CONFIG_LSM`, plus AppArmor, IPE and BPF-LSM;
   - dm-verity with root-hash signatures, erofs with LZMA, overlayfs, PSI, `PREEMPT_LAZY` and HZ=250.

   Not set: `PM_WAKELOCKS`, `USB_CONFIGFS_F_MIDI2`, `ARM_SCMI_CPUFREQ`. The RK3566 uses cpufreq-dt over an SCMI clock (`COMMON_CLK_SCMI=y`), so the last one is not needed.
8. **Backports packages need explicit pinning.** Without an apt preferences file, `apt` cannot solve `wireplumber/trixie-backports` (it needs a `libwireplumber-0.5-0` of exactly the same version). The backports kernel PreDepends `linux-base (>= 4.17~)`, which only backports has. The working pin covers these source packages: `src:mesa src:pipewire src:wireplumber src:alsa-ucm-conf src:alsa-lib src:linux src:linux-signed-arm64 src:linux-base src:firmware-nonfree` (section 7.3).
9. **The trimmed full image is about 683 MiB raw and 218–352 MiB compressed.** Measured:

   | Root image | Size |
   |---|---|
   | raw tree | 683 MiB |
   | erofs LZMA (64 KiB clusters) | 231 MiB |
   | erofs zstd | 315 MiB |
   | erofs lz4hc | 352 MiB |
   | squashfs zstd-19, `/boot` excluded (comparison) | 218 MiB |

   For comparison, a stock minbase is 149 MiB raw, or 105 MiB with docs, man pages and locales excluded.

---

## 2. Init and service management

### 2.1 What is in trixie

| Init / supervisor | Package and trixie version | Notes |
|---|---|---|
| **systemd** | `systemd` 257.13-1~deb13u1 (sid 262.1-1, no backport) | Default since jessie, and the only init "fully supported" ([wiki.debian.org/Init](https://wiki.debian.org/Init)) |
| sysvinit | `sysvinit-core` 3.14-4 | "mostly supported", and packages "are not required to support it" ([wiki](https://wiki.debian.org/Init)) |
| OpenRC | `openrc` 0.56-1 | Alternative since buster |
| runit | `runit-init` 2.2.0-3 | "Support for running runit as PID 1 is still considered experimental" ([wiki](https://wiki.debian.org/Init)) |
| s6 | `s6` 2.13.1.0-1 | Supervision only. **`s6-rc` and `s6-linux-init` are not in Debian** (madison returns nothing) |
| finit | `finit` 4.12-1 | Small, rarely used on Debian |
| **dinit** | **not packaged** in any Debian suite (madison returns nothing) | Would have to be built by us, which breaks OS-005/006 |
| elogind | `elogind` / `libpam-elogind` 255.17-1debian2 | Standalone logind. `Conflicts: systemd`, and provides `logind` |
| seatd | `seatd` / `libseat1` 0.9.1-1 | `libseat1` depends on `seatd \| logind` |

### 2.2 What systemd components are worth keeping

The trixie `systemd` package already contains networkd, logind, journald, `systemd-run`, sysext/confext and `run0`, as the [systemd trixie arm64 file list](https://packages.debian.org/trixie/arm64/systemd/filelist) shows. Other components are split into their own packages, so each can be left out. `systemd-sysupdate` ships in `systemd-container`, not on its own (per the [contents search](https://packages.debian.org/search?searchon=contents&keywords=systemd-sysupdate&mode=exactfilename&suite=trixie&arch=arm64)).

| Component | Keep? | Why |
|---|---|---|
| PID 1 + cgroup v2 supervision | **Keep** | The orchestrator gets restart policies, resource limits (`MemoryMax=`, `CPUWeight=`, `CPUQuota=`), freezing (`systemctl freeze` uses the cgroup freezer, and `CGROUP_FREEZER=y` is set), and PSI-based OOM handling without reimplementing them. |
| Transient units (`StartTransientUnit` on D-Bus, `systemd-run`) | **Keep, and use from the orchestrator** | Ephemeral CLI-like services map to transient `.service` units. Foreground tools the orchestrator launches itself map to `.scope` units. All the sandboxing properties can be set per run ([systemd-run(1)](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)). |
| Socket activation | **Keep** | Persistent engines can start on demand. This saves RAM and boot time. |
| Sandboxing (`ProtectSystem=`, `DynamicUser=`, `PrivateNetwork=`, `RestrictAddressFamilies=`, `SystemCallFilter=`, `PrivateDevices=`, `RootImage=`, `ExtensionImages=`, `MountImages=`, `IPAddressDeny=`, …) | **Keep** | This is the cheapest, best-tested way to sandbox third-party capabilities ([systemd.exec(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html), systemd 262 docs, mostly present in 257). |
| `systemd-udevd` (`udev` 257.13) | **Keep** | Every alternative init on Debian still uses this same udev (Debian has no eudev package). libinput, libseat, PipeWire's ALSA monitor, BlueZ and iwd all rely on it. |
| `systemd-logind` | **Keep** | Seats and sessions for the compositor through libseat, device access, the `user@.service` for PipeWire, `XDG_RUNTIME_DIR`, suspend inhibitor locks, and power-key handling ([systemd-logind(8)](https://manpages.debian.org/trixie/systemd/systemd-logind.service.8.en.html)). WirePlumber's BlueZ seat monitoring integrates with logind and switches itself off without it ([WirePlumber docs](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html)). |
| `systemd-journald` | **Keep, tuned** | Set `Storage=volatile` (or `persistent` with a small `SystemMaxUse=`) and `RateLimit*`. Measured at 6.9 MiB PSS in the container. It is the single largest daemon and a natural place to trim memory. Do not add rsyslog. |
| D-Bus broker | **Keep `dbus-broker` 37-2** | BlueZ, iwd/NetworkManager, logind, WirePlumber, RAUC and polkit all need a system bus, even though our own services use the Rust bus. In the container, dbus-broker used about 2.7 MiB PSS. |
| `systemd-networkd` | **Optional** | Used only if we choose iwd for Wi-Fi (section 6). |
| `systemd-resolved` (separate package) | **Keep** | It gives per-link DNS and DNS-over-TLS, and gives the orchestrator a varlink/D-Bus API. |
| `systemd-timesyncd` | **Keep** | Small SNTP client. chrony is unnecessary on a handheld. |
| `systemd-homed` | **Drop** | Single-user device. Not useful. |
| `systemd-boot` | **Drop** | We boot with U-Boot extlinux and a FIT. systemd-boot is EFI-only. |
| `systemd-repart` | **Keep (build host + first boot)** | Grows or creates the `/var` partition on first boot. |
| `systemd-container` | **Optional** | Provides nspawn and sysupdate. Useful for the `qemu`/`oci` profiles and OS-009. Not needed on T1 if RAUC does the updates. |
| `systemd-coredump`, `-oomd`, `-userdbd`, `-cryptsetup`, `-journal-remote` | Drop by default | `oomd` is worth re-evaluating once memory pressure on T1 is known. |

### 2.3 Cost of the alternatives (measured)

The builds below are minbase plus the docs/man/locale `path-exclude` set, over the live archive, `du -sxm`.

| Init set | Disk | Packages |
|---|---|---|
| `systemd systemd-sysv udev libpam-systemd dbus-broker` | **151 MiB** | 91 |
| `sysvinit-core elogind libpam-elogind dbus-daemon seatd orphan-sysvinit-scripts` | 114 MiB | 103 |
| `sysvinit-core openrc seatd dbus-daemon` | 115 MiB | 97 |
| `runit-init seatd dbus-daemon` | 167 MiB | 105 |

Memory after boot was measured in a privileged container, using the sum of `Pss` from `/proc/*/smaps_rollup` once udev had settled. There is no kernel or hardware in this setup, so udevd and journald will use somewhat more on the device.

| Process | systemd set (PSS / RSS, KiB) | sysvinit + elogind set (PSS / RSS, KiB) |
|---|---|---|
| PID 1 | systemd 7 377 / 12 736 | init 520 / 1 876 |
| logging | journald 6 865 / 11 936 | none (no syslog installed) |
| udev | udevd 4 037 / 9 200 | not started in the container (the Debian udev init script skips containers) |
| login/seat | logind 2 766 / 7 776 | elogind 1 913 / 3 116, seatd 285 / 1 776 |
| D-Bus | dbus-broker-launch 1 928 + dbus-broker 820 | dbus-daemon 1 634 |
| **Total** | **about 24.6 MiB** | **about 6.9 MiB, without udev** (getty processes included) |

`systemd-analyze` in the container reported userspace startup in **149 ms**, with `graphical.target` reached after 143 ms. This is only a lower bound for systemd's own overhead. On T1, boot time will be set by U-Boot, the kernel and device probing (section 8).

What each alternative loses compared with systemd:

- **sysvinit/OpenRC + elogind + seatd.**
  - Lost: transient units, socket activation and the sandboxing directives. Our orchestrator would have to reimplement cgroups, seccomp, namespaces and Landlock, or wrap bubblewrap.
  - The user service manager is gone. PipeWire, pipewire-pulse and WirePlumber ship as `systemd --user` units and sockets in Debian, so they would have to be started by hand from the session.
  - `elogind` Conflicts with `systemd`, so the whole systemd suite has to go.
  - Debian packages "are not required to support" sysvinit, and `orphan-sysvinit-scripts` covers only some of the gaps.
- **runit.** Everything sysvinit loses, plus PID-1 support is "experimental", and this set was the largest measured (167 MiB).
- **s6 / dinit.** Not available as a full init in Debian, so they would have to be built and maintained by us. That conflicts with OS-005/006 and with the maintainers' "no tricks" rule.

**The trade:** about 18 MiB of RAM (out of the 1–4 GB an RK3566 board usually carries; the T1 RAM size is not decided) and about 37 MiB of disk. In return, the alternatives need a custom supervision layer, a non-default and less-tested Debian path, and manual PipeWire session startup. Under the maintainers' "standard, trick-less" rule, that is not a strong enough reason.

### 2.4 Where the orchestrator sits

| Option | Assessment |
|---|---|
| Orchestrator as PID 1 | **Not recommended.** It would have to reap zombies, run early mounts, handle udev coldplug, shutdown ordering, cgroup delegation and emergency mode. A bug there panics the kernel. It throws away everything in section 2.2. |
| Orchestrator replaces parts of systemd | Not recommended. Same objection, only partial. |
| **Orchestrator as a systemd service that owns a delegated cgroup subtree and creates transient units** | **Recommended.** The orchestrator runs as `dap-orchestrator.service`, with `Delegate=yes` if it manages its own sub-cgroups, or with no delegation if it asks PID 1 for every unit. It calls `StartTransientUnit` over D-Bus with per-capability properties (sandbox, `Slice=`, `MemoryMax=`, `CPUWeight=`, `RootImage=`/`MountImages=`). Foreground activities are scopes or services in a `foreground.slice` with higher `CPUWeight=`. Background engines live in `background.slice`. Activity pause/resume (SYS-006) maps to the cgroup freezer (`systemctl freeze`/`thaw`, or `FreezeUnit` on D-Bus). The bus (SYS-004) stays the orchestrator's own. D-Bus is used only as the control channel to systemd, logind, BlueZ, iwd and RAUC. |

Whether the session (compositor, PipeWire, activities) runs under `user@.service` for an unprivileged `dap` user or as system units with `User=` is an open question (Q5). The `user@` route matches what PipeWire, WirePlumber and logind expect out of the box.

---

## 3. Userland

### 3.1 Base variants (measured)

The variant definitions are from [mmdebstrap(1) in trixie](https://manpages.debian.org/trixie/mmdebstrap/mmdebstrap.1.en.html), mmdebstrap 1.5.7.

| Variant | Definition | Size | Packages | Time to build |
|---|---|---|---|---|
| `essential` | `Essential: yes` packages only | 122 MiB | 59 | 15 s |
| `minbase` / `required` | essential + `Priority: required` (includes apt) | 149 MiB | 78 | 21 s |
| `minbase` + docs/man/locale `path-exclude` | same | **105 MiB** | 78 | 18 s |
| `important` (debootstrap default) | required + `Priority: important` | 236 MiB | 144 | 29 s |

`systemd` is `Priority: important`, so a minbase has no init at all. The image has to add it explicitly.

### 3.2 BusyBox in place of coreutils/util-linux (measured, not recommended)

- **Package.** Debian has `busybox` 1:1.37.0-6+b9 (967 KiB installed, depends only on libc6) and `busybox-static`. Per [packages.debian.org](https://packages.debian.org/trixie/busybox), the package "installs the BusyBox binary but does not install symlinks for any of the supported utilities". The trixie build has **271 applets**.
- **Coverage.** 28 of the 104 coreutils binaries have no BusyBox applet: `b2sum base32 basenc chcon cksum comm csplit dir dircolors fmt join nice nohup numfmt pathchk pinky pr printenv ptx runcon sha224sum sha384sum split stdbuf sum tsort users vdir`. Many of the applets that do exist lack GNU options.
- **Size.** `coreutils` is 21 046 KiB, `util-linux` 7 402, `findutils` 2 248, `tar` 3 105, `diffutils` 1 876, `grep` 1 263 and `sed` 995. All of these are `Essential: yes`. Replacing coreutils alone saves about 20 MiB.
- **Compatibility test.** On the full DAP tree:
  1. `dpkg --remove --force-remove-essential --force-depends coreutils` succeeded, with a warning.
  2. `busybox --install -s /usr/bin` succeeded.
  3. `apt-get install openssh-server` **failed**. Its postinst ran `cp -Z`, and BusyBox replied `cp: invalid option -- 'Z'`.
  4. A later `apt-get install --reinstall systemd udev` also failed, because dpkg kept trying to configure the broken package.

  Debian maintainer scripts may assume every Essential package and its GNU options, and Debian Policy allows them to.
- **Verdict.** Keep coreutils and util-linux. BusyBox can still be installed as an extra package, for example inside the initrd, or as a small rescue shell (`busybox-static`). It must not replace Essential packages.

### 3.3 Shells

- `dash` 0.5.12 is `/bin/sh` (Essential) and `bash` 5.2.37 is Essential. Keep both.
- Dropping bash would save about 7 MiB. It is Essential, so the same objection applies as for coreutils.
- An interactive shell for developers belongs to the separate developer repository.

### 3.4 Trimming files, not packages

- **dpkg filters.** These are the supported mechanism ([dpkg(1) `--path-exclude`](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html), recommended by [wiki.debian.org/ReduceDebian](https://wiki.debian.org/ReduceDebian)). Drop `/usr/share/{man,info,doc,locale,lintian,bug}`. Re-include `/usr/share/doc/*/copyright`, which licence compliance needs, and `locale.alias`. Measured saving on minbase: 149 → 105 MiB (−30%). With mkosi this is configured via `WithDocs=no` plus explicit dpkg `path-exclude` drop-ins in the image tree (**UNVERIFIED** exact mkosi option behaviour on Debian in 25.3).
- **Kernel payload filters.** These also go through dpkg and need no rebuild:
  - `path-exclude=/usr/lib/modules/*/dtb/*` with `path-include=…/dtb/rockchip/rk356*`;
  - excludes for the AMD, nouveau, radeon, xe and i915 DRM modules, DVB, PCI media, Ethernet, InfiniBand, SCSI and RC.

  Measured: the modules tree went from 259 to 125 MiB, and the whole tree from 890 to 683 MiB. This needs care. `depmod` runs from the postinst, and any module needed later (a USB Ethernet gadget, a USB DAC quirk) must not be excluded. The exclude list must be reviewed against the T1 device tree and the HAT catalogue.
- **`localepurge`** is unnecessary once dpkg filters are in place.
- **Recommends.** mmdebstrap and mkosi do not install Recommends by default. Keep it that way, because many Debian Recommends are desktop conveniences.

---

## 4. Graphics and session

### 4.1 GPU: Mali-G52 on Panfrost

- **Kernel:** `DRM_PANFROST=m`, `DRM_ROCKCHIP=m`, `ROCKCHIP_VOP2=y`, `ROCKCHIP_DW_MIPI_DSI=y`, `PHY_ROCKCHIP_INNO_DSIDPHY=m` (backports 7.2.9 config).
- **Mesa:** trixie has 25.0.7-2+deb13u1. **trixie-backports has 26.1.6-1~bpo13+1** (sid 26.2.5-1).
- **Feature levels:** Mesa's [Panfrost page](https://docs.mesa3d.org/drivers/panfrost.html) lists Mali-G52 with OpenGL ES 3.1 (conformant submission), OpenGL 3.1 and Vulkan 1.3. On GPUs where PanVK is experimental, the driver refuses to load unless `PAN_I_WANT_A_BROKEN_VULKAN_DRIVER=1` is set. Whether G52 is still experimental for PanVK in 26.1 is **UNVERIFIED**. Plan for GLES (Slint's FemtoVG or Skia-GL renderer) and do not depend on Vulkan.
- **Recommendation:** use the backports Mesa, since Panfrost Bifrost work lands continuously. Install only `libegl-mesa0 libgles2 libgbm1 mesa-libgallium`, not `mesa-vulkan-drivers` (unless PanVK is wanted) and not the X11 GLX packages.
- **Cost:** `mesa-libgallium` 26.1.6 depends on `libllvm19` (120 MiB), `libdrm-amdgpu1`, `libsensors5` and X11/XCB libraries. Measured: adding the GPU and input stack to the systemd base takes 151 → **428 MiB**.

### 4.2 Seat management

- **Recommendation:** `libseat1` with **logind** as the backend. It comes for free with systemd. libseat picks its backend at runtime: seatd, logind or builtin (the man page is [seatd(8)](https://manpages.debian.org/trixie/seatd/seatd.8.en.html); the backend-selection details are **UNVERIFIED** there). Slint's linuxkms backend, Smithay, wlroots and cage all use libseat.
- `seatd` (0.9.1) is only needed if logind is dropped (section 2.3).

### 4.3 Compositor and shell

| Option | In Debian | Fit |
|---|---|---|
| **Slint `backend-linuxkms`** (no Wayland) | Our own Rust build, Slint 1.18.1. It needs `libgbm`, optional `libseat`/`libinput`/`libudev`/`libxkbcommon`, and fontconfig ([Slint linuxkms doc](https://github.com/slint-ui/slint/blob/master/docs/astro/src/content/docs/guide/backends-and-renderers/backend_linuxkms.mdx)) | Fastest to first pixel and lowest RAM. **Not Wayland**, so third-party activities would have to be in-process or rendered by the shell. Ruled out by the maintainers as the product architecture. Still useful for a recovery or update UI. |
| **cage** (kiosk) | `cage` 0.2.0-2 in trixie (wlroots 0.18), 0.3.1 in sid. Trixie's cage **Depends: `xwayland`**, which pulls in an X server | "A kiosk runs a single, maximized application" ([cage README](https://github.com/cage-kiosk/cage)). Good for **bring-up**: run cage with a single Slint client (winit/Wayland). It has no shell semantics (activities, overlays, system UI layers). |
| sway / labwc / weston | 1.10.1 / 0.8.3 / 14.0.2 in trixie | Window managers. Their model is wrong for activities. |
| **Custom Smithay compositor that *is* the shell** | Smithay 0.7.0 (crates.io, 2025-06-24). Compiled as part of our Rust system software, like the orchestrator, so OS-005/006 still hold. It uses Debian's `libseat1`, `libinput10` 1.28.1, `libgbm1`, `libdrm2`, `libxkbcommon0` and `libwayland-server0` | **Recommended target.** The shell's own UI (status bar, launcher, activity switcher, system dialogs) is Slint rendered inside the compositor. Activities, first or third party, are Wayland clients in a Slint winit/Wayland runtime. The compositor maps each activity's surface fullscreen and tells the orchestrator which activity is in the foreground. The orchestrator then freezes or thaws background activities. Our own protocol extensions, or `xdg-activation` and `xdg-toplevel` states, carry activity lifecycle. Only Debian `.so` files are linked. No X11 or Xwayland is needed. |

#### Recommended path

1. Bring-up: cage + a Slint client (Debian package). Consider building without Xwayland later. With trixie's cage that means accepting the `xwayland` dependency for now, or using sid's 0.3.1 (**UNVERIFIED** whether 0.3.1 still hard-depends on xwayland).
2. Product: our own Smithay shell compositor.

Keep Slint `backend-linuxkms` as the recovery UI.

---

## 5. Audio (top priority)

### 5.1 What "bit-perfect" means here, and where each stack can break it

A bit-perfect path delivers the file's PCM samples unchanged, at the file's own sample rate and in its own format, to the DAC: either the on-board codec over I2S, or a USB DAC. It breaks in five places:

1. **Resampling.** The playback rate differs from the device rate.
2. **Format conversion.** Converting integer to float and back. **PipeWire's graph always processes F32** ([pipewire-props(7)](https://docs.pipewire.org/page_man_pipewire-props_7.html): "the graph processing format is always float 32"):
   - 16-bit and 24-bit integers round-trip through F32 exactly (a 24-bit mantissa);
   - **32-bit integer PCM does not**: the low 8 bits are lost;
   - DSD cannot go through an F32 graph as audio at all.
3. **Volume, mixing and dithering.** Any software volume other than unity, any mixing with another stream (notification sounds), or dither applied on output.
4. **Channel mixing or remapping.**
5. **DoP/DSD mangling.** Any of the above applied to DoP frames destroys the DSD marker.

### 5.2 Paths compared

| Path | Bit-perfect PCM | Per-track rate switching | DSD | Mixing with other sounds | Notes |
|---|---|---|---|---|---|
| **Direct ALSA `hw:` (exclusive)** from our playback engine | Yes, by construction (no `plug`, no `dmix`) | Yes. Reopen the PCM with the track's rate and format | Native DSD (`DSD_U8`/`DSD_U16_*`/`DSD_U32_*`) where the driver exposes it. **DoP** works over any 24-bit-capable PCM device | **No.** The device is exclusive | Most predictable. The engine owns period/buffer sizing and xrun handling. |
| **PipeWire, normal profile** | 16/24-bit yes, when unity volume, matching rate and no other streams. 32-bit no | Only if `default.clock.allowed-rates` is set. Upstream does not enable it by default "because of various kernel and Bluetooth issues" ([pipewire.conf(5)](https://docs.pipewire.org/page_man_pipewire_conf_5.html)). The rate switches only when the device is idle | Upstream ships `pw-dsdplay` (in `pipewire-bin` 1.6.9), and `api.alsa.dsd-lsb` exists, so a native DSD path exists for capable ALSA devices (**UNVERIFIED** in which conditions and on which devices it works). DoP through the F32 graph is not safe | Yes | Default resampler `resample.quality = 4` (range 0–14) ([pipewire-props(7)](https://docs.pipewire.org/page_man_pipewire-props_7.html)). |
| **PipeWire, pro-audio profile + per-node settings** | Closer. Pro-audio exposes raw device channels and "disables timer-based scheduling in favor of IRQ-based scheduling". The client sets `audio.format`, `audio.rate` (forces a rate on the node), `node.force-rate`/`node.lock-rate`, `resample.disable = true`, `channelmix.disable = true`, `dither` off | Yes, with `allowed-rates` set or the rate forced per stream | As above | Possible, but any mix breaks bit-perfection for that moment | "Bit-perfect when alone". |
| PulseAudio | No | No | No | Yes | Not considered. |

### 5.3 Recommended audio architecture (recommendation)

- **PipeWire + WirePlumber is the system audio server.** It handles UI sounds, Bluetooth (A2DP/LE Audio codecs from `libspa-0.2-bluetooth` 1.6.9: LDAC, aptX, LC3, …), USB-gadget UAC2 capture, and third-party capabilities that just "play sound".
- **The first-party playback engine has two output modes, chosen per device:**
  1. **"Bit-perfect / exclusive"** (default for wired outputs). The engine asks PipeWire/WirePlumber to release the ALSA card, then opens `hw:CARD,DEV` directly through `alsa-lib` (backports 1.2.16.1).
     - Release goes through the D-Bus device-reservation protocol (`org.freedesktop.ReserveDevice1`), which PipeWire's ALSA monitor implements (**UNVERIFIED** current WirePlumber property name). Alternatively, the orchestrator can disable the device node in WirePlumber.
     - The engine opens a stream per track at the file's native rate and format: S16/S24_3LE/S24_LE/S32_LE, or DSD-native or DoP when the DAC supports it.
     - System sounds are muted, or rendered by the engine itself, while exclusive mode holds the device.
  2. **"Shared"** (Bluetooth, or when the user mixes sources). The engine is a PipeWire client with `resample.disable`, `channelmix.disable`, `node.force-rate = <track rate>`, `audio.allowed-rates` on the sink, `resample.quality` raised (10–14) for the cases where conversion is unavoidable, and unity volume with hardware volume where the codec offers it.
- **Do not use `pipewire-pulse` or `pipewire-alsa` for the first-party engine.** `pipewire-alsa` is still worth installing, so that third-party code that opens `default` lands in PipeWire.
- **Package versions.** Prefer backports `pipewire` 1.6.9, `wireplumber` 0.5.12, `alsa-ucm-conf` 1.2.16.1 and `alsa-lib` 1.2.16.1. These carry newer UCM profiles and USB-audio fixes. The cost is the ONNX dependency chain (about 54 MiB, finding 4). The alternative is trixie's 1.4.2/0.5.8, which is about 50 MiB lighter (resolver estimate) but older. File a Debian bug asking to split `libspa-filter-graph-plugin-onnx.so` out of `libspa-0.2-modules`.

### 5.4 Sample-rate switching per track

- **Exclusive ALSA:** `snd_pcm_hw_params` per track. On the RK817 codec, the I2S master clock (MCLK) must be re-derived for the 44.1 kHz and 48 kHz families. On RK3566 the I2S-TDM block takes MCLK from the CRU PLLs. Whether mainline's `rockchip_i2s_tdm` and the clock tree can produce exact 44.1k-family MCLKs, or round them, is **UNVERIFIED** and is a bring-up test item. If they round, the pitch error is inaudible, but the result is not "clock-exact".
- **PipeWire shared:** `default.clock.allowed-rates = [ 44100 48000 88200 96000 176400 192000 352800 384000 ]` (only the rates the DAC supports). The graph follows the first stream when the device is idle. The engine should leave a short gap (stop the stream, let the node idle) at a rate change.
- **USB DACs:** `snd-usb-audio` (`SND_USB_AUDIO=m`) switches rate per stream, with UAC2 clock-source handling and a quirks table for DSD (**UNVERIFIED**: the exact quirk coverage for the target DACs).

### 5.5 DSD

- **DoP** (DSD over PCM: DSD bits packed into 24-bit PCM frames at 176.4k for DSD64, 352.8k for DSD128, with 0x05/0xFA markers) works over any path that is truly bit-perfect at 24 bits. That means **exclusive ALSA only**: no F32 graph, no volume.
- **Native DSD** (`SND_PCM_FORMAT_DSD_U32_BE` and similar) works when the USB DAC is in the `snd-usb-audio` DSD quirk list, or an I2S DAC driver declares DSD formats. The RK817 codec does not support DSD (**UNVERIFIED**, but very likely). A HAT DAC would need an ASoC codec driver with DSD DAI support and a Debian-enabled config symbol.
- **Software DSD→PCM** conversion is a fallback for non-DSD outputs. It is not bit-perfect by definition.

### 5.6 Latency, xruns, CPU frequency, real-time scheduling

- **Playback-only needs no low latency.** For power, use **large buffers**: a 100–500 ms ALSA buffer, and in PipeWire `default.clock.quantum` of 2048–8192 at 44.1k with `api.alsa.headroom` raised. Fewer wakeups mean longer CPU idle residency. Low quantum is for the UAC2-gadget or monitoring cases only.
- **Real-time scheduling.**
  - `pipewire-bin` ships `/etc/security/limits.d/25-pw-rlimits.conf` (in the backports file list). Add `rtkit` 0.13 so that PipeWire can get SCHED_FIFO without root.
  - Our own engine gets real-time priority through its systemd unit (`CPUSchedulingPolicy=fifo`, `CPUSchedulingPriority=`, `LimitRTPRIO=`) or through rtkit.
  - `RT_GROUP_SCHED` is not set, so real-time priority is not limited per cgroup. That is fine.
- **CPU frequency.** The default governor is schedutil (`CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y`). With large buffers, decoding FLAC/ALAC/WAV costs a few percent of one A55 core at minimum OPP. Xruns at low frequency come from wake-up latency, not throughput.
  - Use `uclamp` (`UCLAMP_TASK=y`) on the engine's cgroup (`CPUSchedulingPolicy` plus `cpu.uclamp.min`) so schedutil does not drop too low while decoding.
  - Do not use the `performance` governor: it costs battery for no audible gain.
- **Kernel.** `PREEMPT_LAZY=y`, `HIGH_RES_TIMERS=y`, `SND_HRTIMER=m`, HZ=250, `NO_HZ_FULL=y`. That is adequate for playback. **PREEMPT_RT is not needed and not available**: there is no RT flavour in the Debian arm64 backports list, and building one is out of scope (**UNVERIFIED** whether Debian still ships `-rt-arm64`).

### 5.7 USB-C audio roles

- **Host to USB DAC:** `snd-usb-audio` as above. Needs DWC3 in host or dual-role mode (`USB_DWC3_DUAL_ROLE=y`, TCPM, FUSB302).
- **Device / "DAP as USB sound card":** configfs `f_uac2` (`USB_CONFIGFS_F_UAC2=y`). The gadget appears as an ALSA capture device that PipeWire or the engine routes to the DAC. Rate and format are fixed by gadget attributes (`c_srate`, `c_ssize`), so this is bit-perfect only when they match the host stream (**UNVERIFIED**: support for multiple rates in `f_uac2` on 7.2).

### 5.8 Audio components to install

`pipewire pipewire-bin wireplumber pipewire-alsa libspa-0.2-bluetooth rtkit alsa-utils alsa-ucm-conf`, all from backports where available.

Optional extras:

- `alsa-tools`;
- `sox`, a test tool that belongs to the developer repo;
- `mpd` 0.24.4, only as a reference implementation during bring-up. It supports both DoP and native DSD outputs to ALSA (**UNVERIFIED** for 0.24 specifics).

---

## 6. Networking and connectivity

| Need | Recommendation | Alternatives (trixie versions) |
|---|---|---|
| Wi-Fi | **iwd** 3.8-2 (2.1 MiB, depends only on `libell0` and readline). It has its own DHCP and DNS hand-off to resolved (`EnableNetworkConfiguration=true`), so systemd-networkd is not even needed for Wi-Fi-only. Lower RAM and faster roaming and reconnect after resume than wpa_supplicant. | NetworkManager 1.52.1 + wpa_supplicant 2.10 (measured **+17 MiB** over the iwd set, plus ModemManager, ppp and polkit through Recommends). NM can use iwd as its backend. ConnMan 1.44 is less standard. |
| Wired / USB-NCM gadget / tethering | `systemd-networkd` (inside `systemd`): static or DHCP-server config for the `usb0` NCM gadget | NM |
| DNS | `systemd-resolved` 257.13 | — |
| Bluetooth | **BlueZ** 5.82-1.1, plus PipeWire's BlueZ SPA plugins for audio. Kernel: `BT_HCIUART_SERDEV`, `BT_HCIUART_BCM=y` | — |
| Wi-Fi/BT firmware | `firmware-brcm80211` 20260916-1~bpo13+1 (backports, 18 MiB). Use dpkg `path-exclude` to keep only the T1 chip's files (**UNVERIFIED** which module T1 uses) | `firmware-realtek` for an RTL8723CS-class module (`RTW88_8723CS=m`) |
| USB gadget | Kernel configfs functions as listed in finding 7. **Debian has no gadget-composition tool.** It has `libusbgx3`/`libusbgx-dev` 0.3.0 (no `gt` CLI), `umtp-responder` 1.3.10 (MTP over FunctionFS), `adbd`, `dfu-util` | Use a small Rust "gadget" service of our own that writes configfs directly (the "standard" kernel ABI, no library) and is driven by the orchestrator and the Type-C role events, or use `libusbgx` through FFI. Modes: NCM (dev and network), UAC2 (USB sound card), MTP (library sync), mass storage (recovery), FunctionFS for a custom protocol. |
| Regulatory | `wireless-regdb` | — |

---

## 7. Updates and image layout

### 7.1 Layout (the decided A/B erofs + dm-verity + signed FIT, made concrete)

```text
eMMC / SD
├─ (raw) idbloader / U-Boot ITB         # mainline U-Boot, built locally (decided)
├─ boot_a   (FAT or ext4)  signed FIT: kernel Image + initrd + DTB(+overlays) + cmdline with roothash
├─ boot_b
├─ root_a   erofs (LZMA)  + verity_a     # /usr + /etc defaults, read-only
├─ root_b   erofs (LZMA)  + verity_b
└─ data     ext4 or f2fs                 # /var, /home, capabilities, logs; created/grown by systemd-repart
```

- `/` is read-only erofs. `/etc` comes from the image with a small writable overlay or a tmpfs plus `systemd-tmpfiles` and confext (Q8). `/var` is the data partition.
- **U-Boot verified boot** checks the FIT signature. The root hash lives in the signed FIT (cmdline or initrd), so dm-verity needs no kernel keyring. With a stock Debian kernel we cannot add our own key to the builtin keyring. `DM_VERITY_VERIFY_ROOTHASH_SIG_SECONDARY_KEYRING` / `_PLATFORM_KEYRING` exist, but there is no UEFI db on U-Boot, so we cannot rely on them.
- **Kernel size.** Debian's arm64 `vmlinuz` is an **uncompressed 48.7 MiB Image** (measured). The FIT can carry it compressed (gzip or lz4, done at image build time, so no compiling). This cuts eMMC read time and the cost of hashing the signature.
- **initrd.** In our build, `initramfs-tools` with `MODULES=most` gave 25 MiB. Use mkosi-initrd (systemd in the initrd: `systemd-veritysetup`, repart), or initramfs-tools with `MODULES=dep` and a hook for verity. Target is 10 MiB or less (estimate).
- **extlinux / u-boot-menu.** `u-boot-menu` 4.2.4 writes `extlinux.conf` from Debian kernel hooks. That suits the `qemu` profile and dev units. On T1 with RAUC, each slot carries a fixed extlinux entry that points at its signed FIT. RAUC's U-Boot bootchooser chooses the slot. Whether U-Boot's extlinux `fit` handling enforces FIT signatures the same way as `bootm` is **UNVERIFIED** and must be tested.

### 7.2 Update mechanisms compared

| Mechanism | Trixie version | Fit |
|---|---|---|
| **RAUC** (decided) | `rauc` 1.13-3+deb13u1 (sid 1.15.2) | Signed bundles (X.509/CMS). **Verity** bundle format with HTTP(S) streaming through range requests since 1.7, adaptive updates, U-Boot/barebox/GRUB/EFI backends, mark-good/bad ([RAUC docs](https://rauc.readthedocs.io/en/latest/basic.html)). Depends on `dbus` and `systemd`. Its `libcurl` HTTP works through the package endpoint. |
| systemd-sysupdate | in `systemd-container` 257.13 | A/B partitions or files, `url-file`/`url-tar` sources, verification through a GPG-signed `SHA256SUMS` ([sysupdate.d(5)](https://manpages.debian.org/trixie/systemd-container/sysupdate.d.5.en.html)). No bootloader integration on U-Boot. Good for **downloading signed sysext/capability images** (see below), not for the OS. |
| SWUpdate | 2024.12.1 (backports 2026.05.1) | Comparable to RAUC. No reason to switch. |
| OSTree | 2025.2 | File-level, not image-level, and does not fit dm-verity erofs well. |
| apt in place | — | Only for the `qemu` profile and dev units on a writable root. |

**OS-013 (updates from both the distro and the OpenDAP repositories) on a read-only A/B root.** CI rebuilds the image from a pinned `snapshot.debian.org` timestamp whenever Debian publishes security updates. It ships the rebuild as a RAUC bundle. Distro updates therefore still flow, but as images. OpenDAP software that is part of the base also ships in the image. **Capabilities** update on their own, outside the image (7.4). Whether this reading satisfies OS-013 is Q1.

### 7.3 Build notes (mkosi)

- `mkosi` 25.3-7 is in trixie and 27.1-1 in sid. mkosi drives apt, so the measured package sets carry over.
- **Pin backports per source package.** Without this, the solver fails.

  ```text
  # /etc/apt/preferences.d/dap-backports.pref (measured working set)
  Package: src:mesa src:pipewire src:wireplumber src:alsa-ucm-conf src:linux src:linux-signed-arm64 src:firmware-nonfree src:alsa-lib src:linux-base
  Pin: release n=trixie-backports
  Pin-Priority: 990
  ```

- Fetch over **HTTPS** (`https://deb.debian.org`). In our runs the plain-HTTP CDN repeatedly closed the connection while serving the 23 MiB `libllvm19` .deb.
- **Reproducibility:** pin a `snapshot.debian.org` timestamp per release (see the base-distribution report).

### 7.4 Where third-party capabilities live (recommendation)

- **Not in the base image, and not installed through apt into `/usr`.** The root is read-only, and apt maintainer scripts run as root, which is unacceptable for third-party code.
- **Format:** an erofs image per capability version, with a dm-verity hash tree and a detached signed manifest. The manifest matches the SYS-002 schema and is the same schema family as the HAT EEPROM manifest. Images are stored under `/var/lib/dap/capabilities/<reverse-domain-id>/<version>/`.
- **Fetching:** over HTTP(S) through the package endpoint, by the orchestrator (or a `dap-fetch` service). The well-known/reverse-domain scheme (SYS-010) resolves to a manifest URL and an image URL.
- **Running:**
  - Each service of a capability runs as a transient systemd unit with `RootImage=` (full isolation, built on our runtime base) or `MountImages=`/`ExtensionImages=` (overlaid on the host `/usr`), plus `DynamicUser=yes`, `ProtectSystem=strict`, `PrivateDevices=` with a `DeviceAllow=` per declared need, `RestrictAddressFamilies=`, `SystemCallFilter=@system-service`, `IPAddressDeny=`, and Landlock rules applied by our launcher.
  - Activities are Wayland clients that reach only the compositor socket and the bus socket.
- **systemd-sysext** (images in `/var/lib/extensions`, matched on `ID`/`SYSEXT_LEVEL`/`ARCHITECTURE`, overlaid on `/usr`; [systemd-sysext(8)](https://manpages.debian.org/trixie/systemd/systemd-sysext.8.en.html)) is suitable for **first-party, system-wide** add-ons such as the separate developer-tools repository. It is not suitable for third-party capabilities, because it merges into the host's `/usr` for everyone.

---

## 8. Power management (top priority)

### 8.1 Suspend on RK3566 with mainline

- **Kernel:** `SUSPEND=y`, `PM_SLEEP_SMP=y`, `SUSPEND_FREEZER=y`, `PM_ADVANCED_DEBUG=y`, `HIBERNATION=y` (not useful here). `PM_WAKELOCKS` is not set, so the orchestrator holds wake state in userspace through logind inhibitors.
- **Firmware:** deep suspend ("mem", where DDR stays in self-refresh) on Rockchip needs **BL31 PSCI `SYSTEM_SUSPEND` support**.
  - TF-A lists rk3566/rk3568 as supported ([TF-A Rockchip docs](https://trustedfirmware-a.readthedocs.io/en/latest/plat/rockchip.html)) but does not document suspend there.
  - Whether mainline TF-A for rk3568 implements system suspend, as opposed to only Rockchip's `rkbin` BL31, is **UNVERIFIED**. This is the single most important power bring-up item.
  - If only `rkbin` BL31 supports it, U-Boot must be built with that blob (it is non-free but redistributable). That is consistent with the DDR TPL blob already needed.
- **Fallback:** `s2idle` (`mem_sleep` = `s2idle`) works generically through the freezer and PSCI CPU idle (`ARM_PSCI_CPUIDLE=y`), but draws noticeably more than deep sleep. The figure is **UNVERIFIED** for RK3566. Measure both.
- **Resume speed:** dominated by device resume (DSI panel power-on sequence, brcmfmac SDIO, the USB PHYs) and by userspace thaw. Keep the compositor and engines resident, and use frozen cgroups rather than restarts. Expect well under 1 s from kernel to first frame, given that panels need tens of ms (estimate, **UNVERIFIED**).

### 8.2 Wake sources

| Source | Kernel support |
|---|---|
| RK817 power key | `INPUT_RK805_PWRKEY=m` |
| RTC alarm, for scheduled wake (e.g. charging) | `RTC_DRV_RK808=y` |
| GPIO keys (hold switch, buttons) | `KEYBOARD_GPIO=m`, with `wakeup-source` in the DT |
| USB-C plug and VBUS | TCPM/FUSB302 interrupt |
| Wi-Fi WoWLAN / BT host wake | brcmfmac out-of-band IRQ (DT `brcm,pcie`/`interrupts`). Optional: it costs standby power |
| HAT interrupt | Through a DT overlay |

Wake sources are set per device in `/sys/devices/.../power/wakeup`. udev rules ship in the image.

### 8.3 Frequency scaling, idle and devfreq

- **CPU:** cpufreq-dt over an SCMI clock (`CPUFREQ_DT=m`, `COMMON_CLK_SCMI=y`, `ARM_SCMI_TRANSPORT_SMC=y`), with schedutil by default and `ENERGY_MODEL=y`. Keep schedutil and steer it with `uclamp` per slice:
  - foreground UI: `cpu.uclamp.min` raised briefly during animations;
  - background: `uclamp.max` capped.
- **GPU:** Panfrost devfreq with simple_ondemand (`DEVFREQ_GOV_SIMPLE_ONDEMAND=y`).
- **DDR:** `ARM_RK3399_DMC_DEVFREQ=m` covers only RK3399. Mainline DMC frequency scaling for RK356x is **UNVERIFIED** and probably absent. DDR then stays at its boot frequency, which is a fixed power cost to measure.
- **Thermal:** `ROCKCHIP_THERMAL=m`, power-allocator governor.
- **Workqueues:** `WQ_POWER_EFFICIENT_DEFAULT` is not set. Enable it with the boot parameter `workqueue.power_efficient=1` (kernel cmdline, no rebuild).

### 8.4 Runtime PM and peripherals

- **USB:** `USB_AUTOSUSPEND_DELAY=2` by default. Use `power/control=auto` through udev for internal devices.
- **Wi-Fi:** iwd with power save on (`iw dev wlan0 set power_save on`, or brcmfmac's default PM). Rfkill Wi-Fi and BT whenever they are not in use (`rfkill` 2.41.5). The orchestrator owns radio policy.
- **Bluetooth audio:** a BT link keeps the radio active. This is a known trade-off, and battery estimates must model it.
- **Display:** PWM backlight (`BACKLIGHT_PWM=m`, `PWM_ROCKCHIP=m`). The compositor does DPMS-off through KMS and the panel driver's disable/unprepare. Screen-off playback must leave **VOP2, the panel and the GPU powered down** through `ROCKCHIP_PM_DOMAINS=y` and genpd.
- **Audio codec:** ASoC DAPM powers down unused paths. PipeWire's `session.suspend-timeout-seconds` (default 5 s) closes the ALSA device when idle, so the codec can sleep.

### 8.5 Playback with the screen off at minimum power (target behaviour)

1. The compositor gets "screen off" from the orchestrator. It turns off the display and backlight, and the UI client activities are frozen (cgroup freezer).
2. The playback engine keeps running with large buffers (section 5.6). It decodes in bursts, so the CPU sits in deep idle (PSCI) between them, with schedutil at the lowest OPP.
3. Radios are off unless BT output is active or streaming is in progress.
4. **This is not suspend-to-RAM.** The SoC is in runtime idle with only the I2S, DMA and codec domains active. Suspend-to-RAM is entered only when playback is paused and the device is idle, after a policy timeout.
5. Optional, later: hand playback to an always-on co-processor. The board has an RP coprocessor (OS-008) that could feed I2S from a buffer while the SoC suspends. This is an architecture question (Q10), not a Debian question.

### 8.6 Measuring

- **Tools:** `powertop` 2.15 (developer repo), `/sys/class/power_supply/*` from the RK817 charger and fuel gauge (`CHARGER_RK817=m`; `BATTERY_CW2015=m` if T1 uses a CW2015 gauge), `upower` 1.90.9 if a D-Bus battery API is wanted (or read sysfs directly from the orchestrator), and `/sys/kernel/debug/wakeup_sources` and `suspend_stats` through debugfs.
- **Ground truth:** an external power analyser on the battery rail. Fuel-gauge current readings are too coarse for differences in the mW range.
- **Not recommended:** `tlp` and `tuned`, which are laptop-x86 oriented; `power-profiles-daemon`, which is not needed when the orchestrator sets the policy; and `thermald` (backports only, x86).

### 8.7 What the init and service layer must do

| Responsibility | Mechanism |
|---|---|
| Who suspends | The orchestrator decides. It calls logind `Suspend()` (or `systemctl suspend`, which runs `systemd-sleep`), so the `sleep.target` hooks run: freeze user slices, notify engines through `PrepareForSleep`. |
| Who may block suspend | Engines and the downloader take logind **delay/block inhibitor locks** while they need the device awake (playing, flashing a HAT, running an update). |
| Power and lid keys | `HandlePowerKey=ignore` in `logind.conf`, so that the orchestrator or compositor maps short and long press to screen-off, suspend or power-off. |
| Background work | Timers (`systemd` `.timer` with `AccuracySec=`, wake-capable `WakeSystem=` only where intended) instead of busy loops. Socket-activate rarely used engines. |
| Journald | `Storage=volatile` or a small `SystemMaxUse=`, so it does not keep the eMMC awake. `SyncIntervalSec` raised. |

---

## 9. Size and boot-time budget

### 9.1 Measured image sizes

The builds are minbase with the docs/man/locale `path-exclude` set, plus systemd, plus the listed additions. All are uncompressed `du -sxm`.

| Step | Total | Δ | Packages |
|---|---|---|---|
| minbase (no excludes) | 149 MiB | — | 78 |
| minbase + excludes | 105 MiB | −44 | 78 |
| + systemd init set | 151 MiB | +46 | 91 |
| + GPU/input stack (backports Mesa 26.1.6 + LLVM 19) | 428 MiB | +277 | 140 |
| + audio (backports PipeWire 1.6.9, WirePlumber 0.5.12, ALSA) | 538 MiB | +110 | 205 |
| + iwd, BlueZ, RAUC, apt, CA certificates | 570 MiB | +32 | 244 |
| + backports kernel 7.2.9, initramfs, `firmware-brcm80211` | 890 MiB | +320 | 260 |
| same, NetworkManager + wpa_supplicant instead of iwd | 907 MiB | +17 | 269 |
| **trimmed**: + DTB/module excludes, + `libspa-0.2-bluetooth` | **683 MiB** | −207 | — |

Compressed, for the trimmed tree:

| Format | Size |
|---|---|
| erofs LZMA, 64 KiB clusters | **231 MiB** |
| erofs zstd, 64 KiB clusters | 315 MiB |
| erofs lz4hc | 352 MiB |
| squashfs zstd-19, `/boot` excluded (comparison) | 218 MiB |

- **Our own software comes on top:** orchestrator, bus, Slint UI runtime, Smithay shell, playback engine, fonts and the design system. Estimate 30–80 MiB (**UNVERIFIED**).
- **A/B budget:** 2 × about 300 MiB root slots (erofs LZMA, with headroom), 2 × about 40 MiB boot/FIT, and the rest as data. **About 1 GiB of eMMC reserved for the OS** is a comfortable target. It is far below what an RK3566 board usually carries (8–32 GB eMMC).
- **Choosing a compressor:** LZMA gives the smallest image, but costs more CPU on reads (cold-start latency and battery). lz4hc gives the fastest reads. A middle ground is erofs `-zlzma` for rarely read data and lz4 for hot binaries, which erofs supports per file through `--compress-hints` (**UNVERIFIED** in mkosi 25.3). The trade-off is worth measuring on T1.
- **Remaining big items** that cannot be removed without rebuilding: `libllvm19` + `libz3` (about 146 MiB raw) and the onnx chain (about 54 MiB, until Debian splits the plugin).

### 9.2 Boot-time budget (estimates, UNVERIFIED, to be measured on T1)

| Stage | Estimate | Main lever |
|---|---|---|
| BootROM + DDR init (`rkbin` TPL) + SPL + TF-A | 0.5–1.0 s | none (vendor blob) |
| U-Boot: load and verify the FIT from eMMC | 0.3–1.0 s | compress the 48.7 MiB Image in the FIT, a small initrd, `bootdelay=0` |
| Kernel to initrd | 0.8–1.5 s | modules built in vs loaded (fixed by Debian), `quiet`, deferred probing |
| initrd: verity open, switch-root | 0.2–0.5 s | a minimal initrd (mkosi-initrd), no fsck on erofs |
| systemd to compositor plus the first Slint frame | 0.5–1.5 s | socket activation, the shell started early (`Before=` most units), engines on demand |
| **Cold boot to UI** | **about 2.5–5.5 s** | |
| Resume from suspend to first frame | about 0.3–1 s | panel and Wi-Fi resume, frozen cgroups instead of restarts |

A stock Debian minbase with systemd boots to a getty in a similar kernel-dominated time. The trimmed image does not boot measurably faster because of fewer packages. Boot time is driven by firmware, the kernel and what starts before the UI.

---

## 10. Security

### 10.1 Trust chain

1. The BootROM loads U-Boot. Rockchip secure boot (OTP-fused key) is optional and **UNVERIFIED** for RK3566 with mainline tooling.
2. U-Boot verifies the **signed FIT**: kernel, initrd, DTB and the cmdline that carries the dm-verity root hash.
3. dm-verity makes the erofs root immutable.
4. The root carries the trust anchors:
   - the RAUC keyring (X.509);
   - the capability-repository and manifest public keys;
   - the HAT-manifest signing keys;
   - the apt keyring (trixie's `apt` 3.0.3 verifies OpenPGP with `sqv` 1.3.0, which is a dependency);
   - for dev/qemu, the developer-repo key through deb822 `Signed-By:` ([sources.list(5)](https://manpages.debian.org/trixie/apt/sources.list.5.en.html)).

### 10.2 Signing the capability repository and the manifests (recommendation)

| Option | In trixie | Fit |
|---|---|---|
| **Ed25519 detached signatures on manifests** (minisign-style or a raw Ed25519 JSON/COSE envelope), verified in Rust by the orchestrator | `minisign` 0.12, `signify-openbsd` 32 (tools); a Rust crate in our code | **Recommended for HAT EEPROM manifests**: a 64-byte signature and a 32-byte key fit small EEPROMs. Use the same format for capability manifests. The manifest pins the erofs image's verity root hash and SHA-256, so the manifest signature covers the payload. |
| OpenPGP (sqv) | `sqv` 1.3.0, `gpgv` 2.4.7 | Natural for apt repositories (the developer repo), but heavy for EEPROM manifests. |
| X.509/CMS | used by RAUC | Already present for OS bundles. Overkill for manifests. |
| Sigstore/cosign | `cosign` 2.5.0 | Transparency log is attractive for third parties, but it needs online verification. A possible later addition, not on the device. |
| `debsig-verify` | 0.33 | Only relevant if capabilities were .debs (not recommended). |

#### Revocation and recalls (SYS-011)

- The package endpoint serves a signed, short-lived "allowed and recalled" list.
- The device refuses capabilities that are on the recall list, or whose manifest is older than the list's minimum version.
- Signing keys are rotated through a key list that is itself signed by a root key in the image.

### 10.3 Sandboxing third-party capabilities

| Layer | Available | Use |
|---|---|---|
| systemd unit sandboxing + transient units | systemd 257.13 | **Primary.** Applied per service by the orchestrator (section 2.4 and 7.4). |
| **Landlock** | `SECURITY_LANDLOCK=y`, first in `CONFIG_LSM` | Our launcher applies Landlock filesystem and network rules derived from the manifest before `exec`. It is unprivileged and stackable. |
| AppArmor | `SECURITY_APPARMOR=y`, Debian default | Profiles for our own daemons. Optional for capabilities. |
| bubblewrap | `bubblewrap` 0.12.0 | Not needed when systemd namespaces are used. Useful for ad-hoc ephemeral CLI tools that run outside units. |
| systemd-nspawn | `systemd-container` 257.13 | For the `qemu`/`oci` developer profiles and OS-009, not per capability. |
| IPE, BPF-LSM | `SECURITY_IPE=y`, `BPF_LSM=y` | IPE could enforce "only execute from dm-verity volumes" (root + capability images), which is a strong, cheap guarantee. Policy deployment needs testing (**UNVERIFIED** with a stock kernel and no builtin keys: IPE policies can be signed or unsigned). |
| seccomp | `libseccomp2` through systemd `SystemCallFilter=` | Yes. |

---

## 11. Recommended component table (recommendations, not decisions)

| Component | Recommended choice (trixie / backports version) | Why | Alternatives |
|---|---|---|---|
| Base | Debian 13 trixie `minbase` + dpkg `path-exclude` for docs/man/locales | Standard Debian. 105 MiB base (measured) | `essential`, `important` |
| Kernel | `linux-image-arm64` 7.2.9-1~bpo13+1 (backports), DTB and module `path-exclude`, Image compressed into the signed FIT | Prebuilt. Config covers RK3566 audio, USB, Type-C, PM and LSMs | Debian config MR for missing panels |
| Bootloader | mainline U-Boot (local build, decided) + extlinux / `u-boot-menu` 4.2.4 + RAUC bootchooser | Decided | — |
| Init | **systemd 257.13** as PID 1 | Standard. Transient units, sandboxing, socket activation, cgroups. +18 MiB RAM vs sysvinit (measured) | sysvinit+elogind+seatd, OpenRC, runit (dinit and s6-rc are not in Debian) |
| Orchestrator placement | systemd service using `StartTransientUnit`, slices, freezer, inhibitors | Reuses PID 1 features. No PID-1 risk | PID 1 (rejected) |
| Device manager | `udev` 257.13 | The only udev in Debian | — |
| Logging | `journald`, volatile or size-capped | Already present. No syslog daemon | `busybox-syslogd` |
| D-Bus | `dbus-broker` 37-2 | Lighter and faster. Required by BlueZ, iwd, logind, RAUC, WirePlumber | `dbus-daemon` 1.16.2 |
| Core utilities | **GNU coreutils 9.7, util-linux 2.41.5**, dash, bash | Essential. BusyBox broke a postinst (`cp -Z`) in our test, for a saving of about 20 MiB | BusyBox only as an extra or in the initrd |
| Seat | logind through `libseat1` 0.9.1 | Comes with systemd | `seatd` 0.9.1 |
| GPU | Mesa 26.1.6 (backports): `libegl-mesa0 libgles2 libgbm1 mesa-libgallium`, Panfrost | Newest Panfrost. GLES 3.1 conformant on G52 | trixie Mesa 25.0.7 |
| Compositor / shell | Our own **Smithay** compositor hosting the Slint shell. Bring-up on **cage** 0.2.0 | Activities model. Wayland as wanted. Links only Debian libraries | cage long-term, Slint linuxkms (recovery UI) |
| UI runtime | Slint 1.18.x (winit/Wayland for activities, linuxkms for recovery), FemtoVG or Skia GLES | Owner direction | software renderer |
| Audio server | **PipeWire 1.6.9 + WirePlumber 0.5.12** (backports), `pipewire-alsa`, `libspa-0.2-bluetooth`, `rtkit` | Standard. Bluetooth codecs, UAC2 gadget, shared use | trixie PipeWire 1.4.2 (no onnx, older) |
| Bit-perfect playback | Our engine with **exclusive ALSA `hw:`** (alsa-lib 1.2.16.1) plus device reservation. PipeWire pro-audio with forced rate for shared mode | Only path that is exact for 32-bit PCM and DoP/DSD | PipeWire-only with `allowed-rates` (not exact for S32 or DSD) |
| Wi-Fi | **iwd** 3.8 (+ resolved) | Light, fast reconnect, standard | NetworkManager 1.52 (+17 MiB), ConnMan |
| Wired/USB networking | systemd-networkd | Already in `systemd` | NM |
| Bluetooth | BlueZ 5.82 | Only option | — |
| USB gadget | Own configfs service (Rust), `umtp-responder` for MTP | No gadget CLI in Debian. configfs is the standard ABI | `libusbgx3` 0.3.0 through FFI |
| Updates (OS) | **RAUC** 1.13 verity bundles over HTTPS through the package endpoint (decided). CI rebuilds from `snapshot.debian.org` | Signed, streaming, A/B, U-Boot | SWUpdate, systemd-sysupdate |
| Root filesystem | **erofs + dm-verity** (decided). Compressor: LZMA (231 MiB) or lz4hc (352 MiB), chosen after a T1 read-latency test | Small, read-only, verifiable | squashfs |
| Image build | **mkosi** (decided). Backports pinned per source package. HTTPS mirror. Snapshot pin | Declarative, profiles t1/qemu/oci | mmdebstrap + genimage |
| Capabilities | Signed manifest + erofs/verity image in `/var/lib/dap/capabilities`, run as sandboxed transient units (`RootImage=`/`MountImages=`, `DynamicUser=`, Landlock) | No third-party root scripts, verifiable, removable | `.deb` + apt (rejected), sysext (for first-party add-ons only) |
| Manifest signatures | Ed25519 detached signatures (minisign-style), verified in Rust. Keys in the verity root | Small (fits EEPROM), simple | OpenPGP (sqv), X.509 |
| Power tools | sysfs plus logind from the orchestrator. `powertop` and `upower` only in the developer repo | Fewer daemons | `power-profiles-daemon`, `tlp` (not for this) |
| Developer tools | Separate repository (decided). Shipped as a first-party sysext or apt on dev units | Keeps the consumer image small | — |

---

## 12. Open questions for the maintainers

1. **OS-013 on an image-based OS.** Is "distro updates arrive as a rebuilt, signed RAUC image, and only capabilities update on their own" an acceptable reading of "updates from both the distribution and the OpenDAP repositories"? Or must a live device also take individual Debian packages?
2. **T1 display panel.** Which DSI panel and controller? If its driver is not among the 13 enabled in Debian's kernel, a Debian kernel config merge request goes on the critical path.
3. **LLVM in Mesa (about 146 MiB).** Accept it, or raise a request with Debian for a no-LLVM gallium build? Rebuilding Mesa ourselves is ruled out.
4. **PipeWire version.** Backports 1.6.9, with the 54 MiB onnx chain until Debian splits the plugin, or trixie 1.4.2?
5. **Session model.** Does the UI and audio session run as `user@.service` for a single unprivileged `dap` user (recommended), or as system units?
6. **Bit-perfect policy.** Should exclusive mode be the default for wired output, with system sounds muted during playback? Is DSD (DoP and/or native) required at launch, and on which outputs: on-board codec, USB DAC, HAT DAC?
7. **Suspend firmware.** If deep suspend needs Rockchip's `rkbin` BL31 rather than mainline TF-A, is shipping that blob acceptable? It is the same class as the DDR TPL blob already needed.
8. **Writable `/etc`.** Overlay on `/var`, or a fully image-defined `/etc` with confext and `systemd-tmpfiles`?
9. **erofs compressor.** Smallest (LZMA) or fastest (lz4hc), decided after measuring cold-start latency on T1?
10. **Screen-off playback.** Is a design where the RP coprocessor feeds I2S while the SoC suspends in scope (OS-008), or is SoC runtime-idle playback enough?
11. **RAM size of T1.** It changes how much the 18 MiB init difference or journald tuning matters.
12. **Wi-Fi/BT module.** Broadcom (`brcmfmac`) or Realtek (`rtw88` SDIO)? It decides the firmware package and the power-save behaviour.

---

## Sources

- Debian archive metadata (2026-10-21): [qa.debian.org/madison.php](https://qa.debian.org/madison.php), [packages.debian.org/trixie](https://packages.debian.org/trixie/), `https://deb.debian.org/debian/dists/{trixie,trixie-backports}/main/binary-arm64/Packages.xz`
- [systemd trixie arm64 file list](https://packages.debian.org/trixie/arm64/systemd/filelist); [contents search for systemd-sysupdate](https://packages.debian.org/search?searchon=contents&keywords=systemd-sysupdate&mode=exactfilename&suite=trixie&arch=arm64)
- Kernel config: `linux-base-7.2.9+deb13-arm64_7.2.9-1~bpo13+1_arm64.deb` from `deb.debian.org/debian/pool/main/l/linux/`; [linux-base 7.2.9 file list](https://packages.debian.org/trixie-backports/arm64/linux-base-7.2.9+deb13-arm64/filelist)
- [wiki.debian.org/Init](https://wiki.debian.org/Init), [wiki.debian.org/ReduceDebian](https://wiki.debian.org/ReduceDebian)
- [mmdebstrap(1)](https://manpages.debian.org/trixie/mmdebstrap/mmdebstrap.1.en.html), [dpkg(1)](https://manpages.debian.org/trixie/dpkg/dpkg.1.en.html), [sources.list(5)](https://manpages.debian.org/trixie/apt/sources.list.5.en.html)
- [systemd.exec(5)](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html), [systemd-run(1)](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html), [systemd-logind(8)](https://manpages.debian.org/trixie/systemd/systemd-logind.service.8.en.html), [systemd-sysext(8)](https://manpages.debian.org/trixie/systemd/systemd-sysext.8.en.html), [systemd-sysupdate(8)](https://manpages.debian.org/trixie/systemd-container/systemd-sysupdate.8.en.html), [sysupdate.d(5)](https://manpages.debian.org/trixie/systemd-container/sysupdate.d.5.en.html)
- [seatd(8)](https://manpages.debian.org/trixie/seatd/seatd.8.en.html), [busybox (trixie)](https://packages.debian.org/trixie/busybox)
- [Mesa Panfrost](https://docs.mesa3d.org/drivers/panfrost.html); [Slint linuxkms backend doc](https://github.com/slint-ui/slint/blob/master/docs/astro/src/content/docs/guide/backends-and-renderers/backend_linuxkms.mdx); [Slint linuxkms Cargo.toml](https://github.com/slint-ui/slint/blob/master/internal/backends/linuxkms/Cargo.toml); [cage](https://github.com/cage-kiosk/cage); crates.io API for `smithay`, `slint`, `winit`, `libseat`, `input`
- [pipewire.conf(5)](https://docs.pipewire.org/page_man_pipewire_conf_5.html), [pipewire-props(7)](https://docs.pipewire.org/page_man_pipewire-props_7.html), [WirePlumber Bluetooth config](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html), [WirePlumber ALSA config](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/alsa.html); [pipewire-bin (backports) file list](https://packages.debian.org/trixie-backports/arm64/pipewire-bin/filelist); [libspa-0.2-modules (backports) file list](https://packages.debian.org/trixie-backports/arm64/libspa-0.2-modules/filelist)
- [RAUC basics](https://rauc.readthedocs.io/en/latest/basic.html); [TF-A Rockchip](https://trustedfirmware-a.readthedocs.io/en/latest/plat/rockchip.html)
- Measurements: `mmdebstrap` 1.5.7 builds and container boot tests, run 2026-10-21 natively on arm64 (`debian:trixie`, privileged Docker). All containers and images were removed afterwards.
