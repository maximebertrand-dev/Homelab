---
title: "ADR 0024 : Une carte graphique confiée à la VM des applications"
description: Une GeForce d'entrée de gamme est confiée en entier à la VM des applications (passage PCI) pour la reconnaissance des photos et la conversion des vidéos, avec un pilote suivi par Debian et des conteneurs qui la demandent par CDI.
date: 2026-10-19
status: accepté
tags: [materiel, proxmox, immich, gpu]
---

# ADR 0024 : Une carte graphique confiée à la VM des applications

## Contexte

Le processeur du serveur (Xeon E3-1220 v6, 4 cœurs) n'a pas de partie graphique. Tout le travail lourd des
applications passait donc par lui :

- la reconnaissance des photos (visages, recherche par description) ;
- la conversion des vidéos pour les téléphones et les navigateurs.

Pendant les imports (≈ 11 500 photos en octobre), la VM des applications restait saturée pendant des heures et le
reste du serveur en pâtissait. Une GeForce GTX 1050 (Pascal, 2 Go, 75 W, sans alimentation supplémentaire) a été
ajoutée au serveur le 19/10.

## Options envisagées

1. **Rester sur le processeur** : aucun changement, mais des imports et des conversions toujours aussi longs.
2. **Confier la carte en entier à la VM des applications (passage PCI, vfio)** : performances natives, pilote dans
   la VM ; une seule VM peut s'en servir.
3. **Pilote sur l'hôte, partage avec des conteneurs LXC** : contraire au choix d'une VM par zone de sécurité
   ([ADR 0010](0010-serveur-unique.md)), et l'hôte exécuterait le pilote propriétaire.
4. **Partager la carte entre plusieurs VM (vGPU)** : non disponible sur une GeForce.

## Décision

Option 2, sur la VM des applications, où tournent tous les services qui en profitent.

- **Hôte** : la carte est réservée à `vfio-pci` dès le démarrage (pilotes de l'hôte écartés) et déclarée en
  « correspondance » Proxmox. Le jeton d'OpenTofu n'a de droit que sur cette correspondance, pas sur le reste du
  matériel.
- **VM** : la carte y est confiée sans sa ROM vidéo, inutile sans écran ; avec elle, le BIOS de la VM se figeait au
  démarrage.
- **Pilote** : celui de Debian (non-free, reconstruit par DKMS à chaque noyau, corrigé par les mises à jour de
  Debian) plutôt que celui de NVIDIA.
- **Conteneurs** : les outils de NVIDIA, depuis leur dépôt (clé rangée dans le rôle Ansible, empreinte vérifiée),
  en mode **CDI**. Un conteneur demande `nvidia.com/gpu=all`, la configuration de Docker reste intacte, et la
  description de la carte est régénérée à chaque démarrage, avant Docker.
- **Applications** : Immich fait la reconnaissance en CUDA et convertit les vidéos sur la carte (NVENC, NVDEC).

## Conséquences

- **Mesures sur un film 4K HDR** : décodage 157 images/s, conversion 4K HDR → 1080p 170 images/s, soit 7 fois le
  temps réel. Au repos, la carte reste à environ 33 °C, ventilateur arrêté.
- **Dépendance au pilote** : sans la carte ou sans son pilote, les conteneurs qui la demandent ne démarrent plus.
  Un relevé (présence, température, charge) alerte si la carte disparaît, par exemple après un nouveau noyau, ou si
  elle chauffe. Un mode dégradé, qui consiste à retirer la demande de carte, ramène tout sur le processeur.
- **Matériel vérifié au démarrage** : si la carte est retirée ou remplacée, la VM refuse de démarrer tant que la
  correspondance n'est pas retirée.
- **Mémoire** : celle de la VM est réservée en entier sur l'hôte, ce qui est nécessaire à l'accès direct de la
  carte à la mémoire.
- **Limites de la carte** : 2 Go de mémoire graphique, pas d'AV1, 8 encodages simultanés au plus sur une GeForce.
  NVIDIA arrête Pascal après sa branche 580, ce qui sera à revoir au passage à Debian 14.
