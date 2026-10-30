#!/usr/bin/env python3
"""
C.O.R.A Audio Device Management
Audio input/output device selection and configuration

Per ARCHITECTURE.md v1.0.0:
- Set up pyaudio for microphone input
- Handle audio device selection
- Configure audio settings
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Optional imports
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False


# Constants
PROJECT_DIR = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_DIR / 'config'
AUDIO_CONFIG_FILE = CONFIG_DIR / 'audio.json'

# Default audio settings
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_FORMAT = 'int16'


@dataclass
class AudioDevice:
    """Audio device information."""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_input: bool
    is_default: bool = False


@dataclass
class AudioConfig:
    """Audio configuration."""
    input_device: Optional[int] = None
    output_device: Optional[int] = None
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    chunk_size: int = DEFAULT_CHUNK_SIZE


class AudioManager:
    """Manages audio devices and settings."""

    def __init__(self):
        """Initialize audio manager."""
        self._pyaudio: Optional[Any] = None
        self._config = AudioConfig()
        self._input_devices: List[AudioDevice] = []
        self._output_devices: List[AudioDevice] = []

        self.load_config()
        self._enumerate_devices()

    def _enumerate_devices(self):
        """Enumerate available audio devices."""
        self._input_devices = []
        self._output_devices = []

        if PYAUDIO_AVAILABLE:
            self._enumerate_pyaudio()
        elif SD_AVAILABLE:
            self._enumerate_sounddevice()

    def _enumerate_pyaudio(self):
        """Enumerate devices using PyAudio."""
        try:
            p = pyaudio.PyAudio()
            default_input = p.get_default_input_device_info()['index']
            default_output = p.get_default_output_device_info()['index']

            for i in range(p.get_device_count()):
                try:
                    info = p.get_device_info_by_index(i)

                    if info['maxInputChannels'] > 0:
                        device = AudioDevice(
                            index=i,
                            name=info['name'],
                            channels=int(info['maxInputChannels']),
                            sample_rate=int(info['defaultSampleRate']),
                            is_input=True,
                            is_default=(i == default_input)
                        )
                        self._input_devices.append(device)

                    if info['maxOutputChannels'] > 0:
                        device = AudioDevice(
                            index=i,
                            name=info['name'],
                            channels=int(info['maxOutputChannels']),
                            sample_rate=int(info['defaultSampleRate']),
                            is_input=False,
                            is_default=(i == default_output)
                        )
                        self._output_devices.append(device)

                except Exception:
                    continue

            p.terminate()

        except Exception as e:
            print(f"[!] PyAudio enumeration error: {e}")

    def _enumerate_sounddevice(self):
        """Enumerate devices using sounddevice."""
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]

            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    device = AudioDevice(
                        index=i,
                        name=dev['name'],
                        channels=dev['max_input_channels'],
                        sample_rate=int(dev['default_samplerate']),
                        is_input=True,
                        is_default=(i == default_input)
                    )
                    self._input_devices.append(device)

                if dev['max_output_channels'] > 0:
                    device = AudioDevice(
                        index=i,
                        name=dev['name'],
                        channels=dev['max_output_channels'],
                        sample_rate=int(dev['default_samplerate']),
                        is_input=False,
                        is_default=(i == default_output)
                    )
                    self._output_devices.append(device)

        except Exception as e:
            print(f"[!] SoundDevice enumeration error: {e}")

    def get_input_devices(self) -> List[AudioDevice]:
        """Get list of input (microphone) devices.

        Returns:
            List of input AudioDevice objects
        """
        return self._input_devices

    def get_output_devices(self) -> List[AudioDevice]:
        """Get list of output (speaker) devices.

        Returns:
            List of output AudioDevice objects
        """
        return self._output_devices

    def get_default_input(self) -> Optional[AudioDevice]:
        """Get default input device.

        Returns:
            Default input device or None
        """
        for dev in self._input_devices:
            if dev.is_default:
                return dev
        return self._input_devices[0] if self._input_devices else None

    def get_default_output(self) -> Optional[AudioDevice]:
        """Get default output device.

        Returns:
            Default output device or None
        """
        for dev in self._output_devices:
            if dev.is_default:
                return dev
        return self._output_devices[0] if self._output_devices else None

    def set_input_device(self, device_index: int) -> bool:
        """Set input device by index.

        Args:
            device_index: Device index

        Returns:
            True if set successfully
        """
        for dev in self._input_devices:
            if dev.index == device_index:
                self._config.input_device = device_index
                self.save_config()
                return True
        return False

    def set_output_device(self, device_index: int) -> bool:
        """Set output device by index.

        Args:
            device_index: Device index

        Returns:
            True if set successfully
        """
        for dev in self._output_devices:
            if dev.index == device_index:
                self._config.output_device = device_index
                self.save_config()
                return True
        return False

    def get_config(self) -> AudioConfig:
        """Get current audio configuration.

        Returns:
            AudioConfig object
        """
        return self._config

    def load_config(self) -> bool:
        """Load audio configuration from file.

        Returns:
            True if loaded successfully
        """
        try:
            if AUDIO_CONFIG_FILE.exists():
                with open(AUDIO_CONFIG_FILE) as f:
                    data = json.load(f)
                    self._config = AudioConfig(
                        input_device=data.get('input_device'),
                        output_device=data.get('output_device'),
                        sample_rate=data.get('sample_rate', DEFAULT_SAMPLE_RATE),
                        channels=data.get('channels', DEFAULT_CHANNELS),
                        chunk_size=data.get('chunk_size', DEFAULT_CHUNK_SIZE)
                    )
                return True
        except Exception as e:
            print(f"[!] Audio config load error: {e}")
        return False

    def save_config(self) -> bool:
        """Save audio configuration to file.

        Returns:
            True if saved successfully
        """
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                'input_device': self._config.input_device,
                'output_device': self._config.output_device,
                'sample_rate': self._config.sample_rate,
                'channels': self._config.channels,
                'chunk_size': self._config.chunk_size
            }
            with open(AUDIO_CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"[!] Audio config save error: {e}")
            return False

    def test_input(self, device_index: Optional[int] = None, duration: float = 1.0) -> bool:
        """Test input device by recording briefly.

        Args:
            device_index: Device to test (or default)
            duration: Test duration in seconds

        Returns:
            True if test successful
        """
        if not PYAUDIO_AVAILABLE and not SD_AVAILABLE:
            return False

        try:
            if SD_AVAILABLE:
                idx = device_index or self._config.input_device
                recording = sd.rec(
                    int(duration * self._config.sample_rate),
                    samplerate=self._config.sample_rate,
                    channels=self._config.channels,
                    device=idx
                )
                sd.wait()
                return len(recording) > 0
            return False

        except Exception as e:
            print(f"[!] Input test error: {e}")
            return False


# Global audio manager instance
_audio_manager: Optional[AudioManager] = None


def get_audio_manager() -> AudioManager:
    """Get or create global audio manager.

    Returns:
        AudioManager instance
    """
    global _audio_manager
    if _audio_manager is None:
        _audio_manager = AudioManager()
    return _audio_manager


# Convenience functions

def list_input_devices() -> List[Dict[str, Any]]:
    """List available input devices.

    Returns:
        List of device info dicts
    """
    manager = get_audio_manager()
    return [
        {
            'index': dev.index,
            'name': dev.name,
            'channels': dev.channels,
            'sample_rate': dev.sample_rate,
            'is_default': dev.is_default
        }
        for dev in manager.get_input_devices()
    ]


def list_output_devices() -> List[Dict[str, Any]]:
    """List available output devices.

    Returns:
        List of device info dicts
    """
    manager = get_audio_manager()
    return [
        {
            'index': dev.index,
            'name': dev.name,
            'channels': dev.channels,
            'sample_rate': dev.sample_rate,
            'is_default': dev.is_default
        }
        for dev in manager.get_output_devices()
    ]


def set_input_device(index: int) -> bool:
    """Set input device by index.

    Args:
        index: Device index

    Returns:
        True if set successfully
    """
    return get_audio_manager().set_input_device(index)


def set_output_device(index: int) -> bool:
    """Set output device by index.

    Args:
        index: Device index

    Returns:
        True if set successfully
    """
    return get_audio_manager().set_output_device(index)


def play_audio(audio_data, sample_rate: int = 22050, device: Optional[int] = None, blocking: bool = True):
    """Play audio data through sounddevice.

    Args:
        audio_data: NumPy array of audio samples
        sample_rate: Audio sample rate (default 22050 for TTS)
        device: Output device index (or default)
        blocking: Wait for playback to complete

    Returns:
        bool: True if playback started/completed successfully
    """
    if not SD_AVAILABLE:
        print("[!] sounddevice not available for playback")
        return False

    try:
        manager = get_audio_manager()
        out_device = device if device is not None else manager._config.output_device

        sd.play(audio_data, samplerate=sample_rate, device=out_device)
        if blocking:
            sd.wait()
        return True

    except Exception as e:
        print(f"[!] Audio playback error: {e}")
        return False


def stop_playback():
    """Stop any currently playing audio."""
    if SD_AVAILABLE:
        try:
            sd.stop()
        except Exception:
            pass


def get_audio_status() -> Dict[str, Any]:
    """Get audio system status.

    Returns:
        Dict with library availability, device counts, etc.
    """
    manager = get_audio_manager()
    return {
        'pyaudio_available': PYAUDIO_AVAILABLE,
        'sounddevice_available': SD_AVAILABLE,
        'input_devices': len(manager.get_input_devices()),
        'output_devices': len(manager.get_output_devices()),
        'default_input': manager.get_default_input().name if manager.get_default_input() else None,
        'default_output': manager.get_default_output().name if manager.get_default_output() else None,
        'config': {
            'input_device': manager._config.input_device,
            'output_device': manager._config.output_device,
            'sample_rate': manager._config.sample_rate
        }
    }


if __name__ == "__main__":
    print("=== AUDIO DEVICE MANAGER TEST ===")

    print("\nAvailable libraries:")
    print(f"  PyAudio: {PYAUDIO_AVAILABLE}")
    print(f"  SoundDevice: {SD_AVAILABLE}")

    if not PYAUDIO_AVAILABLE and not SD_AVAILABLE:
        print("\n[!] No audio library available!")
        print("Install: pip install pyaudio  or  pip install sounddevice")
        sys.exit(1)

    manager = get_audio_manager()

    print("\n--- Input Devices (Microphones) ---")
    for dev in manager.get_input_devices():
        default = " [DEFAULT]" if dev.is_default else ""
        print(f"  [{dev.index}] {dev.name} - {dev.channels}ch @ {dev.sample_rate}Hz{default}")

    print("\n--- Output Devices (Speakers) ---")
    for dev in manager.get_output_devices():
        default = " [DEFAULT]" if dev.is_default else ""
        print(f"  [{dev.index}] {dev.name} - {dev.channels}ch @ {dev.sample_rate}Hz{default}")

    print("\n--- Current Config ---")
    config = manager.get_config()
    print(f"  Input device: {config.input_device}")
    print(f"  Output device: {config.output_device}")
    print(f"  Sample rate: {config.sample_rate}")
    print(f"  Channels: {config.channels}")
