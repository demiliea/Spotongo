#!/usr/bin/env python3
"""
Script de test pour valider le système Raspberry Pi Assistant Vocal
Usage: python3 test_system.py
"""

import sys
import os
import logging
import time
from typing import Dict, Any, List

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from bluetooth_manager import BluetoothManager
from audio_utils import AudioManager


class SystemTester:
    def __init__(self):
        """Initialise le testeur système"""
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        self.test_results = {}
        
        # Initialiser les composants pour les tests
        self.config_manager = ConfigManager("/boot")
        self.bluetooth_manager = BluetoothManager(self.config_manager)
        self.audio_manager = AudioManager(self.config_manager)
    
    def setup_logging(self):
        """Configure le logging pour les tests"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def run_test(self, test_name: str, test_func) -> bool:
        """
        Exécute un test et enregistre le résultat
        
        Args:
            test_name: Nom du test
            test_func: Fonction de test à exécuter
            
        Returns:
            True si le test a réussi
        """
        try:
            self.logger.info(f"=== Test: {test_name} ===")
            result = test_func()
            self.test_results[test_name] = {
                'status': 'PASS' if result else 'FAIL',
                'success': result
            }
            
            if result:
                self.logger.info(f"✓ {test_name} - PASS")
            else:
                self.logger.error(f"✗ {test_name} - FAIL")
            
            return result
            
        except Exception as e:
            self.logger.error(f"✗ {test_name} - ERROR: {e}")
            self.test_results[test_name] = {
                'status': 'ERROR',
                'error': str(e),
                'success': False
            }
            return False
    
    def test_config_manager(self) -> bool:
        """Test le gestionnaire de configuration"""
        try:
            # Tester le chargement des configurations
            config_manager = ConfigManager("/boot")
            
            # Vérifier que les configurations sont chargées
            spotify_config = config_manager.get_config('spotify')
            bluetooth_config = config_manager.get_config('bluetooth')
            gpt_config = config_manager.get_config('gpt')
            openai_config = config_manager.get_config('openai')
            
            # Vérifier les valeurs par défaut
            device_name = config_manager.get_spotify_device_name()
            speaker_name = config_manager.get_speaker_name()
            gpio_pin = config_manager.get_gpio_pin()
            
            self.logger.info(f"Device Spotify: {device_name}")
            self.logger.info(f"Enceinte Bluetooth: {speaker_name}")
            self.logger.info(f"GPIO Pin: {gpio_pin}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur test config: {e}")
            return False
    
    def test_bluetooth_initialization(self) -> bool:
        """Test l'initialisation Bluetooth"""
        try:
            # Tester l'initialisation Bluetooth
            if not self.bluetooth_manager.initialize():
                self.logger.warning("Initialisation Bluetooth échouée")
                return False
            
            # Tester le scan (court)
            devices = self.bluetooth_manager.scan_for_devices(5)
            self.logger.info(f"Appareils Bluetooth trouvés: {len(devices)}")
            
            for device in devices[:3]:  # Limiter l'affichage
                self.logger.info(f"  - {device['name']} ({device['mac']})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur test Bluetooth: {e}")
            return False
    
    def test_audio_system(self) -> bool:
        """Test le système audio"""
        try:
            # Lister les périphériques audio
            self.logger.info("=== Périphériques audio ===")
            self.audio_manager.list_audio_devices()
            
            # Tester la synthèse vocale
            self.logger.info("=== Test TTS ===")
            if not self.audio_manager.test_audio_playback():
                self.logger.warning("Test TTS échoué")
                return False
            
            # Tester l'enregistrement (court)
            self.logger.info("=== Test enregistrement ===")
            if not self.audio_manager.test_audio_recording(3):
                self.logger.warning("Test enregistrement échoué")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur test audio: {e}")
            return False
    
    def test_gpio_availability(self) -> bool:
        """Test la disponibilité des GPIO"""
        try:
            try:
                import RPi.GPIO as GPIO
                self.logger.info("RPi.GPIO disponible")
                
                # Tester la configuration GPIO
                gpio_pin = self.config_manager.get_gpio_pin()
                self.logger.info(f"Pin GPIO configuré: {gpio_pin}")
                
                return True
                
            except ImportError:
                self.logger.warning("RPi.GPIO non disponible (normal si pas sur Raspberry Pi)")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur test GPIO: {e}")
            return False
    
    def test_system_dependencies(self) -> bool:
        """Test les dépendances système"""
        try:
            import subprocess
            
            # Tester les commandes système requises
            commands = [
                ('bluetoothctl', 'Bluetooth'),
                ('pactl', 'PulseAudio'),
                ('espeak-ng', 'Synthèse vocale'),
                ('ffmpeg', 'Conversion audio')
            ]
            
            missing_commands = []
            
            for cmd, desc in commands:
                try:
                    result = subprocess.run(['which', cmd], 
                                          capture_output=True, 
                                          text=True, 
                                          timeout=5)
                    if result.returncode == 0:
                        self.logger.info(f"✓ {desc} ({cmd}) disponible")
                    else:
                        self.logger.warning(f"✗ {desc} ({cmd}) manquant")
                        missing_commands.append(cmd)
                except Exception as e:
                    self.logger.warning(f"✗ {desc} ({cmd}) - erreur: {e}")
                    missing_commands.append(cmd)
            
            if missing_commands:
                self.logger.warning(f"Commandes manquantes: {', '.join(missing_commands)}")
            
            return len(missing_commands) == 0
            
        except Exception as e:
            self.logger.error(f"Erreur test dépendances: {e}")
            return False
    
    def test_openai_config(self) -> bool:
        """Test la configuration OpenAI"""
        try:
            # Vérifier la configuration OpenAI
            api_key = self.config_manager.get_value('openai', 'api_key', '')
            model = self.config_manager.get_value('openai', 'model', '')
            
            if not api_key or api_key == 'sk-votre-clé-openai-ici':
                self.logger.warning("Clé API OpenAI non configurée")
                return False
            
            if not self.config_manager.validate_openai_config():
                self.logger.error("Configuration OpenAI invalide")
                return False
            
            self.logger.info(f"Configuration OpenAI valide (modèle: {model})")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur test OpenAI: {e}")
            return False
    
    def test_file_permissions(self) -> bool:
        """Test les permissions des fichiers"""
        try:
            # Vérifier les permissions des dossiers critiques
            critical_paths = [
                '/opt/rpi-assistant',
                '/opt/rpi-assistant/logs',
                '/tmp/rpi-assistant-audio'
            ]
            
            for path in critical_paths:
                if os.path.exists(path):
                    if os.access(path, os.R_OK | os.W_OK):
                        self.logger.info(f"✓ Permissions OK pour {path}")
                    else:
                        self.logger.warning(f"✗ Permissions insuffisantes pour {path}")
                        return False
                else:
                    self.logger.warning(f"✗ Chemin manquant: {path}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur test permissions: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Exécute tous les tests"""
        self.logger.info("=== DÉBUT DES TESTS SYSTÈME ===")
        
        # Liste des tests à exécuter
        tests = [
            ('Configuration Manager', self.test_config_manager),
            ('Dépendances système', self.test_system_dependencies),
            ('Permissions fichiers', self.test_file_permissions),
            ('GPIO disponibilité', self.test_gpio_availability),
            ('Bluetooth initialisation', self.test_bluetooth_initialization),
            ('Système audio', self.test_audio_system),
            ('Configuration OpenAI', self.test_openai_config),
        ]
        
        # Exécuter tous les tests
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
            time.sleep(1)  # Pause entre les tests
        
        # Générer le rapport
        self.generate_report()
        
        return self.test_results
    
    def generate_report(self) -> None:
        """Génère le rapport de test"""
        self.logger.info("=== RAPPORT DE TEST ===")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['success'])
        failed_tests = total_tests - passed_tests
        
        self.logger.info(f"Total des tests: {total_tests}")
        self.logger.info(f"Tests réussis: {passed_tests}")
        self.logger.info(f"Tests échoués: {failed_tests}")
        
        if failed_tests > 0:
            self.logger.warning("Tests échoués:")
            for test_name, result in self.test_results.items():
                if not result['success']:
                    status = result['status']
                    self.logger.warning(f"  - {test_name}: {status}")
        
        # Recommandations
        self.logger.info("=== RECOMMANDATIONS ===")
        
        if failed_tests == 0:
            self.logger.info("✓ Tous les tests sont passés, le système est prêt!")
        else:
            self.logger.warning("Certains tests ont échoué. Vérifiez:")
            self.logger.warning("1. Les dépendances système sont installées")
            self.logger.warning("2. Les permissions des fichiers")
            self.logger.warning("3. La configuration OpenAI")
            self.logger.warning("4. La connexion Bluetooth")


def main():
    """Fonction principale"""
    print("=== Test du système Raspberry Pi Assistant Vocal ===")
    print("Ce script teste tous les composants du système.")
    print()
    
    tester = SystemTester()
    results = tester.run_all_tests()
    
    # Codes de sortie
    failed_tests = sum(1 for result in results.values() if not result['success'])
    
    if failed_tests == 0:
        print("\n✓ Tous les tests sont passés!")
        sys.exit(0)
    else:
        print(f"\n✗ {failed_tests} test(s) échoué(s)")
        sys.exit(1)


if __name__ == "__main__":
    main()