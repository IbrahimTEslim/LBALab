"""Windows API wrappers and constants"""
import ctypes
from ctypes import wintypes

# Windows API Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_NO_BUFFERING = 0x20000000
INVALID_HANDLE_VALUE = -1

# FSCTL Constants
FSCTL_GET_RETRIEVAL_POINTERS = 0x90073
FSCTL_GET_NTFS_VOLUME_DATA = 0x90064
IOCTL_DISK_GET_PARTITION_INFO_EX = 0x00070048
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x560000

class WindowsAPI:
    """Windows API helper functions"""
    
    @staticmethod
    def is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    @staticmethod
    def close_handle(handle):
        if handle and handle != INVALID_HANDLE_VALUE:
            try:
                ctypes.windll.kernel32.CloseHandle(handle)
            except:
                pass
