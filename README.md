# Mobutu Finds — Bot d'importation

## 1. Site
Le site est statique et fonctionne avec GitHub Pages.
- `index.html` = interface
- `script.js` = chargement/recherche/fiche produit
- `data/products.json` = catalogue
- `images/` = images locales si tu en ajoutes

## 2. Installer le bot sur ton PC
Python 3.10+ recommandé.

```bash
pip install -r bot/requirements.txt
python -m playwright install chromium
```

## 3. Importer un produit
```bash
python bot/scraper.py "https://doppel.fit/item/TAOBAO/1033540814659"
```

Le script récupère les informations publiques rendues par la page et met à jour `data/products.json`.

Important: il ne contourne pas CAPTCHA, connexion ou protections anti-bot. Si le site répond 403/429 ou exige une session, il s'arrête.

## 4. IA facultative
L'IA sert uniquement à nettoyer le nom, la description, la catégorie et les tags.
Ne mets JAMAIS une clé API dans `index.html` ou `script.js`.

macOS/Linux:
```bash
export OPENAI_API_KEY="ta-cle"
python bot/enrich_catalog.py
```

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY="ta-cle"
python bot/enrich_catalog.py
```

Le SDK Python officiel OpenAI utilise actuellement la Responses API; la clé doit rester côté serveur/local et hors du dépôt public.

## 5. GitHub Actions
`/.github/workflows/import-products.yml` permet d'importer une liste d'URLs stockée dans `bot/urls.txt` puis de committer les données générées.
Ajoute tes URLs une par ligne dans `bot/urls.txt`.

Pour l'IA dans GitHub Actions, ajoute un secret de dépôt:
`OPENAI_API_KEY`

## 6. Droits
Avant de republier des photos, textes ou autres contenus récupérés sur un site tiers, vérifie que tu as le droit de les utiliser. Le bot conserve aussi `sourceUrl` et `buyUrl` pour garder le lien vers la source.
