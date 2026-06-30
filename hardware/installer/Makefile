# PixelOS - Makefile pour construire la clé USB bootable d'install
#
# Usage:
#   make all            # Télécharge sets OpenBSD + ISO + site (nécessite internet)
#   make offline-usb    # Prépare clé USB OFFLINE complète (tout pré-chargé)
#   make usb            # Grave sur clé USB (/dev/sd1) - ATTENTION: efface la cible
#   make iso            # Génère une ISO hybride bootable
#   make clean          # Nettoie les fichiers temporaires
#
# Prérequis (sur la machine qui build la clé):
#   - OpenBSD 7.6 avec curl, rsync, signify
#   - Connexion internet pour télécharger les sets
#   - doas pour graver l'USB
#
# La clé produite par "make offline-usb" contient TOUT le nécessaire:
#   - Sets OpenBSD (base, comp, man)
#   - Paquets OpenBSD (.tgz dans packages/)
#   - Paquets Python (.whl dans pip_packages/)
#   - Sources PixelOS + configurations
#   - install.conf (réponses automatiques)
#   -> Installation 100% sans internet

ARCH = amd64
OPENBSD_VER = 76
MIRROR = https://cdn.openbsd.org/pub/OpenBSD/$(OPENBSD_VER)/$(ARCH)
PKG_MIRROR = $(MIRROR)/packages/$(ARCH)
USB_DEV = sd1          # À adapter selon votre matériel (dmesg pour vérifier)

SRC_DIR = src
CONFIG_DIR = configs
BUILD_DIR = build
DIST_DIR = $(BUILD_DIR)/dist
SITE_TGZ = $(BUILD_DIR)/site$(OPENBSD_VER).tgz
INSTALL_ISO = $(BUILD_DIR)/install$(OPENBSD_VER).iso
FINAL_ISO = $(BUILD_DIR)/pixelos-$(OPENBSD_VER)-$(ARCH).iso

# Chemins des sources canoniques
OPENBSD_DIR = ../openbsd
PF_CONF = $(OPENBSD_DIR)/pf.conf
NODES_CONF = $(OPENBSD_DIR)/nodes.conf
SERIAL_SRC_FILE = $(OPENBSD_DIR)/serial_gateway.c

# Sources Python PixelOS (depuis racine du dépôt)
PIXELOS_SRC = ../../pixelos/src

.PHONY: all clean prepare usb iso dirs site offline-usb

all: prepare iso

# ─── Répertoires ──────────────────────────────────────────
dirs:
	mkdir -p $(BUILD_DIR)
	mkdir -p $(DIST_DIR)/pixelos
	mkdir -p $(DIST_DIR)/configs
	mkdir -p $(DIST_DIR)/src/rc.d

# ─── Téléchargement des sets OpenBSD ──────────────────────
download:
	@echo "=== Téléchargement des sets OpenBSD $(OPENBSD_VER)-$(ARCH) ==="
	cd $(BUILD_DIR) && \
	curl -O $(MIRROR)/SHA256.sig && \
	for set in base$(OPENBSD_VER).tgz comp$(OPENBSD_VER).tgz man$(OPENBSD_VER).tgz; do \
		[ -f "$$set" ] || curl -O $(MIRROR)/$$set; \
	done
	@echo "=== Vérification SHA256 ==="
	cd $(BUILD_DIR) && signify -C -p /etc/signify/openbsd-$(OPENBSD_VER)-base.pub -x SHA256.sig \
		base$(OPENBSD_VER).tgz comp$(OPENBSD_VER).tgz man$(OPENBSD_VER).tgz 2>/dev/null || \
	echo "ATTENTION: vérification signifie échouée (clé manquante?)"

# ─── Téléchargement des paquets OpenBSD ───────────────────
download-packages:
	@echo "=== Téléchargement des paquets OpenBSD (offline) ==="
	mkdir -p $(BUILD_DIR)/packages
	cd $(BUILD_DIR)/packages && \
	for pkg in $$(grep -v '^#' ../../packages-list.txt | grep -v '^$$'); do \
		[ -f "$$pkg" ] || curl -O $(PKG_MIRROR)/$$pkg; \
	done
	@echo "Paquets téléchargés: $$(ls $(BUILD_DIR)/packages/*.tgz 2>/dev/null | wc -l)"

# ─── Téléchargement des paquets Python ────────────────────
download-pip:
	@echo "=== Téléchargement des paquets Python (offline) ==="
	mkdir -p $(BUILD_DIR)/pip_packages
	pip3 download -r ../../requirements.txt \
		-d $(BUILD_DIR)/pip_packages 2>&1 || \
	pip3 download \
		structlog paho-mqtt pyyaml numpy scikit-learn scipy \
		onnx onnxruntime skl2onnx flask opencv-python-headless \
		psutil biopython h5py mysql-connector-python pymongo \
		psycopg2-binary pandas plotly streamlit requests \
		-d $(BUILD_DIR)/pip_packages 2>&1 || true
	@echo "Paquets Python téléchargés: $$(ls $(BUILD_DIR)/pip_packages/*.whl 2>/dev/null | wc -l)"

# ─── Téléchargement de l'ISO d'install ────────────────────
download-iso:
	@echo "=== Téléchargement de l'ISO d'installation ==="
	cd $(BUILD_DIR) && \
	[ -f "install$(OPENBSD_VER).iso" ] || curl -O $(MIRROR)/install$(OPENBSD_VER).iso && \
	[ -f "install$(OPENBSD_VER).fs" ] || curl -O $(MIRROR)/install$(OPENBSD_VER).fs

# ─── Construction de siteXX.tgz ───────────────────────────
site: dirs
	@echo "=== Construction de site$(OPENBSD_VER).tgz ==="
	# Script d'installation
	cp install.sh $(DIST_DIR)/
	chmod +x $(DIST_DIR)/install.sh
	# Fichiers requis
	cp requirements.txt $(DIST_DIR)/
	# Configuration
	cp $(CONFIG_DIR)/* $(DIST_DIR)/configs/
	cp $(PF_CONF) $(DIST_DIR)/configs/pf.conf
	cp $(NODES_CONF) $(DIST_DIR)/configs/nodes.conf
	# Sources serial_gateway
	cp $(SERIAL_SRC_FILE) $(DIST_DIR)/src/serial_gateway.c
	if [ -f "$(SRC_DIR)/Makefile.serial" ]; then \
		cp $(SRC_DIR)/Makefile.serial $(DIST_DIR)/src/; \
	fi
	cp -r $(SRC_DIR)/rc.d $(DIST_DIR)/src/
	# Sources Python PixelOS
	if [ -d "$(PIXELOS_SRC)" ]; then \
		cp -r $(PIXELOS_SRC) $(DIST_DIR)/pixelos/; \
		rm -rf $(DIST_DIR)/pixelos/__pycache__; \
		find $(DIST_DIR)/pixelos -name '*.pyc' -delete; \
	fi
	# Créer l'archive
	cd $(DIST_DIR) && tar czf ../site$(OPENBSD_VER).tgz .
	@echo "site$(OPENBSD_VER).tgz créé: $$(du -sh $(BUILD_DIR)/site$(OPENBSD_VER).tgz | cut -f1)"

# ─── Préparation complète (tout ce qui nécessite internet) ─
prepare: download download-packages download-pip download-iso site
	@echo "=== Tout est téléchargé ==="
	@echo "  Sets: $$(ls -lh $(BUILD_DIR)/base*.tgz $(BUILD_DIR)/comp*.tgz)"
	@echo "  Paquets: $$(ls $(BUILD_DIR)/packages/*.tgz 2>/dev/null | wc -l)"
	@echo "  Pip: $$(ls $(BUILD_DIR)/pip_packages/*.whl 2>/dev/null | wc -l)"
	@echo "  Site: $$(ls -lh $(SITE_TGZ))"
	@du -sh $(BUILD_DIR)

# ─── Génération ISO hybride ───────────────────────────────
iso: prepare
	@echo "=== Génération de l'ISO PixelOS bootable ==="
	mkdir -p $(BUILD_DIR)/iso_contents
	vnconfig vnd0 $(BUILD_DIR)/install$(OPENBSD_VER).iso
	mount -t cd9660 /dev/vnd0c $(BUILD_DIR)/mnt_iso 2>/dev/null || \
	  (mkdir -p $(BUILD_DIR)/mnt_iso && mount -t cd9660 /dev/vnd0a $(BUILD_DIR)/mnt_iso)
	cp -r $(BUILD_DIR)/mnt_iso/* $(BUILD_DIR)/iso_contents/
	umount $(BUILD_DIR)/mnt_iso 2>/dev/null; vnconfig -u vnd0 2>/dev/null; true
	# Ajouter install.conf + sets + paquets
	cp install.conf $(BUILD_DIR)/iso_contents/
	cp $(BUILD_DIR)/*.tgz $(BUILD_DIR)/iso_contents/$(OPENBSD_VER)/
	cp -r $(BUILD_DIR)/packages $(BUILD_DIR)/iso_contents/
	cp -r $(BUILD_DIR)/pip_packages $(BUILD_DIR)/iso_contents/
	cp requirements.txt $(BUILD_DIR)/iso_contents/
	# Reconstruire l'ISO
	mkhybrid -o $(FINAL_ISO) -A "PixelOS Offline Installer" \
		-V "PIXELOS_INSTALL" \
		-b $(OPENBSD_VER)/floppy$(OPENBSD_VER).fs \
		-c $(OPENBSD_VER)/boot.catalog \
		$(BUILD_DIR)/iso_contents
	rm -rf $(BUILD_DIR)/iso_contents $(BUILD_DIR)/mnt_iso
	@echo "=== ISO créée: $(FINAL_ISO) ($$(du -sh $(FINAL_ISO) | cut -f1)) ==="

# ─── Clé USB offline complète ─────────────────────────────
offline-usb: prepare
	@echo "=== Construction de la clé USB OFFLINE ==="
	@echo "ATTENTION: Toutes les données sur $(USB_DEV) seront effacées !"
	@echo "Continuer ? (CTRL+C pour annuler)"
	@read -r _ && \
	dd if=/dev/zero of=/dev/r$(USB_DEV) bs=1m count=10 && \
	fdisk -i $(USB_DEV) && \
	fdisk -a $(USB_DEV) && \
	newfs /dev/r$(USB_DEV)a && \
	mkdir -p /mnt/usb && \
	mount /dev/$(USB_DEV)a /mnt/usb && \
	# install.conf à la racine \
	cp install.conf /mnt/usb/ && \
	# Sets OpenBSD \
	mkdir -p /mnt/usb/$(OPENBSD_VER) && \
	cp $(BUILD_DIR)/base$(OPENBSD_VER).tgz /mnt/usb/$(OPENBSD_VER)/ && \
	cp $(BUILD_DIR)/comp$(OPENBSD_VER).tgz /mnt/usb/$(OPENBSD_VER)/ && \
	cp $(BUILD_DIR)/man$(OPENBSD_VER).tgz /mnt/usb/$(OPENBSD_VER)/ && \
	cp $(BUILD_DIR)/SHA256.sig /mnt/usb/$(OPENBSD_VER)/ && \
	cp $(SITE_TGZ) /mnt/usb/$(OPENBSD_VER)/ && \
	# Paquets OpenBSD \
	cp -r $(BUILD_DIR)/packages /mnt/usb/ && \
	# Paquets Python \
	cp -r $(BUILD_DIR)/pip_packages /mnt/usb/ && \
	cp requirements.txt /mnt/usb/ && \
	# ISO bootable \
	cp $(BUILD_DIR)/install$(OPENBSD_VER).iso /mnt/usb/ && \
	# Stats \
	echo "" && \
	echo "=== Clé USB OFFLINE prête ===" && \
	echo "  Chemin: /dev/$(USB_DEV)" && \
	echo "  Taille: $$(df -h /mnt/usb | tail -1 | awk '{print $$2}')" && \
	echo "  Occupé: $$(df -h /mnt/usb | tail -1 | awk '{print $$3}')" && \
	echo "" && \
	echo "Brancher sur le mini PC et booter." && \
	echo "L'installation est 100% automatique SANS internet." && \
	umount /mnt/usb && \
	rmdir /mnt/usb

# ─── Gravure clé USB (mode online, sets uniquement) ───────
usb: site download-iso
	@echo "=== Clé USB (mode online: pkg/pip via internet) ==="
	@echo "ATTENTION: Toutes les données sur $(USB_DEV) seront effacées !"
	@echo "Continuer ? (CTRL+C pour annuler)"
	@read -r _ && \
	dd if=/dev/zero of=/dev/r$(USB_DEV) bs=1m count=10 && \
	fdisk -i $(USB_DEV) && \
	fdisk -a $(USB_DEV) && \
	newfs /dev/r$(USB_DEV)a && \
	mkdir -p /mnt/usb && \
	mount /dev/$(USB_DEV)a /mnt/usb && \
	cp install.conf /mnt/usb/ && \
	mkdir -p /mnt/usb/$(OPENBSD_VER) && \
	cp $(BUILD_DIR)/*.tgz /mnt/usb/$(OPENBSD_VER)/ 2>/dev/null || true && \
	cp $(SITE_TGZ) /mnt/usb/$(OPENBSD_VER)/ && \
	cp install.sh /mnt/usb/ && \
	cp $(BUILD_DIR)/install$(OPENBSD_VER).iso /mnt/usb/ && \
	umount /mnt/usb && \
	echo "=== Clé USB prête (mode online) ==="

# ─── Installation directe (depuis un système déjà booté) ──
install:
	@echo "=== Installation directe PixelOS ==="
	doas sh install.sh

# ─── Stats ────────────────────────────────────────────────
stats:
	@echo "PixelOS Installer - OpenBSD $(OPENBSD_VER)-$(ARCH)"
	@echo "  Site archive: $$(ls -lh $(SITE_TGZ) 2>/dev/null | awk '{print $$5}')"
	@echo "  ISO: $$(ls -lh $(FINAL_ISO) 2>/dev/null | awk '{print $$5}')"
	@echo "  USB device: $(USB_DEV)"
	@echo "  Paquets: $$(ls $(BUILD_DIR)/packages/*.tgz 2>/dev/null | wc -l)"
	@echo "  Paquets Python: $$(ls $(BUILD_DIR)/pip_packages/*.whl 2>/dev/null | wc -l)"
	@echo "  Taille totale build: $$(du -sh $(BUILD_DIR) 2>/dev/null | awk '{print $$1}')"

# ─── Nettoyage ────────────────────────────────────────────
clean:
	rm -rf $(BUILD_DIR)
	rm -f $(SITE_TGZ)
	rm -f $(FINAL_ISO)
	@echo "Nettoyé"
