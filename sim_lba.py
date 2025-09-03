import os

SECTOR_SIZE = 1

def write_virtual_lba(disk_file, lba, data_bytes):
    if len(data_bytes) % SECTOR_SIZE != 0:
        raise ValueError("Data must be multiple of sector size")
    with open(disk_file, "r+b") as f:
        f.seek(lba * SECTOR_SIZE)
        f.write(data_bytes)
    print(f"Wrote {len(data_bytes)} bytes to LBA {lba} in {disk_file}")

def read_virtual_lba(disk_file, lba, num_sectors=1):
    with open(disk_file, "rb") as f:
        f.seek(lba * SECTOR_SIZE)
        return f.read(num_sectors * SECTOR_SIZE)

# Example usage
if __name__ == "__main__":
    disk_file = "virtual_disk.bin"
    
    # Create a 10 MB virtual disk if not exists
    if not os.path.exists(disk_file):
        with open(disk_file, "wb") as f:
            f.truncate(10 * 1024 * 1024)
    
    # Write to LBA 100
    write_virtual_lba(disk_file, 10, b"A" * SECTOR_SIZE)
    
    # Read back
    data = read_virtual_lba(disk_file, 9, 2)
    print(data)
