# Amazon Choice Scraper

This Python script scrapes Amazon India's search results for products with the "Amazon's Choice" badge for a given set of keywords. It extracts product details and saves them to a CSV file.

## Features
- Rotates user agents and adds random delays to avoid rate-limiting
- Handles retries and backoff for HTTP errors (429, 503)
- Extracts product ASIN, title, price, URL, and badge context
- Outputs results to a CSV file

## Requirements
- Python 3.7+
- `requests`
- `beautifulsoup4`
- `pandas`

Install dependencies:
```bash
pip install requests beautifulsoup4 pandas
```

## Usage
Run the script:
```bash
python amazon-choice-scraping.py
```

The script will scrape Amazon for the following keywords:
- wireless earbuds
- office chair
- gaming laptop
- blender
- running shoes
- coffee maker

Results are saved to `amazons_choice.csv` in the current directory.

## Output
The CSV file contains columns:
- `keyword`: Search keyword used
- `asin`: Amazon product ASIN
- `title`: Product title
- `price`: Product price
- `url`: Product URL
- `badge_for`: Context for the "Amazon's Choice" badge (e.g., "for wireless earbuds")

## Notes
- The script is designed to be polite to Amazon's servers, but scraping may still be blocked or rate-limited.
- For best results, use a stable internet connection and avoid running the script too frequently.

## License
This project is for educational purposes only. Use responsibly and respect Amazon's terms of service.
