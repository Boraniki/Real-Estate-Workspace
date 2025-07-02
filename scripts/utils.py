import configparser
import pandas as pd
from pathlib import Path

class URLsHandler:
    def __init__(self, website, base_link=True):
        self.website = website.upper()
        self.base_link = base_link
        self.config = self._load_config()
        self.base_url = self._get_config_value("URLs", f"{self.website}_BASE_URL")
        self.increment = self._get_config_value("Pages", f"{self.website}_INCREMENTS", value_type=int)
        self.last_base_page_number = self._get_config_value("Pages", f"{self.website}_LAST_BASE_PAGE_NUMBER", value_type=int)
        self.last_page_number = self._get_config_value("Pages", f"{self.website}_LAST_PAGE_NUMBER", value_type=int)
        self. base_dir = Path(__file__).resolve().parent.parent 
        self.csv_path = "" if base_link else self.base_dir / "data" / "extracted_links" / f"extracted_{self.website.lower()}" / f"extracted_{self.website.lower()}.csv"
        self.df = pd.DataFrame() if base_link else pd.read_csv(self.csv_path)
        self.current_url = self._get_config_value("URLs", f"{self.website}_FIRST_URL") if base_link else self.df["@id"].iloc[0]
        self.current_page_number = 0

    def _load_config(self):
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

    def _get_config_value(self, section, key, value_type=str, default=None):
        try:
            if value_type == int:
                return self.config.getint(section, key)
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if default is not None:
                return default
            raise KeyError(f"Missing key '{key}' in section [{section}] of config.ini")

    def get_next_page_url(self):
        if self.base_link:
            self.current_page_number += self.increment
            self.current_url = self.base_url.format(page_number=self.current_page_number)
            return self.current_url
        else:
            self.current_page_number += 1
            self.current_url = self.df["@id"].iloc[self.current_page_number]
            return self.current_url