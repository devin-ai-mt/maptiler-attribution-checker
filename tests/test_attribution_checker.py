import pytest
from attribution_checker import MapTilerAttributionChecker
from unittest.mock import MagicMock, patch

@pytest.fixture
def checker():
    with patch('attribution_checker.webdriver.Chrome') as mock_chrome:
        checker = MapTilerAttributionChecker()
        # Mock the WebDriver instance
        checker.driver = MagicMock()
        yield checker

def test_init(checker):
    """Test checker initialization."""
    assert isinstance(checker, MapTilerAttributionChecker)

def test_detect_leaflet_usage(checker):
    """Test detection of Leaflet usage."""
    # Mock page source with Leaflet indicators
    checker.driver.page_source = """
        <script src="leaflet.js"></script>
        <div class="leaflet-control-attribution">
            © MapTiler © OpenStreetMap contributors
        </div>
    """

    # Mock JavaScript execution result
    checker.driver.execute_script.return_value = {
        'tileUrls': ['https://api.maptiler.com/maps/basic/256/10/12/15.png'],
        'mapUrls': ['https://unpkg.com/leaflet@1.7.1/dist/leaflet.js']
    }

    result = checker._detect_map_usage(checker.driver.page_source,
                                     checker.driver.execute_script.return_value)

    assert result['using_maptiler'] == True
    assert result['library'] == 'Leaflet'
    assert len(result['indicators_found']) > 0

def test_detect_openlayers_usage(checker):
    """Test detection of OpenLayers usage."""
    # Mock page source with OpenLayers indicators
    checker.driver.page_source = """
        <script src="ol.js"></script>
        <div class="ol-attribution">
            © MapTiler © OpenStreetMap contributors
        </div>
    """

    # Mock JavaScript execution result
    checker.driver.execute_script.return_value = {
        'tileUrls': ['https://api.maptiler.com/maps/basic/256/10/12/15.png'],
        'mapUrls': ['https://cdn.jsdelivr.net/npm/ol@latest/dist/ol.js']
    }

    result = checker._detect_map_usage(checker.driver.page_source,
                                     checker.driver.execute_script.return_value)

    assert result['using_maptiler'] == True
    assert result['library'] == 'OpenLayers'
    assert len(result['indicators_found']) > 0

def test_check_attribution_leaflet(checker):
    """Test attribution checking for Leaflet."""
    # Mock attribution element
    mock_element = MagicMock()
    mock_element.text = "© MapTiler © OpenStreetMap contributors"
    checker.driver.find_elements.return_value = [mock_element]

    result = checker._check_attribution('Leaflet')

    assert result['has_proper_attribution'] == True
    assert len(result['issues']) == 0

def test_check_attribution_missing(checker):
    """Test detection of missing attribution."""
    # Mock missing attribution
    checker.driver.find_elements.return_value = []

    result = checker._check_attribution('Leaflet')

    assert result['has_proper_attribution'] == False
    assert len(result['issues']) > 0

def test_check_website_integration(checker):
    """Test complete website checking flow."""
    # Mock successful detection and attribution check
    checker.driver.page_source = "<script>L.map('map')</script>"
    checker.driver.execute_script.return_value = {
        'tileUrls': ['https://api.maptiler.com/maps/basic/256/10/12/15.png'],
        'mapUrls': ['leaflet.js']
    }

    mock_element = MagicMock()
    mock_element.text = "© MapTiler © OpenStreetMap contributors"
    checker.driver.find_elements.return_value = [mock_element]

    result = checker.check_website("https://example.com")

    assert result is not None
    assert result['uses_maptiler'] == True
    assert result['map_library'] == 'Leaflet'
    assert result['has_proper_attribution'] == True
