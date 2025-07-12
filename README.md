# Raspberry Pi Zero 2 W - Assistant Vocal & Spotify Connect

## Description

Ce projet transforme un Raspberry Pi Zero 2 W en un assistant vocal intelligent avec les fonctionnalités suivantes :

- **Connexion WiFi facile** : Captive portal automatique au premier démarrage via Balena WiFi Connect
- **Spotify Connect** : Contrôle depuis n'importe quel appareil Spotify via raspotify
- **Enceinte Bluetooth** : Diffusion audio automatique vers une enceinte appairée
- **Assistant vocal ChatGPT** : Activation par bouton physique, transcription Whisper, réponse GPT-4o
- **Configuration simple** : Fichiers texte dans la partition `/boot`
- **Fonctionnement headless** : Aucun écran ni clavier requis

## Prérequis matériel

- Raspberry Pi Zero 2 W
- Carte microSD (16 Go minimum, classe 10 recommandée)
- Alimentation micro USB (5V 2.5A minimum)
- Micro USB ou carte son USB avec microphone
- Bouton poussoir + résistance (connecté au GPIO17 par défaut)
- Enceinte Bluetooth
- Câbles de connexion pour le bouton

### Schéma de câblage du bouton

```
GPIO17 (Pin 11) ----[Bouton]---- GND (Pin 6)
                         |
                    [Résistance 10kΩ] (optionnelle, pull-up interne activé)
                         |
                       3.3V (Pin 1)
```

## Installation rapide

### 1. Préparation de la carte SD

```bash
# Flasher Raspberry Pi OS Lite sur la carte microSD
# Utiliser Raspberry Pi Imager ou dd

# Activer SSH
touch /boot/ssh

# Copier les fichiers de configuration
cp config/*.txt /boot/
```

### 2. Premier démarrage et connexion WiFi

1. Insérer la carte dans le Raspberry Pi et démarrer
2. Se connecter au hotspot WiFi "RPi-Assistant" (mot de passe: `raspberry`)
3. Naviguer vers http://192.168.4.1 pour configurer le WiFi
4. Le Pi redémarre et se connecte automatiquement

### 3. Installation automatique

```bash
# Se connecter en SSH
ssh pi@[adresse-ip-du-pi]

# Télécharger et exécuter l'installation
sudo wget -O /tmp/install.sh https://raw.githubusercontent.com/votre-repo/rpi-assistant/main/install.sh
sudo chmod +x /tmp/install.sh
sudo /tmp/install.sh
```

### 4. Configuration manuelle (alternative)

Si vous préférez installer manuellement ou personnaliser l'installation :

```bash
# Cloner le projet
git clone https://github.com/votre-repo/rpi-assistant.git
cd rpi-assistant

# Exécuter l'installation
sudo ./install.sh
```

## Configuration

### Fichiers de configuration dans `/boot`

#### `config-spotify.txt`
```
device_name=Mon Assistant Pi
bitrate=320
```

#### `config-bluetooth.txt`
```
speaker_name=Mon Enceinte Bluetooth
auto_connect=true
```

#### `config-gpt.txt`
```
enabled=true
gpio_pin=17
recording_duration=10
```

#### `config-openai.txt`
```
api_key=sk-votre-clé-openai-ici
model=gpt-4o
whisper_model=whisper-1
```

## Utilisation

### Première connexion WiFi
1. Au premier démarrage, le Pi créera un hotspot WiFi nommé "RPi-Assistant"
2. Connectez-vous avec le mot de passe : `raspberry`
3. Ouvrez un navigateur et allez à `http://192.168.4.1`
4. Sélectionnez votre réseau WiFi et entrez le mot de passe
5. Le Pi redémarrera automatiquement connecté à votre réseau

### Spotify Connect
1. Ouvrez Spotify sur votre téléphone/ordinateur
2. Sélectionnez "Mon Assistant Pi" dans les appareils disponibles
3. La musique sera diffusée via l'enceinte Bluetooth

### Assistant vocal
1. Appuyez sur le bouton connecté au GPIO17
2. Parlez pendant 10 secondes maximum
3. L'assistant transcrit votre question via Whisper
4. ChatGPT génère une réponse
5. La réponse est lue via TTS sur l'enceinte Bluetooth

### Logs et dépannage
```bash
# Vérifier les services
sudo systemctl status rpi-assistant
sudo systemctl status raspotify
sudo systemctl status wifi-connect

# Consulter les logs
sudo journalctl -u rpi-assistant -f
sudo journalctl -u raspotify -f
```

## Structure du projet

```
rpi-assistant/
├── README.md
├── install.sh
├── src/
│   ├── assistant.py
│   ├── bluetooth_manager.py
│   ├── config_manager.py
│   └── audio_utils.py
├── config/
│   ├── config-spotify.txt
│   ├── config-bluetooth.txt
│   ├── config-gpt.txt
│   └── config-openai.txt
├── systemd/
│   └── rpi-assistant.service
└── scripts/
    └── setup_bluetooth.sh
```

## Tests et validation

### Test automatique du système

Un script de test complet est fourni pour valider l'installation :

```bash
# Exécuter les tests système
python3 test_system.py

# Tests spécifiques
python3 -m src.config_manager  # Test du gestionnaire de config
python3 -m src.audio_utils     # Test du système audio
python3 -m src.bluetooth_manager  # Test Bluetooth
```

### Débogage

#### Commandes de diagnostic

```bash
# Vérifier les services
sudo systemctl status rpi-assistant
sudo systemctl status raspotify
sudo systemctl status bluetooth

# Consulter les logs
sudo journalctl -u rpi-assistant -f
sudo journalctl -u raspotify -f
sudo journalctl -u bluetooth -f

# Vérifier l'audio
pactl list sinks short
pactl list sources short
aplay -l
arecord -l

# Vérifier Bluetooth
bluetoothctl devices
bluetoothctl show
```

#### Logs détaillés

```bash
# Activer les logs détaillés
sudo systemctl edit rpi-assistant
# Ajouter:
# [Service]
# Environment=PYTHONUNBUFFERED=1
# StandardOutput=journal
# StandardError=journal

# Redémarrer le service
sudo systemctl restart rpi-assistant
```

## Dépannage

### Problèmes courants

**L'enceinte Bluetooth ne se connecte pas :**
- Vérifiez que le nom dans `config-bluetooth.txt` correspond exactement
- Assurez-vous que l'enceinte est en mode appairage
- Utilisez le script de configuration : `sudo /opt/rpi-assistant/scripts/setup_bluetooth.sh "Nom Enceinte"`
- Redémarrez le service : `sudo systemctl restart rpi-assistant`

**L'assistant vocal ne répond pas :**
- Vérifiez votre clé API OpenAI dans `config-openai.txt`
- Vérifiez que le bouton est bien connecté au GPIO configuré
- Testez le bouton : `gpio readall` (vérifiez l'état du GPIO17)
- Consultez les logs : `sudo journalctl -u rpi-assistant -f`

**Spotify Connect ne fonctionne pas :**
- Vérifiez que `raspotify` est en cours d'exécution
- Redémarrez le service : `sudo systemctl restart raspotify`
- Vérifiez la configuration : `sudo cat /etc/default/raspotify`

**Problèmes audio :**
- Vérifiez les périphériques : `aplay -l` et `arecord -l`
- Testez PulseAudio : `pactl info`
- Redémarrez PulseAudio : `pulseaudio --kill && pulseaudio --start`

**WiFi Connect ne fonctionne pas :**
- Vérifiez le service : `sudo systemctl status wifi-connect`
- Redémarrez le service : `sudo systemctl restart wifi-connect`
- Vérifiez les interfaces réseau : `ip addr show`

### Récupération d'erreurs

```bash
# Réinitialiser complètement le système
sudo systemctl stop rpi-assistant
sudo systemctl stop raspotify
sudo systemctl restart bluetooth
sudo systemctl restart pulseaudio
sudo systemctl start raspotify
sudo systemctl start rpi-assistant

# Nettoyer les fichiers temporaires
sudo rm -rf /tmp/rpi-assistant-audio/*
sudo rm -rf /opt/rpi-assistant/logs/*

# Reconfigurer Bluetooth
sudo /opt/rpi-assistant/scripts/setup_bluetooth.sh "Nom de votre enceinte"
```

## Maintenance

### Mise à jour du système

```bash
# Sauvegarder la configuration
sudo cp -r /boot/config-*.txt /opt/rpi-assistant/backup/

# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Redémarrer si nécessaire
sudo reboot
```

### Surveillance

```bash
# Surveiller les performances
htop
iotop
sudo systemctl status rpi-assistant

# Surveiller l'espace disque
df -h
sudo du -sh /opt/rpi-assistant/
sudo du -sh /tmp/rpi-assistant-audio/
```

## Optimisations

### Performance

- Utilisez une carte SD rapide (classe 10 ou U3)
- Configurez un swap file si nécessaire
- Limitez les services inutiles
- Utilisez `espeak-ng` plutôt que `gTTS` pour des réponses plus rapides

### Batterie (optionnel)

- Configurez la gestion d'énergie
- Utilisez des LED pour indiquer l'état
- Implémentez un mode veille intelligent

## Sécurité

- Changez le mot de passe par défaut du Pi
- Utilisez une clé API OpenAI avec des limites de coût
- Configurez fail2ban pour protéger SSH
- Utilisez des certificats SSL pour les communications
- Limitez l'accès réseau si possible

## Contributions

Les contributions sont les bienvenues ! Veuillez :

1. Fork le projet
2. Créer une branche pour votre fonctionnalité
3. Tester vos modifications
4. Soumettre une pull request

## Licence

MIT License - Voir le fichier LICENSE pour plus de détails.