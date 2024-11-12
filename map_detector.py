from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

def check_page(url):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"\nChecking {url}")
        driver.get(url)
        time.sleep(5)

        result = driver.execute_script("""
            function findMapTilerInScripts() {
                return Array.from(document.scripts)
                    .some(s => s.textContent && s.textContent.includes('maptiler.com'));
            }

            function getOpenLayersConfig() {
                if (typeof ol === 'undefined') return [];
                try {
                    return window.map instanceof ol.Map ?
                        Array.from(map.getLayers().getArray())
                            .filter(layer => layer instanceof ol.layer.Tile)
                            .map(layer => layer.getSource().getUrls()?.[0] || '')
                            .filter(url => url.includes('maptiler.com')) : [];
                } catch (e) { return []; }
            }

            return {
                leaflet: {
                    present: typeof L !== 'undefined',
                    attribution: document.querySelector('.leaflet-control-attribution')?.innerHTML || '',
                    mapConfig: typeof L !== 'undefined' && findMapTilerInScripts()
                },
                openlayers: {
                    present: typeof ol !== 'undefined',
                    attribution: document.querySelector('.ol-attribution')?.innerHTML || '',
                    sources: getOpenLayersConfig()
                },
                maptiler: {
                    
                    urls: Array.from(document.querySelectorAll('img'))
                        .map(img => img.src)
                        .filter(src => src.includes('maptiler'))
                }
            };
        """)

        analysis = {
            'url': url,
            'using_maptiler': (
                len(result['maptiler']['urls']) > 0 or
                result['leaflet']['mapConfig'] or
                len(result.get('openlayers', {}).get('sources', [])) > 0
            ),
            'using_sdk': result['maptiler']['sdk'],
            'library': 'Leaflet' if result['leaflet']['present'] else 'OpenLayers' if result['openlayers']['present'] else None,
            'has_attribution': ('maptiler' in (
                result['leaflet']['attribution'] +
                result.get('openlayers', {}).get('attribution', '')
            ).lower()),
            'details': {
                'maptiler_urls_found': len(result['maptiler']['urls']) > 0,
                'maptiler_in_config': result['leaflet']['mapConfig'] or len(result.get('openlayers', {}).get('sources', [])) > 0,
                'attribution_text': result['leaflet']['attribution'] or result.get('openlayers', {}).get('attribution', '')
            }
        }

        return analysis

    finally:
        driver.quit()

def test_all_cases():
    test_cases = [
        'http://localhost:8080/leaflet_example.html',
        'http://localhost:8080/openlayers_no_attribution.html',
        'http://localhost:8080/verification/leaflet_no_attribution.html',
        'http://localhost:8080/verification/maptiler_sdk.html'
    ]

    results = []
    for url in test_cases:
        try:
            results.append(check_page(url))
        except Exception as e:
            print(f"Error testing {url}: {str(e)}")
            results.append({'url': url, 'error': str(e)})

    print("\nVerification Summary Report:")
    for result in results:
        if 'error' in result:
            print(f"\nTest Case: {result['url']}")
            print(f"Error: {result['error']}")
            continue

        print(f"\nTest Case: {result['url']}")
        print(f"Library: {result['library']}")
        print(f"Using MapTiler: {result['using_maptiler']}")
        print(f"Using SDK: {result['using_sdk']}")
        print(f"Has Attribution: {result['has_attribution']}")
        if result['using_maptiler'] and not result['has_attribution']:
            print("WARNING: MapTiler attribution missing!")

if __name__ == "__main__":
    test_all_cases()
