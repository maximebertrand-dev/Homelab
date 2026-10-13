---
title: "ADR 0010 : Un seul serveur, avec le pare-feu virtualisé"
description: Le Dell T330 porte l'hyperviseur, le stockage et OPNsense en VM ; pas de cluster ni de bastion pour l'instant.
date: 2026-09-26
status: accepté
tags: [proxmox, opnsense, architecture]
---

# ADR 0010 : Un seul serveur, avec le pare-feu virtualisé

Remplace les ADR [0001](0001-proxmox-zfs-t330.md), [0003](0003-opnsense-dmz-freebox.md) et
[0006](0006-cluster-proxmox-basse-conso.md).

## Contexte

Les ADR précédents prévoyaient un cluster de trois mini-PC pour les services, un boîtier dédié au pare-feu et le
T330 réservé au stockage. Ce matériel ne sera pas acheté avant longtemps, et le budget électrique reste plafonné
à 40 € par mois. Il faut une architecture qui fonctionne **avec une seule machine**, sans renoncer à la séparation
des zones.

## Options envisagées

1. **Attendre le matériel** : rien ne tourne en attendant.
2. **Tout sur le T330, pare-feu physique séparé plus tard** : démarrage immédiat, en acceptant un point unique de
   défaillance.

## Décision

Le **T330 sous Proxmox VE** porte tout :

- le stockage : pool ZFS **RAIDZ2** sur quatre disques SAS, cinq depuis le 05/10/2026 (deux pannes tolérées), système inclus ;
- le pare-feu : **OPNsense en machine virtuelle**, qui reçoit tout le trafic du homelab (mode DMZ de la Freebox) ;
- les services : une machine virtuelle par zone de sécurité.

**Pas de bastion** : avec une seule machine et un seul administrateur, il ajoute plus de complexité que de sécurité.
L'administration passe uniquement par le **VPN WireGuard**, avec double authentification sur les interfaces
d'administration.

## Conséquences

- **Point unique de défaillance** : une maintenance du T330 coupe tout le homelab. Le réseau de la maison n'est pas
  touché (la Freebox reste routeur).
- **Accès de secours** : l'interface hors bande du serveur (iDRAC) reste joignable même quand le pare-feu est
  arrêté.
- **Sauvegardes hors site indispensables** : données et sauvegardes sont sur la même machine.
- Le pare-feu virtualisé partage le matériel des services qu'il protège : les ponts réseau de l'hyperviseur
  n'ont pas d'adresse côté Internet, pour que l'hôte ne soit joignable qu'à travers OPNsense.
- Si le matériel prévu arrive, les ADR 0003 et 0006 pourront être réactivés par un nouvel ADR.
