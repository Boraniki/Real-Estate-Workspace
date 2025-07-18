import configparser
import pandas as pd
from pathlib import Path
from typing import Optional, Any, Tuple, List
import json
import os
from datetime import datetime
from filelock import FileLock
import time

class URLsHandler:
    """
    Handles URL and page batching logic for scraping different real estate websites.
    Reads configuration and provides next page URLs and batches for scraping.
    """
    def __init__(self, website: str, base_link: bool = True):
        """
        Args:
            website (str): The website key (e.g., 'HEPSIEMLAK').
            base_link (bool): Whether to use base links or extracted links.
        """
        self.website = website.upper()
        self.base_link = base_link
        self.config = self._load_config()
        self.base_url = self._get_config_value("URLs", f"{self.website}_BASE_URL")
        self.increment = self._get_config_value("Pages", f"{self.website}_INCREMENTS", value_type=int)
        self.last_base_page_number = self._get_config_value("Pages", f"{self.website}_LAST_BASE_PAGE_NUMBER", value_type=int)
        self.last_page_number = self._get_config_value("Pages", f"{self.website}_LAST_PAGE_NUMBER", value_type=int)
        self.base_dir = Path(__file__).resolve().parent.parent
        self.csv_path = "" if base_link else self.base_dir / "data" / "extracted_links" / f"extracted_{self.website.lower()}" / f"extracted_{self.website.lower()}.csv"
        self.df = pd.DataFrame() if base_link else pd.read_csv(self.csv_path)
        self.current_url = self._get_config_value("URLs", f"{self.website}_FIRST_URL") if base_link else self.df["@id"].iloc[0]
        self.current_page_number = 0
        self.state_dir = self.base_dir / "state"
        self.state_file = self.state_dir / f"{self.website.lower()}_state.json"
        self._ensure_state_dir()
        self.load_state()  # Load state if exists

    def _load_config(self) -> configparser.RawConfigParser:
        """
        Load the configuration file.
        Returns:
            configparser.RawConfigParser: The loaded config object.
        Raises:
            FileNotFoundError: If the config file does not exist.
            ValueError: If the config file is empty or not loaded properly.
        """
        base_dir = Path(__file__).resolve().parent.parent
        config_path = base_dir / "config" / "config.ini"
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        config = configparser.RawConfigParser()
        config.read(config_path, encoding="utf-8")
        if not config.sections():
            raise ValueError("Config file is empty or not loaded properly!")
        print(f"Loaded config from: {config_path}")
        return config

    def _get_config_value(self, section: str, key: str, value_type: type = str, default: Optional[Any] = None) -> Any:
        """
        Get a value from the config, with optional type and default.
        Args:
            section (str): Config section.
            key (str): Config key.
            value_type (type): Desired type (str or int).
            default (Any): Default value if not found.
        Returns:
            Any: The config value.
        Raises:
            KeyError: If the key is missing and no default is provided.
        """
        try:
            if value_type == int:
                return self.config.getint(section, key)
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default is not None:
                return default
            raise KeyError(f"Missing key '{key}' in section [{section}] of config.ini")

    def _ensure_state_dir(self):
        """
        Ensure the state directory exists.
        """
        if not self.state_dir.exists():
            self.state_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self):
        """
        Save the current state (page number, url, timestamp) to a JSON file.
        """
        state = {
            "current_page_number": self.current_page_number,
            "current_url": self.current_url,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self):
        """
        Load the state from the JSON file if it exists, and resume from there.
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                self.current_page_number = state.get("current_page_number", self.current_page_number)
                self.current_url = state.get("current_url", self.current_url)
            except Exception as e:
                print(f"Failed to load state: {e}")

    def reset_state(self):
        """
        Delete the state file to start from zero.
        """
        if self.state_file.exists():
            try:
                os.remove(self.state_file)
                print(f"State file {self.state_file} deleted.")
            except Exception as e:
                print(f"Failed to delete state file: {e}")

    def get_next_page_url(self) -> Tuple[str, bool, int]:
        """
        Returns the next unfetched page URL from the full state JSON, a boolean indicating if it's the last page, and the index.
        """
        import json
        state_json_path = self.state_dir / f"{self.website.lower()}_all_pages_state.json"
        if not state_json_path.exists():
            raise FileNotFoundError(f"Full state JSON not found: {state_json_path}. Please run create_full_state_json first.")
        with open(state_json_path, "r", encoding="utf-8") as f:
            all_pages = json.load(f)
        for idx, entry in enumerate(all_pages):
            if not entry.get("isFetched", False):
                url = entry["url"]
                is_last = (idx == len(all_pages) - 1)
                return url, is_last, idx
        # If all are fetched, return last
        return all_pages[-1]["url"], True, len(all_pages) - 1

    def get_batched_pages(self, number_of_workers: int = 5) -> List[List[Any]]:
        """
        Returns a batch list of URLs, each with a flag for last page and the page number.
        Args:
            batch_number (int): Number of pages in the batch.
        Returns:
            List[List[Any]]: List of [url, is_last_page, page_number].
        """
        batch_list: List[List[Any]] = []
        batch_size = self.last_page_number // number_of_workers
        for _ in range(batch_size):
            url, is_last_url, page_number = self.get_next_page_url()
            if not is_last_url:
                batch_list.append([url, is_last_url, page_number])
            else:
                break
        return batch_list

    def get_all_batches(self, num_workers: int, batch_size: int = None) -> List[List[Any]]:
        """
        Divide all pages among num_workers, returning a list of batches (one per worker).
        Each batch is a list of [url, is_last_page, page_number].
        Args:
            num_workers (int): Number of worker batches to create.
            batch_size (int, optional): Number of URLs per batch. If None, auto-calculate.
        Returns:
            List[List[Any]]: List of batches, each batch is a list of [url, is_last_page, page_number].
        """
        total_pages = self.last_base_page_number if self.base_link else self.last_page_number
        print("batch_size", batch_size)
        if batch_size is None:
            batch_size = total_pages // num_workers + (1 if total_pages % num_workers else 0)
        batches: List[List[Any]] = []
        for _ in range(num_workers):
            batch: List[Any] = []
            for _ in range(batch_size):
                url, is_last_url, page_number = self.get_next_page_url()
                if not is_last_url:
                    batch.append([url, is_last_url, page_number])
                else:
                    break
            if batch:
                batches.append(batch)
        return batches

    def create_full_state_json(self, output_file: str = None):
        """
        Create a JSON file with metadata for every page URL: url, timestamp, isFetched.
        Sets isFetched=False and timestamp=None for all pages initially.
        """
        if output_file is None:
            output_file = self.state_dir / f"{self.website.lower()}_all_pages_state.json"
        page_urls = []
        if self.base_link:
            for i in range(0, self.last_base_page_number + 1, self.increment):
                page_urls.append(self.base_url.format(page_number=i))
        else:
            for i in range(len(self.df)):
                page_urls.append(self.df["@id"].iloc[i])
        meta_data = []
        for url in page_urls:
            meta_data.append({
                "url": url,
                "timestamp": None,
                "isFetched": False
            })
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        print(f"Full state JSON created at {output_file}")

    def mark_url_fetched(self, url, state_json_path=None):
        """
        Mark a URL as fetched (isFetched=True, set timestamp) in the state JSON file, using a file lock for multiprocessing safety.
        """
        if state_json_path is None:
            state_json_path = self.state_dir / f"{self.website.lower()}_all_pages_state.json"
        lock_path = str(state_json_path) + ".lock"
        with FileLock(lock_path):
            with open(state_json_path, "r", encoding="utf-8") as f:
                all_pages = json.load(f)
            for entry in all_pages:
                if entry["url"] == url:
                    entry["isFetched"] = True
                    entry["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    break
            with open(state_json_path, "w", encoding="utf-8") as f:
                json.dump(all_pages, f, ensure_ascii=False, indent=2)

    def get_unfetched_urls(self, state_json_path=None):
        """
        Return a list of all unfetched URLs from the state JSON file.
        """
        if state_json_path is None:
            state_json_path = self.state_dir / f"{self.website.lower()}_all_pages_state.json"
        with open(state_json_path, "r", encoding="utf-8") as f:
            all_pages = json.load(f)
        return [entry["url"] for entry in all_pages if not entry.get("isFetched", False)]