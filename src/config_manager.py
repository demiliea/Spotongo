#!/usr/bin/env python3
"""
Gestionnaire de configuration pour l'assistant Raspberry Pi
Lit les fichiers de configuration depuis /boot
"""

import os
import logging
from configparser import ConfigParser
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, boot_dir: str = "/boot"):
        """
        Initialise le gestionnaire de configuration
        
        Args:
            boot_dir: Chemin vers le dossier de configuration (par défaut /boot)
        """
        self.boot_dir = boot_dir
        self.logger = logging.getLogger(__name__)
        
        # Configurations par défaut
        self.default_configs = {
            'spotify': {
                'device_name': 'Mon Assistant Pi',
                'bitrate': '320',
                'initial_volume': '50'
            },
            'bluetooth': {
                'speaker_name': 'Mon Enceinte Bluetooth',
                'auto_connect': 'true',
                'connection_timeout': '30'
            },
            'gpt': {
                'enabled': 'true',
                'gpio_pin': '17',
                'recording_duration': '10',
                'sample_rate': '44100'
            },
            'openai': {
                'api_key': '',
                'model': 'gpt-4o',
                'whisper_model': 'whisper-1',
                'max_tokens': '150',
                'temperature': '0.7'
            }
        }
        
        self.configs = {}
        self.load_all_configs()
    
    def load_all_configs(self) -> None:
        """Charge toutes les configurations depuis les fichiers"""
        config_files = {
            'spotify': 'config-spotify.txt',
            'bluetooth': 'config-bluetooth.txt',
            'gpt': 'config-gpt.txt',
            'openai': 'config-openai.txt'
        }
        
        for config_name, filename in config_files.items():
            self.configs[config_name] = self._load_config_file(filename, config_name)
    
    def _load_config_file(self, filename: str, config_name: str) -> Dict[str, Any]:
        """
        Charge un fichier de configuration spécifique
        
        Args:
            filename: Nom du fichier de configuration
            config_name: Nom de la configuration
            
        Returns:
            Dictionnaire avec les valeurs de configuration
        """
        filepath = os.path.join(self.boot_dir, filename)
        config = self.default_configs.get(config_name, {}).copy()
        
        if not os.path.exists(filepath):
            self.logger.warning(f"Fichier de configuration {filename} non trouvé, utilisation des valeurs par défaut")
            return config
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
            
            self.logger.info(f"Configuration {config_name} chargée depuis {filename}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de {filename}: {e}")
        
        return config
    
    def get_config(self, config_name: str) -> Dict[str, Any]:
        """
        Récupère une configuration spécifique
        
        Args:
            config_name: Nom de la configuration (spotify, bluetooth, gpt, openai)
            
        Returns:
            Dictionnaire avec les valeurs de configuration
        """
        return self.configs.get(config_name, {})
    
    def get_value(self, config_name: str, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur spécifique de configuration
        
        Args:
            config_name: Nom de la configuration
            key: Clé de la valeur
            default: Valeur par défaut si la clé n'existe pas
            
        Returns:
            Valeur de configuration
        """
        config = self.get_config(config_name)
        return config.get(key, default)
    
    def get_bool_value(self, config_name: str, key: str, default: bool = False) -> bool:
        """
        Récupère une valeur booléenne de configuration
        
        Args:
            config_name: Nom de la configuration
            key: Clé de la valeur
            default: Valeur par défaut
            
        Returns:
            Valeur booléenne
        """
        value = self.get_value(config_name, key, str(default))
        return str(value).lower() in ['true', '1', 'yes', 'on']
    
    def get_int_value(self, config_name: str, key: str, default: int = 0) -> int:
        """
        Récupère une valeur entière de configuration
        
        Args:
            config_name: Nom de la configuration
            key: Clé de la valeur
            default: Valeur par défaut
            
        Returns:
            Valeur entière
        """
        try:
            value = self.get_value(config_name, key, default)
            return int(value)
        except ValueError:
            self.logger.warning(f"Impossible de convertir {key} en entier, utilisation de la valeur par défaut {default}")
            return default
    
    def reload_config(self, config_name: str) -> None:
        """
        Recharge une configuration spécifique
        
        Args:
            config_name: Nom de la configuration à recharger
        """
        config_files = {
            'spotify': 'config-spotify.txt',
            'bluetooth': 'config-bluetooth.txt',
            'gpt': 'config-gpt.txt',
            'openai': 'config-openai.txt'
        }
        
        if config_name in config_files:
            self.configs[config_name] = self._load_config_file(config_files[config_name], config_name)
            self.logger.info(f"Configuration {config_name} rechargée")
    
    def validate_openai_config(self) -> bool:
        """
        Valide la configuration OpenAI
        
        Returns:
            True si la configuration est valide
        """
        api_key = self.get_value('openai', 'api_key', '')
        
        if not api_key or api_key == 'sk-votre-clé-openai-ici':
            self.logger.error("Clé API OpenAI manquante ou invalide")
            return False
        
        if not api_key.startswith('sk-'):
            self.logger.error("Format de clé API OpenAI invalide")
            return False
        
        return True
    
    def is_assistant_enabled(self) -> bool:
        """
        Vérifie si l'assistant vocal est activé
        
        Returns:
            True si l'assistant est activé
        """
        return self.get_bool_value('gpt', 'enabled', True)
    
    def get_gpio_pin(self) -> int:
        """
        Récupère le numéro du pin GPIO pour le bouton
        
        Returns:
            Numéro du pin GPIO
        """
        return self.get_int_value('gpt', 'gpio_pin', 17)
    
    def get_recording_duration(self) -> int:
        """
        Récupère la durée d'enregistrement en secondes
        
        Returns:
            Durée d'enregistrement
        """
        return self.get_int_value('gpt', 'recording_duration', 10)
    
    def get_speaker_name(self) -> str:
        """
        Récupère le nom de l'enceinte Bluetooth
        
        Returns:
            Nom de l'enceinte
        """
        return self.get_value('bluetooth', 'speaker_name', 'Mon Enceinte Bluetooth')
    
    def get_spotify_device_name(self) -> str:
        """
        Récupère le nom du device Spotify
        
        Returns:
            Nom du device Spotify
        """
        return self.get_value('spotify', 'device_name', 'Mon Assistant Pi')
    
    def log_current_config(self) -> None:
        """Log la configuration actuelle pour debug"""
        self.logger.info("Configuration actuelle:")
        for config_name, config in self.configs.items():
            self.logger.info(f"  {config_name}:")
            for key, value in config.items():
                # Masquer les clés API
                if 'api_key' in key.lower() and value:
                    masked_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
                    self.logger.info(f"    {key}: {masked_value}")
                else:
                    self.logger.info(f"    {key}: {value}")


if __name__ == "__main__":
    # Test du gestionnaire de configuration
    logging.basicConfig(level=logging.INFO)
    config_manager = ConfigManager("/tmp")  # Pour les tests
    
    print("Test du gestionnaire de configuration:")
    print(f"Assistant activé: {config_manager.is_assistant_enabled()}")
    print(f"GPIO Pin: {config_manager.get_gpio_pin()}")
    print(f"Durée d'enregistrement: {config_manager.get_recording_duration()}")
    print(f"Nom enceinte: {config_manager.get_speaker_name()}")
    print(f"Device Spotify: {config_manager.get_spotify_device_name()}")
    
    config_manager.log_current_config()