# Résumé du projet : Raspberry Pi Zero 2 W Assistant Vocal

## Vue d'ensemble

Ce projet transforme un Raspberry Pi Zero 2 W en un assistant vocal intelligent avec les fonctionnalités suivantes :

- **Assistant vocal ChatGPT** : Activation par bouton GPIO, transcription Whisper, réponses GPT-4o
- **Spotify Connect** : Contrôle depuis n'importe quel appareil
- **Enceinte Bluetooth** : Connexion automatique et diffusion audio
- **WiFi Connect** : Configuration WiFi via captive portal
- **Configuration simple** : Fichiers texte dans /boot
- **Fonctionnement headless** : Aucun écran requis

## Architecture technique

### Composants principaux

1. **ConfigManager** (`src/config_manager.py`)
   - Lecture des fichiers de configuration depuis /boot
   - Gestion des valeurs par défaut
   - Validation des configurations

2. **BluetoothManager** (`src/bluetooth_manager.py`)
   - Initialisation et gestion Bluetooth
   - Connexion automatique à l'enceinte
   - Surveillance et reconnexion

3. **AudioManager** (`src/audio_utils.py`)
   - Enregistrement audio depuis microphone USB
   - Synthèse vocale (espeak-ng + gTTS)
   - Lecture audio via Bluetooth

4. **VoiceAssistant** (`src/assistant.py`)
   - Gestion GPIO pour le bouton
   - Intégration OpenAI (Whisper + GPT)
   - Orchestration des composants

### Services système

- **rpi-assistant.service** : Service principal systemd
- **raspotify** : Service Spotify Connect
- **wifi-connect** : Service WiFi captive portal
- **bluetooth** : Service Bluetooth système

## Installation

### Prérequis matériel

- Raspberry Pi Zero 2 W
- Carte microSD 16Go+ (classe 10)
- Alimentation 5V 2.5A
- Microphone USB
- Enceinte Bluetooth
- Bouton poussoir + résistance
- Câbles de connexion

### Installation rapide

```bash
# 1. Préparer la carte SD
# Flasher Raspberry Pi OS Lite
# Activer SSH : touch /boot/ssh
# Copier les fichiers config : cp config/*.txt /boot/

# 2. Première connexion WiFi
# Se connecter au hotspot "RPi-Assistant" (password: raspberry)
# Configurer WiFi via http://192.168.4.1

# 3. Installation automatique
ssh pi@[IP_DU_PI]
sudo wget -O /tmp/install.sh https://raw.githubusercontent.com/votre-repo/rpi-assistant/main/install.sh
sudo chmod +x /tmp/install.sh
sudo /tmp/install.sh

# 4. Configuration finale
# Modifier /boot/config-*.txt avec vos paramètres
# Redémarrer : sudo reboot
```

## Configuration

### Fichiers de configuration dans /boot

**config-spotify.txt** : Configuration Spotify Connect
```ini
device_name=Mon Assistant Pi
bitrate=320
initial_volume=50
```

**config-bluetooth.txt** : Configuration Bluetooth
```ini
speaker_name=Mon Enceinte Bluetooth
auto_connect=true
connection_timeout=30
```

**config-gpt.txt** : Configuration assistant vocal
```ini
enabled=true
gpio_pin=17
recording_duration=10
```

**config-openai.txt** : Configuration OpenAI
```ini
api_key=sk-votre-clé-api-ici
model=gpt-4o
whisper_model=whisper-1
max_tokens=150
temperature=0.7
```

## Utilisation

### Workflow de l'assistant vocal

1. **Activation** : Appui sur bouton GPIO17
2. **Enregistrement** : 10 secondes d'audio (configurable)
3. **Transcription** : Whisper d'OpenAI
4. **Génération** : Réponse GPT-4o
5. **Synthèse** : TTS via espeak-ng
6. **Diffusion** : Audio via enceinte Bluetooth

### Commandes utiles

```bash
# Vérifier les services
sudo systemctl status rpi-assistant
sudo systemctl status raspotify
sudo systemctl status bluetooth

# Consulter les logs
sudo journalctl -u rpi-assistant -f

# Configurer l'enceinte Bluetooth
sudo /opt/rpi-assistant/scripts/setup_bluetooth.sh "Nom Enceinte"

# Tester le système
python3 test_system.py
```

## Déploiement

### Déploiement distant

```bash
# Déployer sur un Raspberry Pi distant
./deploy.sh 192.168.1.100 pi
```

### Structure des fichiers

```
rpi-assistant/
├── README.md                 # Documentation complète
├── PROJECT_SUMMARY.md       # Ce fichier
├── LICENSE                  # Licence MIT
├── requirements.txt         # Dépendances Python
├── install.sh              # Installation automatique
├── deploy.sh               # Déploiement distant
├── test_system.py          # Tests système
├── src/
│   ├── config_manager.py   # Gestionnaire configuration
│   ├── bluetooth_manager.py # Gestionnaire Bluetooth
│   ├── audio_utils.py      # Utilitaires audio
│   └── assistant.py        # Assistant principal
├── config/
│   ├── config-spotify.txt  # Config Spotify
│   ├── config-bluetooth.txt # Config Bluetooth
│   ├── config-gpt.txt      # Config assistant
│   └── config-openai.txt   # Config OpenAI
├── systemd/
│   └── rpi-assistant.service # Service systemd
└── scripts/
    └── setup_bluetooth.sh  # Setup Bluetooth
```

## Optimisations

### Performance

- Utilisation d'espeak-ng pour TTS rapide
- Cache intelligent des fichiers audio
- Gestion mémoire optimisée (512Mo max)
- Surveillance santé système

### Robustesse

- Reconnexion automatique Bluetooth
- Surveillance réseau
- Gestion d'erreurs complète
- Redémarrage automatique des services

### Sécurité

- Permissions système restrictives
- Validation des configurations
- Logging sécurisé
- Limitation des ressources

## Tests et validation

### Tests automatiques

```bash
# Tests complets
python3 test_system.py

# Tests spécifiques
python3 -m src.config_manager
python3 -m src.audio_utils
python3 -m src.bluetooth_manager
```

### Validation manuelle

1. **Configuration** : Vérification des fichiers /boot
2. **Bluetooth** : Connexion enceinte
3. **Audio** : Enregistrement et lecture
4. **OpenAI** : Transcription et génération
5. **GPIO** : Fonctionnement du bouton
6. **Spotify** : Visibilité du device

## Dépannage

### Problèmes courants

1. **Enceinte Bluetooth** : Vérifier nom exact dans config
2. **OpenAI API** : Vérifier clé API valide
3. **Audio** : Vérifier micro USB et PulseAudio
4. **GPIO** : Vérifier câblage bouton
5. **Spotify** : Redémarrer service raspotify

### Logs utiles

- `/opt/rpi-assistant/logs/assistant.log`
- `sudo journalctl -u rpi-assistant -f`
- `sudo journalctl -u raspotify -f`
- `sudo journalctl -u bluetooth -f`

## Évolutions possibles

### Fonctionnalités avancées

- Détection vocale automatique (VAD)
- Commandes locales sans API
- Interface web de configuration
- Intégration domotique
- Support multi-langues

### Améliorations matérielles

- Matrice de microphones
- LED d'état
- Écran OLED optionnel
- Alimentation par batterie
- Boîtier 3D

## Ressources

### Documentation

- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [OpenAI API](https://platform.openai.com/docs)
- [Raspotify](https://github.com/dtcooper/raspotify)
- [Balena WiFi Connect](https://github.com/balena-os/wifi-connect)

### Communauté

- Issues GitHub pour bug reports
- Pull requests pour contributions
- Wiki pour documentation additionnelle
- Forum pour support utilisateur

## Licence

MIT License - Utilisation libre pour projets personnels et commerciaux.

---

**Note** : Ce projet est conçu pour être éducatif et facilement extensible. Toutes les contributions sont les bienvenues !