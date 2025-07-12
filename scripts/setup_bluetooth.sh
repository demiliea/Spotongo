#!/bin/bash

# Script de configuration Bluetooth pour Raspberry Pi Assistant
# Usage: ./setup_bluetooth.sh "Nom de l'enceinte"

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
}

# Vérification des paramètres
if [ $# -eq 0 ]; then
    error "Usage: $0 \"Nom de l'enceinte\""
    error "Exemple: $0 \"JBL Flip 5\""
    exit 1
fi

SPEAKER_NAME="$1"
log "Configuration Bluetooth pour l'enceinte: $SPEAKER_NAME"

# Vérifier que bluetoothctl est disponible
if ! command -v bluetoothctl &> /dev/null; then
    error "bluetoothctl n'est pas installé"
    exit 1
fi

# Fonction pour exécuter des commandes bluetoothctl
run_bluetoothctl() {
    local commands="$1"
    echo -e "$commands" | bluetoothctl
}

# Démarrer le service Bluetooth
log "Démarrage du service Bluetooth..."
sudo systemctl start bluetooth
sudo rfkill unblock bluetooth
sleep 2

# Initialiser Bluetooth
log "Initialisation de Bluetooth..."
run_bluetoothctl "power on\nagent on\ndefault-agent"
sleep 2

# Scanner les appareils
log "Scan des appareils Bluetooth (20 secondes)..."
run_bluetoothctl "scan on"
sleep 20
run_bluetoothctl "scan off"

# Rechercher l'enceinte
log "Recherche de l'enceinte: $SPEAKER_NAME"
DEVICES=$(echo "devices" | bluetoothctl | grep "Device")
MAC_ADDRESS=""

# Chercher l'adresse MAC de l'enceinte
while IFS= read -r line; do
    if [[ "$line" == *"$SPEAKER_NAME"* ]]; then
        MAC_ADDRESS=$(echo "$line" | awk '{print $2}')
        break
    fi
done <<< "$DEVICES"

if [ -z "$MAC_ADDRESS" ]; then
    error "Enceinte '$SPEAKER_NAME' non trouvée"
    error "Appareils disponibles:"
    echo "$DEVICES"
    exit 1
fi

log "Enceinte trouvée: $MAC_ADDRESS"

# Supprimer l'appareil s'il existe déjà
log "Suppression de l'ancien appairage..."
run_bluetoothctl "remove $MAC_ADDRESS" || true
sleep 2

# Appairer l'enceinte
log "Appairage de l'enceinte..."
PAIR_RESULT=$(run_bluetoothctl "pair $MAC_ADDRESS")

if [[ "$PAIR_RESULT" == *"successful"* ]] || [[ "$PAIR_RESULT" == *"already paired"* ]]; then
    log "Appairage réussi"
else
    error "Échec de l'appairage: $PAIR_RESULT"
    exit 1
fi

# Faire confiance à l'enceinte
log "Configuration de la confiance..."
run_bluetoothctl "trust $MAC_ADDRESS"

# Connecter l'enceinte
log "Connexion à l'enceinte..."
CONNECT_RESULT=$(run_bluetoothctl "connect $MAC_ADDRESS")

if [[ "$CONNECT_RESULT" == *"successful"* ]] || [[ "$CONNECT_RESULT" == *"already connected"* ]]; then
    log "Connexion réussie"
else
    warn "Connexion échouée, mais l'appairage est configuré"
fi

# Vérifier la connexion
sleep 3
INFO_RESULT=$(run_bluetoothctl "info $MAC_ADDRESS")

if [[ "$INFO_RESULT" == *"Connected: yes"* ]]; then
    log "✓ Enceinte connectée avec succès"
else
    warn "Enceinte appairée mais non connectée"
fi

# Configuration PulseAudio
log "Configuration PulseAudio..."
sleep 3

# Attendre que PulseAudio détecte l'enceinte
SINK_NAME=""
for i in {1..10}; do
    SINKS=$(pactl list sinks short 2>/dev/null || echo "")
    if [[ "$SINKS" == *"bluez"* ]]; then
        SINK_NAME=$(echo "$SINKS" | grep bluez | head -1 | awk '{print $2}')
        break
    fi
    sleep 2
done

if [ -n "$SINK_NAME" ]; then
    log "Configuration du sink audio: $SINK_NAME"
    pactl set-default-sink "$SINK_NAME"
    log "✓ Sink audio configuré"
else
    warn "Sink Bluetooth non détecté par PulseAudio"
fi

# Test audio
log "Test audio..."
if command -v speaker-test &> /dev/null; then
    timeout 5 speaker-test -t sine -f 1000 -c 1 || true
    log "Test audio terminé"
fi

# Afficher les informations finales
log "Configuration terminée!"
log "Informations de l'enceinte:"
run_bluetoothctl "info $MAC_ADDRESS" | grep -E "(Name|Paired|Connected|Trusted)"

# Sauvegarder les informations dans un fichier
cat > /tmp/bluetooth_config.txt << EOF
# Configuration Bluetooth générée automatiquement
speaker_name=$SPEAKER_NAME
speaker_mac=$MAC_ADDRESS
speaker_sink=$SINK_NAME
configured_at=$(date)
EOF

log "Configuration sauvegardée dans /tmp/bluetooth_config.txt"

# Instructions pour l'utilisateur
log "Instructions:"
log "1. Mettez à jour config-bluetooth.txt avec le nom exact: $SPEAKER_NAME"
log "2. Redémarrez le service: sudo systemctl restart rpi-assistant"
log "3. Vérifiez les logs: sudo journalctl -u rpi-assistant -f"

exit 0