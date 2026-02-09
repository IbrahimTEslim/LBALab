#!/usr/bin/env python3
"""
CLI - Command-line interface with interactive mode
Contains main() and all CLI functionality
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import WindowsAPI
from modules import LBAReader, LBAWriter, ResidencyChecker, ComprehensiveAnalyzer

def main():
    """Main CLI with argument parsing and interactive mode"""
    parser = argparse.ArgumentParser(
        description="NTFS Forensics Toolkit - Modular Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --analyze-file "C:\\Windows\\notepad.exe"
  %(prog)s --read-lba 0:2048
  %(prog)s --check-residency "C:\\small_file.txt"
  %(prog)s --mft-record C:5 --hex
  %(prog)s --test
        """
    )
    
    parser.add_argument('--analyze-file', metavar='PATH', help='Analyze file and show LBA mapping')
    parser.add_argument('--read-lba', metavar='DRIVE:LBA', help='Read LBA (e.g., 0:2048)')
    parser.add_argument('--write-lba', metavar='DRIVE:LBA:DATA', help='Write LBA (e.g., 0:2048:"data")')
    parser.add_argument('--check-residency', metavar='PATH', help='Check if file is resident')
    parser.add_argument('--mft-record', metavar='DRIVE:RECORD', help='Analyze MFT record (e.g., C:5)')
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--hex', action='store_true', help='Show hex dump')
    parser.add_argument('--version', action='version', version='NTFS Forensics Toolkit 2.0.0 (Modular)')
    
    args = parser.parse_args()
    
    if not WindowsAPI.is_admin():
        print("⚠️  WARNING: Not running as Administrator.")
        print("   Some operations may fail.\n")
    
    try:
        if args.analyze_file:
            analyzer = ComprehensiveAnalyzer()
            analyzer.print_file_analysis(args.analyze_file)
        
        elif args.read_lba:
            try:
                drive_str, lba_str = args.read_lba.split(':')
                lba = int(lba_str)
                reader = LBAReader()
                
                if drive_str.isdigit():
                    drive_num = int(drive_str)
                    print(f"Reading LBA {lba} from PhysicalDrive{drive_num}")
                    data = reader.read_physical(drive_num, lba, 512)
                else:
                    print(f"Reading LBA {lba} from Volume {drive_str}:")
                    data = reader.read_volume(drive_str, lba, 512)
                
                print(f"Successfully read {len(data)} bytes\n")
                print(reader.hex_dump(data))
                
                if data[:4] == b'FILE':
                    print("\n*** Detected MFT record signature ***")
            except ValueError:
                print("Invalid format. Use DRIVE:LBA (e.g., 0:2048 or C:2048)")
        
        elif args.write_lba:
            try:
                parts = args.write_lba.split(':', 2)
                if len(parts) < 3:
                    print("Invalid format. Use DRIVE:LBA:DATA (e.g., 0:2048:\"data\")")
                    return 1
                
                drive_str, lba_str, data = parts
                lba = int(lba_str)
                writer = LBAWriter()
                
                if drive_str.isdigit():
                    writer.write_physical(int(drive_str), lba, data)
                else:
                    writer.write_volume(drive_str, lba, data)
            except ValueError:
                print("Invalid format. Use DRIVE:LBA:DATA (e.g., 0:2048:\"data\")")
        
        elif args.check_residency:
            checker = ResidencyChecker()
            is_resident = checker.is_file_resident(args.check_residency)
            file_size = os.path.getsize(args.check_residency)
            print(f"File: {args.check_residency}")
            print(f"Size: {file_size:,} bytes")
            print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
        
        elif args.mft_record:
            try:
                parts = args.mft_record.split(':')
                if len(parts) >= 2:
                    drive = parts[0].upper()
                    record_num = int(parts[1])
                    analyzer = ComprehensiveAnalyzer()
                    analyzer.analyze_mft_record(drive, record_num, args.hex)
                else:
                    print("Usage: --mft-record DRIVE:RECORD (e.g., C:5)")
            except ValueError:
                print("Invalid MFT record number")
        
        elif args.test:
            analyzer = ComprehensiveAnalyzer()
            analyzer.test_common_files()
        
        else:
            # Interactive mode
            interactive_mode()
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

def interactive_mode():
    """Interactive menu mode"""
    print("NTFS Forensics Toolkit - Interactive Mode (Modular)")
    print("=" * 50)
    
    analyzer = ComprehensiveAnalyzer()
    reader = LBAReader()
    writer = LBAWriter()
    checker = ResidencyChecker()
    
    while True:
        print("\nOptions:")
        print("1. Analyze file")
        print("2. Read LBA")
        print("3. Check file residency")
        print("4. Analyze MFT record")
        print("5. Write LBA")
        print("6. Quit")
        
        choice = input("\nChoose option (1-6): ").strip()
        
        if choice == "1":
            path = input("Enter file path: ").strip().strip('"')
            if path:
                try:
                    analyzer.print_file_analysis(path)
                except Exception as e:
                    print(f"Error: {e}")
        
        elif choice == "2":
            try:
                drive_input = input("Enter drive (0 for PhysicalDrive0, C for Volume C:): ").strip()
                lba = int(input("Enter LBA: "))
                
                if drive_input.isdigit():
                    drive_num = int(drive_input)
                    data = reader.read_physical(drive_num, lba, 512)
                    print(f"\nRead from PhysicalDrive{drive_num} LBA {lba}:")
                else:
                    data = reader.read_volume(drive_input, lba, 512)
                    print(f"\nRead from Volume {drive_input}: LBA {lba}:")
                
                print(reader.hex_dump(data))
                
                if data[:4] == b'FILE':
                    print("\n*** Detected MFT record signature ***")
            except ValueError:
                print("Invalid input")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "3":
            path = input("Enter file path: ").strip().strip('"')
            if path and os.path.exists(path):
                try:
                    is_resident = checker.is_file_resident(path)
                    file_size = os.path.getsize(path)
                    print(f"\nFile: {path}")
                    print(f"Size: {file_size:,} bytes")
                    print(f"Status: {'RESIDENT' if is_resident else 'NON-RESIDENT'}")
                except Exception as e:
                    print(f"Error: {e}")
        
        elif choice == "4":
            try:
                drive = input("Enter drive letter (default C): ").strip().upper() or "C"
                record_num = int(input("Enter MFT record number: "))
                show_hex = input("Show hex dump? (y/n): ").strip().lower().startswith('y')
                print()
                analyzer.analyze_mft_record(drive, record_num, show_hex)
            except ValueError:
                print("Invalid MFT record number")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "5":
            try:
                drive_input = input("Enter drive (0 for PhysicalDrive0, C for Volume C:): ").strip()
                lba = int(input("Enter LBA: "))
                data = input("Enter data to write: ").strip()
                
                if drive_input.isdigit():
                    writer.write_physical(int(drive_input), lba, data)
                else:
                    writer.write_volume(drive_input, lba, data)
            except ValueError:
                print("Invalid input")
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "6":
            break
        else:
            print("Invalid option")

if __name__ == "__main__":
    sys.exit(main())
