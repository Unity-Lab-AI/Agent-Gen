r"""
# ================================================================
#   ____   ___   ____      _
#  / ___| / _ \ |  _ \    / \
# | |    | | | || |_) |  / _ \
# | |___ | |_| ||  _ <  / ___ \
#  \____| \___/ |_| \_\/_/   \_\
#
# C.O.R.A Media Control Module
# ================================================================
# Version: 1.0.0
# Unity AI Lab
# Website: https://www.unityailab.com
# GitHub: https://github.com/Unity-Lab-AI
# Contact: unityailabcontact@gmail.com
# Creators: Hackall360, Sponge, GFourteen, Alfreddo
# ================================================================
#
# Media control with multiple backends:
# 1. System Media Keys - Control ANY playing app (Spotify, VLC, etc)
# 2. Local File Playback - Play MP3/MP4 files directly
# 3. YouTube Playback - Play YouTube URLs
# 4. Emby (optional) - Control Emby media server if configured
#
# ================================================================
"""

# Split into the cora_tools.media_parts package on 2026-10-14; this module keeps every name it always had.
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import Any, Dict, List, Optional, Path, _media, get_media, json, os, re, subprocess, webbrowser  # noqa: F401
from cora_tools.media_parts.configuration import AUDIO_EXTENSIONS, CONFIG_DIR, MEDIA_CONFIG_FILE, MEDIA_EXTENSIONS, VIDEO_EXTENSIONS, load_media_config  # noqa: F401
from cora_tools.media_parts.system_media_keys_control_any import SystemMediaControl  # noqa: F401
from cora_tools.media_parts.local_file_playback import LocalMediaPlayer  # noqa: F401
from cora_tools.media_parts.youtube_playback import YouTubePlayer  # noqa: F401
from cora_tools.media_parts.emby_media_server_optional import EmbyControl  # noqa: F401
from cora_tools.media_parts.unified_media_controller import MediaController  # noqa: F401
from cora_tools.media_parts.global_instance_convenience_fu import mute, next_track, now, pause, play, prev_track, resume, stop, volume  # noqa: F401




# ================================================================
# MODULE TEST
# ================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  C.O.R.A Media Module v1.0.0")
    print("  Unity AI Lab")
    print("=" * 50)
    print()

    config = load_media_config()
    media = MediaController(config)

    print("[System Media Keys]")
    print(f"  Available: {media.system.available}")
    print(f"  Backend: {media.system._backend}")
    print(f"  Volume: {media.get_volume()}%")
    print()

    print("[YouTube Player]")
    print(f"  Method: {config.get('youtube_method', 'browser')}")
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"  Is YT URL: {media.youtube.is_youtube_url(test_url)}")
    print()

    print("[Local Player]")
    print(f"  Preferred: {config.get('local_player', 'default')}")
    print()

    print("[Emby]")
    if media.emby.configured:
        print(f"  Server: {config.get('emby_server')}:{config.get('emby_port')}")
        print(f"  Now Playing: {media.emby.now_playing()}")
    else:
        print("  Not configured (optional)")
    print()

    print("[Commands]")
    print("  play()              - Toggle play/pause")
    print("  play('song.mp3')    - Play local file")
    print("  play('youtube.com/...')  - Play YouTube")
    print("  play('search query')     - Search & play")
    print("  pause(), resume(), stop()")
    print("  next_track(), prev_track()")
    print("  volume(50), mute()")
    print()
    print("=" * 50)
