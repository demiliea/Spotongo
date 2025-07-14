#!/bin/bash

# Script d'installation pour Raspberry Pi Zero 2 W Assistant Vocal
# Auteur: Assistant IA
# Version: 1.0

set -e

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
    exit 1
}

# Vérifier que le script est exécuté en tant que root
if [[ $EUID -ne 0 ]]; then
   error "Ce script doit être exécuté en tant que root (sudo)"
fi

# Variables
PROJECT_DIR="/opt/rpi-assistant"
SERVICE_USER="pi"
BOOT_DIR="/boot"

log "Début de l'installation du Raspberry Pi Assistant..."

# Mise à jour du système
log "Mise à jour du système..."
apt update && apt upgrade -y

# Installation des dépendances système
log "Installation des dépendances système..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    bluetooth \
    bluez \
    bluez-tools \
    pulseaudio \
    pulseaudio-module-bluetooth \
    alsa-utils \
    espeak-ng \
    portaudio19-dev \
    python3-dev \
    gcc \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    dnsmasq \
    hostapd \
    iptables-persistent \
    libbluetooth-dev

# Création des dossiers
log "Création des dossiers..."
mkdir -p $PROJECT_DIR
mkdir -p $PROJECT_DIR/logs
mkdir -p $PROJECT_DIR/temp
chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR

# Installation de Balena WiFi Connect
ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then
    WIFI_CONNECT_URL="https://github.com/balena-os/wifi-connect/releases/download/v4.4.6/wifi-connect-v4.4.6-linux-aarch64.tar.gz"
else
    WIFI_CONNECT_URL="https://github.com/balena-os/wifi-connect/releases/download/v4.4.6/wifi-connect-v4.4.6-linux-armv7hf.tar.gz"
fi

rm -rf /tmp/wifi-connect /tmp/ui
wget -O /tmp/wifi-connect.tar.gz "$WIFI_CONNECT_URL"
tar -xzf /tmp/wifi-connect.tar.gz -C /tmp/
cp /tmp/wifi-connect /usr/local/bin/
chmod +x /usr/local/bin/wifi-connect

# Configuration du service WiFi Connect
cat > /etc/systemd/system/wifi-connect.service << EOF
[Unit]
Description=Balena WiFi Connect
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/wifi-connect --portal-ssid RPi-Assistant --portal-passphrase raspberry
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Installation de Raspotify
log "Installation de Raspotify..."
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh

# Configuration de Raspotify
cat > /etc/default/raspotify << EOF
# Raspotify configuration
DEVICE_NAME="Mon Assistant Pi"
BITRATE="320"
CACHE_SIZE="1G"
DEVICE_TYPE="speaker"
INITIAL_VOLUME="50"
VOLUME_NORMALISATION="true"
NORMALISATION_PREGAIN="0"
AUTOPLAY="true"
EOF

# Configuration du Bluetooth
log "Configuration du Bluetooth..."
# Activation du bluetooth
systemctl enable bluetooth
systemctl start bluetooth

# Configuration de PulseAudio pour le Bluetooth
mkdir -p /home/$SERVICE_USER/.config/pulse
cat > /home/$SERVICE_USER/.config/pulse/default.pa << EOF
#!/usr/bin/pulseaudio -nF
# Load module-bluetooth-policy
load-module module-bluetooth-policy
# Load module-bluetooth-discover
load-module module-bluetooth-discover
# Load the system configuration
.include /etc/pulse/default.pa
EOF

# Configuration pour auto-démarrage de PulseAudio
cat > /home/$SERVICE_USER/.config/pulse/client.conf << EOF
default-sink = bluez_sink
autospawn = yes
EOF

chown -R $SERVICE_USER:$SERVICE_USER /home/$SERVICE_USER/.config

# Configuration de l'environnement Python
log "Configuration de l'environnement Python..."
cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate

# Installation des dépendances Python
pip install --upgrade pip
pip install \
    openai \
    pyaudio \
    requests \
    configparser \
    RPi.GPIO \
    pydub \
    gTTS \
    pygame

pip install git+https://github.com/pybluez/pybluez.git@master

# Copie des fichiers source
log "Copie des fichiers source..."
# Les fichiers seront copiés par le processus d'installation principal

# Création du service systemd
log "Création du service systemd..."
cat > /etc/systemd/system/rpi-assistant.service << EOF
[Unit]
Description=Raspberry Pi Assistant Vocal
After=network.target bluetooth.target pulseaudio.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStartPre=/bin/sleep 10
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/src/assistant.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Script de configuration Bluetooth
mkdir -p $PROJECT_DIR/scripts
cat > $PROJECT_DIR/scripts/setup_bluetooth.sh << 'EOF'
#!/bin/bash
# Script de configuration Bluetooth

SPEAKER_NAME="$1"
if [ -z "$SPEAKER_NAME" ]; then
    echo "Usage: $0 <speaker_name>"
    exit 1
fi

# Rechercher et appairer l'enceinte
bluetoothctl << EOL
agent on
default-agent
scan on
EOL

# Attendre un peu pour la découverte
sleep 10

# Essayer de se connecter
MAC_ADDRESS=$(bluetoothctl devices | grep "$SPEAKER_NAME" | awk '{print $2}')
if [ -n "$MAC_ADDRESS" ]; then
    bluetoothctl << EOL
pair $MAC_ADDRESS
trust $MAC_ADDRESS
connect $MAC_ADDRESS
EOL
    echo "Enceinte $SPEAKER_NAME connectée avec succès"
else
    echo "Enceinte $SPEAKER_NAME non trouvée"
    exit 1
fi
EOF

chmod +x $PROJECT_DIR/scripts/setup_bluetooth.sh

# Configuration des permissions GPIO
log "Configuration des permissions GPIO..."
usermod -a -G gpio $SERVICE_USER

# Configuration des services
log "Configuration des services..."
systemctl daemon-reload
systemctl enable rpi-assistant
systemctl enable raspotify
systemctl enable wifi-connect

# Redémarrage des services
systemctl restart bluetooth

log "Installation terminée avec succès!"
log "Veuillez copier les fichiers de configuration dans $BOOT_DIR et redémarrer le système."
log "Fichiers de configuration requis :"
log "  - config-spotify.txt"
log "  - config-bluetooth.txt"
log "  - config-gpt.txt"
log "  - config-openai.txt"

warn "N'oubliez pas de configurer votre clé API OpenAI dans config-openai.txt"
warn "Redémarrez le système après avoir copié les fichiers de configuration"

exit 0