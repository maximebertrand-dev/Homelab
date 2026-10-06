#!/usr/bin/env python3
"""Collecteur du NOC : interroge Prometheus et Alertmanager, écrit un instantané JSON pour la page publique.

La page ne parle jamais à Prometheus : elle lit uniquement le fichier produit ici, avec un jeu de requêtes fixé
dans ce code. Aucune dépendance hors de la bibliothèque standard.

Variables d'environnement :
  PROMETHEUS    URL de Prometheus (défaut http://prometheus:9090)
  ALERTMANAGER  URL d'Alertmanager (défaut http://alertmanager:9093)
  CONFIG        fichier JSON des libellés (défaut /etc/noc/noc.json)
  SORTIE        fichier produit (défaut /sortie/etat.json) ; admin.json à côté, servi aux seuls administrateurs
  INTERVALLE    secondes entre deux collectes (défaut 30)
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROMETHEUS = os.environ.get("PROMETHEUS", "http://prometheus:9090").rstrip("/")
ALERTMANAGER = os.environ.get("ALERTMANAGER", "http://alertmanager:9093").rstrip("/")
CONFIG = os.environ.get("CONFIG", "/etc/noc/noc.json")
SORTIE = os.environ.get("SORTIE", "/sortie/etat.json")
INTERVALLE = int(os.environ.get("INTERVALLE", "30"))
# Historique (courbes sur 24 h) : recalculé moins souvent, il change lentement.
INTERVALLE_HISTORIQUE = 300
HISTORIQUE_DUREE = 24 * 3600
HISTORIQUE_PAS = 900


def journal(message):
    print(f"{datetime.now().isoformat(timespec='seconds')} {message}", file=sys.stderr, flush=True)


def lire_json(url, delai=10):
    with urllib.request.urlopen(url, timeout=delai) as reponse:
        return json.load(reponse)


def requete(promql):
    """Requête instantanée : liste de (étiquettes, valeur)."""
    url = f"{PROMETHEUS}/api/v1/query?" + urllib.parse.urlencode({"query": promql})
    donnees = lire_json(url)
    return [(r["metric"], float(r["value"][1])) for r in donnees["data"]["result"]]


def requete_plage(promql, debut, fin, pas):
    url = f"{PROMETHEUS}/api/v1/query_range?" + urllib.parse.urlencode(
        {"query": promql, "start": debut, "end": fin, "step": pas}
    )
    donnees = lire_json(url, delai=20)
    return [(r["metric"], [(int(t), round(float(v), 4)) for t, v in r["values"]]) for r in donnees["data"]["result"]]


def par(etiquette, resultats):
    """Indexe des résultats par une étiquette : {valeur_etiquette: valeur}."""
    return {m.get(etiquette, ""): v for m, v in resultats}


def arrondi(valeur, chiffres=4):
    return None if valeur is None else round(valeur, chiffres)


# --- Blocs du tableau de bord ------------------------------------------------------------------------


def services(libelles):
    etat = par("instance", requete('probe_success{job="services"}'))
    latence = par("instance", requete('probe_duration_seconds{job="services"}'))
    dispo_24h = par("instance", requete('avg_over_time(probe_success{job="services"}[24h])'))
    dispo_7j = par("instance", requete('avg_over_time(probe_success{job="services"}[7d])'))
    certificat = par("instance", requete('(probe_ssl_earliest_cert_expiry{job="services"} - time()) / 86400'))
    liste = []
    for instance in sorted(etat, key=lambda i: (libelles.get(i, {}).get("ordre", 99), i)):
        info = libelles.get(instance, {})
        liste.append({
            "id": instance,
            "nom": info.get("nom", instance),
            "description": info.get("description", ""),
            "ok": etat[instance] == 1,
            "latence_ms": round(latence.get(instance, 0) * 1000),
            "dispo_24h": arrondi(dispo_24h.get(instance)),
            "dispo_7j": arrondi(dispo_7j.get(instance)),
            "certificat_jours": None if instance not in certificat else int(certificat[instance]),
        })
    return liste


def outils(libelles):
    etat = par("instance", requete('probe_success{job="outils-internes"}'))
    return [
        {"id": i, "nom": libelles.get(i, {}).get("nom", i), "ok": v == 1}
        for i, v in sorted(etat.items(), key=lambda e: libelles.get(e[0], {}).get("nom", e[0]))
    ]


def machines(libelles):
    joignable = par("instance", requete('up{job="machines"}'))
    processeur = par("instance", requete('1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))'))
    memoire = par("instance", requete("1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes"))
    memoire_totale = par("instance", requete("node_memory_MemTotal_bytes"))
    disque = par("instance", requete(
        '1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}'
    ))
    demarrage = par("instance", requete("time() - node_boot_time_seconds"))
    charge = par("instance", requete("node_load1"))
    coeurs = par("instance", requete('count by (instance) (node_cpu_seconds_total{mode="idle"})'))
    liste = []
    for instance in sorted(joignable, key=lambda i: (libelles.get(i, {}).get("ordre", 99), i)):
        info = libelles.get(instance, {})
        liste.append({
            "id": instance,
            "nom": instance,
            "role": info.get("role", ""),
            "ok": joignable[instance] == 1,
            "processeur": arrondi(processeur.get(instance)),
            "memoire": arrondi(memoire.get(instance)),
            "memoire_go": arrondi(memoire_totale.get(instance, 0) / 2**30, 1),
            "disque": arrondi(disque.get(instance)),
            "coeurs": int(coeurs.get(instance, 0)),
            "charge": arrondi(charge.get(instance), 2),
            "uptime_s": int(demarrage.get(instance, 0)),
        })
    return liste


def machines_virtuelles():
    noms = {m["id"]: m.get("name", m["id"]) for m, _ in requete('pve_guest_info{type="qemu"}')}
    allumee = par("id", requete('pve_up{id=~"qemu/.*"}'))
    processeur = par("id", requete('pve_cpu_usage_ratio{id=~"qemu/.*"}'))
    # Mémoire allouée : l'occupation vue par Proxmox inclut le cache des invités (proche de 100 %, trompeuse).
    memoire = par("id", requete('pve_memory_size_bytes{id=~"qemu/.*"} / 2^30'))
    demarrage_auto = par("id", requete('pve_onboot_status{id=~"qemu/.*"}'))
    liste = []
    for ident in sorted(noms, key=lambda i: int(i.split("/")[1])):
        liste.append({
            "vmid": int(ident.split("/")[1]),
            "nom": noms[ident],
            "allumee": allumee.get(ident) == 1,
            "demarrage_auto": demarrage_auto.get(ident) == 1,
            "processeur": arrondi(processeur.get(ident)),
            "memoire_go": arrondi(memoire.get(ident), 1),
        })
    return liste


def stockage():
    etats = [(m["zpool"], m["state"]) for m, v in requete("node_zfs_zpool_state") if v == 1]
    pools = [{"nom": nom, "etat": etat} for nom, etat in sorted(etats)]
    sante = par("device", requete("smartctl_device_smart_status"))
    temperature = par("device", requete('smartctl_device_temperature{temperature_type="current"}'))
    heures = par("device", requete("smartctl_device_power_on_seconds / 3600"))
    defauts = par("device", requete("smartctl_scsi_grown_defect_list"))
    modeles = {m["device"]: m for m, _ in requete("smartctl_device")}
    disques = []
    for disque in sorted(sante):
        info = modeles.get(disque, {})
        disques.append({
            "nom": disque,
            "modele": info.get("model_name", ""),
            "ok": sante[disque] == 1,
            "temperature": int(temperature[disque]) if disque in temperature else None,
            "heures": int(heures.get(disque, 0)),
            "defauts": int(defauts.get(disque, 0)),
        })
    occupation = requete(
        'pve_disk_usage_bytes{id=~"storage/.*/local-zfs"} / pve_disk_size_bytes{id=~"storage/.*/local-zfs"}'
    )
    # Jeux de données (relevé de l'hyperviseur) : occupé et place permise (quota, ou reste du pool), puis le total.
    utilise = par("jeu", requete("homelab_stockage_utilise_octets"))
    disponible = par("jeu", requete("homelab_stockage_disponible_octets"))
    donnees = [{"nom": jeu, "utilise": int(utilise[jeu]), "permis": int(utilise[jeu] + disponible.get(jeu, 0)),
                "ratio": arrondi(utilise[jeu] / (utilise[jeu] + disponible.get(jeu, 0)))}
               for jeu in sorted(utilise) if utilise[jeu] + disponible.get(jeu, 0) > 0]
    total_utilise = requete("sum(homelab_stockage_total_utilise_octets)")
    total_libre = requete("sum(homelab_stockage_total_disponible_octets)")
    total = None
    if total_utilise and total_libre and total_utilise[0][1] + total_libre[0][1] > 0:
        occupe, libre = total_utilise[0][1], total_libre[0][1]
        total = {"utilise": int(occupe), "permis": int(occupe + libre), "ratio": arrondi(occupe / (occupe + libre))}
    return {
        "pools": pools,
        "disques": disques,
        "occupation": arrondi(occupation[0][1]) if occupation else None,
        "donnees": donnees,
        "total": total,
    }


def sauvegarde():
    """Sauvegarde hors site (métriques publiées par le script de l'hyperviseur) ; None si jamais exécutée."""
    valeurs = {m["__name__"].removeprefix("homelab_sauvegarde_"): v
               for m, v in requete('{__name__=~"homelab_sauvegarde_.*"}')}
    if "statut" not in valeurs:
        return None
    maintenant = time.time()
    age = lambda cle: int(maintenant - valeurs[cle]) if cle in valeurs else None  # noqa: E731
    return {
        "ok": valeurs["statut"] == 1,
        "depuis_reussite_s": age("derniere_reussite_timestamp"),
        "duree_s": int(valeurs.get("duree_secondes", 0)),
        "ajoute_octets": int(valeurs.get("ajoute_octets", 0)),
        "espace": arrondi(valeurs["espace_utilise_ratio"]) if "espace_utilise_ratio" in valeurs else None,
        "verification": int(valeurs.get("verification_statut", -1)),
        "depuis_verification_s": age("verification_derniere_reussite_timestamp"),
        "fichiers_verifies": int(valeurs.get("verification_fichiers", 0)),
        "octets_verifies": int(valeurs.get("verification_octets", 0)),
    }


def alertes():
    url = f"{ALERTMANAGER}/api/v2/alerts?" + urllib.parse.urlencode(
        {"active": "true", "silenced": "false", "inhibited": "false"}
    )
    liste = []
    for alerte in lire_json(url):
        etiquettes = alerte.get("labels", {})
        annotations = alerte.get("annotations", {})
        # Veille, détection d'intrusion et alertes « admin » : pour l'administrateur seulement (e-mail, téléphone,
        # Grafana), jamais sur le NOC que la famille consulte.
        if etiquettes.get("severite") in ("veille", "securite", "info", "admin"):
            continue
        liste.append({
            "nom": etiquettes.get("alertname", ""),
            "severite": etiquettes.get("severite", "avertissement"),
            "instance": etiquettes.get("instance", ""),
            "resume": annotations.get("resume", ""),
            "description": annotations.get("description", ""),
            "depuis": alerte.get("startsAt", ""),
        })
    ordre = {"critique": 0, "avertissement": 1}
    return sorted(liste, key=lambda a: (ordre.get(a["severite"], 2), a["depuis"]))


def transferts(libelles):
    """Travaux d'import (métriques homelab_import_*) : en cours, programmés, ou finis depuis moins d'une semaine."""
    series = {}
    for m, v in requete('{__name__=~"homelab_import_.*"}'):
        series.setdefault(m.get("travail", ""), {})[m["__name__"].removeprefix("homelab_import_")] = v
    maintenant, liste = time.time(), []
    for travail, s in series.items():
        etat = int(s.get("etat", 0))
        fin = s.get("fin_timestamp")
        if etat == 0 or (etat in (2, 3, 5) and fin and maintenant - fin > 7 * 86400):
            continue
        mesure = s.get("derniere_mesure_timestamp")
        liste.append({
            "nom": libelles.get(travail, travail), "etat": etat,
            "octets": int(s.get("octets", 0)), "total": int(s.get("total_octets", 0)),
            "pourcentage": s.get("pourcentage"), "debit": int(s.get("debit_octets", 0)),
            # Travaux comptés en fichiers (envoi des photos) : pas de volume connu à l'avance.
            "fichiers": int(s.get("fichiers", 0)), "fichiers_total": int(s.get("fichiers_total", 0)),
            "debit_fichiers": round(s.get("debit_fichiers", 0), 2),
            "eta_s": int(s["eta_secondes"]) if s.get("eta_secondes", -1) >= 0 else None,
            "erreurs": int(s.get("erreurs", 0)),
            "depuis_mesure_s": int(maintenant - mesure) if mesure else None,
            "depuis_fin_s": int(maintenant - fin) if fin else None,
        })
    return sorted(liste, key=lambda t: ({1: 0, 5: 1, 3: 2, 4: 3, 2: 4}.get(t["etat"], 5), t["nom"]))


def historique():
    fin = int(time.time())
    debut = fin - HISTORIQUE_DUREE
    series = {}
    for cle, promql in {
        "processeur": '1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))',
        "memoire": "1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes",
    }.items():
        series[cle] = {m.get("instance", ""): v for m, v in requete_plage(promql, debut, fin, HISTORIQUE_PAS)}
    series["latence"] = {
        m.get("instance", ""): [(t, round(v * 1000)) for t, v in valeurs]
        for m, valeurs in requete_plage('probe_duration_seconds{job="services"}', debut, fin, HISTORIQUE_PAS)
    }
    return series


def etat_global(bloc_services, bloc_alertes, bloc_stockage, bloc_sauvegarde):
    if any(a["severite"] == "critique" for a in bloc_alertes):
        return "incident"
    en_panne = [s for s in bloc_services if not s["ok"]]
    pool_degrade = any(p["etat"] != "online" for p in bloc_stockage["pools"])
    sauvegarde_ko = bloc_sauvegarde is not None and (not bloc_sauvegarde["ok"] or bloc_sauvegarde["verification"] == 0)
    if en_panne or pool_degrade or sauvegarde_ko or bloc_alertes:
        return "degrade"
    return "ok"


# --- Boucle --------------------------------------------------------------------------------------------


def ecrire(donnees, chemin=SORTIE):
    temporaire = chemin + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as fichier:
        json.dump(donnees, fichier, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporaire, chemin)


def main():
    historique_cache, historique_date = {}, 0
    while True:
        debut = time.monotonic()
        try:
            with open(CONFIG, encoding="utf-8") as fichier:
                libelles = json.load(fichier)
            bloc_services = services(libelles.get("services", {}))
            bloc_alertes = alertes()
            bloc_stockage = stockage()
            bloc_sauvegarde = sauvegarde()
            if time.time() - historique_date > INTERVALLE_HISTORIQUE:
                historique_cache, historique_date = historique(), time.time()
            ecrire({
                "genere": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "intervalle": INTERVALLE,
                "collecte": {"ok": True},
                "etat": etat_global(bloc_services, bloc_alertes, bloc_stockage, bloc_sauvegarde),
                "services": bloc_services,
                "outils": outils(libelles.get("outils", {})),
                "machines": machines(libelles.get("machines", {})),
                "vms": machines_virtuelles(),
                "stockage": bloc_stockage,
                "sauvegarde": bloc_sauvegarde,
                "alertes": bloc_alertes,
                "historique": historique_cache,
            })
            # Réservé aux administrateurs (nginx refuse /admin.json aux autres comptes).
            ecrire({"genere": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "transferts": transferts(libelles.get("transferts", {}))},
                   os.path.join(os.path.dirname(SORTIE), "admin.json"))
        except Exception as erreur:  # la page doit savoir que la collecte a échoué, pas afficher un état figé
            journal(f"collecte en échec : {erreur!r}")
            try:
                ecrire({
                    "genere": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "intervalle": INTERVALLE,
                    "collecte": {"ok": False, "erreur": type(erreur).__name__},
                    "etat": "inconnu",
                })
            except OSError as erreur_ecriture:
                journal(f"écriture impossible : {erreur_ecriture!r}")
        time.sleep(max(1, INTERVALLE - (time.monotonic() - debut)))


if __name__ == "__main__":
    main()
