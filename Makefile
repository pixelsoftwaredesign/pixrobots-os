# PixelOS Agricol — RootFS Image Generator
#
# Package l'intégralité du dépôt dans un système de fichiers
# en lecture seule (SquashFS ou ISO9660) prêt pour déploiement
# industriel sur les robots de la flotte.
#
# Targets :
#   all          — Détecte l'outil dispo et génère l'image appropriée
#   squashfs     — Génère une image SquashFS (.squashfs)
#   iso          — Génère une image ISO9660 (.iso)
#   hybrid       — Génère les deux formats
#   install      — Extrait l'image sur la cible (destinpath)
#   info         — Affiche les métadonnées de l'image
#   clean        — Supprime les artefacts de build
#
# Usage :
#   make all                         # auto-détection
#   make squashfs                    # SquashFS uniquement
#   make iso                         # ISO uniquement
#   make DESTDIR=/mnt/rootfs install # déploiement
#
# Variables :
#   IMAGE_NAME   — Nom de base (défaut: pixelos-agricol)
#   COMPRESSION  — Algorithme SquashFS (défaut: zstd)
#   DESTDIR      — Répertoire de déploiement (défaut: /opt/pixelos)

IMAGE_NAME ?= pixelos-agricol
COMPRESSION ?= zstd
DESTDIR    ?= /opt/pixelos

BUILD_DIR  ?= build
EXCLUDE    ?= .git __pycache__ *.pyc .DS_Store Thumbs.db *.egg-info \
             .gitignore .gitattributes .github

SQUASHFS_IMAGE := $(BUILD_DIR)/$(IMAGE_NAME).squashfs
ISO_IMAGE      := $(BUILD_DIR)/$(IMAGE_NAME).iso

# Détection des outils disponibles
MKSQUASHFS   := $(shell command -v mksquashfs 2>/dev/null)
GENISOIMAGE  := $(shell command -v genisoimage 2>/dev/null)
XORRISO      := $(shell command -v xorriso 2>/dev/null)
MKHYBRID     := $(shell command -v mkhybrid 2>/dev/null)

.PHONY: all squashfs iso hybrid install info clean

all:
	@echo "=== PixelOS RootFS Builder ==="
	@echo "Detection des outils disponibles..."
	@if [ -n "$(MKSQUASHFS)" ]; then \
		echo "  + mksquashfs: $(MKSQUASHFS)"; \
		$(MAKE) squashfs; \
	elif [ -n "$(GENISOIMAGE)" ]; then \
		echo "  + genisoimage: $(GENISOIMAGE)"; \
		$(MAKE) iso; \
	elif [ -n "$(XORRISO)" ]; then \
		echo "  + xorriso: $(XORRISO)"; \
		$(MAKE) iso; \
	elif [ -n "$(MKHYBRID)" ]; then \
		echo "  + mkhybrid: $(MKHYBRID)"; \
		$(MAKE) iso; \
	else \
		echo "Aucun outil de generation d'image trouve."; \
		echo "Installez squashfs-tools (mksquashfs) ou cdrtools (genisoimage)."; \
		exit 1; \
	fi

# ─── SquashFS ──────────────────────────────────────────────
# Lecture seule, compression zstd, compatible Linux overlayfs

squashfs: $(SQUASHFS_IMAGE)

$(SQUASHFS_IMAGE): $(BUILD_DIR)
	@echo "=== Construction SquashFS ==="
	@echo "  Source:    $(CURDIR)"
	@echo "  Cible:     $@"
	@echo "  Compress:  $(COMPRESSION)"
	@EXCLUDE_OPTS=""; \
	for e in $(EXCLUDE); do \
		EXCLUDE_OPTS="$$EXCLUDE_OPTS -e $$e"; \
	done; \
	$(MKSQUASHFS) "$(CURDIR)" "$@" \
		$$EXCLUDE_OPTS \
		-comp $(COMPRESSION) \
		-b 1048576 \
		-no-recovery \
		-quiet
	@echo "  Taille: $$(du -sh $@ | cut -f1)"
	@echo "=== SquashFS creee: $@ ==="

# ─── ISO9660 ───────────────────────────────────────────────
# Bootable optionnelle, compatible UEFI+Legacy

iso: $(ISO_IMAGE)

$(ISO_IMAGE): $(BUILD_DIR)
	@echo "=== Construction ISO9660 ==="
	@echo "  Source: $(CURDIR)"
	@echo "  Cible:  $@"
	@if [ -n "$(GENISOIMAGE)" ]; then \
		genisoimage -o "$@" \
			-l -J -R -L -v -d -D -N \
			-A "PixelOS Agricol RootFS" \
			-V "PIXELOS_ROOTFS" \
			-quiet \
			$(foreach e,$(EXCLUDE),-m "$e") \
			"$(CURDIR)"; \
	elif [ -n "$(XORRISO)" ]; then \
		xorriso -as mkisofs -o "$@" \
			-l -J -R -L -V "PIXELOS_ROOTFS" \
			$(foreach e,$(EXCLUDE),-m "$e") \
			"$(CURDIR)"; \
	elif [ -n "$(MKHYBRID)" ]; then \
		mkhybrid -o "$@" \
			-l -J -R -L -v -d -D -N \
			-A "PixelOS Agricol RootFS" \
			-V "PIXELOS_ROOTFS" \
			$(foreach e,$(EXCLUDE),-m "$e") \
			"$(CURDIR)"; \
	else \
		echo "Aucun outil ISO trouve (genisoimage, xorriso, mkhybrid)"; \
		exit 1; \
	fi
	@echo "  Taille: $$(du -sh $@ | cut -f1)"
	@echo "=== ISO creee: $@ ==="

# ─── Hybride ───────────────────────────────────────────────

hybrid: squashfs iso
	@echo "=== Images generees ==="
	@ls -lh $(SQUASHFS_IMAGE) $(ISO_IMAGE)

# ─── Installation / Deploiement ───────────────────────────

install: $(SQUASHFS_IMAGE)
	@echo "=== Deploiement RootFS ==="
	@if [ ! -d "$(DESTDIR)" ]; then \
		echo "Creation de $(DESTDIR)..."; \
		mkdir -p "$(DESTDIR)"; \
	fi
	@unsquashfs -f -d "$(DESTDIR)" "$(SQUASHFS_IMAGE)" >/dev/null 2>&1 && \
		echo "  Extrait dans $(DESTDIR)" || \
		echo "  Erreur d'extraction. unsquashfs est-il installe ?"
	@echo "=== Termine ==="

# ─── Informations ──────────────────────────────────────────

info:
	@echo "=== PixelOS RootFS ==="
	@echo "  Image:       $(IMAGE_NAME)"
	@echo "  Compression: $(COMPRESSION)"
	@echo "  Excludes:    $(EXCLUDE)"
	@echo "  Build dir:   $(BUILD_DIR)"
	@echo "  Dest deploi: $(DESTDIR)"
	@echo ""
	@echo "Outils detectes:"
	@for tool in mksquashfs genisoimage xorriso mkhybrid unsquashfs; do \
		p=$$(command -v $$tool 2>/dev/null); \
		if [ -n "$$p" ]; then \
			echo "  + $$tool: $$p"; \
		else \
			echo "  - $$tool: introuvable"; \
		fi; \
	done
	@echo ""
	@echo "Arborescence source:"
	@du -sh --exclude=.git 2>/dev/null || du -sh
	@echo ""
	@echo "Targets disponibles:"
	@echo "  make all        — Auto-detect + build"
	@echo "  make squashfs   — Image SquashFS"
	@echo "  make iso        — Image ISO9660"
	@echo "  make hybrid     — Les deux formats"
	@echo "  make DESTDIR=... install — Deploiement"

# ─── Clean ─────────────────────────────────────────────────

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)
	@echo "Nettoye: $(BUILD_DIR)"
