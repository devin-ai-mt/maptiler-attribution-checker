import pytest
from unittest.mock import Mock, patch
from web_crawler import MapTilerWebCrawler
from bs4 import BeautifulSoup
import json

@pytest.fixture
def crawler():
    return MapTilerWebCrawler(max_pages=10, max_depth=2, concurrency=2)

def test_init():
    """Test crawler initialization."""
    crawler = MapTilerWebCrawler()
    assert crawler.max_pages == 100
    assert crawler.max_depth == 3
    assert crawler.concurrency == 5
    assert len(crawler.visited_urls) == 0

def test_robots_parser(crawler):
    """Test robots.txt parsing."""
    with patch('urllib.robotparser.RobotFileParser') as mock_parser:
        mock_instance = Mock()
        mock_parser.return_value = mock_instance

        # Set up all required mock methods
        mock_instance.set_url.return_value = None
        mock_instance.read.return_value = None
        mock_instance.can_fetch.return_value = True

        # Test the method
        result = crawler._can_fetch('https://example.com/page')

        # Verify the complete chain of calls
        assert result == True
        mock_instance.set_url.assert_called_once_with('https://example.com/robots.txt')
        mock_instance.read.assert_called_once()
        mock_instance.can_fetch.assert_called_once_with('*', 'https://example.com/page')

def test_extract_links(crawler):
    """Test link extraction from HTML."""
    html = """
    <html>
        <body>
            <a href="https://example.com/page1">Link 1</a>
            <a href="/page2">Link 2</a>
            <a href="page3">Link 3</a>
        </body>
    </html>
    """
    base_url = 'https://example.com'
    links = crawler._extract_links(base_url, html)

    assert 'https://example.com/page1' in links
    assert 'https://example.com/page2' in links
    assert 'https://example.com/page3' in links

@patch('requests.get')
@patch('web_crawler.MapTilerAttributionChecker')
def test_crawl_url(mock_checker, mock_get, crawler):
    """Test crawling a single URL."""
    mock_response = Mock()
    mock_response.ok = True
    mock_response.text = '<html><a href="https://example.com/page2">Link</a></html>'
    mock_get.return_value = mock_response

    mock_checker_instance = Mock()
    mock_checker_instance.check_website.return_value = {'uses_maptiler': True}
    crawler.checker = mock_checker_instance

    links = crawler._crawl_url('https://example.com')
    assert 'https://example.com/page2' in links
    assert 'https://example.com' in crawler.visited_urls

@patch('requests.get')
def test_crawl_respects_max_pages(mock_get, crawler):
    """Test crawler respects max_pages limit."""
    mock_response = Mock()
    mock_response.ok = True
    mock_response.text = '<html><a href="https://example.com/page2">Link</a></html>'
    mock_get.return_value = mock_response

    crawler.max_pages = 2
    crawler.crawl(['https://example.com'])
    assert len(crawler.visited_urls) <= 2

def test_save_results(crawler, tmp_path):
    """Test saving results to file."""
    crawler.results = [{'url': 'https://example.com', 'uses_maptiler': True}]
    crawler.visited_urls = {'https://example.com'}

    output_file = tmp_path / "test_results.json"
    crawler.save_results(str(output_file))

    with open(output_file) as f:
        data = json.load(f)
        assert data['total_pages_crawled'] == 1
        assert data['maptiler_pages_found'] == 1
        assert len(data['results']) == 1

@patch('requests.get')
def test_crawl_handles_errors(mock_get, crawler):
    """Test crawler handles network errors gracefully."""
    mock_get.side_effect = Exception("Network error")
    crawler.crawl(['https://example.com'])
    assert len(crawler.results) == 0
    assert 'https://example.com' in crawler.visited_urls

def test_concurrent_crawling(crawler):
    """Test concurrent crawling functionality."""
    test_urls = [f'https://example.com/page{i}' for i in range(5)]
    with patch.object(crawler, '_crawl_url') as mock_crawl:
        mock_crawl.return_value = set()
        crawler.crawl(test_urls)
        assert mock_crawl.call_count == 5

if __name__ == '__main__':
    pytest.main(['-v'])
