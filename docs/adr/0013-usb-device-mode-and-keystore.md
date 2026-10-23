# ADR 0013: USB device mode, music volume handover and the keystore

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decided by:**
  - the maintainers, for the keystore (OS-032);
  - Claude under the maintainers' delegation, for the USB device mode (T1-065, [RFC 0004](https://github.com/opendap-project/rfcs/blob/main/text/0004-opendap-protocol.md) §3).

## Context

- **USB storage.** Over USB the T1 must appear as plain storage by default (T1-065), while sync and connected features go through OpenDAP Desktop or the CLI (DESK-011). The Linux mass-storage gadget forbids the device from touching a backing store while the host has it ([kernel docs](https://docs.kernel.org/usb/mass-storage.html)), so the live library cannot be shared read-write. Windows installs a composite device without a driver only when it has a single configuration ([Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/enumeration-of-the-composite-parent-device)). The RK3566's device-mode port is USB 2.0 High-Speed only (`board` ADR 0003).
- **Keys.** Device identity keys need protected storage. The RK3566 has no mainline OP-TEE port and its OTP is read-only to Linux ([OP-TEE platforms](https://optee.readthedocs.io/en/latest/general/platforms.html)).

## Decision

1. **One USB configuration with IAD**, composed of:
   - NCM, for the OpenDAP Protocol and SSH;
   - ACM, for the console (BRD-039);
   - mass storage, for plain files;
   - UAC2 when the listener selects USB DAC (T1-054).

   There is never a second configuration.
2. **Music volume handover.** With no OpenDAP client on the host, the T1 hands its music volume to the host exclusively:
   - which volume: the SD/TF card if present, otherwise a dedicated music partition of the internal storage;
   - while the volume is handed over, the T1 keeps playing what its cache levels hold (OS-022), and its screen shows "Connected to a computer" with **Eject**;
   - on release (eject or unplug), the T1 remounts the volume, re-indexes only what changed, and reports what it found.

   The volume follows the user-facing layout of the [conventions spec](https://github.com/opendap-project/system/blob/main/docs/specs/user-facing-conventions.md) §1: exFAT, label `OPENDAP`, `Music/`, `Podcasts/`, `Audiobooks/`, `Recordings/`, `Playlists/`.
3. **With a client present**, OpenDAP Desktop or the CLI talk over NCM and the volume is not handed over, so nothing interrupts the device. The listener can still choose plain storage from the T1's screen.
4. **Keys always go through a keystore** (OS-032). Services never handle key files directly:
   - every identity and pairing key lives behind one keystore interface;
   - today it is backed by protected storage on the filesystem, with its protection level documented;
   - it is backed by a TEE as soon as one is available on the platform, through an OP-TEE port or another hardware key holder, with no change for its users.

## Consequences

- Hosts without an OpenDAP client get a standard drive on Windows, macOS and Linux. Windows 10 has no inbox NCM driver, which does not affect plain storage.
- Music on the handed-over volume and not cached cannot play until it is released; the screen says so.
- A TEE port, or a hardware key holder (a secure element, the RP2350), becomes a platform task for `board` and `blackbird-os`.
- To verify on the bench: driverless enumeration of the composite on Windows 11 and macOS, and the RK3566 DWC3 endpoint count.
