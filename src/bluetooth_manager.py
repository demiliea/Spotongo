#!/usr/bin/env python3
"""
Gestionnaire Bluetooth pour l'assistant Raspberry Pi
Gère la connexion automatique avec l'enceinte Bluetooth
"""

import os
import subprocess
import time
import logging
import re
from typing import List, Optional, Dict, Any

class BluetoothManager:
    def __init__(self, config_manager):
        """
        Initialise le gestionnaire Bluetooth
        
        Args:
            config_manager: Instance du gestionnaire de configuration
        """
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.connected_devices = {}
        self.target_speaker = None
        self.target_mac = None
        
    def initialize(self) -> bool:
        """
        Initialise le service Bluetooth
        
        Returns:
            True si l'initialisation est réussie
        """
        try:
            # Démarrer le service Bluetooth
            self._run_command("sudo systemctl start bluetooth")
            time.sleep(2)
            
            # Activer le contrôleur Bluetooth
            self._run_command("sudo rfkill unblock bluetooth")
            time.sleep(1)
            
            # Configurer bluetoothctl
            self._bluetoothctl_command("power on")
            time.sleep(1)
            self._bluetoothctl_command("agent on")
            self._bluetoothctl_command("default-agent")
            
            self.logger.info("Service Bluetooth initialisé avec succès")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation Bluetooth: {e}")
            return False
    
    def scan_for_devices(self, duration: int = 10) -> List[Dict[str, str]]:
        """
        Scanne les appareils Bluetooth disponibles
        
        Args:
            duration: Durée du scan en secondes
            
        Returns:
            Liste des appareils découverts
        """
        devices = []
        
        try:
            self.logger.info(f"Début du scan Bluetooth ({duration}s)...")
            
            # Lancer le scan
            self._bluetoothctl_command("scan on")
            time.sleep(duration)
            self._bluetoothctl_command("scan off")
            
            # Récupérer la liste des appareils
            result = self._bluetoothctl_command("devices")
            
            for line in result.split('\n'):
                if line.strip().startswith('Device'):
                    parts = line.strip().split(' ', 2)
                    if len(parts) >= 3:
                        mac = parts[1]
                        name = parts[2]
                        devices.append({
                            'mac': mac,
                            'name': name,
                            'connected': self._is_device_connected(mac)
                        })
            
            self.logger.info(f"Scan terminé, {len(devices)} appareils trouvés")
            return devices
            
        except Exception as e:
            self.logger.error(f"Erreur lors du scan: {e}")
            return []
    
    def find_target_speaker(self) -> Optional[Dict[str, str]]:
        """
        Trouve l'enceinte cible configurée
        
        Returns:
            Informations sur l'enceinte si trouvée
        """
        target_name = self.config_manager.get_speaker_name()
        self.logger.info(f"Recherche de l'enceinte: {target_name}")
        
        devices = self.scan_for_devices(15)
        
        for device in devices:
            if target_name.lower() in device['name'].lower():
                self.target_speaker = device
                self.target_mac = device['mac']
                self.logger.info(f"Enceinte trouvée: {device['name']} ({device['mac']})")
                return device
        
        self.logger.warning(f"Enceinte '{target_name}' non trouvée")
        return None
    
    def pair_device(self, mac_address: str) -> bool:
        """
        Appaire un appareil Bluetooth
        
        Args:
            mac_address: Adresse MAC de l'appareil
            
        Returns:
            True si l'appairage est réussi
        """
        try:
            self.logger.info(f"Appairage de l'appareil {mac_address}...")
            
            # Supprimer l'appareil s'il existe déjà
            self._bluetoothctl_command(f"remove {mac_address}")
            time.sleep(1)
            
            # Appairer l'appareil
            result = self._bluetoothctl_command(f"pair {mac_address}")
            
            if "successful" in result.lower() or "paired" in result.lower():
                # Faire confiance à l'appareil
                self._bluetoothctl_command(f"trust {mac_address}")
                self.logger.info(f"Appareil {mac_address} appairé avec succès")
                return True
            else:
                self.logger.warning(f"Échec de l'appairage: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'appairage: {e}")
            return False
    
    def connect_device(self, mac_address: str) -> bool:
        """
        Connecte un appareil Bluetooth
        
        Args:
            mac_address: Adresse MAC de l'appareil
            
        Returns:
            True si la connexion est réussie
        """
        try:
            self.logger.info(f"Connexion à l'appareil {mac_address}...")
            
            result = self._bluetoothctl_command(f"connect {mac_address}")
            
            if "successful" in result.lower() or "connected" in result.lower():
                self.logger.info(f"Connexion réussie à {mac_address}")
                self.connected_devices[mac_address] = True
                return True
            else:
                self.logger.warning(f"Échec de la connexion: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la connexion: {e}")
            return False
    
    def disconnect_device(self, mac_address: str) -> bool:
        """
        Déconnecte un appareil Bluetooth
        
        Args:
            mac_address: Adresse MAC de l'appareil
            
        Returns:
            True si la déconnexion est réussie
        """
        try:
            self.logger.info(f"Déconnexion de l'appareil {mac_address}...")
            
            result = self._bluetoothctl_command(f"disconnect {mac_address}")
            
            if mac_address in self.connected_devices:
                del self.connected_devices[mac_address]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la déconnexion: {e}")
            return False
    
    def setup_target_speaker(self) -> bool:
        """
        Configure l'enceinte cible (scan, appairage, connexion)
        
        Returns:
            True si la configuration est réussie
        """
        try:
            # Initialiser Bluetooth
            if not self.initialize():
                return False
            
            # Chercher l'enceinte cible
            speaker = self.find_target_speaker()
            if not speaker:
                return False
            
            mac_address = speaker['mac']
            
            # Vérifier si déjà connecté
            if self._is_device_connected(mac_address):
                self.logger.info("Enceinte déjà connectée")
                return True
            
            # Appairer si nécessaire
            if not self._is_device_paired(mac_address):
                if not self.pair_device(mac_address):
                    return False
            
            # Connecter l'enceinte
            if self.connect_device(mac_address):
                # Configurer comme sortie audio par défaut
                self._set_bluetooth_audio_sink(mac_address)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la configuration de l'enceinte: {e}")
            return False
    
    def ensure_connection(self) -> bool:
        """
        S'assure que l'enceinte cible est connectée
        
        Returns:
            True si la connexion est active
        """
        if not self.target_mac:
            return self.setup_target_speaker()
        
        if self._is_device_connected(self.target_mac):
            return True
        
        # Tenter de reconnecter
        return self.connect_device(self.target_mac)
    
    def _is_device_connected(self, mac_address: str) -> bool:
        """
        Vérifie si un appareil est connecté
        
        Args:
            mac_address: Adresse MAC de l'appareil
            
        Returns:
            True si l'appareil est connecté
        """
        try:
            result = self._bluetoothctl_command(f"info {mac_address}")
            return "Connected: yes" in result
        except:
            return False
    
    def _is_device_paired(self, mac_address: str) -> bool:
        """
        Vérifie si un appareil est appairé
        
        Args:
            mac_address: Adresse MAC de l'appareil
            
        Returns:
            True si l'appareil est appairé
        """
        try:
            result = self._bluetoothctl_command(f"info {mac_address}")
            return "Paired: yes" in result
        except:
            return False
    
    def _bluetoothctl_command(self, command: str) -> str:
        """
        Execute une commande bluetoothctl
        
        Args:
            command: Commande à exécuter
            
        Returns:
            Résultat de la commande
        """
        try:
            full_command = f"echo '{command}' | bluetoothctl"
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout lors de l'exécution de: {command}")
            return ""
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution de {command}: {e}")
            return ""
    
    def _run_command(self, command: str) -> str:
        """
        Execute une commande système
        
        Args:
            command: Commande à exécuter
            
        Returns:
            Résultat de la commande
        """
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution de {command}: {e}")
            return ""
    
    def _set_bluetooth_audio_sink(self, mac_address: str) -> None:
        """
        Configure l'enceinte Bluetooth comme sortie audio par défaut
        
        Args:
            mac_address: Adresse MAC de l'enceinte
        """
        try:
            # Attendre que l'enceinte soit reconnue par PulseAudio
            time.sleep(3)
            
            # Récupérer le nom du sink Bluetooth
            result = self._run_command("pactl list sinks short")
            
            for line in result.split('\n'):
                if 'bluez' in line and mac_address.replace(':', '_') in line:
                    sink_name = line.split()[1]
                    self._run_command(f"pactl set-default-sink {sink_name}")
                    self.logger.info(f"Sortie audio configurée: {sink_name}")
                    break
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la configuration audio: {e}")
    
    def get_connected_devices(self) -> List[Dict[str, str]]:
        """
        Retourne la liste des appareils connectés
        
        Returns:
            Liste des appareils connectés
        """
        devices = []
        try:
            result = self._bluetoothctl_command("devices")
            
            for line in result.split('\n'):
                if line.strip().startswith('Device'):
                    parts = line.strip().split(' ', 2)
                    if len(parts) >= 3:
                        mac = parts[1]
                        name = parts[2]
                        if self._is_device_connected(mac):
                            devices.append({
                                'mac': mac,
                                'name': name,
                                'connected': True
                            })
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des appareils: {e}")
        
        return devices
    
    def monitor_connection(self) -> None:
        """
        Surveille la connexion Bluetooth et reconnecte si nécessaire
        """
        if not self.target_mac:
            self.logger.warning("Aucune enceinte cible configurée pour la surveillance")
            return
        
        while True:
            try:
                if not self._is_device_connected(self.target_mac):
                    self.logger.warning("Enceinte déconnectée, tentative de reconnexion...")
                    self.connect_device(self.target_mac)
                
                time.sleep(30)  # Vérifier toutes les 30 secondes
                
            except KeyboardInterrupt:
                self.logger.info("Arrêt de la surveillance Bluetooth")
                break
            except Exception as e:
                self.logger.error(f"Erreur dans la surveillance: {e}")
                time.sleep(60)


if __name__ == "__main__":
    # Test du gestionnaire Bluetooth
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from config_manager import ConfigManager
    
    logging.basicConfig(level=logging.INFO)
    
    config_manager = ConfigManager("/tmp")
    bluetooth_manager = BluetoothManager(config_manager)
    
    print("Test du gestionnaire Bluetooth:")
    print("Initialisation...")
    if bluetooth_manager.initialize():
        print("✓ Bluetooth initialisé")
        
        print("Scan des appareils...")
        devices = bluetooth_manager.scan_for_devices(5)
        print(f"✓ {len(devices)} appareils trouvés")
        
        for device in devices:
            print(f"  - {device['name']} ({device['mac']})")
    else:
        print("✗ Erreur d'initialisation")