#!/usr/bin/env python3
"""
Test script to verify CSS selector functionality
"""

from enhanced_parser import enhanced_fetch_app_metadata

def test_parser():
    # Test URL
    test_url = 'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ'
    
    print('🧪 Testing enhanced parser with updated CSS selectors')
    print('=' * 60)
    print(f'URL: {test_url}')
    print()
    
    print('🔄 Testing without Selenium:')
    try:
        metadata = enhanced_fetch_app_metadata(test_url, use_selenium=False)
        
        if metadata:
            print(f'✅ Name: {metadata.name}')
            print(f'✅ Developer: {metadata.developer}')
            print(f'✅ Logo: {len(metadata.logo_bytes)} bytes')
            print(f'✅ Logo MIME: {metadata.logo_mime}')
        else:
            print('❌ No metadata extracted')
    except Exception as e:
        print(f'❌ Error: {e}')

if __name__ == '__main__':
    test_parser()