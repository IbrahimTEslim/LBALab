# NTFS Forensics Tests

This directory is reserved for future test implementations.

## Planned Test Categories

### Unit Tests
- Individual function testing
- MFT record parsing validation
- Address calculation verification
- Error handling validation

### Integration Tests
- End-to-end workflow testing
- Cross-tool compatibility
- File system interaction testing

### Forensic Tests
- Known file analysis verification
- Deleted file recovery testing
- Fragmented file reconstruction
- Timeline analysis validation

## Test Data

Future test implementations will include:
- Sample MFT records
- Known file signatures
- Test disk images
- Validation datasets

## Usage

```bash
# Future test execution
python -m pytest tests/
python tests/test_mft_parsing.py
python tests/test_lba_calculations.py
```

## Contributing

When adding tests, ensure:
- Comprehensive coverage of core functionality
- Safe test data that doesn't require admin privileges
- Clear documentation of test purposes
- Validation against known good results