#!/bin/bash

# Script de déploiement pour Raspberry Pi Assistant Vocal
# Usage: ./deploy.sh [IP_DU_RASPBERRY_PI] [UTILISATEUR]

set -e

# Configuration par défaut
DEFAULT_USER="pi"
DEFAULT_IP=""
PROJECT_DIR="/opt/rpi-assistant"

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonction pour afficher des messages colorés
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Vérification des paramètres
if [ $# -eq 0 ]; then
    error "Usage: $0 <IP_DU_RASPBERRY_PI> [UTILISATEUR]"
    error "Exemple: $0 192.168.1.100 pi"
    exit 1
fi

RASPBERRY_IP="$1"
USER="${2:-$DEFAULT_USER}"

log "Déploiement sur Raspberry Pi $RASPBERRY_IP avec l'utilisateur $USER"

# Vérifier la connectivité
log "Vérification de la connectivité..."
if ! ping -c 1 "$RASPBERRY_IP" &> /dev/null; then
    error "Impossible de joindre le Raspberry Pi à l'adresse $RASPBERRY_IP"
    exit 1
fi

# Vérifier la connexion SSH
log "Vérification de la connexion SSH..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$USER@$RASPBERRY_IP" exit &> /dev/null; then
    error "Impossible de se connecter en SSH à $USER@$RASPBERRY_IP"
    error "Vérifiez que:"
    error "1. SSH est activé sur le Raspberry Pi"
    error "2. Les clés SSH sont configurées ou utilisez ssh-copy-id"
    exit 1
fi

# Créer l'archive du projet
log "Création de l'archive du projet..."
tar -czf rpi-assistant.tar.gz \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.tar.gz' \
    --exclude='venv' \
    --exclude='.DS_Store' \
    src/ config/ systemd/ scripts/ install.sh requirements.txt README.md

# Copier l'archive sur le Raspberry Pi
log "Copie des fichiers sur le Raspberry Pi..."
scp rpi-assistant.tar.gz "$USER@$RASPBERRY_IP:/tmp/"

# Déploiement et installation
log "Déploiement et installation sur le Raspberry Pi..."
ssh "$USER@$RASPBERRY_PI" << 'EOF'
set -e

# Créer le répertoire de destination
sudo mkdir -p /opt/rpi-assistant
cd /opt/rpi-assistant

# Extraire l'archive
sudo tar -xzf /tmp/rpi-assistant.tar.gz

# Changer les permissions
sudo chown -R pi:pi /opt/rpi-assistant

# Rendre les scripts exécutables
sudo chmod +x install.sh scripts/*.sh

# Exécuter l'installation
sudo ./install.sh

# Nettoyer l'archive temporaire
rm -f /tmp/rpi-assistant.tar.gz

echo "Déploiement terminé!"
EOF

# Nettoyer l'archive locale
rm -f rpi-assistant.tar.gz

# Configuration post-installation
log "Configuration post-installation..."
log "Connexion au Raspberry Pi pour la configuration finale..."

ssh "$USER@$RASPBERRY_PI" << 'EOF'
echo "=== Configuration finale ==="

# Vérifier les services
echo "Statut des services:"
sudo systemctl status rpi-assistant --no-pager || true
sudo systemctl status raspotify --no-pager || true
sudo systemctl status bluetooth --no-pager || true

# Afficher les logs récents
echo -e "\n=== Logs récents ==="
sudo journalctl -u rpi-assistant -n 10 --no-pager || true

# Instructions finales
echo -e "\n=== Instructions finales ==="
echo "1. Configurez les fichiers dans /boot:"
echo "   - config-spotify.txt"
echo "   - config-bluetooth.txt"
echo "   - config-gpt.txt"
echo "   - config-openai.txt"
echo ""
echo "2. Redémarrez le système:"
echo "   sudo reboot"
echo ""
echo "3. Vérifiez les logs après redémarrage:"
echo "   sudo journalctl -u rpi-assistant -f"
echo ""
echo "4. Configurez l'enceinte Bluetooth:"
echo "   sudo /opt/rpi-assistant/scripts/setup_bluetooth.sh \"Nom de votre enceinte\""
EOF

log "Déploiement terminé avec succès!"
log "Instructions finales:"
log "1. Connectez-vous au Raspberry Pi: ssh $USER@$RASPBERRY_IP"
log "2. Modifiez les fichiers de configuration dans /boot"
log "3. Redémarrez le système: sudo reboot"
log "4. Configurez l'enceinte Bluetooth avec le script fourni"

warn "N'oubliez pas de configurer votre clé API OpenAI dans config-openai.txt"

exit 0