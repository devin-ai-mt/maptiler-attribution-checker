import logging
import json
import csv
from datetime import datetime
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)

class MapTilerAttributionChecker:
    def __init__(self):
        """Initialize the checker with Selenium WebDriver."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def __del__(self):
        """Clean up WebDriver resources."""
        if hasattr(self, 'driver'):
            self.driver.quit()

    def check_website(self, url):
        """Check a website for MapTiler usage and proper attribution."""
        try:
            logging.info(f"\nChecking {url}")
            self.driver.get(url)

            # Get page source and execute JavaScript to gather information
            page_source = self.driver.page_source.lower()
            js_variables = self._get_map_variables()

            # Detect map library and MapTiler usage
            detection_result = self._detect_map_usage(page_source, js_variables)

            if not detection_result['using_maptiler']:
                logging.info("No MapTiler usage detected")
                return None

            # Check attribution if MapTiler is being used
            attribution_result = self._check_attribution(detection_result['library'])

            result = {
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'uses_maptiler': detection_result['using_maptiler'],
                'map_library': detection_result['library'],
                'has_proper_attribution': attribution_result['has_proper_attribution'],
                'issues': attribution_result['issues'],
                'maptiler_indicators': detection_result['indicators_found']
            }

            return result

        except Exception as e:
            logging.error(f"Error checking {url}: {str(e)}")
            return {
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def _get_map_variables(self):
        """Execute JavaScript to gather map-related variables."""
        return self.driver.execute_script("""
            function getTileUrls() {
                const urls = [];
                document.querySelectorAll('img').forEach(img => {
                    if (img.src && img.src.includes('maptiler')) {
                        urls.push(img.src);
                    }
                });
                return urls;
            }

            function getMapUrls() {
                return Array.from(document.scripts)
                    .map(script => script.src)
                    .filter(src => src && src.includes('maptiler'));
            }

            return {
                tileUrls: getTileUrls(),
                mapUrls: getMapUrls()
            };
        """)

    def _detect_map_usage(self, page_source, js_variables):
        """Detect which map library is being used and if it's using MapTiler."""
        logging.info("Detecting map library usage...")

        # Patterns to check for library presence
        library_patterns = {
            'Leaflet': ['leaflet.js', 'L.map(', 'L.tileLayer('],
            'OpenLayers': ['ol.js', 'ol.Map', 'new ol.Map']
        }

        # Patterns to check for MapTiler usage
        maptiler_patterns = [
            'maptiler.com',
            'maptiler-cdn',
            'maptiler-server',
            'maptiler.org'
        ]

        detected_library = None
        found_indicators = []

        # Check for library usage
        for library, patterns in library_patterns.items():
            library_found = False
            for pattern in patterns:
                if pattern.lower() in page_source:
                    if not library_found:
                        logging.info(f"Found {library} through pattern: {pattern}")
                        library_found = True
                        if not detected_library:
                            detected_library = library
                    found_indicators.append(f"{library}:pattern:{pattern}")

            # Check script sources for library files
            for url in js_variables['mapUrls']:
                if any(pattern in url.lower() for pattern in [library.lower() + '.js',
                                                          library.lower() + '.min.js']):
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
