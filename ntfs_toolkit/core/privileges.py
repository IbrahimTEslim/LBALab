"""Windows privilege management for disk operations."""
import ctypes
from ctypes import wintypes

from .windows_api import (
    SE_MANAGE_VOLUME_PRIVILEGE, SE_PRIVILEGE_ENABLED,
    TOKEN_QUERY, TOKEN_ADJUST_PRIVILEGES,
)
from .ntfs_structures import TOKEN_PRIVILEGES


def enable_manage_volume_privilege(verbose=False):
    """Enable SeManageVolumePrivilege for advanced disk operations.

    Returns True on success, False otherwise.
    """
    try:
        h_token = wintypes.HANDLE()
        if not ctypes.windll.advapi32.OpenProcessToken(
            ctypes.windll.kernel32.GetCurrentProcess(),
            TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES,
            ctypes.byref(h_token),
        ):
            return False

        try:
            luid = wintypes.LARGE_INTEGER()
            if not ctypes.windll.advapi32.LookupPrivilegeValueW(
                None, SE_MANAGE_VOLUME_PRIVILEGE, ctypes.byref(luid)
            ):
                return False

            token_privs = TOKEN_PRIVILEGES()
            token_privs.PrivilegeCount = 1
            token_privs.Privileges[0].Luid = luid
            token_privs.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

            if ctypes.windll.advapi32.AdjustTokenPrivileges(
                h_token, False, ctypes.byref(token_privs),
                ctypes.sizeof(TOKEN_PRIVILEGES), None, None,
            ):
                error = ctypes.windll.kernel32.GetLastError()
                if error == 0:
                    if verbose:
                        print("SeManageVolumePrivilege enabled successfully")
                    return True
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(h_token)

    except Exception:
        return False
