# Phase 5 Runbook — Product Images + UI Polish

Adds: real product images (from Amazon metadata), a horizontal collapsible filter bar (dropdowns + removable chips, replacing the vertical rail), and richer animations (card hover-lift, animated dropdowns/chips, header fade-in).

---

## 0. Sync to your working repo

```powershell
robocopy "C:\Users\manir\OneDrive\Documents\Claude\Projects\Building my portfolio\priceSentry" "C:\Drive D\GIt project\PriceSentry" /E /XD .git node_modules .next __pycache__ .pytest_cache /XF .env
```

## 1. Apply the images schema

```bash
docker compose cp db/05_phase5_images.sql postgres:/tmp/05.sql
docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/05.sql
```

## 2. Backfill product images (real Amazon CDN images)

The scraper image already has the `datasets` dependency, so no rebuild needed:

```bash
docker compose exec scraper python /app/scripts/update_images.py --meta-limit 20000
```

This streams the metadata and fills `products.image_url` for products matched by ASIN. Watch the `images.progress` logs. Verify:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "SELECT COUNT(*) FROM products WHERE image_url IS NOT NULL;"
```

You should see a few thousand+ products with images.

## 3. Restart API (picks up the schema column) and rebuild web

```bash
docker compose restart api
docker compose build web && docker compose up -d web
```

## 4. See it

Open **http://localhost:3000/dashboard**:
- Product cards now show **real images** (gradient fallback when an image is missing or fails to load).
- The vertical filter rail is gone — there's a **horizontal filter bar** on top: search box + dropdown pills (Sort, Deals, Sentiment, Brand, Category).
- Selected filters appear as **removable chips** below the bar; the result count sits on the right.
- Cards **lift on hover**; dropdowns and chips **animate** in/out; the header fades in.

---

## Notes

- Images use a plain `<img>` with lazy loading and an `onError` fallback to the gradient — no Next.js remote-image config needed.
- Some products won't have images (the metadata didn't include one, or they weren't in the streamed slice). Those keep the gradient — that's expected.
- The old `components/catalog/filters.tsx` (vertical rail) is no longer used; you can delete it or keep it for reference.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No images appear | Step 2 didn't run, or web not rebuilt. Re-run update_images, then rebuild web. |
| `column image_url does not exist` | Step 1 (the 05 SQL) wasn't applied. Apply it, then `docker compose restart api`. |
| Filter dropdowns don't open | web not rebuilt with the new components. `docker compose build web --no-cache && docker compose up -d web`. |
| Build error about framer-motion/lucide | deps already in package.json; rebuild clears it: `docker compose build web --no-cache`. |
