#!/usr/bin/env python3
"""
Utilitaires audio pour l'assistant Raspberry Pi
Gère l'enregistrement audio et la synthèse vocale
"""

import os
import time
import logging
import subprocess
import tempfile
import wave
import pyaudio
from typing import Optional, Tuple
from gtts import gTTS
import pygame

class AudioManager:
    def __init__(self, config_manager):
        """
        Initialise le gestionnaire audio
        
        Args:
            config_manager: Instance du gestionnaire de configuration
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Configuration audio
        self.sample_rate = self.config_manager.get_int_value('gpt', 'sample_rate', 44100)
        self.channels = 1
        self.chunk_size = 1024
        self.audio_format = pyaudio.paInt16
        
        # Initialiser PyAudio
        self.pyaudio = pyaudio.PyAudio()
        
        # Initialiser pygame pour la lecture audio
        pygame.mixer.init()
        
        # Répertoire temporaire pour les fichiers audio
        self.temp_dir = "/tmp/rpi-assistant-audio"
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.logger.info("Gestionnaire audio initialisé")
    
    def list_audio_devices(self) -> None:
        """Liste tous les périphériques audio disponibles"""
        self.logger.info("Périphériques audio disponibles:")
        
        for i in range(self.pyaudio.get_device_count()):
            device_info = self.pyaudio.get_device_info_by_index(i)
            self.logger.info(f"  Device {i}: {device_info['name']}")
            self.logger.info(f"    Channels: {device_info['maxInputChannels']} input, {device_info['maxOutputChannels']} output")
            self.logger.info(f"    Sample rate: {device_info['defaultSampleRate']}")
    
    def find_usb_microphone(self) -> Optional[int]:
        """
        Trouve le micro USB connecté
        
        Returns:
            Index du périphérique audio ou None si non trouvé
        """
        for i in range(self.pyaudio.get_device_count()):
            device_info = self.pyaudio.get_device_info_by_index(i)
            device_name = device_info['name'].lower()
            
            # Rechercher des mots-clés indicatifs d'un micro USB
            usb_keywords = ['usb', 'microphone', 'mic', 'webcam', 'headset']
            
            if (device_info['maxInputChannels'] > 0 and 
                any(keyword in device_name for keyword in usb_keywords)):
                self.logger.info(f"Micro USB trouvé: {device_info['name']} (index {i})")
                return i
        
        self.logger.warning("Aucun micro USB trouvé, utilisation du périphérique par défaut")
        return None
    
    def record_audio(self, duration: int, output_file: str = None) -> Optional[str]:
        """
        Enregistre l'audio depuis le microphone
        
        Args:
            duration: Durée d'enregistrement en secondes
            output_file: Chemin du fichier de sortie (optionnel)
            
        Returns:
            Chemin du fichier audio enregistré ou None en cas d'erreur
        """
        if output_file is None:
            output_file = os.path.join(self.temp_dir, f"recording_{int(time.time())}.wav")
        
        try:
            self.logger.info(f"Début d'enregistrement audio ({duration}s)...")
            
            # Trouver le micro USB
            input_device = self.find_usb_microphone()
            
            # Configurer le stream audio
            stream = self.pyaudio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=input_device,
                frames_per_buffer=self.chunk_size
            )
            
            # Enregistrer l'audio
            frames = []
            for i in range(0, int(self.sample_rate / self.chunk_size * duration)):
                data = stream.read(self.chunk_size)
                frames.append(data)
            
            # Fermer le stream
            stream.stop_stream()
            stream.close()
            
            # Sauvegarder le fichier WAV
            with wave.open(output_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio.get_sample_size(self.audio_format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
            
            self.logger.info(f"Enregistrement terminé: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement: {e}")
            return None
    
    def convert_to_mp3(self, wav_file: str) -> Optional[str]:
        """
        Convertit un fichier WAV en MP3
        
        Args:
            wav_file: Chemin du fichier WAV
            
        Returns:
            Chemin du fichier MP3 ou None en cas d'erreur
        """
        try:
            mp3_file = wav_file.replace('.wav', '.mp3')
            
            # Utiliser ffmpeg pour la conversion
            command = [
                'ffmpeg', '-i', wav_file,
                '-acodec', 'libmp3lame',
                '-ab', '128k',
                '-y',  # Overwrite output file
                mp3_file
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"Conversion réussie: {mp3_file}")
                return mp3_file
            else:
                self.logger.error(f"Erreur de conversion: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la conversion: {e}")
            return None
    
    def text_to_speech(self, text: str, language: str = 'fr') -> Optional[str]:
        """
        Convertit du texte en audio via gTTS
        
        Args:
            text: Texte à convertir
            language: Langue de synthèse (par défaut français)
            
        Returns:
            Chemin du fichier audio généré ou None en cas d'erreur
        """
        try:
            self.logger.info(f"Génération TTS: {text[:50]}...")
            
            # Générer le fichier audio
            output_file = os.path.join(self.temp_dir, f"tts_{int(time.time())}.mp3")
            
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(output_file)
            
            self.logger.info(f"TTS généré: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération TTS: {e}")
            return None
    
    def espeak_tts(self, text: str, language: str = 'fr') -> bool:
        """
        Utilise espeak pour la synthèse vocale (plus rapide, offline)
        
        Args:
            text: Texte à dire
            language: Langue de synthèse
            
        Returns:
            True si la synthèse a réussi
        """
        try:
            self.logger.info(f"Synthèse vocale espeak: {text[:50]}...")
            
            # Utiliser espeak-ng pour la synthèse
            command = [
                'espeak-ng',
                '-v', language,
                '-s', '150',  # Vitesse de parole
                '-a', '50',   # Amplitude
                text
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Synthèse vocale réussie")
                return True
            else:
                self.logger.error(f"Erreur espeak: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la synthèse espeak: {e}")
            return False
    
    def play_audio_file(self, audio_file: str) -> bool:
        """
        Lit un fichier audio via pygame
        
        Args:
            audio_file: Chemin du fichier audio
            
        Returns:
            True si la lecture a réussi
        """
        try:
            self.logger.info(f"Lecture audio: {audio_file}")
            
            # Charger et lire le fichier
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            # Attendre la fin de la lecture
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            self.logger.info("Lecture audio terminée")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la lecture: {e}")
            return False
    
    def play_audio_via_bluetooth(self, audio_file: str) -> bool:
        """
        Lit un fichier audio via l'enceinte Bluetooth
        
        Args:
            audio_file: Chemin du fichier audio
            
        Returns:
            True si la lecture a réussi
        """
        try:
            self.logger.info(f"Lecture audio via Bluetooth: {audio_file}")
            
            # Utiliser paplay pour forcer la lecture sur l'enceinte Bluetooth
            command = ['paplay', audio_file]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info("Lecture Bluetooth réussie")
                return True
            else:
                self.logger.error(f"Erreur lecture Bluetooth: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la lecture Bluetooth: {e}")
            return False
    
    def speak_text(self, text: str, use_bluetooth: bool = True) -> bool:
        """
        Synthèse vocale et lecture du texte
        
        Args:
            text: Texte à dire
            use_bluetooth: Utiliser l'enceinte Bluetooth si possible
            
        Returns:
            True si la synthèse et lecture ont réussi
        """
        try:
            if use_bluetooth:
                # Essayer d'abord espeak direct (plus rapide)
                if self.espeak_tts(text):
                    return True
            
            # Fallback vers gTTS + lecture fichier
            audio_file = self.text_to_speech(text)
            if audio_file:
                if use_bluetooth:
                    success = self.play_audio_via_bluetooth(audio_file)
                else:
                    success = self.play_audio_file(audio_file)
                
                # Nettoyer le fichier temporaire
                self.cleanup_file(audio_file)
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la synthèse vocale: {e}")
            return False
    
    def test_audio_recording(self, duration: int = 5) -> bool:
        """
        Test l'enregistrement audio
        
        Args:
            duration: Durée du test en secondes
            
        Returns:
            True si le test a réussi
        """
        try:
            self.logger.info(f"Test d'enregistrement audio ({duration}s)...")
            
            # Enregistrer un échantillon
            test_file = self.record_audio(duration)
            
            if test_file and os.path.exists(test_file):
                # Vérifier la taille du fichier
                file_size = os.path.getsize(test_file)
                
                if file_size > 1000:  # Au moins 1KB
                    self.logger.info(f"Test réussi: fichier {file_size} bytes")
                    self.cleanup_file(test_file)
                    return True
                else:
                    self.logger.warning(f"Fichier trop petit: {file_size} bytes")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test audio: {e}")
            return False
    
    def test_audio_playback(self) -> bool:
        """
        Test la lecture audio
        
        Returns:
            True si le test a réussi
        """
        try:
            self.logger.info("Test de lecture audio...")
            
            # Générer un message de test
            test_message = "Test de l'assistant vocal. Audio fonctionnel."
            
            return self.speak_text(test_message)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du test de lecture: {e}")
            return False
    
    def cleanup_file(self, file_path: str) -> None:
        """
        Supprime un fichier temporaire
        
        Args:
            file_path: Chemin du fichier à supprimer
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug(f"Fichier supprimé: {file_path}")
        except Exception as e:
            self.logger.warning(f"Impossible de supprimer {file_path}: {e}")
    
    def cleanup_temp_files(self) -> None:
        """Supprime tous les fichiers temporaires"""
        try:
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                if os.path.isfile(file_path):
                    self.cleanup_file(file_path)
            
            self.logger.info("Fichiers temporaires nettoyés")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage: {e}")
    
    def get_audio_info(self, audio_file: str) -> Optional[dict]:
        """
        Récupère les informations d'un fichier audio
        
        Args:
            audio_file: Chemin du fichier audio
            
        Returns:
            Dictionnaire avec les informations audio
        """
        try:
            if audio_file.endswith('.wav'):
                with wave.open(audio_file, 'rb') as wf:
                    return {
                        'channels': wf.getnchannels(),
                        'sample_width': wf.getsampwidth(),
                        'sample_rate': wf.getframerate(),
                        'frames': wf.getnframes(),
                        'duration': wf.getnframes() / wf.getframerate()
                    }
            else:
                # Utiliser ffprobe pour autres formats
                command = [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', audio_file
                ]
                
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    return data
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des infos audio: {e}")
        
        return None
    
    def __del__(self):
        """Nettoyage lors de la destruction de l'objet"""
        try:
            self.pyaudio.terminate()
            pygame.mixer.quit()
            self.cleanup_temp_files()
        except:
            pass


if __name__ == "__main__":
    # Test du gestionnaire audio
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config_manager import ConfigManager
    
    logging.basicConfig(level=logging.INFO)
    
    config_manager = ConfigManager("/tmp")
    audio_manager = AudioManager(config_manager)
    
    print("Test du gestionnaire audio:")
    
    # Lister les périphériques audio
    print("Périphériques audio:")
    audio_manager.list_audio_devices()
    
    # Test de synthèse vocale
    print("\nTest de synthèse vocale:")
    if audio_manager.test_audio_playback():
        print("✓ Test de lecture réussi")
    else:
        print("✗ Échec du test de lecture")
    
    # Test d'enregistrement (uniquement si sur Raspberry Pi)
    print("\nTest d'enregistrement:")
    if audio_manager.test_audio_recording(3):
        print("✓ Test d'enregistrement réussi")
    else:
        print("✗ Échec du test d'enregistrement")