import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
import time
from urllib.robotparser import RobotFileParser
import json
from datetime import datetime
from attribution_checker import MapTilerAttributionChecker

class MapTilerWebCrawler:
    def __init__(self, max_pages=100, max_depth=3, concurrency=5):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.visited_urls = set()
        self.robots_cache = {}
        self.results = []
        self.checker = MapTilerAttributionChecker()

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _get_robots_parser(self, base_url):
        """Get and cache robots.txt parser for a domain."""
        if base_url in self.robots_cache:
            return self.robots_cache[base_url]

        robots_url = urljoin(base_url, '/robots.txt')
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            self.robots_cache[base_url] = rp
        except Exception as e:
            self.logger.warning(f"Could not fetch robots.txt for {base_url}: {e}")
            return None
        return rp

    def _can_fetch(self, url):
        """Check if we're allowed to fetch the URL according to robots.txt."""
        try:
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            rp = self._get_robots_parser(base_url)
            if rp:
                return rp.can_fetch("*", url)
            return True
        except Exception:
            return True

    def _extract_links(self, url, html):
        """Extract links from HTML content."""
        links = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute_url = urljoin(url, href)
                if absolute_url.startswith(('http://', 'https://')):
                    links.add(absolute_url)
        except Exception as e:
            self.logger.error(f"Error extracting links from {url}: {e}")
        return links

    def _crawl_url(self, url, depth=0):
        """Crawl a single URL and check for MapTiler usage."""
        if depth > self.max_depth or url in self.visited_urls:
            return set()

        if not self._can_fetch(url):
            self.logger.info(f"Skipping {url} (robots.txt)")
            return set()

        self.visited_urls.add(url)
        self.logger.info(f"Crawling {url} (depth {depth})")

        try:
            # Check for MapTiler usage
            result = self.checker.check_website(url)
            if result and result.get('uses_maptiler'):
                self.results.append(result)
                self.logger.info(f"Found MapTiler usage on {url}")

            # Get links for further crawling
            response = requests.get(url, timeout=10)
            if not response.ok:
                return set()

            return self._extract_links(url, response.text)

        except Exception as e:
            self.logger.error(f"Error crawling {url}: {e}")
            return set()

    def crawl(self, start_urls):
        """Start crawling from given URLs."""
        if isinstance(start_urls, str):
            start_urls = [start_urls]

        urls_to_crawl = set(start_urls)
        current_depth = 0

        while urls_to_crawl and len(self.visited_urls) < self.max_pages and current_depth <= self.max_depth:
            new_urls = set()

            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                # Submit crawling tasks
                future_to_url = {
                    executor.submit(self._crawl_url, url, current_depth): url
                    for url in urls_to_crawl
                }

                # Process results and collect new URLs
                for future in future_to_url:
                    try:
                        new_urls.update(future.result())
                    except Exception as e:
                        self.logger.error(f"Error processing {future_to_url[future]}: {e}")

            urls_to_crawl = new_urls - self.visited_urls
            current_depth += 1

            # Rate limiting
            time.sleep(1)

    def save_results(self, output_file=None):
        """Save crawling results to a file."""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'maptiler_crawl_results_{timestamp}.json'

        results_data = {
            'timestamp': datetime.now().isoformat(),
            'total_pages_crawled': len(self.visited_urls),
            'maptiler_pages_found': len(self.results),
            'results': self.results
        }

        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)

        self.logger.info(f"Results saved to {output_file}")
        return output_file

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Crawl websites to find MapTiler usage')
    parser.add_argument('--urls', type=str, help='File containing start URLs (one per line)')
    parser.add_argument('--url', type=str, help='Single URL to start crawling from')
    parser.add_argument('--max-pages', type=int, default=100, help='Maximum number of pages to crawl')
    parser.add_argument('--max-depth', type=int, default=3, help='Maximum crawl depth')
    parser.add_argument('--concurrency', type=int, default=5, help='Number of concurrent crawlers')
    parser.add_argument('--output', type=str, help='Output file path')
    args = parser.parse_args()

    if not args.urls and not args.url:
        parser.error("Either --urls or --url must be provided")

    start_urls = []
    if args.urls:
        with open(args.urls, 'r') as f:
            start_urls.extend(line.strip() for line in f if line.strip())
    if args.url:
        start_urls.append(args.url)

    crawler = MapTilerWebCrawler(
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        concurrency=args.concurrency
    )

    crawler.crawl(start_urls)
    output_file = crawler.save_results(args.output)
    print(f"\nCrawling complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
