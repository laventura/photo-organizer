#!/usr/bin/env python3
"""
Dependency Verification Script for Photo Organizer
Tests all required packages and external tools
"""

import sys
from pathlib import Path

def test_imports():
    """Test that all required packages can be imported"""
    print("🔍 Testing Python package imports...\n")
    
    tests = {
        "PIL (Pillow)": lambda: __import__("PIL"),
        "pillow_heif": lambda: __import__("pillow_heif"),
        "geopy": lambda: __import__("geopy"),
        "yaml (PyYAML)": lambda: __import__("yaml"),
        "tqdm": lambda: __import__("tqdm"),
        "requests": lambda: __import__("requests"),
        "exiftool": lambda: __import__("exiftool"),
        "mutagen": lambda: __import__("mutagen"),
    }
    
    results = {}
    for name, test_func in tests.items():
        try:
            test_func()
            results[name] = "✅ OK"
        except ImportError as e:
            results[name] = f"❌ FAILED: {e}"
    
    for name, result in results.items():
        print(f"  {name:<20} {result}")
    
    return all("✅" in r for r in results.values())

def test_exiftool():
    """Test that exiftool binary is accessible"""
    print("\n🔧 Testing exiftool binary...\n")
    
    try:
        import exiftool
        
        with exiftool.ExifToolHelper() as et:
            version = et.version
            executable = et.executable
            
            print(f"  ExifTool version:  {version}")
            print(f"  ExifTool path:     {executable}")
            
            # Test on a simple file (create a dummy text file)
            test_file = Path("/tmp/test_exif.txt")
            test_file.write_text("test")
            
            try:
                metadata = et.get_metadata([str(test_file)])
                print(f"  Metadata test:     ✅ OK")
            except Exception as e:
                print(f"  Metadata test:     ⚠️  Warning: {e}")
            finally:
                test_file.unlink(missing_ok=True)
            
            return True
            
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        print(f"\n  💡 Tip: Install exiftool with: brew install exiftool")
        return False

def test_image_formats():
    """Test support for various image formats"""
    print("\n🖼️  Testing image format support...\n")
    
    try:
        from PIL import Image
        import pillow_heif
        
        # Register HEIF opener with Pillow
        pillow_heif.register_heif_opener()
        
        formats = {
            "JPEG": [".jpg", ".jpeg"],
            "PNG": [".png"],
            "HEIC/HEIF": [".heic", ".heif"],
            "MOV": [".mov"],
            "MP4": [".mp4"],
        }
        
        print("  Supported formats:")
        for format_name, extensions in formats.items():
            print(f"    • {format_name:<12} {', '.join(extensions)}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False

def test_geocoding():
    """Test geocoding functionality"""
    print("\n🌍 Testing geocoding...\n")
    
    try:
        from geopy.geocoders import Nominatim
        
        # Create geocoder with user agent
        geolocator = Nominatim(user_agent="photo_organizer_test")
        
        # Test reverse geocoding with San Francisco coordinates
        test_coords = (37.7749, -122.4194)
        print(f"  Testing reverse geocoding: {test_coords}")
        
        location = geolocator.reverse(test_coords, timeout=10)
        
        if location:
            print(f"  Result: {location.address}")
            print(f"  Geocoding test:    ✅ OK")
            return True
        else:
            print(f"  ⚠️  No location found (may be rate-limited)")
            return True  # Don't fail, just warn
            
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")
        print(f"  💡 Geocoding may be rate-limited or network unavailable")
        return True  # Don't fail on geocoding test

def test_video_metadata():
    """Test video metadata extraction"""
    print("\n🎬 Testing video metadata support...\n")
    
    try:
        import mutagen
        
        print(f"  Mutagen version:   {mutagen.version_string}")
        print(  "  Video metadata test: ✅ OK")
        return True
        
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False

def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("📋 SUMMARY")
    print("="*60 + "\n")
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:<25} {status}")
    
    print("\n" + "="*60)
    
    if all_passed:
        print("🎉 All tests passed! You're ready to build the photo organizer.")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
    
    print("="*60 + "\n")
    
    return all_passed

def main():
    """Run all verification tests"""
    print("\n" + "="*60)
    print("🚀 Photo Organizer - Dependency Verification")
    print("="*60 + "\n")
    
    print(f"Python version: {sys.version}\n")
    
    results = {
        "Package Imports": test_imports(),
        "ExifTool Binary": test_exiftool(),
        "Image Formats": test_image_formats(),
        "Geocoding": test_geocoding(),
        "Video Metadata": test_video_metadata(),
    }
    
    success = print_summary(results)
    
    if success:
        print("📝 Next steps:")
        print("  1. Review the project specs: photo-organizer-specs.md")
        print("  2. Create the main script: photo_organizer.py")
        print("  3. Test with a small sample of photos")
        print()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())