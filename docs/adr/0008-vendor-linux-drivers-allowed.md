# ADR 0008: Vendor Linux drivers allowed when mainline lacks one

- **Status:** Accepted
- **Date:** 2026-10-22

## Context

Parts are chosen by availability first (T1-028, T1-029), so a part may need a driver that mainline Linux does not have. Missing modules already ship through DKMS ([ADR 0007](0007-kernel-modules-through-dkms.md)).

## Decision

When mainline has no driver for a part, a **Linux driver published by the vendor** may be used, built as a DKMS module, preferably one that looks validated (maintained, versioned, used in shipping products) and with a licence compatible with the kernel. Mainline drivers stay the first choice.
