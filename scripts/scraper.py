import os
import time
import random
from pathlib import Path
import cloudscraper
from utils import URLsHandler
import configparser

class Scraper:
    def __init__(self, website, base_link=True):
        self.website = website
        self.base_link = base_link
        self.urls_handler = URLsHandler(self.website, self.base_link)
        self._create_scraper()
        self._create_output_folder()
        self.max_retries = self._get_max_retries()

    def _get_max_retries(self):
        try:
            return self.urls_handler.config.getint('Scraper', 'MAX_RETRIES')
        except (configparser.NoSectionError, configparser.NoOptionError):
            return 3

    def _create_scraper(self):
        self.scraper = cloudscraper.create_scraper()
        self._rotate_user_agent()

        self.scraper.headers.update({
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com.tr/?hl=tr",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def _reset_scraper_session(self):
        print("Resetting session...")
        self._create_scraper()
        time.sleep(random.uniform(30, 90))

    def _rotate_user_agent(self):
        """Updates headers with a new random User-Agent."""
        self.scraper.headers.update({
            "User-Agent": self._get_random_user_agent(),
        })

    def _is_blocked(self, html):
        blocked_keywords = [
            "access denied", "cloudflare", "captcha", "security check", 
            "403 forbidden", "unusual traffic", "request unsuccessful"
        ]
        html_lower = html.lower()
        return any(keyword in html_lower for keyword in blocked_keywords)

    def _create_output_folder(self):
        base_dir = Path(__file__).resolve().parent.parent
        if self.base_link: 
            self.output_dir = base_dir / "data" / "raw_html" / f"base_links_raw_{self.website}"
        else:
            self.output_dir = base_dir / "data" / "raw_html" / f"links_raw_{self.website}"
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_random_user_agent(self):
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/119.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
        ]
        return random.choice(user_agents)

    def fetch_and_save_pages(self):
        print(f"Starting scrape: {self.urls_handler.current_url}")
        number_of_pages = range(301, self.urls_handler.last_base_page_number + 1) if self.base_link else range(1, self.urls_handler.last_page_number)

        for page_number in number_of_pages:
            url = self.urls_handler.get_next_page_url() if page_number > 1 else self.urls_handler.current_url
            print(f"Fetching: {url}")

            success = False
            for attempt in range(self.max_retries):
                try:
                    self._rotate_user_agent()
                    response = self.scraper.get(url, timeout=60)

                    if response.status_code == 200:
                        html_source = response.text
                        if self._is_blocked(html_source):
                            print("Blocked content detected. Retrying...")
                            raise Exception("Blocked content")

                        self._save_page(html_source, page_number)
                        print(f"Saved page {page_number}")
                        success = True

                        time.sleep(random.uniform(1, 5))

                        if page_number % 10 == 0:
                            cooldown = random.uniform(60, 180)
                            print(f"Cooldown: {int(cooldown)}s...")
                            time.sleep(cooldown)
                        break

                    elif response.status_code in [403, 429, 500, 502, 503, 504]:
                        print(f"Status {response.status_code}. Retry {attempt+1}/{self.max_retries}")
                        self._reset_scraper_session()
                    else:
                        print(f"Status {response.status_code}. Retry {attempt+1}/{self.max_retries}")

                    delay = (2 ** attempt) * random.uniform(1.5, 3)
                    print(f"Retry in {delay:.1f}s...")
                    time.sleep(delay)

                except Exception as e:
                    print(f"Attempt {attempt+1} failed: {str(e)[:100]}")
                    delay = (2 ** attempt) * random.uniform(1.5, 3)
                    print(f"Retry in {delay:.1f}s...")
                    time.sleep(delay)

            if not success:
                print(f"Failed page {page_number} after {self.max_retries} retries.")

        print("Scraping completed!")

    def _save_page(self, html_source, page_number):
        file_path = self.output_dir / f"{self.website}_page_{page_number}.html"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_source)

a = Scraper("hepsiemlak", base_link=False)
a.fetch_and_save_pages()