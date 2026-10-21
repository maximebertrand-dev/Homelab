---
title: Architecture overview
description: The machines, the software layers, and what is exposed and what is not.
tags: [architecture]
---

# Overview

## Principles

1. **Everything as code**: no VM and no DNS record created by hand. OpenTofu for the infrastructure, Ansible for the configuration.
2. **Minimal exposure**: the showcase site goes through Cloudflare Tunnel; personal services and the monitoring page go through a single inbound port, filtered by the firewall and then by a WAF, with single sign-on. Administration is reachable only over the VPN.
3. **Separate zones**: the home network (Freebox) and the homelab (OPNsense) are isolated; the homelab is split into VLANs, and each zone can reach only what it needs.
4. **Everything can be restored**: an encrypted off-site backup every night, read back and compared automatically; procedures in [`runbooks/`](../runbooks/), incidents analysed in [`postmortems/`](../postmortems/).

## Layers

| Layer | Tools |
|---|---|
| Hardware | Dell PowerEdge T330 (single server, GTX 1050 graphics card handed to the applications VM: [ADR 0024](../adr/0024-carte-graphique.md)), Dell PowerEdge R610 (LAB powered on demand, upcoming) |
| Hypervisor & storage | Proxmox VE, ZFS RAIDZ2 |
| Network & security | OPNsense (virtualised), VLANs, WireGuard, BunkerWeb (WAF), CrowdSec, Cloudflare (DNS, tunnel for the showcase site) |
| Identity | LLDAP (directory), Authelia (SSO and two-factor authentication), accounts page (invitations without any password being sent) |
| Provisioning | OpenTofu (bpg/proxmox, opnsense, cloudflare), Ansible, also run from Semaphore UI |
| Applications | Docker Compose in dedicated VMs, one per zone |
| Secrets | OpenBao vault (SSO, AppRole, audit), SOPS + age for bootstrapping |
| Observability | Prometheus, Alertmanager, custom NOC, Grafana (internal), VictoriaLogs (centralised logs), ntfy (alerts on the phone), login watch (unknown addresses), UptimeRobot external probe |
| Infrastructure services | NetBox (source of truth), Semaphore UI (running playbooks) |

The structural choices are explained in the ADRs, in particular [ADR 0010](../adr/0010-serveur-unique.md)
(a single server), [ADR 0008](../adr/0008-exposition-directe-waf.md) (publishing the services),
[ADR 0014](../adr/0014-supervision-noc.md) (monitoring), [ADR 0015](../adr/0015-semaphore-ansible.md)
(Semaphore), [ADR 0016](../adr/0016-coffre-openbao.md) (secrets vault), [ADR 0017](../adr/0017-invitations-page-comptes.md)
(invitations and the accounts page), [ADR 0018](../adr/0018-droits-par-groupes-quotas.md) (group-based access and quotas),
[ADR 0019](../adr/0019-sauvegardes-hors-site.md) (off-site backups) and [ADR 0020](../adr/0020-journaux-centralises.md)
(centralised logs).

## What is exposed

| Service | Domain | Access |
|---|---|---|
| Showcase site | `maximebertrand.net` | Public (Cloudflare Tunnel) |
| NOC (custom monitoring page) | `noc.maximebertrand.net` | Public, behind OPNsense, WAF and SSO; read-only |
| Alert notifications (ntfy) | `ntfy.maximebertrand.net` | Public, behind OPNsense and WAF; dedicated accounts, everything denied by default |
| Personal services (photos, files) | subdomains of `maximebertrand.net` | Public, behind OPNsense, WAF and SSO with two-factor authentication |
| Administration, directory, internal tools | `*.home.maximebertrand.net` (internal DNS only) | VPN only; SSO as well for the accounts page |
