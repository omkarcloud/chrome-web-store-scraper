# 🧩 Chrome Web Store Scraper

Chrome Web Store Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Chrome Web Store data for free.

## ✨ What Can I Get?

- 🧩 **Full details on 300K+ extensions & themes** — users, rating, version, size, permissions, privacy practices & the full manifest
- 📇 **Developer contacts for B2B leads** — email, phone, address, legal name, DUNS number & every extension a publisher ships
- ⭐ **Up to 20,000 reviews per extension** — full text, stars, version, language & the developer's reply, in 4 sort orders
- 📈 **Top charts, 30 categories & 100+ curated collections** — plus a direct .crx download link for any extension

## 🎥 Example: A Full Chrome Web Store Extension

```json
{
  "id": "kbfnbcaeplbcioakkpcpgfkobkghlhen",
  "name": "Grammarly: AI Writing Assistant and Grammar Checker App",
  "link": "https://chromewebstore.google.com/detail/grammarly-ai-writing-assi/kbfnbcaeplbcioakkpcpgfkobkghlhen",
  "summary": "Grammarly for Chrome helps you write with confidence. Get AI support for grammar, clarity, and tone, from first draft to final edit.",
  "rating": 3.87,
  "rating_count": 43166,
  "users": 40000000,
  "category": { "id": 3, "slug": "productivity/communication", "name": "Communication" },
  "is_featured": true,
  "is_established_publisher": true,
  "version": "14.1346.0",
  "updated_at": "2026-11-09T16:20:22Z",
  "size": "19.03MiB",
  "permissions": ["scripting", "sidePanel", "offscreen"],
  "host_permissions": ["http://*/*", "https://*/*"],
  "developer": {
    "legal_name": "Grammarly, Inc.",
    "email": "support@grammarly.com",
    "phone": "+16282338294",
    "address": "548 Market St Ste 35410\nSan Francisco, CA 94104-5401\nUS",
    "duns_number": "031633083",
    "is_trader": true,
    "publisher": { "id": "u7431803589585a11dd7aea578e1005d0", "name": "Grammarly", "link": "https://chromewebstore.google.com/publisher/grammarly/u7431803589585a11dd7aea578e1005d0" }
  },
  "privacy": {
    "policy_link": "https://www.grammarly.com/privacy-policy",
    "collects_data": true,
    "data_collected": ["personally_identifiable_information", "personal_communications", "location"]
  },
  "related": [
    { "id": "kdfieneakcjfaiglcfcgkidlkmlijjnh", "name": "AI Grammar and Spell Checker by Ginger", "rating": 4.03, "users": 500000 }
  ]
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Chrome Web Store Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/chrome-web-store-scraper
cd chrome-web-store-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/extensions/details?extension=kbfnbcaeplbcioakkpcpgfkobkghlhen"
```

```json
{
  "id": "kbfnbcaeplbcioakkpcpgfkobkghlhen",
  "name": "Grammarly: AI Writing Assistant and Grammar Checker App",
  "link": "https://chromewebstore.google.com/detail/grammarly-ai-writing-assi/kbfnbcaeplbcioakkpcpgfkobkghlhen",
  "rating": 3.87,
  "rating_count": 43166,
  "users": 40000000,
  "category": { "id": 3, "slug": "productivity/communication", "name": "Communication" },
  "version": "14.1346.0",
  "updated_at": "2026-11-09T16:20:22Z",
  "size": "19.03MiB",
  "permissions": ["scripting", "sidePanel", "offscreen", "tabs", "notifications", "cookies", "identity", "storage"],
  "developer": {
    "legal_name": "Grammarly, Inc.",
    "email": "support@grammarly.com",
    "phone": "+16282338294",
    "duns_number": "031633083"
  },
  "privacy": {
    "collects_data": true,
    "data_collected": ["personally_identifiable_information", "personal_communications", "location", "user_activity", "website_content"]
  }
}
```

All 10 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

10 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Extension Details | `/extensions/details` | Everything about one extension: users, rating, contacts, privacy, manifest |
| Search Extensions | `/extensions/search` | 50 extensions or themes per page, filtered by rating and badges |
| Extension Reviews | `/extensions/reviews` | Full-text reviews, 100 per page, with the developer's reply |
| Download Extension | `/extensions/download` | Latest version, size, SHA-256 and a direct .crx download link |
| Publisher Details | `/publishers/details` | Publisher email, phone, address, DUNS and every extension they publish |
| Top Charts | `/charts/list` | The store's 25 most popular, trending or new and notable |
| Categories | `/categories/list` | All 30 categories with slugs, ready for Category Extensions |
| Category Extensions | `/categories/extensions` | One category, 50 per page, ranked by relevance, rating, newest or trending |
| Collections | `/collections/list` | 100+ curated collections with titles and descriptions |
| Collection Extensions | `/collections/extensions` | Every extension in one curated collection, in the store's order |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-chrome-web-store-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-chrome-web-store-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-chrome-web-store-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/extensions/reviews",
    params={"extension": "kbfnbcaeplbcioakkpcpgfkobkghlhen", "sort": "lowest"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Chrome Web Store Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://www.omkar.cloud/l/chrome-web-store-scraper-github-whatsapp)

[![Ask Us by Email about Chrome Web Store Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Chrome%20Web%20Store%20Scraper%20API&body=I%20need%20help%20using%20the%20Chrome%20Web%20Store%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/chrome-web-store-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/chrome-web-store-scraper)
