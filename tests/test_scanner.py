"""
Tests for scanner module.
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from src.scanner import MediaScanner, scan_directory


@pytest.fixture
def temp_photo_dir():
    """Create a temporary directory with sample files."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create sample files
    (temp_dir / "photo1.jpg").touch()
    (temp_dir / "photo2.JPG").touch()
    (temp_dir / "photo3.png").touch()
    (temp_dir / "video1.mp4").touch()
    (temp_dir / "video2.MOV").touch()
    (temp_dir / "document.txt").touch()  # Should be ignored

    # Create subdirectory
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "photo4.jpeg").touch()
    (subdir / "video3.avi").touch()

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


def test_scanner_finds_all_media_files(temp_photo_dir):
    """Test that scanner finds all media files recursively."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True)

    # Should find 7 media files (5 images + 2 videos in root, 1 image + 1 video in subdir)
    # But we created 5 in root + 2 in subdir = 7 total
    assert len(files) == 7


def test_scanner_non_recursive(temp_photo_dir):
    """Test that non-recursive scan only finds files in root."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=False)

    # Should find only files in root directory
    assert len(files) == 5


def test_scanner_case_insensitive(temp_photo_dir):
    """Test that scanner handles uppercase extensions."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True)

    # Check that both .jpg and .JPG files are found
    jpg_files = [f for f in files if f.suffix.lower() == '.jpg']
    assert len(jpg_files) >= 2


def test_scanner_ignores_non_media_files(temp_photo_dir):
    """Test that scanner ignores non-media files."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True)

    # Should not include document.txt
    txt_files = [f for f in files if f.suffix == '.txt']
    assert len(txt_files) == 0


def test_is_image(temp_photo_dir):
    """Test image file detection."""
    scanner = MediaScanner()
    jpg_file = temp_photo_dir / "photo1.jpg"

    assert scanner.is_image(jpg_file) is True


def test_is_video(temp_photo_dir):
    """Test video file detection."""
    scanner = MediaScanner()
    mp4_file = temp_photo_dir / "video1.mp4"

    assert scanner.is_video(mp4_file) is True


def test_get_file_stats(temp_photo_dir):
    """Test file statistics generation."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True)
    stats = scanner.get_file_stats(files)

    assert stats['total'] == 7
    assert stats['images'] == 4  # photo1.jpg, photo2.JPG, photo3.png, photo4.jpeg
    assert stats['videos'] == 3  # video1.mp4, video2.MOV, video3.avi
    assert '.jpg' in stats['by_extension']


def test_scanner_invalid_path():
    """Test scanner with invalid path."""
    scanner = MediaScanner()

    with pytest.raises(FileNotFoundError):
        scanner.scan(Path("/nonexistent/path"))


def test_scanner_file_instead_of_directory(temp_photo_dir):
    """Test scanner with file path instead of directory."""
    scanner = MediaScanner()
    file_path = temp_photo_dir / "photo1.jpg"

    with pytest.raises(ValueError):
        scanner.scan(file_path)


def test_convenience_function(temp_photo_dir):
    """Test convenience function."""
    files = scan_directory(temp_photo_dir)

    assert len(files) == 7
    assert all(isinstance(f, Path) for f in files)


def test_exclude_directory_by_name(temp_photo_dir):
    """Test excluding directories by exact name match."""
    scanner = MediaScanner()

    # Exclude 'subdir' directory
    files = scanner.scan(temp_photo_dir, recursive=True, exclude_patterns=['subdir'])

    # Should only find files in root (5 files), not in subdir
    assert len(files) == 5

    # Verify no files from subdir are included
    for f in files:
        assert 'subdir' not in str(f)


def test_exclude_multiple_patterns(temp_photo_dir):
    """Test excluding multiple patterns."""
    # Create another subdirectory
    cache_dir = temp_photo_dir / ".cache"
    cache_dir.mkdir()
    (cache_dir / "cached_photo.jpg").touch()

    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['subdir', '.cache'])

    # Should only find files in root (5 files)
    assert len(files) == 5


def test_exclude_glob_pattern(temp_photo_dir):
    """Test excluding using glob patterns."""
    # Create nested structure
    nested = temp_photo_dir / "2023" / "thumbnails"
    nested.mkdir(parents=True)
    (nested / "thumb.jpg").touch()

    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['*/thumbnails/*'])

    # Should not include thumbnail
    assert all('thumbnails' not in str(f) for f in files)


def test_exclude_hidden_directories(temp_photo_dir):
    """Test excluding hidden directories (starting with dot)."""
    # Create hidden directory
    hidden_dir = temp_photo_dir / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.jpg").touch()

    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['.hidden'])

    # Should not include files from hidden directory
    assert all('.hidden' not in str(f) for f in files)


def test_exclude_pattern_with_instance_init(temp_photo_dir):
    """Test excluding patterns set during scanner initialization."""
    scanner = MediaScanner(exclude_patterns=['subdir'])
    files = scanner.scan(temp_photo_dir, recursive=True)

    # Should only find files in root (5 files)
    assert len(files) == 5


def test_exclude_pattern_merge(temp_photo_dir):
    """Test that instance and method exclude patterns are merged."""
    # Create cache directory
    cache_dir = temp_photo_dir / ".cache"
    cache_dir.mkdir()
    (cache_dir / "cached.jpg").touch()

    # Initialize with one pattern
    scanner = MediaScanner(exclude_patterns=['subdir'])

    # Add another pattern in scan call
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['.cache'])

    # Should exclude both 'subdir' and '.cache'
    # Only 5 files in root should be found
    assert len(files) == 5
    assert all('subdir' not in str(f) for f in files)
    assert all('.cache' not in str(f) for f in files)


def test_exclude_no_match(temp_photo_dir):
    """Test that non-matching patterns don't exclude anything."""
    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['nonexistent_dir'])

    # Should find all files since pattern doesn't match anything
    assert len(files) == 7


def test_exclude_wildcard_pattern(temp_photo_dir):
    """Test excluding with wildcard patterns."""
    # Create multiple cache-like directories
    (temp_photo_dir / "cache1").mkdir()
    (temp_photo_dir / "cache1" / "photo.jpg").touch()
    (temp_photo_dir / "cache2").mkdir()
    (temp_photo_dir / "cache2" / "photo.jpg").touch()

    scanner = MediaScanner()
    files = scanner.scan(temp_photo_dir, recursive=True,
                        exclude_patterns=['cache*'])

    # Should exclude both cache1 and cache2
    assert all('cache' not in str(f) for f in files)


def test_exclude_convenience_function(temp_photo_dir):
    """Test exclude patterns with convenience function."""
    files = scan_directory(temp_photo_dir, recursive=True,
                          exclude_patterns=['subdir'])

    assert len(files) == 5
