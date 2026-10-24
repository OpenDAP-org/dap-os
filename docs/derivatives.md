# Building a custom ROM based on Blackbird OS

A custom ROM here is a distribution based on Blackbird OS: your own system for OpenDAP hardware such as the T1 (or a virtual device), with your name, theme, drivers, packages and configuration, built on top of Blackbird OS instead of a fork of it.

Blackbird OS is built on Debian and changes it apart, in its own repository: its own identity, packages, configuration and drivers on top of Debian's. A distribution based on Blackbird OS works the same way. It keeps Blackbird OS's image definition unchanged and adds what makes it different (a theme, drivers, configuration, other packages), so it can follow Blackbird OS releases without carrying a patched copy.

Derivatives are the community's scope: OpenDAP documents how to build one and keeps the image definition derivable, but does not support them (SYS-035). Requirement: OS-028. Decision: [ADR 0012](adr/0012-derivable-image-definition.md).

## A minimal derivative

[`examples/derivative/`](../examples/derivative/) is a working example, built and checked on 2026-10-23 with mkosi 25.3:

```text
examples/derivative/
├── mkosi.conf              includes ../../image, then sets ImageId, Hostname and its own output and cache directories
├── identity.env            the OS_* identity variables (name, ID, ID_LIKE, version, URLs)
├── overlay/                files copied on top of Blackbird OS's trees
└── mkosi.profiles/<p>/     the output name for each Blackbird OS profile (qemu, oci)
```

Build it from the Blackbird OS build VM, like Blackbird OS itself:

```sh
limactl shell blackbird-os-build -- sudo mkosi -C "$PWD/examples/derivative" --profile=oci -f build
```

Its `/usr/lib/os-release` then reads `NAME="Example OS"`, `ID=example`, `ID_LIKE="blackbird debian"`, with its own hostname, banner and login message. In your own repository, point `Include=` at a Blackbird OS checkout (for example a git submodule pinned to a release).

## Step by step, in your own repository

Checked on 2026-10-23 on macOS (Apple silicon) with Lima 2.2.1, mkosi 25.3 in the build VM and QEMU 11.1, from a folder outside the OpenDAP workspace.

1. **Host tools.** QEMU, Lima and Python 3, as for Blackbird OS (`toolkit-host/setup.sh` installs them), and the `opendap` CLI.
2. **Your repository, with Blackbird OS as a submodule.** Pin it to a release (or a commit) so your builds are reproducible:

   ```sh
   mkdir my-rom && cd my-rom && git init
   git submodule add https://github.com/opendap-project/blackbird-os.git blackbird-os
   ```

3. **Start from the example.** Copy it and point `Include=` at the submodule:

   ```sh
   cp -R blackbird-os/examples/derivative/. .
   sed -i '' 's|Include=../../image|Include=blackbird-os/image|' mkosi.conf   # GNU sed: sed -i
   ```

   Then set your identity in `identity.env` (`OS_NAME`, `OS_PRETTY_NAME`, `OS_ID`, …), your `ImageId` and `Hostname` in `mkosi.conf`, and your output names in `mkosi.profiles/<profile>/mkosi.conf`.
4. **Add what makes it yours:** files in `overlay/`, packages with `Packages=`, drivers as DKMS packages, a theme (see the table below).
5. **The build VM.** Images build inside a Debian VM, from toolkit-image (`odapkit image vm start`). Mount your repository into it, or add the mount to an existing one:

   ```sh
   limactl stop blackbird-os-build && limactl edit blackbird-os-build --mount "$PWD:w" --tty=false && limactl start blackbird-os-build
   ```

6. **Build.** The container profile needs nothing else. The qemu profile, for virtual devices, takes two inputs that the build passes in, never your definition: the development key tree (`odapkit dev-key tree`) and the virtual board's support package (virtual-devices `export/bsp`, a mkosi config directory):

   ```sh
   limactl shell blackbird-os-build -- sudo mkosi -C "$PWD" --profile=oci -f build
   limactl shell blackbird-os-build -- sudo mkosi -C "$PWD" --profile=qemu \
     --extra-tree="$(odapkit dev-key tree)" --include="<virtual-devices>/export/bsp" -f build
   ```

7. **Run it on a virtual device.** Point virtual-devices at your image:

   ```sh
   ODAP_IMAGE="$PWD/mkosi.output/<your-image>-qemu.raw" odap-vdev start --wait
   odap-vdev ssh cat /etc/os-release
   odap-vdev stop
   ```

8. **Follow Blackbird OS.** Move the submodule to a new release, rebuild, and test. Your changes stay in your files, so there is nothing to rebase.

Flashing a real T1 and signed releases come with the `t1` profile and OS-011, which are not built yet.

## Rules that keep a derivative working

mkosi reads an included directory's default-named files (`mkosi.env`, `mkosi.extra/`) before the including directory's settings that follow `Include=`, and later values win. So:

- **Identity:** put the `OS_*` variables in a file with another name (`identity.env`) and list it in `EnvironmentFiles=` after `Include=`. A file named `mkosi.env` is read before Blackbird OS's and loses.
- **Files:** put your tree in a directory with another name (`overlay/`) and list it in `ExtraTrees=` after `Include=`, so your files replace Blackbird OS's. A tree named `mkosi.extra/` is copied first and loses.
- **Outputs:** set your own `ImageId`, `OutputDirectory`, `CacheDirectory` and, per profile, `Output`, so a build never overwrites Blackbird OS's images.
- **`ID_LIKE`:** list `blackbird` before `debian`, so tools that know Blackbird OS treat your system as a relative.

## What a derivative changes

| Change | How |
|---|---|
| Name, version, URLs | `identity.env` (`OS_NAME`, `OS_PRETTY_NAME`, `OS_ID`, `OS_ID_LIKE`, `OS_VERSION`, `OS_HOME_URL`, `OS_SUPPORT_URL`, `OS_BUG_REPORT_URL`, and `OS_BASED_ON` for the login message) |
| Theme | A token set and templates, installed as files or a package (SYS-030; the theme format is not defined yet) |
| Drivers | DKMS packages (ADR 0007) or vendor drivers (ADR 0008), added with `Packages=` |
| Packages and configuration | `Packages=`, `RemovePackages=`, `overlay/`, more `PostInstallationScripts=` |
| Kernel command line, boot | `KernelCommandLine=` and the other mkosi settings, after `Include=` |

## Names, repositories and keys

Decided by the maintainers on 2026-10-23:

- **Names.** Blackbird OS and OpenDAP are registered marks, and derivatives may use them freely, for example "based on Blackbird OS".
- **What you may reuse.** Everything OpenDAP publishes: the image definition, the packages and the package repositories. Use it as it is, change it, and add your own.
- **Signing keys.** Your releases are signed with your own keys (OS-011 covers Blackbird OS's).

## Not covered yet

- **Package repositories and release signing** are not built yet (OS-011, OS-013); this guide will say how to point a derivative at them when they exist.
- **Board support.** The `t1` profile is not implemented yet; board support is meant to stay separable (SYS-035).
