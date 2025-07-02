import os
import json
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup

class Extractor:
    def __init__(self, website: str):
        self.website = website
        self.base_dir = Path(__file__).resolve().parent.parent
        self.input_dir = self.base_dir / "data" / "raw_html" / f"raw_{self.website}"
        self.output_dir = self.base_dir / "data" / "extracted_links" / f"extracted_{self.website}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def html_to_json(self, html_content: str):
        """Extract JSON from HTML content."""
        soup = BeautifulSoup(html_content, "html.parser")
        script_tag = soup.find("script", type="application/ld+json")
        if script_tag and script_tag.string:
            try:
                return json.loads(script_tag.string)
            except json.JSONDecodeError:
                pass
        return None

    def extract_links(self):
        """Extract links from all HTML files and merge them into a DataFrame."""
        all_data = []
        
        for file_path in self.input_dir.glob("*.html"):
            with file_path.open("r", encoding="utf-8") as f:
                html_content = f.read()
            
            json_data = self.html_to_json(html_content)
            if json_data:
                graph_data = json_data.get("@graph", {}).get("itemListElement", [])
                if graph_data:
                    all_data.extend(graph_data)

        if all_data:
            self.df_merged = pd.json_normalize(
                all_data,
                meta=[
                    "position",
                    ["item", "name"],
                    ["item", "url"],
                    ["item", "description"],
                    ["item", "numberOfRooms"],
                    ["item", "floorSize", "value"],
                    ["item", "address", "addressCountry"],
                    ["item", "address", "addressLocality"],
                    ["item", "address", "streetAddress"],
                    ["item", "telephone"]
                ]
            )
            self.df_merged.columns = self.df_merged.columns.str.replace(r"^item\.", "", regex=True)
        else:
            self.df_merged = pd.DataFrame()

    def save_csv(self):
        """Save extracted data to a CSV file."""
        if not self.df_merged.empty:
            self.df_merged.to_csv(self.output_dir / f"extracted_{self.website}.csv", index=False)
