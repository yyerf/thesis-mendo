"""Fetch the documented public product reference photos for the offline catalog."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

TARGET = Path(__file__).resolve().parents[1] / "web/static/images/medicines"
ASSETS = {
    "kremil-s.png": ("https://www.rosepharmacy.com/ph1/wp-content/uploads/2016/09/12959.png", "https://www.rosepharmacy.com/product/kremil-s-tablet/"),
    "bioflu.webp": ("https://assetsprod.unilab.com.ph/uploads/Common/ProductShot/1_Isabella_Zotter.webp", "https://www.unilab.com.ph/products/bioflu"),
    "biogesic.webp": ("https://assetsprod.unilab.com.ph/uploads/Common/ProductShot/PDP_BIOGESIC_500s_072026_Carlos_Alfonso_Muyco.webp", "https://www.unilab.com.ph/products/biogesic"),
    "cetirizine.jpg": ("https://www.colabella.com.au/cdn/shop/files/CE5F5C31-1652-4519-8F56-55E660C318AA_1445x.jpg?v=1758590177", "https://www.colabella.com.au/products/watsons-cetirizine-10mg-8-2-capsules"),
    "solmux.jpg": ("https://www.rosepharmacy.com/ph1/wp-content/uploads/2016/09/36878.jpg", "https://www.rosepharmacy.com/product/solmux-500-mg-capsule/"),
    "sinecod.png": ("https://www.rosepharmacy.com/ph1/wp-content/uploads/2016/09/9617-1.png", "https://www.rosepharmacy.com/product/sinecod-forte-50-mg-tablet/"),
    "symdex.jpg": ("https://www.bambangpharma.com/cdn/shop/files/441032247_1412736172701539_1518235734984779480_n.jpg?v=1715393735", "https://www.bambangpharma.com/products/phenylpropanolamine-hydrochloride-chlorphenamine-maleate-paracetamol-symdex-d-25mg-2mg-325mg-tablet-100s"),
    "buscopan.png": ("https://www.rosepharmacy.com/ph1/wp-content/uploads/2017/11/64603.png", "https://www.rosepharmacy.com/product/buscopan-10mg-4x30/"),
    "loperamide.webp": ("https://assetsprod.unilab.com.ph/uploads/Common/ProductShot/Diatabs_4s_Supermarket_Pack_Maria_Samantha_Padua.webp", "https://www.unilab.com.ph/products/diatabs?sku=153"),
    "nutrabliss.jpg": ("https://img.ph.my-best.com/product_images/401a24244bc58b4312a4004fdc684509.jpg?fit=clip&h=800&ixlib=rails-4.3.1&lossless=0&q=70&s=1f9ac17cf937603d1f066d410e0552f6&w=800", "https://ph.my-best.com/16498"),
}


def fetch(item):
    name, (url, page) = item
    if (TARGET / name).is_file():
        return {"file": name, "url": url, "source_page": page, "bytes": (TARGET / name).stat().st_size}
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": page})
    with urlopen(request, timeout=30) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"Not an image: {name} ({content_type})")
    (TARGET / name).write_bytes(data)
    return {"file": name, "url": url, "source_page": page, "content_type": content_type, "bytes": len(data)}


if __name__ == "__main__":
    TARGET.mkdir(parents=True, exist_ok=True)
    records, failures = [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [(name, pool.submit(fetch, (name, urls))) for name, urls in ASSETS.items()]
        for name, job in jobs:
            try:
                record = job.result()
                records.append(record)
                print(f"Saved {name} ({record['bytes']} bytes)")
            except Exception as exc:
                failures.append(name)
                print(f"Failed {name}: {exc}")
    (TARGET / "sources.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(1)
