"""
Dangerous write operations — opt-in only.

WARNING: Every module in this package performs raw disk writes that can
corrupt file systems, destroy data, or render drives unbootable.

Import explicitly to acknowledge the risk::

    from ntfs_toolkit.dangerous import LBAWriter, SecureDeleter
"""
from .lba_writer import LBAWriter
from .content_overwriter import ContentOverwriter
from .mft_destroyer import MFTDestroyer
from .metadata_wiper import MetadataWiper
from .reference_eliminator import ReferenceEliminator
from .ssd_handler import SSDHandler
from .secure_deleter import SecureDeleter

__all__ = [
    "LBAWriter",
    "ContentOverwriter",
    "MFTDestroyer",
    "MetadataWiper",
    "ReferenceEliminator",
    "SSDHandler",
    "SecureDeleter",
]
