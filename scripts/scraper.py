import os
import time
import random
import json
import hashlib
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import URLsHandler
from multiprocessing import Process, Event, Manager
import signal
import warnings
from typing import List, Tuple, Any, Dict
import datetime
warnings.filterwarnings("ignore")

# Global variables to be set before starting batch processing
GLOBAL_PROCESSES = None
GLOBAL_STOP_EVENT = None

def global_signal_handler(sig, frame):
    logger.warning("Signal received. Sending stop signal to all workers.")
    if GLOBAL_STOP_EVENT is not None:
        GLOBAL_STOP_EVENT.set()
    if GLOBAL_PROCESSES is not None:
        for p in GLOBAL_PROCESSES:
            if p.is_alive():
                p.terminate()

# --- Setup logging ---
os.makedirs("logs", exist_ok=True)
log_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"logs/scraper_{log_time}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Scraper:
    """
    Web scraper for real estate websites using Selenium and multiprocessing.
    """
    def __init__(self, website: str, base_link: bool = True):
        """
        Initialize the Scraper.
        Args:
            website (str): The website to scrape.
            base_link (bool): Whether to use base links or extracted links.
        """
        self.base_dir = Path(__file__).resolve().parent.parent
        self.website = website
        self.base_link = base_link
        self.urls_handler = URLsHandler(self.website, self.base_link)
        self._create_output_folder()
        self._load_config()
        self.min_delay = self.config.getint('Scraper', 'MIN_DELAY', fallback=2)
        self.max_delay = self.config.getint('Scraper', 'MAX_DELAY', fallback=8)
        self.cooldown_interval = self.config.getint('Scraper', 'COOLDOWN_INTERVAL', fallback=10)
        self.max_retries = self.config.getint('Scraper', 'MAX_RETRIES', fallback=5)
        self.session_timeout = self.config.getint('Scraper', 'SESSION_TIMEOUT', fallback=300)
        # Always run in non-headless mode for manual captcha solving
        self.headless = False
        self.session_start_time = time.time()
        self.last_request_time = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.session_data = {}
        self.batch_size = None
        self.number_of_rotate_sesion = 35
        self.shared_cookies = None # Initialize shared_cookies
        logger.info(f"Initialized scraper for '{self.website}' with base_link={self.base_link}, headless={self.headless}")

    def _load_config(self) -> None:
        """Load configuration from URLsHandler."""
        try:
            self.config = self.urls_handler.config
            logger.info("Configuration loaded successfully.")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    def _create_output_folder(self) -> None:
        """Create the output directory for saving HTML and metadata files."""
        if self.base_link:
            self.output_dir = self.base_dir / "data" / "raw_html" / f"base_links_raw_{self.website}"
        else:
            self.output_dir = self.base_dir / "data" / "raw_html" / f"links_raw_{self.website}"
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")
        
    def _setup_chrome_options(self) -> None:
        """Set up Chrome options for Selenium WebDriver."""
        self.chrome_options = Options()
        # Do NOT add --headless, always show browser window
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--lang=tr-TR")

    def _initialize_scraper(self) -> None:
        """Initialize the Selenium WebDriver."""
        try:
            self._setup_chrome_options()
            self.service = Service()
            self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
            logger.info("Chrome WebDriver initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")

    def _validate_html_content(self, html_content: str, url: str, captcha_event: Event = None) -> Tuple[bool, str]:
        """Validate the HTML content of a page. If captcha detected, signal main process for manual intervention."""
        if not html_content or len(html_content.strip()) < 500:
            return False, "Content too short or empty"
        block_phrases = [
            "İnsan olduğunuz doğrulanıyor. Bu işlem birkaç saniye sürebilir.",
            "Devam etmek için doğrulama yapmalısınız"
        ]
        for phrase in block_phrases:
            if phrase in html_content:
                logger.warning(f"Bot/captcha detected on {url}: '{phrase}' found in HTML.")
                if captcha_event is not None:
                    captcha_event.set()
                return False, f"Bot/captcha verification detected: '{phrase}'"
        return True, "Valid content"

    def _make_request(self, url: str, attempt: int = 0, captcha_event: Event = None) -> Tuple[Any, bool]:
        """
        Request a page and return its HTML content if valid.
        Uses WebDriverWait for dynamic page load.
        """
        try:
            logger.info(f"Requesting: {url} (Attempt {attempt + 1})")
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.debug(f"Page loaded for {url}")
            except Exception as wait_exc:
                logger.warning(f"Timeout waiting for page to load: {url} ({wait_exc})")
            html_content = self.driver.page_source
            is_valid, message = self._validate_html_content(html_content, url, captcha_event)
            if is_valid:
                self.successful_requests += 1
                logger.info(f"Page valid: {url}")
                return html_content, True
            else:
                logger.warning(f"Invalid content: {url} — Reason: {message}")
                return None, False
        except Exception as e:
            logger.error(f"Exception during request to {url}: {e}")
            return None, False

    def _rotate_session(self) -> None:
        """Rotate the Selenium session (re-initialize the driver)."""
        logger.info("Closing current session")
        self.driver.quit()
        logger.info("Rotating session...")
        self._initialize_scraper()
        self.session_data = {}
        delay = random.uniform(0.5, 2)
        logger.info(f"Sleeping {delay:.1f}s during session rotation...")
        time.sleep(delay)

    def _save_page(self, html_content: str, page_number: int, url: str) -> None:
        """Save the HTML content and metadata for a page."""
        try:
            content_hash = hashlib.md5(html_content.encode()).hexdigest()[:8]
            filename = f"{self.website}_page_{page_number}_{content_hash}.html"
            file_path = self.output_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            metadata = {
                'page_number': page_number,
                'url': url,
                'timestamp': time.time(),
                'content_length': len(html_content),
                'content_hash': content_hash,
                'website': self.website
            }
            metadata_file = file_path.with_suffix('.json')
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Saved page {page_number} to {filename}")
        except Exception as e:
            logger.error(f"Failed to save page {page_number} ({url}): {e}")

    def _save_failed_page(self, page_number: int, url: str) -> None:
        """Save information about a failed page scrape."""
        try:
            failed_file = self.output_dir / "failed_pages.json"
            failed_data = {
                'page_number': page_number,
                'url': url,
                'timestamp': time.time(),
                'website': self.website
            }
            existing_failed = []
            if failed_file.exists():
                try:
                    with open(failed_file, 'r', encoding='utf-8') as f:
                        existing_failed = json.load(f)
                except Exception:
                    existing_failed = []
            existing_failed.append(failed_data)
            with open(failed_file, 'w', encoding='utf-8') as f:
                json.dump(existing_failed, f, indent=2)
            logger.warning(f"Failed page info saved for page {page_number}: {url}")
        except Exception as e:
            logger.error(f"Failed to save failed page info for page {page_number} ({url}): {e}")

    def _fetch_and_save_pages(self, batch_url_list: List[List[Any]], worker_id: int = 0, captcha_event: Event = None, status_dict=None, progress_dict=None, start_index=0, shutdown_event: Event = None, shared_cookies: list = None) -> None:
        """
        Fetch and save a batch of pages. Each worker gets a unique batch.
        Args:
            batch_url_list (List[List[Any]]): List of [url, is_last_page, page_number].
            worker_id (int): Worker process ID for logging.
            captcha_event (Event): Event to signal captcha detection.
            status_dict (dict): Shared dict for worker status.
            progress_dict (dict): Shared dict for worker progress (current index).
            start_index (int): Index to start from in the batch.
            shutdown_event (Event): Event to signal shutdown.
            shared_cookies (list): Cookies to inject into the session after captcha solve.
        """
        logger.info(f"[Worker {worker_id}] Started.")
        if status_dict is not None:
            status_dict[worker_id] = "started"
        self._initialize_scraper()
        # Inject cookies if provided
        if shared_cookies:
            # Visit the domain first to set cookies
            test_url = batch_url_list[start_index][0] if batch_url_list and len(batch_url_list[start_index]) > 0 else None
            if test_url:
                self.driver.get(test_url)
                for cookie in shared_cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"[Worker {worker_id}] Failed to add cookie: {cookie} ({e})")
                self.driver.refresh()
        try:
            logger.info(f"[Worker {worker_id}] Entering main processing loop with {len(batch_url_list)} URLs.")
            for index in range(start_index, len(batch_url_list)):
                if shutdown_event is not None and shutdown_event.is_set():
                    logger.info(f"[Worker {worker_id}] Shutdown event set. Closing driver and exiting.")
                    self.driver.quit()
                    return
                url, is_last_page, page_number = batch_url_list[index]
                # UPDATE PROGRESS
                if progress_dict is not None:
                    progress_dict[worker_id] = index
                if is_last_page:
                    logger.info(f"[Worker {worker_id} PID {os.getpid()}] Last page reached.")
                    if status_dict is not None:
                        status_dict[worker_id] = "finished"
                    break
                if captcha_event is not None and captcha_event.is_set():
                    logger.warning(f"[Worker {worker_id}] Captcha event set. Pausing until cleared.")
                    logger.info(f"[Worker {worker_id}] Waiting for captcha to be solved (waiting for event to clear)...")
                    if status_dict is not None:
                        status_dict[worker_id] = "paused for captcha"
                    captcha_event.wait()
                    logger.info(f"[Worker {worker_id}] Captcha event cleared by main process. Resuming work.")
                    if status_dict is not None:
                        status_dict[worker_id] = "resumed after captcha"
                # Only rotate session after the first batch
                if index != 0 and index % self.number_of_rotate_sesion == 0:
                    self._rotate_session()
                logger.info(f"[Worker {worker_id}] Processing page {page_number}: {url}")
                if status_dict is not None:
                    status_dict[worker_id] = f"processing page {page_number}"
                success = False
                for attempt in range(self.max_retries):
                    html_content, is_valid = self._make_request(url, attempt, captcha_event)
                    if html_content and is_valid:
                        self._save_page(html_content, page_number, url)
                        # Mark URL as fetched in the state JSON (multiprocessing-safe)
                        self.urls_handler.mark_url_fetched(url)
                        success = True
                        break
                    else:
                        if attempt < self.max_retries - 1:
                            delay = (2 ** attempt) * random.uniform(0.5, 1.5)
                            logger.info(f"[Worker {worker_id}] Retrying in {delay:.1f}s (attempt {attempt+1}/{self.max_retries})...")
                            time.sleep(delay)
                            if attempt > 1:
                                self._rotate_session()
                        if captcha_event is not None and captcha_event.is_set():
                            logger.warning(f"[Worker {worker_id}] Captcha event set during retry. Closing browser session and pausing until cleared.")
                            try:
                                self.driver.quit()
                                logger.info(f"[Worker {worker_id}] WebDriver closed due to captcha event (retry).")
                            except Exception:
                                pass
                            logger.info(f"[Worker {worker_id}] Waiting for captcha to be solved (waiting for event to clear)...")
                            if status_dict is not None:
                                status_dict[worker_id] = "paused for captcha"
                            captcha_event.wait()
                            logger.info(f"[Worker {worker_id}] Captcha event cleared by main process. Re-initializing browser and resuming work.")
                            if status_dict is not None:
                                status_dict[worker_id] = "resumed after captcha"
                            self._initialize_scraper()
                if not success:
                    self.failed_requests += 1
                    logger.error(f"[Worker {worker_id}] Failed to scrape page {page_number} after {self.max_retries} attempts.")
                    self._save_failed_page(page_number, url)
            if status_dict is not None:
                status_dict[worker_id] = "finished"
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Exception: {e}", exc_info=True)
        finally:
            try:
                self.driver.quit()
                logger.info(f"[Worker {worker_id}] WebDriver closed.")
            except Exception:
                pass
        total = self.successful_requests + self.failed_requests
        success_rate = (self.successful_requests / total * 100) if total else 0
        logger.info(f"[Worker {worker_id}] Scraping finished. Successful: {self.successful_requests}, Failed: {self.failed_requests}, Success rate: {success_rate:.2f}%")
        if status_dict is not None:
            status_dict[worker_id] = "done"

    def _batch_processing(self, num_workers: int = 5) -> None:
        """
        Launch multiple worker processes, each with a unique batch of URLs.
        Handles graceful shutdown on KeyboardInterrupt or signals.
        Pauses all workers if a captcha is detected, allows manual solve, then resumes scraping from the last failed URL.
        Args:
            num_workers (int): Number of worker processes to launch.
        """
        global GLOBAL_PROCESSES, GLOBAL_STOP_EVENT
        stop_event = Event()
        captcha_event = Event()
        manager = Manager()
        status_dict = manager.dict()
        progress_dict = manager.dict()  # NEW: Track progress
        processes: List[Process] = []
        last_failed_url = None
        all_batches = self.urls_handler.get_all_batches(num_workers, self.batch_size)
        start_indices = [0] * num_workers  # NEW: Track start index for each worker
        # shared_cookies = None # This line is removed as per the edit hint

        # Set globals for the signal handler
        GLOBAL_PROCESSES = processes
        GLOBAL_STOP_EVENT = stop_event

        # Register the global signal handler
        signal.signal(signal.SIGINT, global_signal_handler)
        signal.signal(signal.SIGTERM, global_signal_handler)

        try:
            while not stop_event.is_set():
                logger.info(f"Launching {num_workers} worker processes...")
                processes.clear()
                # Get all unfetched URLs and split among workers
                unfetched_urls = self.urls_handler.get_unfetched_urls()
                if not unfetched_urls:
                    logger.info("No unfetched URLs left. Exiting batch processing loop.")
                    break
                # Split unfetched_urls into batches for each worker
                batch_size = len(unfetched_urls) // num_workers + (1 if len(unfetched_urls) % num_workers else 0)
                all_batches = [
                    [[url, False, idx] for idx, url in enumerate(unfetched_urls[i*batch_size:(i+1)*batch_size])]
                    for i in range(num_workers)
                ]
                start_indices = [0] * num_workers
                for i, batch_url_list in enumerate(all_batches):
                    if not batch_url_list or start_indices[i] >= len(batch_url_list):
                        logger.info(f"No more batches to process. Worker {i} exiting.")
                        continue
                    logger.info(f"Starting worker {i} with {len(batch_url_list) - start_indices[i]} URLs (from index {start_indices[i]}).")
                    status_dict[i] = "starting"
                    progress_dict[i] = start_indices[i]
                    scraper_args = (self.website, self.base_link)
                    p = Process(
                        target=worker_fetch_and_save_pages,
                        args=(scraper_args, batch_url_list, i, captcha_event, status_dict, progress_dict, start_indices[i], stop_event)
                    )
                    p.start()
                    processes.append(p)
                all_done = all(
                    not batch_url_list or start_indices[i] >= len(batch_url_list)
                    for i, batch_url_list in enumerate(all_batches)
                )
                if all_done:
                    logger.info("All batches processed. Exiting batch processing loop.")
                    break
                # Monitor worker status
                while any(p.is_alive() for p in processes):
                    logger.info(f"Worker status: {dict(status_dict)}")
                    if captcha_event.is_set():
                        logger.warning("Captcha detected by a worker. Pausing all workers for manual intervention.")
                        last_failed_url = self.urls_handler.current_url
                        # Do NOT terminate workers; they will pause and resume after captcha is solved
                        break
                    time.sleep(2)
                if captcha_event.is_set():
                    # Save progress for each worker
                    for i in range(num_workers):
                        start_indices[i] = progress_dict.get(i, start_indices[i])
                    # Prompt user to solve captcha in any open browser window
                    print("\n[CAPTCHA DETECTED]")
                    print("Please solve the captcha in any open browser window, then press Enter here to continue...")
                    input()
                    captcha_event.clear()
                    logger.info("Resuming scraping after manual captcha solve.")
                    sleep_time = random.uniform(1, 3)
                    logger.info(f"Sleeping {sleep_time:.1f}s before resuming workers after captcha solve.")
                    time.sleep(sleep_time)
                    continue
                logger.info(f"Worker status at batch end: {dict(status_dict)}")
                logger.info("Batch completed. Preparing next batch...")
                for i in range(num_workers):
                    start_indices[i] = progress_dict.get(i, start_indices[i])
                time.sleep(1)
        except KeyboardInterrupt:
            logger.warning("KeyboardInterrupt received. Sending stop signal.")
            stop_event.set()
            for p in processes:
                if p.is_alive():
                    p.terminate()
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
            logger.info("All worker processes terminated.")

def worker_fetch_and_save_pages(scraper_args, batch_url_list, worker_id, captcha_event, status_dict, progress_dict, start_index, shutdown_event):
    logger.info(f"[Worker {worker_id}] Worker function started with {len(batch_url_list)} URLs.")
    try:
        scraper = Scraper(*scraper_args)
        scraper._fetch_and_save_pages(batch_url_list, worker_id, captcha_event, status_dict, progress_dict, start_index, shutdown_event)
    except Exception as e:
        logger.error(f"[Worker {worker_id}] Exception: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting scraping script.")
    scraper = Scraper("hepsiemlak", base_link=True)
    scraper._batch_processing(num_workers=4)
    logger.info("Script completed.")