---
title: "ADR 0021 : Détection et prévention des intrusions en couches légères"
description: Suricata sur le pare-feu, CrowdSec partagé par toutes les machines avec blocage au pare-feu, règles de détection sur les journaux centralisés ; pas de SIEM lourd.
date: 2026-09-29
status: accepté
tags: [securite, detection, ids, crowdsec, suricata]
---

# ADR 0021 : Détection et prévention des intrusions en couches légères

## Contexte

Le homelab bloque déjà beaucoup à l'entrée : WAF (règles OWASP), CrowdSec **dans le seul WAF**, barrière SSO, pare-feu
par zones. Il **détecte** peu : une attaque qui ne passe pas par le WAF (VPN, flux sortants, mouvement latéral entre
zones, compte volé) n'alerte personne, et un comportement suspect vu par le WAF ne protège pas les autres services.
L'audit du 29/09 l'a montré : sur un point d'entrée d'application mobile, un mauvais mot de passe renvoie un succès
HTTP, invisible pour le WAF. La mémoire reste le facteur limitant : 32 Go pour tout le homelab.

## Options envisagées

1. **SIEM complet (Wazuh, Security Onion)** : très complet, mais 4 à 16 Go de mémoire rien que pour lui : hors de
   portée.
2. **Couches légères, chacune à sa place** — retenu :
   - réseau : IDS/IPS sur le pare-feu ;
   - réputation et blocage : CrowdSec étendu à toutes les machines, décisions appliquées par le pare-feu ;
   - hôtes et applications : règles de détection sur les journaux déjà centralisés ([ADR 0020](0020-journaux-centralises.md)).

## Décision

1. **Suricata sur OPNsense** (fonction intégrée, règles ET Open et listes abuse.ch) :
   - d'abord en **détection** sur le WAN et sur les interfaces internes (mouvements latéraux, trafic vers des serveurs
     de commande connus) ;
   - puis **prévention** sur le WAN une fois les faux positifs réglés (deux semaines) ;
   - mémoire du pare-feu portée de 2 à 3 Go.
2. **CrowdSec partagé** :
   - une API locale centrale sur la VM de supervision ;
   - des agents sur chaque machine (SSH, portail de connexion, applications) ;
   - le **pare-feu comme bouclier** (greffon CrowdSec d'OPNsense) : une adresse qui attaque un service est bloquée pour
     tous ;
   - la liste communautaire bloque d'avance les adresses connues ;
   - l'adresse de la maison est exclue du blocage au pare-feu (une seule adresse pour tout le foyer).
3. **Détection sur les journaux** (vmalert sur VictoriaLogs, alertes par le gestionnaire existant) :
   - connexion SSH d'une source inattendue, élévation de privilèges ;
   - clé SSH ajoutée, compte d'administration créé ;
   - rafales d'échecs de connexion (portail, applications, y compris les points d'entrée mobiles qui répondent 200) ;
   - modification de la configuration du pare-feu ;
   - arrêt ou redémarrage inattendu d'un conteneur.
4. **Traçabilité sur les hôtes** : auditd sur les fichiers sensibles (clés autorisées, sudoers, comptes), vers le
   journal systemd donc les journaux centralisés.

## Conséquences

- Une alerte critique réelle doit rester rare : chaque règle est d'abord observée en « avertissement ».
- Les exclusions (adresse de la maison, trafic légitime qui ressemble à un robot) sont écrites dans le code, avec la
  raison ; aucune désactivation globale.
- Le pare-feu devient un point de blocage partagé : une erreur de décision coupe tous les services pour l'adresse
  concernée ; le runbook décrit comment lever une décision.
- Ce qui reste hors de portée : l'analyse comportementale poussée et la corrélation longue (un SIEM complet) ; à
  reconsidérer avec plus de matériel.

## Mise en œuvre

Par étapes, la moins coûteuse d'abord ; chaque règle est observée en « avertissement » avant de devenir une alerte.

1. **Fait le 29/09** : l'adresse de la maison n'est plus jamais bannie par CrowdSec (liste « postoverflow » du WAF,
   remise en place automatiquement après chaque recréation du conteneur).
2. **Fait le 29/09** : règles de détection sur les journaux centralisés (vmalert sur VictoriaLogs) : connexions SSH,
   sudo, clés ajoutées, rafales d'échecs de connexion (portail, applications mobiles).
3. **Fait le 29/09** : auditd sur toutes les machines (rôle commun), vers le journal systemd.
4. **Fait le 08/10** : veille des connexions : une adresse devient connue à sa première connexion complète réussie ;
   des échecs depuis une adresse inconnue sans succès dans le quart d'heure, ou un mot de passe accepté sans second
   facteur valide, déclenchent une alerte (voir le [journal du 13/10](../journal/2026-10-13-veille-connexions-waf.md)).
5. CrowdSec partagé : API locale sur la VM de supervision, agents sur les machines, greffon d'OPNsense (après sa
   mise à jour).
6. Suricata sur OPNsense, en détection puis en prévention sur le WAN (après sa mise à jour ; mémoire du pare-feu
   portée à 3 Go).
