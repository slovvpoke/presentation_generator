#!/usr/bin/env python3
"""Test text width calculation"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sfapps_template_generator import _calculate_text_width

def test_text_width():
    print("🧪 Testing text width calculation:")
    print("-" * 50)
    
    # Test cases with different text lengths
    test_cases = [
        ("By Certinia", 27),
        ("By Astrea IT Services Pvt Ltd", 27),
        ("By Company", 27),
        ("By Very Long Company Name Inc Ltd", 27),
        ("By A", 27),
    ]
    
    for text, font_size in test_cases:
        width = _calculate_text_width(text, font_size)
        print(f"Text: '{text}'")
        print(f"  Font size: {font_size}pt")
        print(f"  Calculated width: {width:.1f}pt")
        print(f"  Length: {len(text)} chars")
        print()

if __name__ == "__main__":
    test_text_width()