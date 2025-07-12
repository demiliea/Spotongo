#!/usr/bin/env python3
"""
Assistant vocal principal pour Raspberry Pi Zero 2 W
Intègre GPIO, enregistrement audio, OpenAI API, TTS et Bluetooth
"""

import os
import sys
import time
import logging
import signal
import threading
from typing import Optional

# Imports pour Raspberry Pi
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO non disponible, mode simulation activé")
    GPIO = None

import openai
from openai import OpenAI

# Imports locaux
from config_manager import ConfigManager
from bluetooth_manager import BluetoothManager
from audio_utils import AudioManager


class VoiceAssistant:
    def __init__(self, config_dir: str = "/boot"):
        """
        Initialise l'assistant vocal
        
        Args:
            config_dir: Répertoire des fichiers de configuration
        """
        self.config_dir = config_dir
        self.running = False
        self.button_pressed = False
        
        # Configuration du logging
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialiser les composants
        self.config_manager = ConfigManager(config_dir)
        self.bluetooth_manager = BluetoothManager(self.config_manager)
        self.audio_manager = AudioManager(self.config_manager)
        
        # Configuration OpenAI
        self.setup_openai()
        
        # Configuration GPIO
        self.setup_gpio()
        
        self.logger.info("Assistant vocal initialisé")
    
    def setup_logging(self) -> None:
        """Configure le système de logging"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/opt/rpi-assistant/logs/assistant.log')
            ]
        )
    
    def setup_openai(self) -> None:
        """Configure le client OpenAI"""
        try:
            api_key = self.config_manager.get_value('openai', 'api_key', '')
            
            if not api_key or not self.config_manager.validate_openai_config():
                self.logger.error("Configuration OpenAI invalide")
                self.openai_client = None
                return
            
            self.openai_client = OpenAI(api_key=api_key)
            self.logger.info("Client OpenAI configuré")
            
        except Exception as e:
            self.logger.error(f"Erreur configuration OpenAI: {e}")
            self.openai_client = None
    
    def setup_gpio(self) -> None:
        """Configure les pins GPIO"""
        if not GPIO:
            self.logger.warning("GPIO non disponible, mode simulation")
            return
        
        try:
            # Configuration du mode GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Configuration du bouton
            self.button_pin = self.config_manager.get_gpio_pin()
            GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Configuration de l'interruption
            GPIO.add_event_detect(
                self.button_pin,
                GPIO.FALLING,
                callback=self.button_callback,
                bouncetime=300
            )
            
            self.logger.info(f"GPIO configuré, bouton sur pin {self.button_pin}")
            
        except Exception as e:
            self.logger.error(f"Erreur configuration GPIO: {e}")
    
    def button_callback(self, channel):
        """Callback appelé lors de l'appui sur le bouton"""
        if not self.button_pressed:
            self.button_pressed = True
            self.logger.info("Bouton pressé, démarrage de l'enregistrement")
            
            # Démarrer l'enregistrement dans un thread séparé
            thread = threading.Thread(target=self.handle_voice_command)
            thread.daemon = True
            thread.start()
    
    def handle_voice_command(self) -> None:
        """Gère une commande vocale complète"""
        try:
            self.logger.info("Traitement de la commande vocale...")
            
            # Vérifier que l'enceinte est connectée
            if not self.bluetooth_manager.ensure_connection():
                self.logger.warning("Enceinte Bluetooth non connectée")
                self.audio_manager.speak_text("Enceinte non connectée", use_bluetooth=False)
                return
            
            # Signal sonore de début d'enregistrement
            self.audio_manager.speak_text("J'écoute", use_bluetooth=True)
            
            # Enregistrer l'audio
            duration = self.config_manager.get_recording_duration()
            audio_file = self.audio_manager.record_audio(duration)
            
            if not audio_file:
                self.logger.error("Échec de l'enregistrement audio")
                self.audio_manager.speak_text("Erreur d'enregistrement", use_bluetooth=True)
                return
            
            # Transcrire avec Whisper
            self.audio_manager.speak_text("Je traite votre demande", use_bluetooth=True)
            transcription = self.transcribe_audio(audio_file)
            
            if not transcription:
                self.logger.error("Échec de la transcription")
                self.audio_manager.speak_text("Je n'ai pas compris", use_bluetooth=True)
                return
            
            self.logger.info(f"Transcription: {transcription}")
            
            # Générer la réponse avec GPT
            response = self.generate_response(transcription)
            
            if not response:
                self.logger.error("Échec de la génération de réponse")
                self.audio_manager.speak_text("Erreur de connexion", use_bluetooth=True)
                return
            
            self.logger.info(f"Réponse: {response}")
            
            # Lire la réponse
            self.audio_manager.speak_text(response, use_bluetooth=True)
            
            # Nettoyer le fichier audio
            self.audio_manager.cleanup_file(audio_file)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement: {e}")
            self.audio_manager.speak_text("Une erreur est survenue", use_bluetooth=True)
        
        finally:
            # Réinitialiser le flag
            self.button_pressed = False
    
    def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """
        Transcrit un fichier audio via Whisper
        
        Args:
            audio_file: Chemin du fichier audio
            
        Returns:
            Texte transcrit ou None en cas d'erreur
        """
        try:
            if not self.openai_client:
                self.logger.error("Client OpenAI non configuré")
                return None
            
            # Convertir en MP3 si nécessaire
            if audio_file.endswith('.wav'):
                mp3_file = self.audio_manager.convert_to_mp3(audio_file)
                if mp3_file:
                    audio_file = mp3_file
            
            # Transcrire avec Whisper
            with open(audio_file, 'rb') as audio_data:
                model = self.config_manager.get_value('openai', 'whisper_model', 'whisper-1')
                
                response = self.openai_client.audio.transcriptions.create(
                    model=model,
                    file=audio_data,
                    language='fr'
                )
                
                return response.text.strip()
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la transcription: {e}")
            return None
    
    def generate_response(self, text: str) -> Optional[str]:
        """
        Génère une réponse via GPT
        
        Args:
            text: Texte de la question
            
        Returns:
            Réponse générée ou None en cas d'erreur
        """
        try:
            if not self.openai_client:
                self.logger.error("Client OpenAI non configuré")
                return None
            
            # Configuration du modèle
            model = self.config_manager.get_value('openai', 'model', 'gpt-4o')
            max_tokens = self.config_manager.get_int_value('openai', 'max_tokens', 150)
            temperature = float(self.config_manager.get_value('openai', 'temperature', '0.7'))
            
            # Système de prompt
            system_prompt = """Tu es un assistant vocal amical et concis pour une enceinte connectée. 
            Réponds en français de manière claire et brève. 
            Limite tes réponses à 2-3 phrases maximum pour un confort d'écoute optimal."""
            
            # Générer la réponse
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de réponse: {e}")
            return None
    
    def startup_sequence(self) -> None:
        """Séquence de démarrage de l'assistant"""
        try:
            self.logger.info("Démarrage de l'assistant vocal...")
            
            # Vérifier la configuration
            if not self.config_manager.is_assistant_enabled():
                self.logger.info("Assistant désactivé dans la configuration")
                return
            
            if not self.openai_client:
                self.logger.error("Configuration OpenAI invalide, assistant désactivé")
                return
            
            # Initialiser Bluetooth
            self.logger.info("Configuration Bluetooth...")
            if not self.bluetooth_manager.setup_target_speaker():
                self.logger.warning("Échec de la configuration Bluetooth")
                # Continuer quand même, on essaiera de reconnecter plus tard
            
            # Test audio
            self.logger.info("Test des composants audio...")
            if not self.audio_manager.test_audio_playback():
                self.logger.warning("Problème avec le système audio")
            
            # Signal de démarrage
            self.audio_manager.speak_text("Assistant vocal prêt", use_bluetooth=True)
            
            self.logger.info("Assistant vocal démarré avec succès")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage: {e}")
    
    def run(self) -> None:
        """Boucle principale de l'assistant"""
        try:
            self.running = True
            self.startup_sequence()
            
            # Démarrer la surveillance Bluetooth dans un thread séparé
            bluetooth_thread = threading.Thread(target=self.bluetooth_monitor)
            bluetooth_thread.daemon = True
            bluetooth_thread.start()
            
            self.logger.info("Assistant vocal en cours d'exécution...")
            
            # Boucle principale
            while self.running:
                time.sleep(1)
                
                # Vérifier l'état du système périodiquement
                if int(time.time()) % 300 == 0:  # Toutes les 5 minutes
                    self.system_health_check()
            
        except KeyboardInterrupt:
            self.logger.info("Arrêt demandé par l'utilisateur")
        except Exception as e:
            self.logger.error(f"Erreur dans la boucle principale: {e}")
        finally:
            self.shutdown()
    
    def bluetooth_monitor(self) -> None:
        """Surveille la connexion Bluetooth"""
        try:
            while self.running:
                if not self.bluetooth_manager.ensure_connection():
                    self.logger.warning("Tentative de reconnexion Bluetooth...")
                
                time.sleep(30)  # Vérifier toutes les 30 secondes
                
        except Exception as e:
            self.logger.error(f"Erreur dans la surveillance Bluetooth: {e}")
    
    def system_health_check(self) -> None:
        """Vérification de la santé du système"""
        try:
            # Vérifier l'espace disque
            import shutil
            disk_usage = shutil.disk_usage('/tmp')
            free_space = disk_usage.free / (1024 * 1024 * 1024)  # GB
            
            if free_space < 0.1:  # Moins de 100MB
                self.logger.warning(f"Espace disque faible: {free_space:.2f} GB")
                self.audio_manager.cleanup_temp_files()
            
            # Vérifier la connectivité réseau
            import subprocess
            result = subprocess.run(['ping', '-c', '1', '8.8.8.8'], 
                                  capture_output=True, timeout=5)
            
            if result.returncode != 0:
                self.logger.warning("Connectivité réseau limitée")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification système: {e}")
    
    def shutdown(self) -> None:
        """Arrêt propre de l'assistant"""
        try:
            self.logger.info("Arrêt de l'assistant vocal...")
            self.running = False
            
            # Nettoyer les GPIO
            if GPIO:
                GPIO.cleanup()
            
            # Nettoyer les fichiers temporaires
            self.audio_manager.cleanup_temp_files()
            
            self.logger.info("Assistant vocal arrêté")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt: {e}")
    
    def signal_handler(self, signum, frame):
        """Gestionnaire de signaux pour arrêt propre"""
        self.logger.info(f"Signal {signum} reçu, arrêt en cours...")
        self.shutdown()
        sys.exit(0)


def main():
    """Fonction principale"""
    try:
        # Créer l'assistant
        assistant = VoiceAssistant()
        
        # Configurer les gestionnaires de signaux
        signal.signal(signal.SIGINT, assistant.signal_handler)
        signal.signal(signal.SIGTERM, assistant.signal_handler)
        
        # Démarrer l'assistant
        assistant.run()
        
    except Exception as e:
        print(f"Erreur critique: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()