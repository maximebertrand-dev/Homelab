---
title: AI in this project
description: "I design, decide and review; an AI assistant advises me and executes under my control. Who does what, the guardrails and the rules I set."
slug: ai
date: 2026-10-05
---

## In short

- **I design, I decide, I review.** The architecture, the trade-offs, irreversible actions and everything that goes
  to production go through me.
- **The AI advises me and executes under control.** I use Claude, by Anthropic, inside my code editor: as an adviser,
  and as a supervised executor. I say so here and in the repository's README, and every commit it contributed to says
  so too.
- **The services do not need AI to run.** It is used to build and to diagnose; the family's photos, files and
  accounts are never handed to it.

## My role, the AI's role

**My role**: I set the requirements, design the architecture and decide between the options written down in each
[architecture decision](/en/adr/). I review what goes to production, approve every irreversible action, and run the
platform day to day. The most sensitive changes (production firewall rules, machine sizing, secrets) are usually
applied by me, from a reviewed plan.

**The AI plays two roles:**

- **adviser**: it proposes options and weighs their trade-offs (each decision keeps a record of the options ruled
  out), audits the security of what exists, and challenges my choices when they are fragile;
- **supervised executor**: it writes most of the code (OpenTofu, Ansible, scripts) and of the documentation, runs the
  diagnostic and deployment commands, then checks the result (probes, logs, screenshots), always under my approval.

Decisions, trade-offs and responsibility stay with me. In practice: I set the course and review; the assistant is
fast, documents everything and points out what I forget.

## Guardrails

- **Propose, explain, then apply.** An architecture choice is presented with its options and consequences before it
  is applied.
- **No destructive action without my explicit approval**: deleting data or a machine, wiping a disk, an irreversible
  change to storage.
- **What gets applied is what was reviewed**: infrastructure changes go through a saved OpenTofu plan, applied as is.
- **Limited, revocable access**: the assistant works from my workstation, through the administration VPN, with
  restricted permissions; its access is listed in the internal documentation so it can be audited and withdrawn. Its
  own safety filter also refuses some actions (writing a secret, applying production firewall rules): I do those
  myself.
- **Secrets never travel in clear text**: they are encrypted in the repository and decrypted only on the machines that
  need them; commands are written so as not to display them.
- **Everything is traceable**: every change is a reviewable commit, every incident has its post-mortem.

## The family's data

During a diagnosis, the assistant reads code, configuration and technical logs. Those logs may contain IP addresses
or sign-in usernames; they then pass through Anthropic's servers, under its terms of use. I keep these reads to what
is needed: the assistant never reads the content of photos or files (at most their names, when they appear in an
import log).

The artificial intelligence that recognises faces and lets you search the photos (Immich) runs **on the home server**,
with no outside service: photos never leave the homelab, except encrypted, for the backup.

## When the AI gets it wrong

It does, and I write it down. Several outages in this project come from the assistant's actions:

- a security test run from home got the whole family banned by the web application firewall
  ([post-mortem of 29/09](/en/postmortems/2026-09-29-maison-bannie-par-le-waf/));
- a non-existent configuration option stopped the web application firewall for an hour
  ([post-mortem of 30/09](/en/postmortems/2026-09-30-coupures-du-waf/));
- a setting deployed before the network flow it depended on was opened took the sign-in portal down for several
  hours, and a large photo import started during the day exhausted the server's memory.

My approval does not catch everything. Hence the rest: monitoring that alerts early, network zones that limit the
damage, backups verified every night, and post-mortems that turn each mistake into a rule.

## The limits I set myself

- **I remain responsible** for everything that runs here, whoever wrote the code.
- **I do not publish what I cannot defend**: every decision is explained in writing, and I must be able to justify any
  file in the repository.
- **The AI decides nothing about people**: the family's accounts, access and rights are granted by me.
- **No gratuitous use**: an AI model consumes energy in data centres. I use it to build and to fix, not to run the
  services day to day.
- **Transparency by default**: if AI helped, it shows (commits, README, this page).
