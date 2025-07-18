import pandas as pd
from pathlib import Path

website = "hepsiemlak"

base_dir = Path(__file__).resolve().parent.parent
input_dir = base_dir / "data" / "raw_html" / f"raw_{website}"
output_dir = base_dir / "data" / "extracted_links" / f"extracted_{website}"


df = pd.read_csv(output_dir / f"extracted_{website}.csv")

print(df["@id"][0])