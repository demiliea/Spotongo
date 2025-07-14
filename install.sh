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
    libbluetooth-dev \
    nginx

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
# Redirect all DNS queries to our captive portal
address=/#/192.168.4.1
# Don't read /etc/hosts
no-hosts
# Don't poll /etc/resolv.conf
no-poll
# Cache size
cache-size=300
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

echo "Démarrage de nginx..."
systemctl start nginx

echo "Démarrage de l'API captive portal..."
systemctl start captive-portal-api

# Configuration du NAT pour partager la connexion Ethernet
echo "Configuration du NAT..."
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || true
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT 2>/dev/null || true

# Sauvegarde des règles iptables
iptables-save > /etc/iptables/rules.v4 2>/dev/null || true

echo "Hotspot démarré avec succès - SSID: RPi-Assistant, Mot de passe: raspberry"
echo "Captive portal disponible à l'adresse: http://192.168.4.1"
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

# Configuration de nginx pour le captive portal
cat > /etc/nginx/sites-available/captive-portal << EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    root /var/www/captive-portal;
    index index.html;
    
    # Redirect all requests to captive portal
    location / {
        try_files \$uri \$uri/ /index.html;
    }
    
    # API endpoint for WiFi configuration
    location /api/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# Activer le site captive portal
ln -sf /etc/nginx/sites-available/captive-portal /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Créer le dossier web pour le captive portal
mkdir -p /var/www/captive-portal

# Créer la page web du captive portal
cat > /var/www/captive-portal/index.html << 'EOF'
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuration WiFi - RPi Assistant</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: #555;
            font-weight: 500;
        }
        input[type="text"], input[type="password"], select {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e1e5e9;
            border-radius: 6px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        input[type="text"]:focus, input[type="password"]:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        button:hover {
            transform: translateY(-2px);
        }
        .status {
            margin-top: 1rem;
            padding: 0.75rem;
            border-radius: 6px;
            text-align: center;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Configuration WiFi</h1>
        <p style="text-align: center; color: #666; margin-bottom: 2rem;">
            Connectez votre Raspberry Pi Assistant à votre réseau WiFi
        </p>
        
        <form id="wifiForm">
            <div class="form-group">
                <label for="ssid">Nom du réseau (SSID):</label>
                <input type="text" id="ssid" name="ssid" required>
            </div>
            
            <div class="form-group">
                <label for="password">Mot de passe WiFi:</label>
                <input type="password" id="password" name="password">
            </div>
            
            <button type="submit">Se connecter</button>
        </form>
        
        <div id="status" class="status" style="display: none;"></div>
    </div>

    <script>
        document.getElementById('wifiForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const ssid = document.getElementById('ssid').value;
            const password = document.getElementById('password').value;
            const status = document.getElementById('status');
            
            // Show loading
            status.style.display = 'block';
            status.className = 'status';
            status.textContent = 'Configuration en cours...';
            
            // Send configuration to API
            fetch('/api/configure', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ ssid: ssid, password: password })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    status.className = 'status success';
                    status.textContent = 'Configuration réussie! Redémarrage en cours...';
                } else {
                    status.className = 'status error';
                    status.textContent = 'Erreur: ' + (data.error || 'Configuration échouée');
                }
            })
            .catch(error => {
                status.className = 'status error';
                status.textContent = 'Erreur de connexion au serveur';
            });
        });
    </script>
</body>
</html>
EOF

# Créer le serveur API Python pour la configuration WiFi
cat > $PROJECT_DIR/captive_portal_api.py << 'EOF'
#!/usr/bin/env python3
import json
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

class CaptivePortalHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/configure':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                ssid = data.get('ssid', '').strip()
                password = data.get('password', '').strip()
                
                if not ssid:
                    self.send_json_response({'success': False, 'error': 'SSID requis'})
                    return
                
                # Configure WiFi
                success = self.configure_wifi(ssid, password)
                
                if success:
                    self.send_json_response({'success': True})
                    # Restart networking after a delay
                    threading.Thread(target=self.restart_networking).start()
                else:
                    self.send_json_response({'success': False, 'error': 'Erreur de configuration'})
                    
            except json.JSONDecodeError:
                self.send_json_response({'success': False, 'error': 'JSON invalide'})
            except Exception as e:
                self.send_json_response({'success': False, 'error': str(e)})
    
    def configure_wifi(self, ssid, password):
        try:
            # Create wpa_supplicant configuration
            config = f"""
country=GB
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
            
            with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
                f.write(config)
            
            return True
        except Exception as e:
            print(f"Error configuring WiFi: {e}")
            return False
    
    def restart_networking(self):
        time.sleep(2)
        try:
            # Stop hotspot
            subprocess.run(['systemctl', 'stop', 'rpi-hotspot'], check=False)
            subprocess.run(['systemctl', 'stop', 'hostapd'], check=False)
            subprocess.run(['systemctl', 'stop', 'dnsmasq'], check=False)
            
            # Reset interface to managed mode
            subprocess.run(['ip', 'link', 'set', 'wlan0', 'down'], check=False)
            subprocess.run(['iw', 'dev', 'wlan0', 'set', 'type', 'managed'], check=False)
            subprocess.run(['ip', 'link', 'set', 'wlan0', 'up'], check=False)
            
            # Start wpa_supplicant
            subprocess.run(['systemctl', 'restart', 'wpa_supplicant'], check=False)
            
            print("Network configuration applied")
        except Exception as e:
            print(f"Error restarting networking: {e}")
    
    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8080), CaptivePortalHandler)
    print("Captive portal API server started on port 8080")
    server.serve_forever()
EOF

chmod +x $PROJECT_DIR/captive_portal_api.py

# Service systemd pour l'API du captive portal
cat > /etc/systemd/system/captive-portal-api.service << EOF
[Unit]
Description=Captive Portal API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/python3 $PROJECT_DIR/captive_portal_api.py
Restart=always
RestartSec=10

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

# Unmask hostapd service (often masked by default)
systemctl unmask hostapd

systemctl enable rpi-assistant
systemctl enable raspotify
systemctl enable hostapd
systemctl enable dnsmasq
systemctl enable unblock-rfkill
systemctl enable rpi-hotspot
systemctl enable captive-portal-api
systemctl enable nginx

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