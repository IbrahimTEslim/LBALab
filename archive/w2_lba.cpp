#include <iostream>
#include <string>
#include <windows.h>
#include <cstring>
#include <cstdint>

#define SECTOR_SIZE 512

bool readFromVolume(uint64_t sectorOffset, const std::string& volumeLetter) {
    std::string volumePath = "\\\\.\\" + volumeLetter + ":";
    
    HANDLE hVolume = CreateFileA(
        volumePath.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING,
        NULL
    );
    
    if (hVolume == INVALID_HANDLE_VALUE) {
        std::cerr << "Error: Cannot open volume for reading" << std::endl;
        return false;
    }
    
    // Seek to sector
    LARGE_INTEGER offset;
    offset.QuadPart = sectorOffset * SECTOR_SIZE;
    SetFilePointerEx(hVolume, offset, NULL, FILE_BEGIN);
    
    // Read sector
    char* buffer = (char*)VirtualAlloc(NULL, SECTOR_SIZE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    DWORD bytesRead;
    
    if (ReadFile(hVolume, buffer, SECTOR_SIZE, &bytesRead, NULL)) {
        std::cout << "Read " << bytesRead << " bytes from sector " << sectorOffset << std::endl;
        std::cout << "First 64 bytes as hex: ";
        for (int i = 0; i < 64 && i < bytesRead; i++) {
            printf("%02X ", (unsigned char)buffer[i]);
        }
        std::cout << std::endl;
        
        std::cout << "First 64 bytes as text: ";
        for (int i = 0; i < 64 && i < bytesRead; i++) {
            char c = buffer[i];
            if (c >= 32 && c <= 126) {
                std::cout << c;
            } else {
                std::cout << ".";
            }
        }
        std::cout << std::endl;
    }
    
    VirtualFree(buffer, 0, MEM_RELEASE);
    CloseHandle(hVolume);
    return true;
}

bool writeToVolume(const std::string& payload, uint64_t sectorOffset, const std::string& volumeLetter, bool skipLocking = true) {
    // Enable SeManageVolumePrivilege
    HANDLE hToken;
    TOKEN_PRIVILEGES tokenPriv;
    
    if (OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
        LookupPrivilegeValue(NULL, SE_MANAGE_VOLUME_NAME, &tokenPriv.Privileges[0].Luid);
        tokenPriv.PrivilegeCount = 1;
        tokenPriv.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
        AdjustTokenPrivileges(hToken, FALSE, &tokenPriv, 0, NULL, NULL);
        CloseHandle(hToken);
    }
    
    // Construct volume path (e.g., \\.\D:)
    std::string volumePath = "\\\\.\\" + volumeLetter + ":";
    
    std::cout << "Attempting to open volume: " << volumePath << std::endl;
    std::cout << "IMPORTANT: Close any files/folders open on " << volumeLetter << ": drive!" << std::endl;
    std::cout << "Press Enter when ready...";
    std::cin.get();
    
    // Open the volume
    HANDLE hVolume = CreateFileA(
        volumePath.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH,
        NULL
    );
    
    if (hVolume == INVALID_HANDLE_VALUE) {
        std::cerr << "Error: Cannot open volume " << volumePath << std::endl;
        std::cerr << "Error code: " << GetLastError() << std::endl;
        return false;
    }
    
    // Lock the volume
    std::cout << "Attempting to lock volume..." << std::endl;
    DWORD bytesReturned;
    if (!DeviceIoControl(hVolume, FSCTL_LOCK_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL)) {
        std::cerr << "Error: Cannot lock volume. Error code: " << GetLastError() << std::endl;
        std::cerr << "Make sure no programs are using the " << volumeLetter << ": drive" << std::endl;
        CloseHandle(hVolume);
        return false;
    }
    
    std::cout << "Volume locked successfully." << std::endl;
    
    // Dismount the volume
    std::cout << "Dismounting volume..." << std::endl;
    if (!DeviceIoControl(hVolume, FSCTL_DISMOUNT_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL)) {
        std::cerr << "Warning: Cannot dismount volume. Error code: " << GetLastError() << std::endl;
        // Continue anyway - sometimes dismount fails but write still works
    }
    
    // Calculate the byte offset from sector
    LARGE_INTEGER offset;
    offset.QuadPart = sectorOffset * SECTOR_SIZE;
    
    // Seek to the specified sector position
    if (SetFilePointerEx(hVolume, offset, NULL, FILE_BEGIN) == 0) {
        std::cerr << "Error: Cannot seek to sector " << sectorOffset << std::endl;
        std::cerr << "Error code: " << GetLastError() << std::endl;
        
        // Unlock volume before closing
        DeviceIoControl(hVolume, FSCTL_UNLOCK_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL);
        CloseHandle(hVolume);
        return false;
    }
    
    // Prepare the sector buffer - must be aligned for unbuffered I/O
    char* sector = (char*)VirtualAlloc(NULL, SECTOR_SIZE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (sector == NULL) {
        std::cerr << "Error: Cannot allocate aligned memory" << std::endl;
        DeviceIoControl(hVolume, FSCTL_UNLOCK_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL);
        CloseHandle(hVolume);
        return false;
    }
    
    // Initialize with zeros
    memset(sector, 0, SECTOR_SIZE);
    
    // Copy payload to sector buffer
    size_t copySize = std::min(payload.length(), (size_t)SECTOR_SIZE);
    memcpy(sector, payload.c_str(), copySize);
    
    // Write the sector
    std::cout << "Writing sector..." << std::endl;
    DWORD bytesWritten = 0;
    BOOL result = WriteFile(hVolume, sector, SECTOR_SIZE, &bytesWritten, NULL);
    
    if (!result || bytesWritten != SECTOR_SIZE) {
        std::cerr << "Error: Failed to write complete sector. Written: " << bytesWritten << " bytes" << std::endl;
        std::cerr << "Error code: " << GetLastError() << std::endl;
        VirtualFree(sector, 0, MEM_RELEASE);
        if (!skipLocking) {
            DeviceIoControl(hVolume, FSCTL_UNLOCK_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL);
        }
        CloseHandle(hVolume);
        return false;
    }
    
    // Force write to disk
    if (!FlushFileBuffers(hVolume)) {
        std::cerr << "Warning: Failed to flush data to disk" << std::endl;
    }
    
    std::cout << "Write successful!" << std::endl;
    
    // Unlock the volume (only if we locked it)
    if (!skipLocking) {
        std::cout << "Unlocking volume..." << std::endl;
        if (!DeviceIoControl(hVolume, FSCTL_UNLOCK_VOLUME, NULL, 0, NULL, 0, &bytesReturned, NULL)) {
            std::cerr << "Warning: Cannot unlock volume. Error code: " << GetLastError() << std::endl;
        }
    }
    
    // Clean up
    VirtualFree(sector, 0, MEM_RELEASE);
    CloseHandle(hVolume);
    
    std::cout << "Successfully wrote " << copySize << " bytes to sector " << sectorOffset 
              << " on volume " << volumeLetter << ":" << std::endl;
    
    return true;
}

int main() {
    // Set your parameters here
    std::string payload = "Hello World";  // Your data to write
    uint64_t sectorOffset = 13364696;          // Target sector within the volume (try a low number first!)
    std::string volumeLetter = "D";       // Volume letter (D for D: drive)
    
    std::cout << "DEBUG: Writing to sector " << sectorOffset << " on volume " << volumeLetter << std::endl;
    std::cout << "This corresponds to byte offset: " << (sectorOffset * 512) << std::endl;
    
    std::cout << "WARNING: This will directly modify disk sectors on volume " << volumeLetter << ":!" << std::endl;
    std::cout << "Payload: \"" << payload << "\"" << std::endl;
    std::cout << "Sector: " << sectorOffset << " (relative to volume start)" << std::endl;
    std::cout << "Volume: " << volumeLetter << ":" << std::endl;
    std::cout << "Continue? (y/N): ";
    
    char confirm;
    std::cin >> confirm;
    std::cin.ignore(); // consume newline
    
    if (confirm != 'y' && confirm != 'Y') {
        std::cout << "Operation cancelled." << std::endl;
        return 0;
    }
    
    // Read before writing
    std::cout << "\n=== BEFORE WRITE ===" << std::endl;
    readFromVolume(sectorOffset, volumeLetter);
    
    if (writeToVolume(payload, sectorOffset, volumeLetter)) {
        std::cout << "Write operation completed successfully." << std::endl;
        
        // Read after writing to verify
        std::cout << "\n=== AFTER WRITE ===" << std::endl;
        readFromVolume(sectorOffset, volumeLetter);
        
        return 0;
    } else {
        std::cout << "Write operation failed." << std::endl;
        return 1;
    }
}