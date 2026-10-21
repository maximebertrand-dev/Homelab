variable "etat_passphrase" {
  description = "Phrase de passe de chiffrement de l'état (16 caractères minimum). Jamais en clair dans un fichier versionné."
  type        = string
  sensitive   = true
}

variable "proxmox_endpoint" {
  description = "URL de l'API Proxmox (joignable via le VPN d'administration)."
  type        = string
  default     = "https://hv01.home.maximebertrand.net:8006/"
}

variable "proxmox_api_token" {
  description = "Jeton API Proxmox d'un compte de service aux droits limités. Fourni par variable d'environnement."
  type        = string
  sensitive   = true
}

variable "noeud" {
  description = "Nom du nœud Proxmox qui héberge les VM."
  type        = string
  default     = "hv01"
}

variable "stockage_vm" {
  description = "Stockage des disques des VM."
  type        = string
  default     = "local-zfs"
}

variable "pont" {
  description = "Pont réseau (compatible VLAN) sur lequel les VM sont branchées."
  type        = string
  default     = "vmbr0"
}

variable "image_debian" {
  description = "Image cloud Debian importée sur le nœud (identifiant de volume, type « import »)."
  type        = string
}

variable "cloud_init_vendor" {
  description = "Extrait cloud-init « vendor data » commun (installation de l'agent QEMU)."
  type        = string
  default     = "local:snippets/debian-base.yaml"
}

variable "domaine_interne" {
  description = "Domaine de recherche DNS des VM."
  type        = string
  default     = "home.maximebertrand.net"
}

variable "utilisateur" {
  description = "Compte d'administration créé par cloud-init (connexion par clé uniquement, sudo)."
  type        = string
  default     = "admin"
}

variable "cles_ssh" {
  description = "Clés SSH publiques autorisées sur le compte d'administration."
  type        = list(string)
}

variable "vms" {
  description = "VM à créer, indexées par nom d'hôte. VMID = VLAN × 10 + rang."
  type = map(object({
    vmid        = number
    description = string
    vlan        = number
    ipv4        = string # adresse/masque, ex. 192.0.2.10/24
    passerelle  = string # sert aussi de serveur DNS (Unbound sur le pare-feu)
    coeurs      = number
    memoire_mo  = number
    disque_go   = number
    partages    = optional(list(string), []) # correspondances de dossiers virtiofs
    pci         = optional(list(string), []) # correspondances PCI confiées à la VM (rôle Ansible hyperviseur)
    tags        = optional(list(string), [])
    ordre       = optional(number, 5)  # ordre de démarrage au boot de l'hôte (le pare-feu est à 1)
    delai       = optional(number, 15) # secondes d'attente avant la VM suivante
    creer       = optional(bool, true) # false : décrite mais pas créée
    demarrer    = optional(bool, true)
  }))

  validation {
    condition     = alltrue([for nom, vm in var.vms : can(cidrhost(vm.ipv4, 0))])
    error_message = "Chaque ipv4 doit être au format adresse/masque."
  }
}
