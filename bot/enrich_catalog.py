import json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ai import enrich
root=Path(__file__).resolve().parents[1]
path=root/"data/products.json"
products=json.loads(path.read_text(encoding="utf-8"))
products=[enrich(p) for p in products]
path.write_text(json.dumps(products,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"{len(products)} produit(s) traité(s).")
