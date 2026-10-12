from pathlib import Path
import pandas as pd

file_path = Path("data/raw/product_category_name_translation.csv")

# Baca header dengan dua encoding
df_utf8 = pd.read_csv(file_path, encoding="utf-8", nrows=0)
df_sig = pd.read_csv(file_path, encoding="utf-8-sig", nrows=0)

print("=== BOM ENCODING CHECK ===")
print("UTF-8:", repr(df_utf8.columns[0]))
print("UTF-8-SIG:", repr(df_sig.columns[0]))

# Periksa byte asli agar keberadaan BOM benar-benar terbukti
with file_path.open("rb") as f:
    first_bytes = f.read(3)

print("First 3 bytes:", first_bytes)
print("Has UTF-8 BOM:", first_bytes == b"\xef\xbb\xbf")