# Une VM par zone de sécurité (voir docs/adr/0010-serveur-unique.md).
# Toutes partent de la même image cloud Debian ; la configuration applicative est faite par Ansible.

locals {
  vms = { for nom, vm in var.vms : nom => vm if vm.creer }
}

resource "proxmox_virtual_environment_vm" "vm" {
  for_each = local.vms

  name        = each.key
  node_name   = var.noeud
  vm_id       = each.value.vmid
  description = "${each.value.description} — géré par OpenTofu"
  tags        = sort(distinct(concat(["opentofu"], each.value.tags)))

  on_boot = each.value.demarrer

  started         = each.value.demarrer
  machine         = "q35"
  scsi_hardware   = "virtio-scsi-single"
  stop_on_destroy = true

  # L'agent QEMU remonte l'adresse IP et fige les systèmes de fichiers pendant les sauvegardes.
  agent {
    enabled = true
    trim    = true
  }

  # Nœud unique, pas de migration : le type « host » expose toutes les instructions du processeur
  # (AVX2, nécessaire à certains modèles d'apprentissage automatique).
  cpu {
    cores = each.value.coeurs
    type  = "host"
  }

  memory {
    dedicated = each.value.memoire_mo
  }

  operating_system {
    type = "l26"
  }

  # Console série : les images cloud Debian l'utilisent par défaut.
  serial_device {}
  vga {
    type = "serial0"
  }

  disk {
    datastore_id = var.stockage_vm
    import_from  = var.image_debian
    interface    = "scsi0"
    size         = each.value.disque_go
    discard      = "on"
    iothread     = true
    ssd          = true
  }

  network_device {
    bridge  = var.pont
    vlan_id = each.value.vlan
  }

  # Données de l'hôte partagées sans passer par le réseau.
  dynamic "virtiofs" {
    for_each = each.value.partages
    content {
      mapping = virtiofs.value
      cache   = "auto"
    }
  }

  # Cartes confiées en entier à la VM (passage PCI), par correspondance Proxmox : le jeton n'a de droit que sur
  # elles. La mémoire de la VM est alors réservée en entier sur l'hôte (accès direct de la carte à la mémoire).
  dynamic "hostpci" {
    for_each = { for i, correspondance in each.value.pci : "hostpci${i}" => correspondance }
    content {
      device  = hostpci.key
      mapping = hostpci.value
      pcie    = true
      # ROM de la carte cachée : SeaBIOS l'exécutait au démarrage et la VM se figeait avant Linux (19/10). Inutile pour
      # le calcul et la vidéo (pas d'affichage).
      rombar = false
    }
  }

  initialization {
    datastore_id        = var.stockage_vm
    vendor_data_file_id = var.cloud_init_vendor

    dns {
      domain  = var.domaine_interne
      servers = [each.value.passerelle]
    }

    ip_config {
      ipv4 {
        address = each.value.ipv4
        gateway = each.value.passerelle
      }
    }

    user_account {
      username = var.utilisateur
      keys     = var.cles_ssh
    }
  }

  lifecycle {
    # Une nouvelle image Debian ne doit pas recréer les VM existantes.
    # L'ordre de démarrage est réglé par Ansible (rôle hyperviseur) : il exige un droit sur tout l'hôte
    # (Sys.Modify) que le jeton d'OpenTofu n'a volontairement pas.
    ignore_changes = [disk[0].import_from, startup]
  }
}
