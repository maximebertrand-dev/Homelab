---
title: "ADR 0001: The Dell T330 dedicated to storage"
description: The T330 becomes the storage machine (ZFS RAIDZ2, PBS); compute moves to a dedicated cluster.
date: 2026-09-22
status: remplacé
tags: [proxmox, zfs, storage]
---

# ADR 0001: The Dell T330 dedicated to storage

> **Superseded decision.** This decision was superseded by [ADR 0010](0010-serveur-unique.md) on 26/09/2026. It is kept for the record.

## Context

The T330 (8 hot-plug bays, 32 GB DDR4 ECC, PERC H330) was first meant to host everything: firewall, storage and services. One machine for everything is a single point of failure, and every maintenance takes the whole lot down.

## Options considered

1. **Everything on the T330**: simple, but fragile and hard to maintain.
2. **T330 for storage only, compute on a cluster**: separate roles, as in a company.
3. **TrueNAS SCALE on the T330**: very well suited to a NAS, but one more tool to master.

## Decision

The T330 stays on **Proxmox VE** (one tool across the whole infrastructure, driven by OpenTofu) and carries only storage: a **ZFS RAIDZ2** pool on 4 SAS disks, the PERC H330 in **HBA mode**, **Proxmox Backup Server** for the cluster's backups.

## Consequences

- About 6 TB usable, two disk failures tolerated (relevant with second-hand disks).
- NAS data and backups on the same machine: **an encrypted off-site copy is mandatory**.
- VM disks are not stored on the NAS, so as not to make it a single point of failure for the cluster.

## Update (07/10/2026)

The pool grew to **five disks** (RAIDZ2 expansion on 05/10, 13.6 TB raw, ≈ 8 TB usable once the data is rewritten)
and a worn disk was replaced by the spare on 06/10: see the [journal entry of 07/10](../journal/2026-10-07-disques.md).
