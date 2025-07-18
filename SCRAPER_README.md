# Advanced Web Scraper for High-Security Websites

This is an optimized web scraper specifically designed to handle high-security websites like **sahibinden.com** and **hepsiemlak.com** that employ advanced bot detection mechanisms.

## 🚀 Key Features

### Anti-Detection Mechanisms

- **Cloudscraper Integration**: Automatically bypasses Cloudflare protection
- **Dynamic User-Agent Rotation**: Randomly rotates browser user agents
- **Realistic Browser Headers**: Mimics real browser behavior
- **Intelligent Rate Limiting**: Prevents triggering rate limits
- **Session Rotation**: Automatically rotates sessions to avoid detection
- **Proxy Support**: Optional proxy rotation for additional anonymity

### Content Validation

- **HTML Structure Validation**: Ensures retrieved content is legitimate
- **Blocking Detection**: Detects various blocking mechanisms
- **Content Length Verification**: Validates minimum content requirements
- **Website-Specific Validation**: Checks for expected content patterns

### Error Handling & Recovery

- **Exponential Backoff**: Intelligent retry mechanism with increasing delays
- **Session Recovery**: Automatic session rotation on repeated failures
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Failed Page Tracking**: Keeps track of failed requests for later retry

## 📋 Requirements

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Dependencies

- `cloudscraper>=1.2.71` - Cloudflare bypass
- `beautifulsoup4>=4.12.0` - HTML parsing
- `requests>=2.31.0` - HTTP requests
- `fake-useragent>=1.4.0` - User agent rotation
- `lxml>=4.9.0` - XML/HTML parser
- `urllib3>=2.0.0` - HTTP client

## ⚙️ Configuration

The scraper uses `config/config.ini` for configuration:

```ini
[URLs]
HEPSIEMLAK_BASE_URL = https://www.hepsiemlak.com/istanbul-kiralik?page={page_number}
HEPSIEMLAK_FIRST_URL = https://www.hepsiemlak.com/istanbul-kiralik

SAHIBINDEN_BASE_URL = https://www.sahibinden.com/emlak/istanbul?pagingOffset={page_number}&query_text_mf=kiral%C4%B1k&query_text=kiral%C4%B1k
SAHIBINDEN_FIRST_URL = https://www.sahibinden.com/emlak/istanbul?query_text_mf=kiral%C4%B1k&query_text=kiral%C4%B1k

[Pages]
HEPSIEMLAK_INCREMENTS = 1
HEPSIEMLAK_LAST_BASE_PAGE_NUMBER = 421
HEPSIEMLAK_LAST_PAGE_NUMBER = 8942

SAHIBINDEN_INCREMENTS = 20
SAHIBINDEN_LAST_BASE_PAGE_NUMBER = 1000
SAHIBINDEN_LAST_PAGE_NUMBER = 3553

[Scraper]
HEADLESS = True
MAX_RETRIES = 5
MIN_DELAY = 2
MAX_DELAY = 8
COOLDOWN_INTERVAL = 10
SESSION_TIMEOUT = 300
```

### Configuration Parameters

| Parameter           | Description                              | Default |
| ------------------- | ---------------------------------------- | ------- |
| `MAX_RETRIES`       | Maximum retry attempts per page          | 5       |
| `MIN_DELAY`         | Minimum delay between requests (seconds) | 2       |
| `MAX_DELAY`         | Maximum delay between requests (seconds) | 8       |
| `COOLDOWN_INTERVAL` | Pages between cooldown periods           | 10      |
| `SESSION_TIMEOUT`   | Session timeout in seconds               | 300     |

## 🎯 Usage

### Basic Usage

```python
from scripts.scraper import AdvancedScraper

# Scrape HepsieMlak
scraper = AdvancedScraper("hepsiemlak", base_link=True, use_proxies=False)
scraper.fetch_and_save_pages()

# Scrape Sahibinden
scraper = AdvancedScraper("sahibinden", base_link=True, use_proxies=False)
scraper.fetch_and_save_pages()
```

### Advanced Usage

```python
# With proxy support
scraper = AdvancedScraper("hepsiemlak", base_link=True, use_proxies=True)

# Scrape individual property pages (not base pages)
scraper = AdvancedScraper("hepsiemlak", base_link=False, use_proxies=False)
```

### Testing

Run the test script to verify functionality:

```bash
python scripts/test_scraper.py
```

## 📁 Output Structure

The scraper saves data in the following structure:

```
data/
├── raw_html/
│   ├── base_links_raw_hepsiemlak/
│   │   ├── hepsiemlak_page_301_a1b2c3d4.html
│   │   ├── hepsiemlak_page_301_a1b2c3d4.json
│   │   ├── hepsiemlak_page_302_e5f6g7h8.html
│   │   ├── hepsiemlak_page_302_e5f6g7h8.json
│   │   └── failed_pages.json
│   └── base_links_raw_sahibinden/
│       ├── sahibinden_page_1_i9j0k1l2.html
│       ├── sahibinden_page_1_i9j0k1l2.json
│       └── failed_pages.json
└── logs/
    └── scraper.log
```

### File Naming Convention

- HTML files: `{website}_page_{page_number}_{content_hash}.html`
- Metadata files: `{website}_page_{page_number}_{content_hash}.json`
- Failed pages: `failed_pages.json`

## 🔧 Proxy Support

To use proxies, create a `config/proxies.txt` file with one proxy per line:

```
proxy1.example.com:8080
proxy2.example.com:8080
proxy3.example.com:8080
```

Then enable proxy support:

```python
scraper = AdvancedScraper("hepsiemlak", use_proxies=True)
```

## 📊 Monitoring & Logging

The scraper provides comprehensive logging:

- **Console Output**: Real-time progress updates
- **Log File**: Detailed logs in `logs/scraper.log`
- **Statistics**: Success/failure rates and performance metrics
- **Failed Pages**: Track of pages that couldn't be scraped

### Log Levels

- `INFO`: General progress and successful operations
- `WARNING`: Retries and minor issues
- `ERROR`: Failed requests and critical errors
- `DEBUG`: Detailed debugging information

## 🛡️ Anti-Detection Features

### 1. Browser Fingerprinting

- Realistic user agents
- Proper browser headers
- Accept-Language settings
- DNT (Do Not Track) headers

### 2. Request Patterns

- Random delays between requests
- Exponential backoff on failures
- Session rotation
- Cooldown periods

### 3. Content Validation

- HTML structure verification
- Blocking detection
- Content length validation
- Website-specific content checks

## ⚠️ Important Notes

1. **Respect Robots.txt**: Always check the website's robots.txt file
2. **Rate Limiting**: The scraper includes built-in rate limiting, but be respectful
3. **Legal Compliance**: Ensure your scraping activities comply with local laws
4. **Terms of Service**: Review and respect the website's terms of service

## 🐛 Troubleshooting

### Common Issues

1. **Cloudflare Detection**

   - Solution: The scraper automatically handles this with cloudscraper
   - If issues persist, try rotating sessions more frequently

2. **Rate Limiting**

   - Solution: Increase delays in config.ini
   - Use proxy rotation

3. **Session Timeouts**

   - Solution: Decrease SESSION_TIMEOUT in config.ini
   - Enable automatic session rotation

4. **Invalid Content**
   - Check logs for specific validation errors
   - Verify website structure hasn't changed

### Debug Mode

Enable debug logging by modifying the logging level in the scraper:

```python
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance Optimization

### For Large-Scale Scraping

1. **Use Proxies**: Distribute requests across multiple IPs
2. **Adjust Delays**: Find the optimal balance between speed and detection
3. **Session Management**: Monitor session timeout settings
4. **Parallel Processing**: Consider running multiple instances with different configurations

### Monitoring Success Rate

The scraper provides real-time statistics:

- Success rate percentage
- Failed requests count
- Average response times
- Session rotation frequency

## 🔄 Updates and Maintenance

- Regularly update dependencies
- Monitor website changes
- Adjust validation patterns as needed
- Update user agent lists periodically

## 📞 Support

For issues or questions:

1. Check the logs in `logs/scraper.log`
2. Review the failed pages in `failed_pages.json`
3. Test with a small number of pages first
4. Verify configuration settings
