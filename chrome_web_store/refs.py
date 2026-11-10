"""Reference resolvers + the slug tables for /chrome-web-store/*.

ONE param per input (tripadvisor QueryOrIdField convention): every
resolver accepts a bare id / slug OR any chromewebstore.google.com link
and raises ValueError with a user-facing message (RefField -> 400).

Identifier shapes:
  * item id        32 chars a-p (cjpalhdlnbpafiamejdnhcphjbkeiagm); links
                   /detail/<any-slug>/<id>, /detail/<id>, the legacy
                   chrome.google.com/webstore/detail/<slug>/<id>, and the
                   /reviews, /support, /privacy sub-pages
  * publisher id   "u" + 32 hex; link /publisher/<slug>/<id>
  * category slug  group/name ("productivity/developer") for extensions,
                   a bare name ("dark") for themes; links
                   /category/extensions/<group>/<name>, /category/themes/<name>
  * collection     slug ("writing_essentials"); link /collection/<slug>

The category names and groups are the store's own menu (CWFOxc + the
category pages, captured 2026-11-07); the collection slugs are the switch
tables in the store's categoryview JS module (127 slugs, captured
2026-11-07; the 101 still live on 2026-11-10 are kept). Both are static
tables on the store's side.
"""
import re
from urllib.parse import unquote, urlparse

SITE = "https://chromewebstore.google.com"
LEGACY_HOSTS = ("chrome.google.com",)

ITEM_ID_RE = re.compile(r"^[a-p]{32}$")
PUBLISHER_ID_RE = re.compile(r"^u[0-9a-f]{32}$")
SLUG_RE = re.compile(r"^[a-z0-9_-]+$")

_LINK_ITEM_RE = re.compile(r"/detail/(?:[^/?#]+/)?([a-p]{32})(?:[/?#]|$)")
_LINK_PUBLISHER_RE = re.compile(r"/publisher/(?:[^/?#]+/)?(u[0-9a-f]{32})(?:[/?#]|$)")
_LINK_CATEGORY_RE = re.compile(r"/category/(extensions|themes)(?:/([a-z0-9_]+)(?:/([a-z0-9_]+))?)?(?:[/?#]|$)")
_LINK_COLLECTION_RE = re.compile(r"/collection/([a-z0-9_-]+)(?:[/?#]|$)")


def _is_link(value):
    return value.startswith(("http://", "https://", "//"))


def _store_url(value, what):
    """A pasted link -> its URL string, after checking it is the store's."""
    url = value if not value.startswith("//") else "https:" + value
    host = (urlparse(url).hostname or "").lower()
    if host not in ("chromewebstore.google.com", *LEGACY_HOSTS):
        raise ValueError(f"Must be a chromewebstore.google.com {what} link.")
    return url


# ---- items --------------------------------------------------------------------

def resolve_item(value):
    """Bare 32-char id or a store item link -> the item id."""
    value = (value or "").strip()
    if ITEM_ID_RE.match(value.lower()) and not _is_link(value):
        return value.lower()
    if _is_link(value):
        url = _store_url(value, "extension")
        match = _LINK_ITEM_RE.search(url)
        if match:
            return match.group(1)
        raise ValueError("Must be a Chrome Web Store item link "
                         "(https://chromewebstore.google.com/detail/<name>/<32-char id>).")
    raise ValueError("Must be a 32-character extension id (cjpalhdlnbpafiamejdnhcphjbkeiagm) "
                     "or a chromewebstore.google.com item link.")


def slugify(name, limit=25):
    """The store's own link slug: the name lower-cased, runs of anything but
    letters and digits folded to one hyphen, cut at 25 characters (the slug
    is cosmetic; the store 301s any slug to the canonical one)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:limit].rstrip("-")
    return slug or "x"


def item_link(item_id, name=None):
    """The store link; without a name the slug segment is left out
    (/detail/<id> resolves just as well)."""
    if name:
        return f"{SITE}/detail/{slugify(name)}/{item_id}"
    return f"{SITE}/detail/{item_id}"


def reviews_link(item_id, name=None):
    return item_link(item_id, name) + "/reviews"


def review_link(item_id, review_id, name=None):
    return f"{reviews_link(item_id, name)}/{review_id}"


# ---- publishers ---------------------------------------------------------------

def resolve_publisher(value):
    """Bare publisher id ("u" + 32 hex), a publisher link, OR an item id /
    item link (the publisher is then read off the item's details in
    api.py) -> ("publisher", id) | ("item", id)."""
    value = (value or "").strip()
    low = value.lower()
    if not _is_link(value):
        if PUBLISHER_ID_RE.match(low):
            return ("publisher", low)
        if ITEM_ID_RE.match(low):
            return ("item", low)
        raise ValueError("Must be a publisher id (u + 32 hex), a chromewebstore.google.com publisher "
                         "link, or an extension id / link of one of the publisher's items.")
    url = _store_url(value, "publisher")
    match = _LINK_PUBLISHER_RE.search(url)
    if match:
        return ("publisher", match.group(1))
    match = _LINK_ITEM_RE.search(url)
    if match:
        return ("item", match.group(1))
    raise ValueError("Must be a Chrome Web Store publisher link "
                     "(https://chromewebstore.google.com/publisher/<name>/<id>) or an item link.")


def publisher_link(publisher_id, name=None):
    return f"{SITE}/publisher/{slugify(name)}/{publisher_id}"


# ---- categories ---------------------------------------------------------------

# group id -> (slug, label) as the store's menu shows them
CATEGORY_GROUPS = {
    2: ("productivity", "Productivity"),
    8: ("lifestyle", "Lifestyle"),
    19: ("make_chrome_yours", "Make Chrome Yours"),
    23: ("themes", "Themes"),
}

# slug -> (id, group id, label); CWFOxc [1] + [2] and the menu labels of the
# category pages, captured 2026-11-07
EXTENSION_CATEGORIES = {
    "productivity/communication": (3, 2, "Communication"),
    "productivity/workflow": (4, 2, "Workflow & Planning"),
    "productivity/tools": (5, 2, "Tools"),
    "productivity/education": (6, 2, "Education"),
    "productivity/developer": (7, 2, "Developer Tools"),
    "lifestyle/shopping": (9, 8, "Shopping"),
    "lifestyle/news": (10, 8, "News & Weather"),
    "lifestyle/entertainment": (11, 8, "Entertainment"),
    "lifestyle/games": (12, 8, "Games"),
    "lifestyle/social": (13, 8, "Social Networking"),
    "lifestyle/art": (14, 8, "Art & Design"),
    "lifestyle/well_being": (15, 8, "Well-being"),
    "lifestyle/travel": (16, 8, "Travel"),
    "lifestyle/household": (17, 8, "Household"),
    "lifestyle/fun": (18, 8, "Just for Fun"),
    "make_chrome_yours/accessibility": (20, 19, "Accessibility"),
    "make_chrome_yours/functionality": (21, 19, "Functionality & UI"),
    "make_chrome_yours/privacy": (22, 19, "Privacy & Security"),
}
THEME_CATEGORIES = {
    "dark": (25, 23, "Dark & Black"),
    "colors": (26, 23, "Colors"),
    "minimalist": (27, 23, "Minimalist"),
    "space": (28, 23, "Space & Sky"),
    "games": (29, 23, "Games & Anime"),
    "nature": (30, 23, "Nature & Landscapes"),
    "animals": (31, 23, "Animals"),
    "entertainment": (32, 23, "Entertainment"),
    "art": (33, 23, "Art & Patterns"),
    "cars": (34, 23, "Cars"),
    "other": (35, 23, "Other"),
    "artist": (36, 23, "Artist Series"),
}
CATEGORY_IDS = {v[0]: k for k, v in {**EXTENSION_CATEGORIES, **THEME_CATEGORIES}.items()}

# the RPC's list kinds: 3 = an extension category, 4 = a theme category
CATEGORY_KIND_EXTENSION, CATEGORY_KIND_THEME = 3, 4


def category_label(slug):
    entry = EXTENSION_CATEGORIES.get(slug) or THEME_CATEGORIES.get(slug)
    return entry[2] if entry else None


def category_link(slug):
    if slug in THEME_CATEGORIES:
        return f"{SITE}/category/themes/{slug}"
    return f"{SITE}/category/extensions/{slug}"


def resolve_category(value):
    """A category slug ("productivity/developer", "developer", "themes/dark",
    "dark") or a store category link -> (kind, slug)."""
    value = (value or "").strip()
    if _is_link(value):
        url = _store_url(value, "category")
        match = _LINK_CATEGORY_RE.search(url)
        if not match:
            raise ValueError("Must be a Chrome Web Store category link "
                             "(https://chromewebstore.google.com/category/extensions/<group>/<name>).")
        area, first, second = match.groups()
        if area == "themes":
            value = f"themes/{first or ''}"
        else:
            value = "/".join(p for p in (first, second) if p)
    low = unquote(value).lower().strip("/")
    if low.startswith("extensions/"):
        low = low[len("extensions/"):]
    if low.startswith("themes/"):
        name = low[len("themes/"):]
        if name in THEME_CATEGORIES:
            return (CATEGORY_KIND_THEME, name)
        raise ValueError(f"Unknown theme category {name!r}; one of: {', '.join(THEME_CATEGORIES)}.")
    if low in EXTENSION_CATEGORIES:
        return (CATEGORY_KIND_EXTENSION, low)
    # a bare extension category name ("developer", "games") wins over a
    # theme category of the same name; themes/<name> names the theme one
    tails = [slug for slug in EXTENSION_CATEGORIES if slug.split("/", 1)[1] == low]
    if len(tails) == 1:
        return (CATEGORY_KIND_EXTENSION, tails[0])
    if low in THEME_CATEGORIES:
        return (CATEGORY_KIND_THEME, low)
    raise ValueError("Unknown category; use an extension category slug "
                     f"({', '.join(EXTENSION_CATEGORIES)}), a theme category "
                     f"(themes/{', themes/'.join(THEME_CATEGORIES)}) or a store category link.")


# ---- collections --------------------------------------------------------------

def collection_link(slug):
    return f"{SITE}/collection/{slug}"


def resolve_collection(value):
    """A collection slug or a store collection link -> the slug (any slug of
    the right shape is accepted; an unknown one is a 404 from the store)."""
    value = (value or "").strip()
    if _is_link(value):
        url = _store_url(value, "collection")
        match = _LINK_COLLECTION_RE.search(url)
        if not match:
            raise ValueError("Must be a Chrome Web Store collection link "
                             "(https://chromewebstore.google.com/collection/<slug>).")
        return match.group(1).lower()
    low = value.lower()
    if SLUG_RE.match(low):
        return low
    raise ValueError("Must be a collection slug (writing_essentials) or a store collection link.")


# slug -> (title, description): the store's own copy for every curated
# collection (categoryview JS switch tables, 2026-11-07). The 26 slugs the
# store has retired (no items on 2026-11-10: the 2020-2022 favorites, wfh,
# wordle, woof, spotlight, sunny_themes, test-collection, ...) are left out
# so /collections/list never advertises a 404; /collections/extensions
# still accepts any slug, so a revived seasonal collection keeps working.
COLLECTIONS = {
    '2023_favorites': ('Favorites of 2023', 'Discover the standout extensions that made our year'),
    '2024_favorites': ('Favorites of 2024', 'Discover the standout extensions that made our year'),
    '2025_favorites': ('Favorites of 2025', 'Discover the standout AI extensions that made our year'),
    '3p_accessibility_extensions': ('Accessibility extensions', 'Adapt Chrome to your needs'),
    'ai_assistants': ('Helpful AI assistants', 'AI-powered Chrome extensions that answer questions and streamline your browsing'),
    'ai_content': ('The future of writing', 'Elevate your writing and create engaging and high-quality content effortlessly'),
    'ai_images': ('Unlock your creativity with AI', 'Explore the creative possibilities of AI with image generators and editors'),
    'ai_learning': ('Knowledge at your fingertips', 'Unlock deeper insights and accelerate your learning with AI-powered research tools'),
    'ai_productivity': ('Work smarter, not harder with AI', 'Automate tasks and stay focused and organized with AI-powered productivity extensions'),
    'ai_sidekick': ('Your AI sidekick on every tab', 'Chat with leading AI assistants without leaving the page'),
    'annotate_the_web': ('Annotate the web', 'Add notes, highlight & more'),
    'apahm_2023': ('Asian & Pacific Islander Artists Series', 'Discover backgrounds by Asian & Pacific Islander artists'),
    'apps_kiosks': ('Top Chrome Apps for Kiosks', 'Browse popular Chrome Apps for kiosks'),
    'apps_users': ('Top Chrome Apps for Users & MGS', 'Browse popular Chrome Apps for your organization'),
    'artist_themes': ('Black Artists Series', 'Explore Chrome backgrounds by Black artists'),
    'beach_themes': ("Let's go to the beach", 'Choose your ocean view'),
    'blogger_extensions': ("Blogger's toolkit", 'Extensions to help you blog like a pro'),
    'brain_training': ('Train your brain', 'Keep your mind active and engaged'),
    'by_chrome_extensions': ('Developed by Google', None),
    'cats_themes': ('Cat themes', 'Add some cuteness to your browser'),
    'charity': ('Extensions for a cause', 'Make a positive impact with these charitable Chrome extensions'),
    'chrome-dev-tools-extensions': ('Chrome developer tools', None),
    'chrome_color_themes': ('Color themes by Chrome', 'With love from the Chrome team ♥'),
    'chrome_themes': ('Themes developed by Google', None),
    'chrome_toolkit': ('Chrome toolkit', 'Calculators, clocks & more'),
    'collaboration': ('Connect and collaborate', 'Bridge the distance and work together effortlessly'),
    'customize_recorder': ('Recorder extensions', 'Customize the Chrome DevTools Recorder with export and replay extensions'),
    'customize_your_new_tab_page': ('Customize your New Tab Page', 'Pictures, weather updates & more'),
    'cwscms': ('Chrome monthly spotlight', 'Promising extensions to try out'),
    'cyber_monday': ('Shop and save', 'Big savings from stores you love'),
    'dark_mode': ('Darken your browser', 'Screen shaders & more'),
    'dark_themes': ('Dark & black themes', 'Darken your browser'),
    'dc_super_heroes_collection': ('DC Super Heroes Collection', 'Celebrate your superhero fandom with custom, official DC themes of your favorite characters'),
    'deep_work_collection': ('The Deep Work Collection', 'Eliminate digital distractions and stay in the flow state with site blockers and focus timers'),
    'earth_day': ('Every day is Earth Day', 'Plant trees, shop sustainably, and more'),
    'editors_picks_extensions': ("Editors' Picks extensions", 'Handpicked by Chrome Editors'),
    'ent_education': ('Transform your classroom', 'Enhance lessons, improve study habits, and foster engaging learning experiences'),
    'ent_focus': ('Focus & flow', 'Eliminate distractions, manage time effectively, and achieve deep focus'),
    'ent_projects': ('Power up your projects', 'Track tasks, collaborate seamlessly, and manage deadlines effectively'),
    'ent_starter_kit': ('Work essentials', 'Boost your workflow and simplify daily tasks with extensions'),
    'fall_themes': ('Autumn hues', 'Create a warm and cozy atmosphere'),
    'fishy_themes': ('Under the sea', "There's something fishy about these themes..."),
    'flower_themes': ('Chrome in full bloom', 'Add flowers to your browser'),
    'foodies_themes': ('Themes for foodies', 'Fill your browser with delicious fruits and delicacies'),
    'for_animal_lovers': ('For animal lovers', 'Personalize Chrome with your favorite furry friends'),
    'for_creatives': ('Made for creatives', 'Must-have graphics & design tools'),
    'fun': ('Just for fun', 'Bring some joy to your browser'),
    'game_themes': ('High scoring themes', 'Bring your favorite video games to your browser'),
    'games': ('Game on', 'Beat boredom with bite-sized games in your browser'),
    'games_extension': ('Enhance your gameplay', 'Extensions for games and gamer tools'),
    'games_retro': ('Retro games', 'Take a break with these classic games in Chrome'),
    'gen_ai_extensions': ('AI-powered extensions', 'Elevate your browser with Generative AI powered extensions'),
    'genai_themes': ('Generative AI themes made by Chrome', "Made using 'Create themes with AI' and voted as top choices by the team"),
    'get_organized': ('Get organized', 'Manage tasks, plan & more'),
    'get_started': ('Extensions starter kit', 'New to extensions? Start here.'),
    'global_themes': ('Faraway locations', 'Chrome themes that transport you around the globe'),
    'gmail_extensions': ('Works with Gmail', 'Boost your email productivity'),
    'green_open_spaces': ('Green open spaces', 'Beautiful fields of grass'),
    'health': ('Health & fitness', 'Extensions for nutrition, exercise, and motivation'),
    'holiday_themes': ('A sprinkle of holiday magic', 'Bring holiday cheer to your browser with festive Chrome themes'),
    'job_hunting': ('Job hunting', 'Optimize your job search'),
    'kitchen_companions': ('Kitchen companions', 'Recipes & more'),
    'language_learning': ('Learn a new language', 'Study while you browse'),
    'latino_artist_themes': ('Latino Artists Series', 'Explore Chrome backgrounds by Latino artists'),
    'let_it_snow': ('Winter wonderland themes', 'Snow, trees & cozy scenes'),
    'lgbtq_themes': ('LGBTQ Artists Series', 'Celebrate Pride with Chrome backgrounds'),
    'minimalist_themes': ('Minimalist themes', 'Simple yet elegant'),
    'music_extensions': ('For music lovers', 'Equalizers, radios, playlists, and more'),
    'native_american_artists_collection': ('Native American Artists Series', 'Explore Chrome backgrounds by Native American artists'),
    'nature_themes': ('Window to the wild', 'Chrome themes to immerse yourself in the beauty of nature'),
    'notepads_lists': ('Hold that thought', 'Notepads & to do lists'),
    'online_tools': ('Measure your online presence', 'Social & SEO tools'),
    'onlineeducation': ('Online education', 'Tools for school'),
    'password_managers': ('Never forget a password', 'Trusted password managers that save, fill and protect your logins'),
    'pdf_extensions': ('Do more with PDFs', 'Annotate, highlight & more'),
    'personalize_chrome': ('Personalize Chrome', 'Extensions that make Chrome yours'),
    'procrastination_station': ('Procrastination station', "We've all been there"),
    'productivity': ('Your productivity toolkit', 'Transform the way you work with Chrome extensions'),
    'reading_lovers': ('Focused reading', 'Tools for saving, organizing, and enjoying distraction-free reading'),
    'recommended_extensions': ('Recommended for you', 'Extensions you might like'),
    'relax_extensions': ('Keep calm & carry on', 'Stay focused and relaxed'),
    'relaxing_themes': ('Tranquil themes', 'Escape the everyday with peaceful Chrome themes'),
    'retro_themes': ('Throwback themes', 'Add a splash of retro color to your browser with these pixel-perfect themes'),
    'rising_artists_themes': ('Rising Artists Series', 'The Canvas of Tomorrow'),
    'roblox_extensions': ('Level up your Roblox experience', 'Get more out of Roblox with Chrome extensions'),
    'screen_capture': ('Capture your screen', 'Snap screenshots, record videos & more'),
    'side_panel': ('Extend your browser', 'Discover a new level of convenience and customization with side panel extensions'),
    'sky_themes': ('Up in the sky', 'A breath of fresh air'),
    'social': ('Social media essentials', 'Connect, follow, share'),
    'space_exploration': ('Space exploration', 'Stars, planets, galaxies and more'),
    'spooky_themes': ('Spooky scenes', 'Give Chrome a macabre makeover'),
    'spring_cleaning': ('Conquer the clutter', 'Essential Chrome extensions for spring cleaning your browser'),
    'spring_themes': ('Fresh tabs, fresh outlook', 'Awaken your browser with vibrant spring landscapes'),
    'tabs_control': ('Take control of your tabs', 'Get and stay organized'),
    'the_art_gallery': ('Art gallery themes', 'Turn your browser into a work of art'),
    'travel_smarter': ('Travel smarter', 'Extensions to plan your trip'),
    'valentine_themes': ('Feel the love', 'Shower your screen with affection'),
    'weather_extensions': ('Weather & outdoor', 'Get the forecast'),
    'writing_essentials': ('Write like a pro', 'Eliminate typos and grammatical errors'),
    'youtube': ('Transform YouTube', 'Personalize YouTube with extensions'),
    'zodiac_animals_theme': ('Zodiac animal themes', 'A playful take on the lunar zodiac'),
}
