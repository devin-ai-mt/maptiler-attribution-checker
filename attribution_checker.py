import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import re
import json
from urllib.parse import urlparse
import time
import argparse
import csv
from datetime import datetime
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

class MapTilerAttributionChecker:
    def __init__(self):
        logging.info("Initializing MapTilerAttributionChecker...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            logging.info("Setting up Chrome WebDriver...")
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            logging.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
            raise

    def __del__(self):
        if hasattr(self, 'driver'):
            logging.info("Closing Chrome WebDriver...")
            self.driver.quit()

    def check_website(self, url):
        """Check a website for MapTiler map usage with Leaflet or OpenLayers."""
        logging.info(f"\nChecking website: {url}")
        try:
            # Load the page
            logging.info("Loading page...")
            self.driver.get(url)

            # Wait for page load and dynamic content
            logging.info("Waiting for page to load...")
            self.driver.implicitly_wait(15)  # Increased wait time
            time.sleep(10)  # Additional wait for dynamic content

            # Debug page state
            logging.info("Debugging page state...")
            page_title = self.driver.title
            logging.info(f"Page title: {page_title}")

            # Check for map elements with explicit waits
            logging.info("Checking for map elements...")
            try:
                # Check Leaflet elements
                leaflet_elements = self.driver.find_elements(By.CLASS_NAME, "leaflet-container")
                if leaflet_elements:
                    logging.info(f"Found {len(leaflet_elements)} Leaflet container(s)")
                    # Wait additional time for Leaflet to initialize
                    time.sleep(5)

                # Check OpenLayers elements
                ol_elements = self.driver.find_elements(By.CLASS_NAME, "ol-viewport")
                if ol_elements:
                    logging.info(f"Found {len(ol_elements)} OpenLayers viewport(s)")
                    # Wait additional time for OpenLayers to initialize
                    time.sleep(5)

                logging.info(f"Map elements found: Leaflet={bool(leaflet_elements)}, OpenLayers={bool(ol_elements)}")
            except Exception as e:
                logging.warning(f"Error checking map elements: {str(e)}")

            # Debug JavaScript environment
            logging.info("Debugging JavaScript environment...")
            js_debug = self.driver.execute_script("""
                return {
                    windowKeys: Object.keys(window),
                    hasL: typeof L !== 'undefined',
                    hasOl: typeof ol !== 'undefined',
                    documentReady: document.readyState,
                    mapElements: {
                        leaflet: document.querySelectorAll('.leaflet-container').length,
                        openlayers: document.querySelectorAll('.ol-viewport').length
                    }
                }
            """)
            logging.info(f"JavaScript debug info: {js_debug}")

            # Get page source and JavaScript variables
            logging.info("Getting page source and JavaScript variables...")
            page_source = self.driver.page_source
            js_variables = self._get_js_variables()

            # Check if using MapTiler with Leaflet or OpenLayers
            logging.info("Checking for MapTiler usage with Leaflet/OpenLayers...")
            usage_info = self._check_map_usage(page_source, js_variables)

            if not usage_info['using_maptiler']:
                logging.info("No MapTiler usage detected or SDK usage found (excluded)")
                return None

            logging.info(f"Found MapTiler usage with {usage_info['library']}")
            logging.info(f"Indicators found: {', '.join(usage_info['indicators_found'])}")

            # Check attribution elements
            logging.info("Checking attribution elements...")
            attribution_status = self._check_attribution(usage_info['library'])

            result = {
                'url': url,
                'uses_maptiler': True,
                'map_library': usage_info['library'],
                'maptiler_indicators': usage_info['indicators_found'],
                'has_proper_attribution': attribution_status['has_proper_attribution'],
                'issues': attribution_status['issues'],
                'timestamp': datetime.now().isoformat()
            }

            logging.info(f"Attribution check result: {'Proper' if result['has_proper_attribution'] else 'Improper'} attribution")
            if result['issues']:
                logging.warning(f"Attribution issues found: {', '.join(result['issues'])}")

            return result

        except Exception as e:
            logging.error(f"Error checking website {url}: {str(e)}")
            return {
                'url': url,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _get_js_variables(self):
        """Extract JavaScript variables and URLs from the page."""
        logging.info("Extracting JavaScript variables and URLs...")
        try:
            # Get all script tags and their sources
            scripts = self.driver.find_elements(By.TAG_NAME, "script")
            script_srcs = [script.get_attribute("src") or "" for script in scripts]
            logging.info(f"Found {len(script_srcs)} script sources")

            # Check for library presence and get tile URLs
            js_check_result = self.driver.execute_script("""
                return {
                    leaflet: {
                        present: typeof L !== 'undefined',
                        version: (typeof L !== 'undefined' && L.version) || null,
                        containers: document.querySelectorAll('.leaflet-container').length,
                        tileUrls: Array.from(document.querySelectorAll('.leaflet-tile')).map(tile => tile.src)
                    },
                    openlayers: {
                        present: typeof ol !== 'undefined',
                        version: (typeof ol !== 'undefined' && ol.VERSION) || null,
                        containers: document.querySelectorAll('.ol-viewport').length,
                        tileUrls: Array.from(document.querySelectorAll('.ol-layer canvas')).map(canvas => {
                            try {
                                return canvas.toDataURL();
                            } catch(e) {
                                return '';
                            }
                        })
                    }
                };
            """)

            logging.info(f"Library detection results: {js_check_result}")

            # Combine tile URLs from both libraries
            tile_urls = (js_check_result.get('leaflet', {}).get('tileUrls', []) +
                        js_check_result.get('openlayers', {}).get('tileUrls', []))

            return {
                'mapUrls': script_srcs,
                'tileUrls': tile_urls,
                'libraryInfo': js_check_result
            }
        except Exception as e:
            logging.error(f"Error extracting JavaScript variables: {str(e)}")
            return {
                'mapUrls': [],
                'tileUrls': [],
                'libraryInfo': {'leaflet': {'present': False}, 'openlayers': {'present': False}}
            }

    def _check_map_usage(self, page_source, js_variables):
        """Check if the page is using MapTiler with Leaflet or OpenLayers."""
        logging.info("Starting map usage detection...")

        library_info = js_variables.get('libraryInfo', {
            'leaflet': {'present': False},
            'openlayers': {'present': False}
        })
        logging.info(f"Processing library detection results: {library_info}")

        # Patterns to detect library usage
        library_patterns = {
            'leaflet': [
                'leaflet.js',
                'L.tileLayer',
                'class="leaflet-',
                'leaflet.css',
                'L.map(',
                'leaflet-container'
            ],
            'openlayers': [
                'ol.js',
                'ol/Map',
                'class="ol-',
                'ol.css',
                'new ol.Map',
                'ol-map',
                'ol.source.XYZ'
            ]
        }

        # Patterns to detect MapTiler usage
        maptiler_patterns = [
            'api.maptiler.com',
            'maps.maptiler.com',
            '.maptiler.com/maps/',
            '.maptiler.com/tiles/',
            'key=[a-zA-Z0-9]+',  # MapTiler API key pattern
            'maptiler',
            'tileserver.maptiler.com'
        ]

        found_indicators = []
        detected_library = None

        # Check for library usage
        logging.info("Checking for mapping library usage...")
        for library, patterns in library_patterns.items():
            library_found = False
            lib_info = library_info.get(library, {})

            # Check JavaScript detection first (most reliable)
            if lib_info.get('present', False):
                logging.info(f"Found {library} through JavaScript detection (version: {lib_info.get('version')})")
                library_found = True
                detected_library = library
                found_indicators.append(f"{library}:js_detection")

                # Check for containers
                containers = lib_info.get('containers', 0)
                if containers > 0:
                    logging.info(f"Found {containers} {library} container(s)")
                    found_indicators.append(f"{library}:containers:{containers}")

            # Check DOM patterns if JavaScript detection failed
            if not library_found:
                for pattern in patterns:
                    if pattern in page_source:
                        if not library_found:
                            logging.info(f"Found {library} through pattern matching: {pattern}")
                            library_found = True
                            if not detected_library:
                                detected_library = library
                        found_indicators.append(f"{library}:{pattern}")

            # Check script sources
            for url in js_variables['mapUrls']:
                if url and any(p in url.lower() for p in [library.lower(), library.lower() + '.min.js']):
                    if not library_found:
                        logging.info(f"Found {library} through script URL: {url}")
                        library_found = True
                        if not detected_library:
                            detected_library = library
                    found_indicators.append(f"{library}:script:{url}")

        # Check for MapTiler usage in various contexts
        logging.info("Checking for MapTiler usage...")
        maptiler_found = False

        # Check in tile URLs first (most reliable indicator)
        for url in js_variables['tileUrls']:
            for pattern in maptiler_patterns:
                if pattern in url:
                    if not maptiler_found:
                        logging.info(f"Found MapTiler tile URL: {url}")
                        maptiler_found = True
                    found_indicators.append(f"tile:{url}")

        # Check in script sources
        for url in js_variables['mapUrls']:
            if url:  # Only check non-empty URLs
                for pattern in maptiler_patterns:
                    if pattern in url:
                        if not maptiler_found:
                            logging.info(f"Found MapTiler script URL: {url}")
                            maptiler_found = True
                        found_indicators.append(f"script:{url}")

        # Check in page source
        for pattern in maptiler_patterns:
            if pattern in page_source:
                if not maptiler_found:
                    logging.info(f"Found MapTiler pattern in page source: {pattern}")
                    maptiler_found = True
                found_indicators.append(f"source:{pattern}")

        # Check if using MapTiler SDK (to exclude)
        sdk_indicators = ['@maptiler/sdk', 'maptilersdk', 'maptiler-sdk']
        using_sdk = any(indicator in page_source for indicator in sdk_indicators)
        if using_sdk:
            logging.info("Found MapTiler SDK usage - excluding from results")
            return {
                'using_maptiler': False,
                'library': None,
                'indicators_found': []
            }

        is_using_maptiler = len(found_indicators) > 0
        logging.info(f"Map usage detection complete. Using MapTiler: {is_using_maptiler}, Library: {detected_library}")
        if detected_library:
            logging.info(f"Detected indicators: {', '.join(found_indicators)}")

        return {
            'using_maptiler': is_using_maptiler,
            'library': detected_library,
            'indicators_found': found_indicators
        }

    def _check_attribution(self, library_type):
        """Check if proper attribution is present based on the library type."""
        logging.info(f"Checking attribution for {library_type} library...")

        if not library_type:
            return {
                'has_proper_attribution': False,
                'issues': ['Unknown library type: None']
            }

        # Common attribution patterns
        maptiler_attribution = [
            'maptiler',
            '© maptiler',
            'mapTiler',
            '© MapTiler',
            'MapTiler Cloud'
        ]

        osm_attribution = [
            'openstreetmap',
            '© openstreetmap',
            '© OpenStreetMap',
            'OpenStreetMap contributors'
        ]

        try:
            attribution_found = False
            attribution_elements = []

            # Check for attribution elements based on library type
            if library_type.lower() == 'leaflet':
                attribution_elements = self.driver.find_elements(By.CLASS_NAME, 'leaflet-control-attribution')
            elif library_type.lower() == 'openlayers':
                attribution_elements = self.driver.find_elements(By.CLASS_NAME, 'ol-attribution')

            if not attribution_elements:
                logging.warning(f"No attribution elements found for {library_type}")
                return {
                    'has_proper_attribution': False,
                    'issues': [f'No attribution element found for {library_type}']
                }

            # Check attribution text
            issues = []
            for element in attribution_elements:
                attribution_text = element.text.lower()
                logging.info(f"Found attribution text: {attribution_text}")

                maptiler_found = any(pattern.lower() in attribution_text for pattern in maptiler_attribution)
                osm_found = any(pattern.lower() in attribution_text for pattern in osm_attribution)

                if not maptiler_found:
                    issues.append('Missing MapTiler attribution')
                if not osm_found:
                    issues.append('Missing OpenStreetMap attribution')

                attribution_found = maptiler_found and osm_found
                if attribution_found:
                    break

            if attribution_found:
                logging.info("Proper attribution found")
                return {
                    'has_proper_attribution': True,
                    'issues': []
                }
            else:
                logging.warning(f"Attribution issues found: {', '.join(issues)}")
                return {
                    'has_proper_attribution': False,
                    'issues': issues
                }

        except Exception as e:
            logging.error(f"Error checking attribution: {str(e)}")
            return {
                'has_proper_attribution': False,
                'issues': [f'Error checking attribution: {str(e)}']
            }

def save_results(results, output_format='json', output_file=None):
    """Save results to a file in the specified format."""
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'maptiler_attribution_report_{timestamp}.{output_format}'

    if output_format == 'json':
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
    elif output_format == 'csv':
        if not results:
            return

        # Flatten the results for CSV format
        flattened_results = []
        for result in results:
            if result is None:
                continue
            flat_result = {
                'url': result['url'],
                'uses_maptiler': result.get('uses_maptiler', False),
                'map_library': result.get('map_library', ''),
                'has_proper_attribution': result.get('has_proper_attribution', False),
                'issues': '; '.join(result.get('issues', [])) if 'issues' in result else '',
                'indicators': '; '.join(result.get('maptiler_indicators', [])) if 'maptiler_indicators' in result else '',
                'error': result.get('error', ''),
                'timestamp': result['timestamp']
            }
            flattened_results.append(flat_result)

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flattened_results[0].keys())
            writer.writeheader()
            writer.writerows(flattened_results)

def main():
    parser = argparse.ArgumentParser(description='Check websites for proper MapTiler attribution in Leaflet/OpenLayers maps')
    parser.add_argument('--urls', type=str, help='File containing URLs to check (one per line)')
    parser.add_argument('--url', type=str, help='Single URL to check')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='Output format (default: json)')
    parser.add_argument('--output', type=str, help='Output file path')
    args = parser.parse_args()

    if not args.urls and not args.url:
        parser.error("Either --urls or --url must be provided")

    urls = []
    if args.urls:
        with open(args.urls, 'r') as f:
            urls.extend(line.strip() for line in f if line.strip())
    if args.url:
        urls.append(args.url)

    checker = MapTilerAttributionChecker()
    results = []

    for url in urls:
        print(f"Checking {url}...")
        result = checker.check_website(url)
        if result:
            results.append(result)
            print(f"Found MapTiler usage with {result.get('map_library', 'unknown library')}: "
                  f"{'Proper' if result.get('has_proper_attribution') else 'Improper'} attribution")
        else:
            print("No MapTiler usage detected or SDK usage found (excluded)")

    save_results(results, args.format, args.output)
    print(f"\nResults saved to {args.output or 'maptiler_attribution_report_<timestamp>.' + args.format}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
