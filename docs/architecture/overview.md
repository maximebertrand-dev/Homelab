---
title: Vue d'ensemble de l'architecture
description: Les machines, les couches logicielles et ce qui est exposé ou non.
tags: [architecture]
---

# Vue d'ensemble

## Principes

1. **Tout en code** : aucune VM, aucun enregistrement DNS créé à la main. OpenTofu pour l'infrastructure, Ansible pour la configuration.
2. **Exposition minimale** : la vitrine passe par Cloudflare Tunnel ; les services personnels et la page de supervision passent par un seul port entrant, filtré par le pare-feu puis par un WAF, avec authentification unique. L'administration n'est accessible que par le VPN.
3. **Séparation des zones** : réseau domestique (Freebox) et homelab (OPNsense) sont isolés ; le homelab est découpé en VLAN, et chaque zone n'a accès qu'à ce dont elle a besoin.
4. **Tout se restaure** : sauvegarde chiffrée hors site chaque nuit, relue et comparée automatiquement ; procédures dans [`runbooks/`](../runbooks/), incidents analysés dans [`postmortems/`](../postmortems/).

## Couches

| Couche | Outils |
|---|---|
| Matériel | Dell PowerEdge T330 (serveur unique), Dell PowerEdge R610 (LAB allumé à la demande, à venir) |
| Hyperviseur & stockage | Proxmox VE, ZFS RAIDZ2 |
| Réseau & sécurité | OPNsense (virtualisé), VLAN, WireGuard, BunkerWeb (WAF), CrowdSec, Cloudflare (DNS, tunnel de la vitrine) |
| Identité | LLDAP (annuaire), Authelia (SSO et double authentification), page des comptes (invitations sans mot de passe transmis) |
| Provisionnement | OpenTofu (bpg/proxmox, opnsense, cloudflare), Ansible, lancé aussi depuis Semaphore UI |
| Applications | Docker Compose dans des VM dédiées par zone |
| Secrets | Coffre OpenBao (SSO, AppRole, audit), SOPS + age pour le démarrage |
| Observabilité | Prometheus, Alertmanager, NOC sur mesure, Grafana (interne), VictoriaLogs (journaux centralisés), ntfy (alertes sur téléphone), veille des connexions (adresses inconnues), sonde externe UptimeRobot |
| Services d'infra | NetBox (source de vérité), Semaphore UI (lancement des playbooks) |

Les choix structurants sont expliqués dans les ADR, en particulier l'[ADR 0010](../adr/0010-serveur-unique.md)
(un seul serveur), l'[ADR 0008](../adr/0008-exposition-directe-waf.md) (publication des services),
l'[ADR 0014](../adr/0014-supervision-noc.md) (supervision), l'[ADR 0015](../adr/0015-semaphore-ansible.md)
(Semaphore), l'[ADR 0016](../adr/0016-coffre-openbao.md) (coffre à secrets), l'[ADR 0017](../adr/0017-invitations-page-comptes.md)
(invitations et page des comptes), l'[ADR 0018](../adr/0018-droits-par-groupes-quotas.md) (droits par groupes et quotas),
l'[ADR 0019](../adr/0019-sauvegardes-hors-site.md) (sauvegardes hors site) et l'[ADR 0020](../adr/0020-journaux-centralises.md)
(journaux centralisés).

## Ce qui est exposé

| Service | Domaine | Accès |
|---|---|---|
| Site vitrine | `maximebertrand.net` | Public (Cloudflare Tunnel) |
| NOC (page de supervision sur mesure) | `noc.maximebertrand.net` | Public, derrière OPNsense, WAF et SSO ; lecture seule |
| Notifications d'alerte (ntfy) | `ntfy.maximebertrand.net` | Public, derrière OPNsense et WAF ; comptes dédiés, tout refusé par défaut |
| Services personnels (photos, fichiers) | sous-domaines de `maximebertrand.net` | Public, derrière OPNsense, WAF et SSO avec double authentification |
| Administration, annuaire, outils internes | `*.home.maximebertrand.net` (DNS interne uniquement) | VPN uniquement ; SSO en plus pour la page des comptes |
