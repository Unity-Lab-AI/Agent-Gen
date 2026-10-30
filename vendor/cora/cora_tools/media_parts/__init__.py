#!/usr/bin/env python3
"""cora_tools.media_parts: parts of cora_tools/media.py; importing the package loads every part."""
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts import configuration as _configuration  # noqa: F401
from cora_tools.media_parts import system_media_keys_control_any as _system_media_keys_control_any  # noqa: F401
from cora_tools.media_parts import local_file_playback as _local_file_playback  # noqa: F401
from cora_tools.media_parts import youtube_playback as _youtube_playback  # noqa: F401
from cora_tools.media_parts import emby_media_server_optional as _emby_media_server_optional  # noqa: F401
from cora_tools.media_parts import unified_media_controller as _unified_media_controller  # noqa: F401
from cora_tools.media_parts import global_instance_convenience_fu as _global_instance_convenience_fu  # noqa: F401
