"""
Secure Deleter — Multi-phase file destruction coordinator.

Orchestrates six destruction phases through specialized modules:

1. Content overwriting (multi-pass patterns)
2. MFT record corruption
3. MFT mirror destruction
4. Metadata journal wiping ($UsnJrnl, $LogFile)
5. Related-record elimination (directory refs, hard links, $Secure)
6. Hidden-space wiping (SSD only)

WARNING: This is IRREVERSIBLE. Data destroyed by this tool cannot be
recovered by any known forensic method.

Usage::

    from ntfs_toolkit.dangerous import SecureDeleter

    sd = SecureDeleter()
    sd.secure_delete_file(r"D:\\secret.docx", passes=7)
"""
import os
import time

from ntfs_toolkit.core.disk_writer import DiskWriter
from ntfs_toolkit.analyzers.comprehensive_analyzer import ComprehensiveAnalyzer
from ntfs_toolkit.analyzers.lba_reader import LBAReader
from ntfs_toolkit.dangerous.content_overwriter import ContentOverwriter
from ntfs_toolkit.dangerous.mft_destroyer import MFTDestroyer
from ntfs_toolkit.dangerous.metadata_wiper import MetadataWiper
from ntfs_toolkit.dangerous.reference_eliminator import ReferenceEliminator
from ntfs_toolkit.dangerous.ssd_handler import SSDHandler


class SecureDeleter:
    """Coordinate multi-layer secure file destruction."""

    def __init__(self, enable_aggressive_mode=False):
        self.disk_writer = DiskWriter(
            enable_aggressive_write=enable_aggressive_mode,
        )
        self.analyzer = ComprehensiveAnalyzer(self.disk_writer)
        self.reader = LBAReader(self.disk_writer)

        # BUG FIX: original SSDContentOverwriter never initialized
        # ssd_detector or trim_manager — now unified in SSDHandler
        self.ssd = SSDHandler(self.disk_writer)
        self.overwriter = ContentOverwriter(self.disk_writer)
        self.mft_destroyer = MFTDestroyer(self.disk_writer)
        self.metadata_wiper = MetadataWiper(self.disk_writer)
        self.ref_eliminator = ReferenceEliminator(self.disk_writer)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyze_file_structure(self, file_path):
        """Build the ``structure`` dict consumed by all destruction phases.

        BUG FIX: original called ``analyze_file_complete`` but the new
        ComprehensiveAnalyzer method is ``analyze``.  Also, original
        looked for ``lba_start`` key but extents use ``lba_absolute``.
        """
        # Uses the new clean analyzer
        analysis = self.analyzer.analyze(file_path)

        lba_ranges = []
        if analysis.get("extents"):
            for ext in analysis["extents"]:
                if ext.get("type") == "allocated":
                    # Convert cluster-level extent to sector-level range
                    lba = ext["lba_absolute"]
                    sectors = ext["size_bytes"] // 512
                    lba_ranges.append((lba, sectors))

        return {
            "path": file_path,
            "size": analysis.get("file_size", 0),
            "is_resident": analysis.get("is_resident", False),
            "mft_record": analysis["file_info"]["mft_record_number"],
            "drive_letter": analysis["drive_letter"],
            "lba_ranges": lba_ranges,
        }

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------

    @staticmethod
    def confirm_destruction(file_path):
        """Triple confirmation gate. Returns True only if user confirms all three."""
        print("\n" + "=" * 70)
        print("  IRREVERSIBLE DATA DESTRUCTION")
        print("=" * 70)
        print(f"Target: {file_path}")
        if os.path.exists(file_path):
            print(f"Size:   {os.path.getsize(file_path):,} bytes")
        print("=" * 70)

        try:
            if input("Type 'DESTROY' to continue: ").strip().upper() != "DESTROY":
                return False
            if input("Type the full path to confirm: ").strip() != file_path:
                return False
            if input("Type 'I_UNDERSTAND' for final confirm: ").strip().upper() != "I_UNDERSTAND":
                return False
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return False
        return True

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def secure_delete_file(self, file_path, passes=7):
        """Execute all destruction phases. Returns True on full success."""
        print(f"\nSTARTING SECURE DELETION: {file_path}")
        if not self.confirm_destruction(file_path):
            return False

        start = time.time()
        ok = True

        try:
            structure = self.analyze_file_structure(file_path)
            drive_info = self.ssd.get_drive_info(structure["drive_letter"])

            # Phase 1 — content overwrite
            if not self.overwriter.overwrite_file_content(structure, passes):
                ok = False
            # Phase 2 — MFT record corruption
            if not self.mft_destroyer.corrupt_mft_record(structure):
                ok = False
            # Phase 3 — MFT mirror destruction
            if not self.mft_destroyer.destroy_mft_mirror(structure):
                ok = False
            # Phase 4 — metadata wiping
            if not self.metadata_wiper.wipe_metadata_traces(structure):
                ok = False
            # Phase 5 — related records
            if not self.ref_eliminator.eliminate_related_records(structure):
                ok = False
            # Phase 6 — SSD hidden space (only if SSD)
            if drive_info["is_ssd"]:
                self.ssd.wipe_hidden_areas(structure["drive_letter"])

            elapsed = time.time() - start
            status = "SUCCESS" if ok else "PARTIAL"
            print(f"\nSECURE DELETION {status} in {elapsed:.1f}s")
            return ok

        except Exception as e:
            print(f"\nSECURE DELETION FAILED: {e}")
            return False
