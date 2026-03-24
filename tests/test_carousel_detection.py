"""
Test carousel detection logic without dependencies
Run: python3 test_carousel_detection.py
"""

from enum import Enum

class ContentType(str, Enum):
    VIDEO = "video"
    CAROUSEL = "carousel"
    UNKNOWN = "unknown"

def _detect_content_type(info: dict) -> ContentType:
    """Copy of detection logic from downloader.py for isolated testing"""
    if 'entries' in info and info['entries']:
        entries = info['entries']
        if len(entries) > 1:
            image_extensions = {'jpg', 'jpeg', 'png', 'webp'}
            all_images = all(
                e.get('ext', '').lower() in image_extensions 
                for e in entries if e
            )
            if all_images:
                return ContentType.CAROUSEL
    return ContentType.VIDEO

def test_content_type_detection():
    print("Testing content type detection...\n")

    # Test 1: Video (no entries)
    video_info = {
        'title': 'My Travel Video',
        'ext': 'mp4',
        'duration': 120,
    }
    result = _detect_content_type(video_info)
    assert result == ContentType.VIDEO, f"Expected VIDEO, got {result}"
    print("✓ Test 1: Video detected correctly")

    # Test 2: Carousel with multiple images
    carousel_info = {
        'title': 'My Carousel Post',
        'entries': [
            {'ext': 'jpg', 'title': 'Image 1'},
            {'ext': 'jpg', 'title': 'Image 2'},
            {'ext': 'png', 'title': 'Image 3'},
        ]
    }
    result = _detect_content_type(carousel_info)
    assert result == ContentType.CAROUSEL, f"Expected CAROUSEL, got {result}"
    print("✓ Test 2: Carousel detected correctly")

    # Test 3: Single image (not a carousel)
    single_image_info = {
        'title': 'Single Image Post',
        'entries': [
            {'ext': 'jpg', 'title': 'Image 1'},
        ]
    }
    result = _detect_content_type(single_image_info)
    assert result == ContentType.VIDEO, f"Expected VIDEO for single image, got {result}"
    print("✓ Test 3: Single image treated as video")

    # Test 4: Mixed content (images + video) -> VIDEO
    mixed_info = {
        'title': 'Mixed Content',
        'entries': [
            {'ext': 'mp4', 'title': 'Video'},
            {'ext': 'jpg', 'title': 'Image'},
        ]
    }
    result = _detect_content_type(mixed_info)
    assert result == ContentType.VIDEO, f"Expected VIDEO for mixed, got {result}"
    print("✓ Test 4: Mixed content treated as video")

    # Test 5: Empty entries
    empty_entries_info = {
        'title': 'Empty Post',
        'entries': []
    }
    result = _detect_content_type(empty_entries_info)
    assert result == ContentType.VIDEO, f"Expected VIDEO for empty entries, got {result}"
    print("✓ Test 5: Empty entries treated as video")

    # Test 6: Carousel with webp images
    webp_carousel_info = {
        'title': 'WebP Carousel',
        'entries': [
            {'ext': 'webp', 'title': 'Image 1'},
            {'ext': 'webp', 'title': 'Image 2'},
        ]
    }
    result = _detect_content_type(webp_carousel_info)
    assert result == ContentType.CAROUSEL, f"Expected CAROUSEL for webp, got {result}"
    print("✓ Test 6: WebP carousel detected correctly")

    # Test 7: JPEG with capital extension
    jpeg_carousel_info = {
        'title': 'JPEG Carousel',
        'entries': [
            {'ext': 'JPEG', 'title': 'Image 1'},
            {'ext': 'JPG', 'title': 'Image 2'},
        ]
    }
    result = _detect_content_type(jpeg_carousel_info)
    assert result == ContentType.CAROUSEL, f"Expected CAROUSEL for JPEG/JPG, got {result}"
    print("✓ Test 7: JPEG/JPG carousel detected (case insensitive)")

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_content_type_detection()
