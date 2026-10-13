---
title: "ADR 0010: A single server, with a virtualised firewall"
description: The Dell T330 runs the hypervisor, the storage and OPNsense as a VM; no cluster and no bastion host for now.
date: 2026-09-26
status: accepté
tags: [proxmox, opnsense, architecture]
---

# ADR 0010: A single server, with a virtualised firewall

Supersedes ADRs [0001](0001-proxmox-zfs-t330.md), [0003](0003-opnsense-dmz-freebox.md) and
[0006](0006-cluster-proxmox-basse-conso.md).

## Context

The previous ADRs planned a cluster of three mini-PCs for the services, a dedicated box for the firewall and the
T330 reserved for storage. That hardware will not be bought for a long time, and the electricity budget stays capped
at €40 a month. The architecture has to work **with a single machine**, without giving up zone separation.

## Options considered

1. **Wait for the hardware**: nothing runs in the meantime.
2. **Everything on the T330, a separate physical firewall later**: start right away, accepting a single point of
   failure.

## Decision

The **T330 running Proxmox VE** carries everything:

- storage: a ZFS **RAIDZ2** pool on four SAS disks, five since 05/10/2026 (two failures tolerated), system included;
- the firewall: **OPNsense as a virtual machine**, receiving all the homelab's traffic (the Freebox's DMZ mode);
- services: one virtual machine per security zone.

**No bastion host**: with a single machine and a single administrator, it adds more complexity than security.
Administration goes only through the **WireGuard VPN**, with two-factor authentication on the administration
interfaces.

## Consequences

- **Single point of failure**: maintaining the T330 takes the whole homelab down. The home network is not affected
  (the Freebox stays the router).
- **Emergency access**: the server's out-of-band interface (iDRAC) stays reachable even when the firewall is down.
- **Off-site backups are essential**: data and backups are on the same machine.
- The virtualised firewall shares the hardware of the services it protects: the hypervisor's network bridges have
  no address on the Internet side, so that the host is reachable only through OPNsense.
- If the planned hardware arrives, ADRs 0003 and 0006 can be revived by a new ADR.
