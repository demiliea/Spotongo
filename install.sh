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

# Configuration du point d'accès WiFi avec hostapd et dnsmasq
log "Configuration du point d'accès WiFi..."

# Configuration de hostapd
cat > /etc/hostapd/hostapd.conf << EOF
interface=wlan0
driver=nl80211
ssid=RPi-Assistant
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=raspberry
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Configuration par défaut de hostapd
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

# Configuration de dnsmasq pour le captive portal
cat > /etc/dnsmasq.conf << EOF
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=wlan
address=/#/192.168.4.1
EOF

# Script de démarrage du hotspot
cat > $PROJECT_DIR/scripts/start_hotspot.sh << 'EOF'
#!/bin/bash
set -e

echo "Démarrage du hotspot WiFi..."

# Ensure WiFi is unblocked and in AP mode (with retries)
for i in {1..3}; do
    echo "Tentative $i/3 de déblocage RF-kill..."
    rfkill unblock all
    sleep 2
    
    # Check if unblocked
    if ! rfkill list | grep -q "Soft blocked: yes"; then
        echo "RF-kill débloqué avec succès"
        break
    fi
    
    if [ $i -eq 3 ]; then
        echo "Erreur: Impossible de débloquer RF-kill après 3 tentatives"
        exit 1
    fi
done

# Configuration de l'interface WiFi (ensure it's in AP mode)
echo "Configuration de l'interface wlan0..."
ip link set wlan0 down
iw dev wlan0 set type __ap
ip link set wlan0 up

# Remove existing IP if present, then add new one
ip addr del 192.168.4.1/24 dev wlan0 2>/dev/null || true
ip addr add 192.168.4.1/24 dev wlan0

# Wait a moment for interface to be ready
sleep 3

# Démarrage des services
echo "Démarrage de hostapd..."
systemctl start hostapd

echo "Démarrage de dnsmasq..."
systemctl start dnsmasq

# Configuration du NAT pour partager la connexion Ethernet
echo "Configuration du NAT..."
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT 2>/dev/null || true

# Sauvegarde des règles iptables
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true

echo "Hotspot démarré avec succès - SSID: RPi-Assistant, Mot de passe: raspberry"
EOF

chmod +x $PROJECT_DIR/scripts/start_hotspot.sh

# Script d'arrêt du hotspot
cat > $PROJECT_DIR/scripts/stop_hotspot.sh << 'EOF'
#!/bin/bash
# Arrêt des services
systemctl stop hostapd
systemctl stop dnsmasq

# Remise en mode managed
ip link set wlan0 down
iw dev wlan0 set type managed
ip link set wlan0 up

# Suppression de la configuration IP
ip addr del 192.168.4.1/24 dev wlan0 2>/dev/null || true

# Nettoyage des règles iptables
iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
iptables -D FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i wlan0 -o eth0 -j ACCEPT 2>/dev/null || true

echo "Hotspot arrêté"
EOF

chmod +x $PROJECT_DIR/scripts/stop_hotspot.sh

# Service systemd pour débloquer rfkill au démarrage
cat > /etc/systemd/system/unblock-rfkill.service << EOF
[Unit]
Description=Unblock WiFi rfkill and prepare interface
Before=hostapd.service
Before=rpi-hotspot.service
After=sys-subsystem-net-devices-wlan0.device
Wants=sys-subsystem-net-devices-wlan0.device

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'sleep 5 && rfkill unblock all && sleep 3 && ip link set wlan0 down && iw dev wlan0 set type __ap && ip link set wlan0 up'
RemainAfterExit=yes
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Service systemd pour le hotspot
cat > /etc/systemd/system/rpi-hotspot.service << EOF
[Unit]
Description=Raspberry Pi Hotspot
After=network.target
After=unblock-rfkill.service
Wants=unblock-rfkill.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$PROJECT_DIR/scripts/start_hotspot.sh
ExecStop=$PROJECT_DIR/scripts/stop_hotspot.sh
User=root

[Install]
WantedBy=multi-user.target
EOF

# Activation du forwarding IP
echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

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

# Unmask hostapd service (often masked by default)
systemctl unmask hostapd

systemctl enable rpi-assistant
systemctl enable raspotify
systemctl enable hostapd
systemctl enable dnsmasq
systemctl enable unblock-rfkill
systemctl enable rpi-hotspot

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