"""
Mobutu Finds - importateur UUFinds

Utilisation :
python bot/scraper.py "https://www.uufinds.com/goodItemDetail/qc/..."

Le scraper utilise uniquement les informations publiques rendues
par la page dans un navigateur normal.

Il ne contourne pas CAPTCHA, login, anti-bot ou protections d'accès.
"""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "products.json"

SIZE_LABELS = {
    "XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL",
    "ONE SIZE", "OS", "FREE",
}
SEASON_LABELS = {"Winter", "Summer", "Spring", "Autumn", "Fall"}
UI_SKIP_LABELS = {
    "Size", "Styles", "How to cop", "Comment", "Back", "Browse", "Seller",
    "Social", "Get up to 40% OFF", "Tao Bao", "Copy link", "Select Buy",
    "Find Similar", "Platform 1", "Platform 2", "More", "Size Tag",
    "Close", "INVITE NOW", "Sign in", "Sign up free",
}
MAX_QC_IMAGES = 24
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL", "4XL", "5XL"]


def clean(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def first_nonempty(*values):
    for value in values:
        if value is None:
            continue
        value = clean(value)
        if value:
            return value
    return ""


def unique(items):
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def extract_price(text):
    if not text:
        return ""

    patterns = [
        r"(?:USD|US\$|\$)\s*([0-9]+(?:[.,][0-9]{1,2})?)",
        r"([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:USD|US\$|\$)",
        r"(?:EUR|€)\s*([0-9]+(?:[.,][0-9]{1,2})?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", ".")

    return ""


def parse_url_params(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    path_id = parsed.path.rstrip("/").split("/")[-1]

    return {
        "spuNo": first_nonempty(*(params.get("spuNo") or [])),
        "originPrice": first_nonempty(*(params.get("originPrice") or [])),
        "originCurrencyCode": first_nonempty(
            *(params.get("originCurrencyCode") or [])
        ),
        "channel": first_nonempty(*(params.get("channel") or [])),
        "pathId": path_id if path_id and path_id != "qc" else "",
    }


def get_url_id(url):
    params = parse_url_params(url)
    return params["spuNo"] or params["pathId"] or url.split("?")[0].rstrip("/").split("/")[-1]


def is_product_image(url):
    if not url or not url.startswith("http"):
        return False

    lower = url.lower()

    if "file.uufinds.com/product/" not in lower:
        return False

    if "/major/" in lower or "/qc/" in lower:
        return True

    return False


def is_noise_image(url):
    lower = url.lower()

    noise_parts = (
        "/assets/",
        "/all/buy/",
        "/user/",
        "placeholder",
        "logo",
        "avatar",
        "meta-weight",
        "invite-rewards",
        "social_discord",
        "hoobuy_promo",
        "icon_feature",
        "alicdn.com",
        "geilicdn.com",
        "jd.com",
    )

    return any(part in lower for part in noise_parts)


def extract_product_folder(url):
    match = re.search(r"/product/\d{4}/\d{2}/\d{2}/(\d+)/", url)
    if match:
        return match.group(1)
    return ""


def extract_product_images(image_urls, primary_folder=""):
    product_images = []
    qc_images = []

    for image in image_urls:
        if not image or not is_product_image(image) or is_noise_image(image):
            continue

        lower = image.lower()

        if primary_folder and f"/{primary_folder}/" not in lower:
            continue

        if "/major/" in lower:
            product_images.append(image)
        elif "/qc/" in lower:
            qc_images.append(image)

    product_images = unique(product_images)
    qc_images = unique(qc_images)[:MAX_QC_IMAGES]
    images = unique(product_images + qc_images)

    return images, product_images, qc_images


def extract_weight(body_text, name=""):
    for source in (body_text, name):
        if not source:
            continue

        match = re.search(r"≈\s*(\d+\s*g\b)", source, re.IGNORECASE)
        if match:
            return clean(match.group(1))

        match = re.search(r"\b(\d+\s*g)\b", source, re.IGNORECASE)
        if match and "union" in source.lower():
            return clean(match.group(1))

    match = re.search(r"Weight:\s*(\d+\s*g\b)", body_text or "", re.IGNORECASE)
    if match:
        return clean(match.group(1))

    return ""


def sort_sizes(sizes):
    def sort_key(size):
        upper = size.upper()
        if upper in SIZE_ORDER:
            return SIZE_ORDER.index(upper)
        return 1000

    return sorted(unique(sizes), key=sort_key)


def format_weight(value):
    value = clean(value)
    if not value:
        return ""

    if re.search(r"\bg\b", value, re.IGNORECASE):
        return value

    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        number = float(value)
        if number.is_integer():
            return f"{int(number)}g"
        return f"{number:g}g"

    return value


def extract_sizes_from_text(body_text):
    if not body_text:
        return []

    sizes = re.findall(r"Sizes:\s*([A-Za-z0-9 ]+)", body_text)
    parsed = []

    for size in sizes:
        token = clean(size.split(",")[0])
        if token.upper() in SIZE_LABELS or re.fullmatch(r"\d{2,3}", token):
            parsed.append(token.upper() if token.upper() in SIZE_LABELS else token)

    return unique(parsed)


def extract_styles_from_text(body_text):
    if not body_text:
        return []

    styles = re.findall(
        r"Color:\s*(.+?)(?:\n|QC time|$)",
        body_text,
        re.IGNORECASE,
    )

    return unique(clean(style) for style in styles if clean(style))


def is_weak_name(name):
    name = clean(name).lower()
    return (
        not name
        or name == "test"
        or name == "produit uufinds"
        or name.startswith("uufinds |")
        or len(name) < 8
    )


def choose_name(*candidates):
    strong = [clean(name) for name in candidates if clean(name) and not is_weak_name(name)]
    if strong:
        return max(strong, key=len)
    return first_nonempty(*candidates) or "Produit UUFinds"


def normalize_size_label(label):
    label = clean(label)
    if not label:
        return ""

    upper = label.upper()
    if upper in SIZE_LABELS:
        return upper

    if re.fullmatch(r"\d{2,3}", label):
        return label

    return ""


def walk_json(node, results=None):
    if results is None:
        results = []

    if isinstance(node, dict):
        results.append(node)
        for value in node.values():
            walk_json(value, results)
    elif isinstance(node, list):
        for item in node:
            walk_json(item, results)

    return results


def extract_from_api_payloads(payloads, url_params):
    name = ""
    description = ""
    price = url_params.get("originPrice", "")
    currency = url_params.get("originCurrencyCode", "USD") or "USD"
    sku = url_params.get("spuNo", "")
    seller = ""
    sizes = []
    styles = []
    season = ""
    weight = ""
    images = []

    for _, payload in payloads:
        for obj in walk_json(payload):
            name = first_nonempty(
                name,
                obj.get("name"),
                obj.get("productName"),
                obj.get("goodsName"),
                obj.get("title"),
                obj.get("subject"),
            )

            description = first_nonempty(
                description,
                obj.get("description"),
                obj.get("desc"),
            )

            price = first_nonempty(
                price,
                obj.get("price"),
                obj.get("originPrice"),
                obj.get("salePrice"),
            )

            currency = first_nonempty(
                currency,
                obj.get("currency"),
                obj.get("originCurrencyCode"),
                obj.get("priceCurrency"),
            )

            sku = first_nonempty(
                sku,
                obj.get("spuNo"),
                obj.get("sku"),
                obj.get("spu"),
            )

            seller = first_nonempty(
                seller,
                obj.get("sellerName"),
                obj.get("shopName"),
            )

            if isinstance(obj.get("seller"), dict):
                seller = first_nonempty(
                    seller,
                    obj["seller"].get("name"),
                    obj["seller"].get("shopName"),
                )

            weight = first_nonempty(
                weight,
                obj.get("weight"),
                obj.get("goodsWeight"),
            )

            for key in ("sizes", "sizeList", "skuSizeList"):
                values = obj.get(key)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict):
                            label = first_nonempty(
                                item.get("size"),
                                item.get("name"),
                                item.get("value"),
                            )
                        else:
                            label = clean(item)

                        normalized = normalize_size_label(label)
                        if normalized:
                            sizes.append(normalized)

            for key in ("styles", "styleList", "colorList", "skuStyleList"):
                values = obj.get(key)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict):
                            label = first_nonempty(
                                item.get("style"),
                                item.get("color"),
                                item.get("name"),
                                item.get("value"),
                            )
                        else:
                            label = clean(item)

                        if label and label not in UI_SKIP_LABELS:
                            styles.append(label)

            for key in ("season", "seasonName"):
                season = first_nonempty(season, obj.get(key))

            for key in ("images", "imageList", "majorImages", "qcImages"):
                values = obj.get(key)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict):
                            image = first_nonempty(
                                item.get("url"),
                                item.get("imageUrl"),
                                item.get("src"),
                            )
                        else:
                            image = clean(item)

                        if image.startswith("http"):
                            images.append(image)

    return {
        "name": name,
        "description": description,
        "price": price,
        "currency": currency or "USD",
        "sku": sku,
        "seller": seller,
        "sizes": unique(sizes),
        "styles": unique(styles),
        "season": season,
        "weight": weight,
        "images": unique(images),
    }


async def get_attribute_safe(locator, attribute):
    try:
        if await locator.count() == 0:
            return ""
        value = await locator.first.get_attribute(attribute)
        return clean(value)
    except Exception:
        return ""


async def close_popups(page):
    for label in ("Close", "×"):
        try:
            button = page.get_by_role("button", name=label, exact=True)
            if await button.count() > 0:
                await button.first.click(timeout=1500)
                await page.wait_for_timeout(300)
        except Exception:
            pass


async def wait_for_product_detail(page):
    selectors = (
        '[aria-label="Product detail"]',
        'button:has-text("Styles")',
        'button:has-text("Size")',
    )

    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=30000)
            return
        except Exception:
            continue

    await page.wait_for_timeout(8000)


async def read_region_button_labels(page, region_selector, min_length=0):
    try:
        labels = await page.eval_on_selector(
            region_selector,
            """
            (selector) => {
                const region = document.querySelector(selector);
                if (!region) return [];
                return [...region.querySelectorAll('button')]
                    .map((button) => (button.textContent || '').trim())
                    .filter(Boolean);
            }
            """,
            region_selector,
        )
    except Exception:
        return []

    if min_length:
        labels = [label for label in labels if len(label) >= min_length]

    return labels


async def collect_toggle_options(page, toggle_label):
    region = page.locator('[aria-label="Product detail"]')
    toggle = region.get_by_role("button", name=toggle_label, exact=True)

    if await toggle.count() == 0:
        toggle = page.get_by_role("button", name=toggle_label, exact=True).first

    if await toggle.count() == 0:
        return []

    try:
        await toggle.click(timeout=3000)
        await page.wait_for_timeout(900)
    except Exception:
        return []

    labels = await read_region_button_labels(page, '[aria-label="Product detail"]')

    if toggle_label == "Styles":
        blocked = {
            "UnionKingdom", "Tao Bao", "Find Similar", "Select Buy", "Copy link",
        }
        return [
            label for label in labels
            if label not in SEASON_LABELS
            and label not in UI_SKIP_LABELS
            and label not in SIZE_LABELS
            and label not in blocked
            and not normalize_size_label(label)
            and 3 <= len(label) <= 40
            and not label.startswith("Platform")
            and "Sweatpants" not in label
            and "Kingdom" not in label
        ]

    if toggle_label == "Size":
        return [
            normalize_size_label(label)
            for label in labels
            if normalize_size_label(label)
        ]

    return []


async def extract_product_title(page):
    labels = await read_region_button_labels(
        page,
        '[aria-label="Product detail"]',
        min_length=20,
    )

    if labels:
        return clean(labels[0])

    try:
        expanded = page.locator(
            '[aria-label="Product detail"] button[aria-expanded="true"]'
        )
        if await expanded.count() > 0:
            return clean(await expanded.first.inner_text())
    except Exception:
        pass

    return ""


async def extract_seller(page, body_text):
    labels = await read_region_button_labels(page, '[aria-label="Product detail"]')

    for label in labels:
        if label in UI_SKIP_LABELS or label in SEASON_LABELS:
            continue
        if label in {"Size", "Styles", "Tao Bao"}:
            continue
        if len(label) < 3:
            continue
        if label.startswith("Platform"):
            continue
        if re.search(r"\d", label) and len(label) <= 4:
            continue
        if "Union" in label or "Kingdom" in label or label.isalpha():
            return label

    match = re.search(r"Seller[:：]\s*(.+?)(?:\n|$)", body_text or "")
    if match:
        return clean(match.group(1))

    return ""


async def extract_season(page):
    labels = await read_region_button_labels(page, '[aria-label="Product detail"]')

    for label in labels:
        if label in SEASON_LABELS:
            return label

    return ""


async def extract_channel(page):
    try:
        button = page.locator('[aria-label="Product detail"]').get_by_role(
            "button",
            name=re.compile(r"Tao Bao|Weidian|1688|Alibaba", re.I),
        )
        if await button.count() > 0:
            return clean(await button.first.inner_text())
    except Exception:
        pass

    return ""


async def extract_region_images(page, selector, limit=0):
    try:
        urls = await page.eval_on_selector(
            selector,
            """
            (selector) => {
                const root = document.querySelector(selector);
                if (!root) return [];
                const values = [];
                for (const img of root.querySelectorAll('img')) {
                    for (const attr of ['src', 'data-src', 'data-original', 'data-lazy-src']) {
                        const value = img.getAttribute(attr);
                        if (value) values.push(value);
                    }
                }
                return values;
            }
            """,
            selector,
        )
    except Exception:
        return []

    resolved = []
    for url in urls:
        full_url = urljoin(page.url, clean(url))
        if full_url.startswith("http"):
            resolved.append(full_url)

    resolved = unique(resolved)
    if limit:
        return resolved[:limit]

    return resolved


async def extract(url, headless=False):
    url_params = parse_url_params(url)
    api_payloads = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=80 if not headless else 0,
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        async def capture_response(response):
            if response.status != 200:
                return

            if "uufinds.com" not in response.url:
                return

            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return

            try:
                payload = await response.json()
                api_payloads.append((response.url, payload))
            except Exception:
                pass

        page.on("response", capture_response)

        print("")
        print("====================================")
        print("Ouverture de UUFinds...")
        print("====================================")
        print(url)
        print("")

        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            print(
                f"Réponse initiale : "
                f"{response.status if response else 'inconnue'}"
            )

        except Exception as error:
            print("")
            print("Erreur lors de l'ouverture de la page :")
            print(error)
            print("")
            await browser.close()
            raise

        if not headless:
            print("")
            print("Si une vérification apparaît dans Chromium,")
            print("termine-la manuellement.")
            print("")

        await wait_for_product_detail(page)
        await close_popups(page)
        await page.wait_for_timeout(3000 if headless else 5000)

        try:
            title_button = page.locator(
                '[aria-label="Product detail"] button'
            ).filter(has_text=re.compile(r".{20,}"))

            if await title_button.count() > 0:
                await title_button.first.click(timeout=3000)
                await page.wait_for_timeout(400)
        except Exception:
            pass

        print("")
        print("Lecture des meta et du contenu...")

        meta_description = await get_attribute_safe(
            page.locator('meta[property="og:description"]'),
            "content",
        )

        body_text = ""

        try:
            body_text = clean(await page.locator("body").inner_text(timeout=10000))
        except Exception as error:
            print(f"Impossible de lire le texte : {error}")

        api_data = extract_from_api_payloads(api_payloads, url_params)

        dom_name = await extract_product_title(page)

        name = choose_name(dom_name, api_data["name"])

        description = first_nonempty(api_data["description"], meta_description)
        price = first_nonempty(api_data["price"], url_params["originPrice"])
        currency = first_nonempty(api_data["currency"], url_params["originCurrencyCode"], "USD")
        sku = first_nonempty(api_data["sku"], url_params["spuNo"])
        seller = first_nonempty(await extract_seller(page, body_text), api_data["seller"])
        season = first_nonempty(await extract_season(page), api_data["season"])
        channel = first_nonempty(await extract_channel(page), url_params["channel"])
        weight = format_weight(first_nonempty(
            api_data["weight"],
            extract_weight(body_text, name),
        ))

        styles = unique(
            await collect_toggle_options(page, "Styles")
            + extract_styles_from_text(body_text)
            + api_data["styles"]
        )

        sizes = sort_sizes(
            await collect_toggle_options(page, "Size")
            + extract_sizes_from_text(body_text)
            + api_data["sizes"]
        )

        detail_images = await extract_region_images(
            page,
            '[aria-label="Product detail"]',
        )

        qc_images_raw = await extract_region_images(page, "body")
        qc_images_raw = [
            image for image in qc_images_raw
            if "/qc/" in image.lower()
        ]

        all_image_urls = unique(detail_images + qc_images_raw + api_data["images"])

        primary_folder = ""
        for image in all_image_urls:
            primary_folder = extract_product_folder(image)
            if primary_folder:
                break

        images, major_images, qc_images = extract_product_images(
            all_image_urls,
            primary_folder,
        )

        if not name and major_images:
            name = "Produit UUFinds"

        if not name:
            name = "Produit UUFinds"

        if not price:
            price = extract_price(body_text)

        product_id = first_nonempty(sku, url_params["pathId"], get_url_id(url))
        
        def get_category(text):
            text = str(text).lower()
            if any(w in text for w in ["pantalon", "pants", "sweatpants", "trousers", "jeans", "jogging", "shorts", "cargo", "trackpant"]):
                return "pantalon"
            elif any(w in text for w in ["tee", "t-shirt", "shirt", "hoodie", "sweat", "zip", "jacket", "veste", "pull", "coat"]):
                return "vêtement"
            elif any(w in text for w in ["shoe", "sneaker", "dunk", "jordan", "runner", "chaussure"]):
                return "chaussures"
            else:
                return "accessoire"

        product = {
            "id": product_id,
            "name": name,
            "title": name,
            "category": get_category(name),
            "price": price,
            "currency": currency,
            "description": description,
            "sizes": sizes,
            "styles": styles,
            "season": season,
            "weight": weight,
            "dimensions": "",
            "seller": seller,
            "channel": channel,
            "sku": sku,
            "images": images,
            "productImages": major_images,
            "qcImages": qc_images,
            "buyUrl": url,
            "sourceUrl": url,
            "tags": unique(
            ([season] if season else [])
            + ([channel] if channel else [])
            ),
            }

        print("")
        print("====================================")
        print("PRODUIT TROUVÉ")
        print("====================================")
        print("")
        print(json.dumps(product, ensure_ascii=False, indent=2))
        print("")
        print("====================================")
        print(f"Tailles : {', '.join(sizes) if sizes else '(aucune)'}")
        print(f"Styles : {', '.join(styles) if styles else '(aucun)'}")
        print(f"Poids : {weight or '(inconnu)'}")
        print(f"Photos produit : {len(major_images)}")
        print(f"Photos QC : {len(qc_images)}")
        print("====================================")
        print("")

        await browser.close()

        return product


def save(product):
    DATA.parent.mkdir(parents=True, exist_ok=True)

    try:
        if DATA.exists():
            existing = json.loads(DATA.read_text(encoding="utf-8"))
        else:
            existing = []

        if not isinstance(existing, list):
            existing = []

    except Exception:
        existing = []

    product_ids = {
        str(product["id"]),
        str(product.get("sku", "")),
        get_url_id(product.get("sourceUrl", "")),
    }

    existing = [
        item for item in existing
        if str(item.get("id")) not in product_ids
        and str(item.get("sku", "")) not in product_ids
        and get_url_id(item.get("sourceUrl", "")) not in product_ids
    ]

    existing.append(product)

    DATA.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("")
    print("====================================")
    print("IMPORT TERMINÉ")
    print("====================================")
    print(f"Produit : {product['name']}")
    print(f"Fichier : {DATA}")
    print("")


async def main():
    parser = argparse.ArgumentParser(description="Importateur UUFinds")

    parser.add_argument("url", help="URL du produit UUFinds")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Lancer Chromium sans interface (CI / automation)",
    )

    args = parser.parse_args()
    headless = args.headless or os.getenv("HEADLESS", "").lower() in {
        "1", "true", "yes",
    }

    product = await extract(args.url, headless=headless)
    save(product)


if __name__ == "__main__":
    asyncio.run(main())
