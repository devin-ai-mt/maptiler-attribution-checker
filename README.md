# MapTiler Attribution Checker

This script checks websites for proper MapTiler map attribution.

## Usage

```bash
# Check a single URL
python attribution_checker.py --url https://example.com

# Check multiple URLs from a file
python attribution_checker.py --urls urls.txt

# Specify output format (json or csv)
python attribution_checker.py --urls urls.txt --format csv

# Specify custom output file
python attribution_checker.py --urls urls.txt --output report.json
```

## Requirements

- Python 3.x
- Chrome/Chromium browser
- Required Python packages (install using pip):
  - requests
  - beautifulsoup4
  - selenium
  - webdriver-manager

## Installation

```bash
pip install requests beautifulsoup4 selenium webdriver-manager
```

## Output Format

The script generates a report containing:
- URL checked
- Whether MapTiler is being used
- Attribution status
- Specific issues found
- Indicators of MapTiler usage
- Timestamp of check

## Attribution Requirements

Based on MapTiler SDK requirements:
1. Attribution control must be present
2. MapTiler logo is required for free plans
3. Attribution text must include MapTiler
4. Copyright notice must be included
