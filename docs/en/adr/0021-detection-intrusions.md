---
title: "ADR 0021: Intrusion detection and prevention in lightweight layers"
description: Suricata on the firewall, CrowdSec shared by every machine with blocking at the firewall, detection rules on the centralised logs; no heavy SIEM.
date: 2026-09-29
status: accepté
tags: [security, detection, ids, crowdsec, suricata]
---

# ADR 0021: Intrusion detection and prevention in lightweight layers

## Context

The homelab already blocks a lot at the entrance: WAF (OWASP rules), CrowdSec **in the WAF only**, SSO barrier,
zone-based firewall. It **detects** little: an attack that does not go through the WAF (VPN, outbound flows, lateral
movement between zones, stolen account) alerts nobody, and suspicious behaviour seen by the WAF does not protect the
other services. The 29/09 audit showed it: on a mobile app endpoint, a wrong password returns an HTTP success,
invisible to the WAF. Memory remains the limiting factor: 32 GB for the whole homelab.

## Options considered

1. **A full SIEM (Wazuh, Security Onion)**: very complete, but 4 to 16 GB of memory for it alone: out of reach.
2. **Lightweight layers, each in its place** — chosen:
   - network: IDS/IPS on the firewall;
   - reputation and blocking: CrowdSec extended to every machine, decisions enforced by the firewall;
   - hosts and applications: detection rules on the logs that are already centralised
     ([ADR 0020](0020-journaux-centralises.md)).

## Decision

1. **Suricata on OPNsense** (built-in feature, ET Open rules and abuse.ch lists):
   - first in **detection** mode on the WAN and on the internal interfaces (lateral movement, traffic towards known
     command-and-control servers);
   - then **prevention** on the WAN once false positives have been tuned (two weeks);
   - firewall memory raised from 2 to 3 GB.
2. **Shared CrowdSec**:
   - a central local API on the monitoring VM;
   - agents on every machine (SSH, sign-in portal, applications);
   - the **firewall as the shield** (OPNsense's CrowdSec plugin): an address that attacks one service is blocked for
     all of them;
   - the community list blocks known addresses in advance;
   - the home address is excluded from blocking at the firewall (a single address for the whole household).
3. **Detection on logs** (vmalert on VictoriaLogs, alerts through the existing manager):
   - SSH sign-in from an unexpected source, privilege escalation;
   - SSH key added, administration account created;
   - bursts of sign-in failures (portal, applications, including mobile endpoints that answer 200);
   - change to the firewall's configuration;
   - unexpected stop or restart of a container.
4. **Traceability on the hosts**: auditd on sensitive files (authorised keys, sudoers, accounts), into the systemd
   journal and hence the centralised logs.

## Consequences

- A real critical alert must stay rare: each rule is first observed as a "warning".
- Exclusions (the home address, legitimate traffic that looks like a bot) are written in the code, with the reason;
  no global disabling.
- The firewall becomes a shared blocking point: a wrong decision cuts every service for the address concerned; the
  runbook describes how to lift a decision.
- What remains out of reach: advanced behavioural analysis and long-range correlation (a full SIEM); to be
  reconsidered with more hardware.

## Implementation

In stages, the cheapest first; each rule is observed as a "warning" before becoming an alert.

1. **Done on 29/09**: the home address is never banned by CrowdSec any more (the WAF's "postoverflow" list, restored
   automatically after each recreation of the container).
2. **Done on 29/09**: detection rules on the centralised logs (vmalert on VictoriaLogs): SSH sign-ins, sudo, keys
   added, bursts of sign-in failures (portal, mobile applications).
3. **Done on 29/09**: auditd on every machine (common role), into the systemd journal.
4. **Done on 08/10**: login watch: an address becomes known at its first complete successful login; failures from an
   unknown address with no success within a quarter of an hour, or a password accepted without a valid second factor,
   raise an alert (see the [journal entry of 13/10](../journal/2026-10-13-veille-connexions-waf.md)).
5. Shared CrowdSec: local API on the monitoring VM, agents on the machines, OPNsense plugin (after its update).
6. Suricata on OPNsense, in detection then prevention mode on the WAN (after its update; firewall memory raised to
   3 GB).
