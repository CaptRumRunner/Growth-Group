"""
SBC Growth Group - Food Sign Up
---------------------------------
Single-page, mobile-first food sign-up board.

Signing a family up for a category IS their RSVP -- one active weekly
sign-up per family (category + headcount + optional allergy note).
Allergy notes live in a separate, persistent collection that survives
"Clear for new night."

All HTML fragments passed to st.markdown are built as single-line
strings (no embedded newlines/indentation) -- multi-line f-strings with
Python indentation get misread as Markdown code blocks instead of HTML,
which is why the hero looked broken before.

Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
Icons are inline SVGs; edit controls use the plain Unicode pencil glyph
"\u270e" rather than a multi-byte emoji, to avoid copy/paste corruption.
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date, datetime, timedelta

st.set_page_config(page_title="SBC Growth Group", page_icon=":books:", layout="centered")

PENCIL = "\u270e"

FAMILIES = {
    "Griffith": ["Claire Griffith", "Shannon Griffith"],
    "Crissman": ["David Crissman", "Nicole Crissman"],
    "Lee": ["Ben Lee", "Lisa Lee"],
    "Russell": ["Mark Russell", "Megan Russell"],
    "Siefert": ["Scott Siefert", "Susan Siefert"],
}

FAMILY_COLORS = {
    "Griffith": "#f2b134",
    "Crissman": "#ef6f61",
    "Lee": "#34d399",
    "Russell": "#60a5fa",
    "Siefert": "#c084fc",
}

TYPICAL_CATEGORIES = [
    "Main Dish", "Side Dish", "Salad", "Bread", "Appetizer",
    "Dessert", "Drinks", "Snacks", "Plates / Utensils", "Other",
]

DEFAULT_HERO_IMAGE = (
    "https://images.unsplash.com/photo-1566392062329-9935b9a7c950"
    "?fm=jpg&q=70&w=1600&auto=format&fit=crop"
)  # "Open bible with leaves on top" by Sixteen Miles Out -- Unsplash License (free to use)

DEFAULT_EVENT = {
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "time": "5:00 PM",
    "upcoming_dates": [],  # list of ISO "YYYY-MM-DD" strings
    "hero_image_url": DEFAULT_HERO_IMAGE,
    "hero_title": "Bible Study & Fellowship",
    "hero_sub": "Food Brings Us Together",
    "hero_verse_text": "They broke bread in their homes and ate together with glad and sincere hearts.",
    "hero_verse_ref": "Acts 2:46",
    "callout_text": (
        "Sign your family up below to bring a dish, drink, or item. Signing up also "
        "lets us know you're planning to be there -- thank you for helping make this "
        "a special time together!"
    ),
    "categories": [
        {"name": "Main Dish", "desc": "Casserole, pasta, chicken, etc.", "slots": 2},
        {"name": "Side Dish", "desc": "Salad, vegetables, rice, etc.", "slots": 4},
        {"name": "Dessert", "desc": "Cookies, brownies, fruit, etc.", "slots": 2},
        {"name": "Drinks", "desc": "Water, tea, lemonade, etc.", "slots": 2},
        {"name": "Plates / Utensils", "desc": "Plates, cups, napkins, utensils", "slots": 2},
        {"name": "Other", "desc": "Anything else!", "slots": 2},
    ],
}

# ----------------------------------------------------------------------
# Icons -- single-line SVG strings only (multi-line breaks HTML rendering)
# ----------------------------------------------------------------------
ICON_LEAF = '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#e8a33d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"></path><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 11 13.6 12 12"></path></svg>'
ICON_CAL = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#e8a33d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>'
ICON_PIN = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#e8a33d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>'
ICON_PEOPLE = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#e8a33d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>'
ICON_UTENSILS_W = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h1a2 2 0 0 0 2-2V2"></path><path d="M6 11v11"></path><path d="M18 2c-2 0-3 2-3 5v2c0 1 1 2 2 2h1v10"></path></svg>'
ICON_UTENSILS_D = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#e8a33d" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h1a2 2 0 0 0 2-2V2"></path><path d="M6 11v11"></path><path d="M18 2c-2 0-3 2-3 5v2c0 1 1 2 2 2h1v10"></path></svg>'
ICON_PLATE = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="3.5"></circle></svg>'
ICON_BOWL = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11h18a9 6.2 0 0 1-18 0z"></path><path d="M12 11V5"></path><path d="M8 7l4-2.5L16 7"></path></svg>'
ICON_CUPCAKE = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 10h14l-1.4 9a2 2 0 0 1-2 1.7h-7.2a2 2 0 0 1-2-1.7z"></path><path d="M7 10a5 4 0 0 1 10 0"></path><path d="M12 3v3"></path></svg>'
ICON_CUP = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3h13v9a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"></path><path d="M17 7h2a3 3 0 0 1 0 6h-2"></path><line x1="6" y1="21" x2="14" y2="21"></line></svg>'
ICON_BREAD = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12c0-5 3-9 8-9s8 4 8 9-3 6-8 6-8-1-8-6z"></path><path d="M9 11v3"></path><path d="M12 10v4"></path><path d="M15 11v3"></path></svg>'
ICON_BOX = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8l-9-5-9 5 9 5 9-5z"></path><path d="M3 8v8l9 5 9-5V8"></path><path d="M12 13v8"></path></svg>'
ICON_ALERT = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#b45309" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
DECO_BOOK_CUP = '<svg class="hero-deco" width="140" height="140" viewBox="0 0 100 100"><path d="M10 70h60l-4 22a4 4 0 0 1-4 3H18a4 4 0 0 1-4-3z" fill="none" stroke="#f7f3ec" stroke-width="3"/><path d="M14 70c0-14 8-24 26-24s26 10 26 24" fill="none" stroke="#f7f3ec" stroke-width="3"/><path d="M75 8L45 20v45l30-12z" fill="none" stroke="#f7f3ec" stroke-width="3"/><path d="M75 8l25 12v45L75 53z" fill="none" stroke="#f7f3ec" stroke-width="3"/><line x1="75" y1="8" x2="75" y2="53" stroke="#f7f3ec" stroke-width="3"/></svg>'

CATEGORY_ICONS = {
    "Main Dish": ICON_PLATE, "Side Dish": ICON_BOWL, "Salad": ICON_BOWL,
    "Dessert": ICON_CUPCAKE, "Drinks": ICON_CUP, "Snacks": ICON_BOX,
    "Bread": ICON_BREAD, "Appetizer": ICON_UTENSILS_W,
    "Plates / Utensils": ICON_UTENSILS_W, "Other": ICON_BOX,
}


def cat_icon(name):
    return CATEGORY_ICONS.get(name, ICON_UTENSILS_W)


def initials(name):
    letters = name.strip()
    return (letters[:2] if len(letters) >= 2 else letters).upper()


def fmt_date(iso_str):
    try:
        d = datetime.strptime(iso_str, "%Y-%m-%d").date()
        return d.strftime("%A, %m/%d/%Y")
    except ValueError:
        return iso_str


def weekday_of(iso_str):
    try:
        d = datetime.strptime(iso_str, "%Y-%m-%d").date()
        return d.strftime("%A")
    except ValueError:
        return ""


# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown(
    '<style>'
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');"
    '#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}'
    # Override Streamlit's own theme variables directly -- dark navy base,
    # gold accent, matching the SBC Hoops app.
    ':root, .stApp {'
    '--background-color:#0d1117 !important; --secondary-background-color:#161b22 !important; '
    '--text-color:#f3f4f6 !important; --primary-color:#e8a33d !important;'
    '}'
    'html, body, .stApp { background-color: #0d1117 !important; }'
    "html, body, [class*='css'] { font-family: 'Inter', sans-serif; color:#f3f4f6; }"
    '.block-container {padding-top: 0.5rem; padding-bottom: 1.6rem; max-width: 560px;}'
    '.brand-row {display:flex; align-items:center; gap:0.5rem;}'
    ".brand-name {font-family:'Inter', sans-serif; font-size:1.5rem; font-weight:900; color:#f3f4f6 !important; margin:0; letter-spacing:0.01em;}"
    '.brand-sub {font-size:0.75rem; color:#9ca3af !important; margin-top:-0.1rem; text-transform:uppercase; letter-spacing:0.05em;}'
    '.st-key-admin_toggle_btn button {padding: 0.2rem 0.9rem !important; font-size: 0.78rem !important; min-height: 0 !important; margin-top: 0.35rem; font-weight:800 !important; text-transform:uppercase; letter-spacing:0.04em;}'
    '.hero {position: relative; border-radius: 16px; overflow: hidden; margin: 0.6rem 0 0.8rem 0; color:#f3f4f6; min-height: 190px; background: linear-gradient(120deg, #2a2115 0%, #3a2f1c 45%, #4a3a20 100%); background-size: cover; background-position: center; border:1px solid #2a2f3a;}'
    '.hero-overlay {position: absolute; inset: 0; z-index: 2; display:flex; flex-direction:column; justify-content:center; background: linear-gradient(180deg, rgba(8,10,14,0.75), rgba(8,10,14,0.9)); padding: 1.3rem 1.2rem;}'
    ".hero-title {font-family:'Inter', sans-serif; font-size:1.7rem; font-weight:900; line-height:1.2; margin:0; color:#f3f4f6 !important; text-shadow: 0 2px 6px rgba(0,0,0,0.6);}"
    '.hero-sub {font-size:1.02rem; opacity:0.96; margin: 0.15rem 0 0.6rem 0; color:#e8a33d !important; font-weight:700; text-shadow: 0 1px 4px rgba(0,0,0,0.5);}'
    '.hero-verse {font-size:0.85rem; font-style:italic; color:#e5e7eb !important; opacity:0.96; border-left:3px solid #e8a33d; padding-left:0.6rem;}'
    '.hero-deco {position:absolute; right:-10px; bottom:-10px; opacity:0.15; z-index:1;}'
    '.stat-card {background:#161b22; border:1px solid #2a2f3a; border-radius:12px; padding:0.65rem 0.75rem; height:100%;}'
    '.stat-label {font-size:0.68rem; color:#9ca3af !important; font-weight:800; text-transform:uppercase; letter-spacing:0.05em;}'
    '.stat-value {font-size:0.92rem; color:#f3f4f6 !important; font-weight:800; margin-top:0.15rem; line-height:1.35;}'
    '.stat-row {display:flex; align-items:flex-start; gap:0.4rem;}'
    '.section-title {display:flex; align-items:center; gap:0.4rem; font-family:"Inter", sans-serif; font-size:1.05rem; font-weight:800; color:#e8a33d !important; margin:0.8rem 0 0.4rem 0; text-transform:uppercase; letter-spacing:0.04em;}'
    '.dates-strip {display:flex; gap:0.5rem; overflow-x:auto; padding-bottom:0.3rem;}'
    '.date-pill {flex: 0 0 auto; min-width: 100px; text-align:center; border-radius:10px; padding:0.5rem 0.6rem; border:1px solid #2a2f3a; background:#161b22;}'
    '.date-pill.next {background:rgba(232,163,61,0.12); border-color:#e8a33d;}'
    '.date-pill .dow {font-size:0.7rem; color:#9ca3af !important; font-weight:700; text-transform:uppercase;}'
    '.date-pill.next .dow {color:#e8a33d !important;}'
    '.date-pill .dnum {font-size:0.85rem; font-weight:800; color:#f3f4f6 !important; margin-top:0.15rem;}'
    '.allergy-card {background:#241c10; border:1px solid #6b4f1a; border-radius:12px; padding:0.75rem 1rem; margin:0.6rem 0;}'
    '.allergy-title {display:flex; align-items:center; gap:0.4rem; font-weight:800; color:#f2b134 !important; font-size:0.95rem; margin-bottom:0.3rem;}'
    '.allergy-row {font-size:0.87rem; color:#e5d4a8 !important; margin-top:0.2rem;}'
    '.callout {background:#12241d; border:1px solid #1f4d3d; border-radius:12px; padding:0.85rem 1rem; margin:0.7rem 0; display:flex; gap:0.6rem;}'
    '.callout b {color:#4ade80 !important;} .callout p {margin:0.2rem 0 0 0; font-size:0.92rem; color:#d1fae5 !important;}'
    '.cat-card {background:#161b22; border:1.5px solid #2a2f3a; border-radius:14px; padding:0.85rem 1rem; margin-bottom:0.7rem; box-shadow: 0 2px 8px rgba(0,0,0,0.3);}'
    '.cat-row {display:flex; align-items:center; gap:0.7rem;}'
    '.cat-avatar {width:44px; height:44px; border-radius:10px; flex-shrink:0; display:flex; align-items:center; justify-content:center; background:#2a2115; border:1px solid #e8a33d;}'
    '.cat-name {font-weight:800; font-size:1.05rem; color:#f3f4f6 !important; margin:0;}'
    '.cat-desc {color:#9ca3af !important; font-size:0.85rem; margin:0.1rem 0 0 0;}'
    '.cat-progress {font-size:0.8rem; color:#4ade80 !important; font-weight:700; margin-top:0.15rem;}'
    '.cat-row-slim {display:flex; align-items:center; gap:0.5rem; flex-wrap:nowrap; overflow:hidden;}'
    '.cat-avatar-sm {width:26px; height:26px; border-radius:7px; flex-shrink:0; display:flex; align-items:center; justify-content:center; background:#2a2115; border:1px solid #e8a33d;}'
    '.cat-avatar-sm svg {width:14px !important; height:14px !important;}'
    '.cat-name-slim {font-weight:800; font-size:0.9rem; color:#f3f4f6 !important; white-space:nowrap; flex-shrink:0;}'
    '.cat-desc-slim {color:#9ca3af !important; font-size:0.78rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}'
    '.cat-qty-slim {color:#4ade80 !important; font-weight:700; font-size:0.78rem; white-space:nowrap; margin-left:auto; padding-left:0.4rem; flex-shrink:0;}'
    '.cat-qty-slim.full {color:#6b7280 !important;}'
    '.cat-progress.full {color:#6b7280 !important;}'
    '.who-label {font-size:0.72rem; font-weight:700; color:#9ca3af !important; text-transform:uppercase; letter-spacing:0.03em; margin-top:0.25rem;}'
    '.signee-row {display:flex; align-items:center; justify-content:space-between; background:linear-gradient(135deg, #16302650, #0d1117); border:1px solid #1f4d3d; border-radius:8px; padding:0.35rem 0.65rem; margin-top:0.15rem; font-size:0.87rem;}'
    '.signee-left {display:flex; align-items:center;}'
    '.signee-avatar {width:28px; height:28px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; color:#0d1117 !important; font-size:0.7rem; font-weight:900; margin-right:0.55rem; flex-shrink:0;}'
    '.signee-name {font-weight:800; color:#f3f4f6 !important;}'
    '.signee-detail {color:#9ca3af !important;}'
    'div.stButton > button {border-radius:8px; font-weight:700; font-size:0.9rem; background-color:#161b22; color:#f3f4f6; border:1px solid #2a2f3a;}'
    # Attribute-based selector, matches every Streamlit button regardless of
    # which container (dialog, form, expander) it's rendered inside.
    'button[kind="secondary"], button[kind="secondaryFormSubmit"] {'
    'background-color:#161b22 !important; color:#f3f4f6 !important; border:1px solid #2a2f3a !important;}'
    'button[kind="primary"], button[kind="primaryFormSubmit"] {'
    'background-color:#e8a33d !important; color:#1a1206 !important; border:none !important; font-weight:800 !important;}'
    '.version-tag {text-align:left; color:#4b5563; font-size:0.68rem; margin:0.1rem 0 0.3rem 0;}'
    # --- Fallback overrides for native widget chrome. ---
    '[data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {background-color:#0d1117 !important;}'
    '.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input {'
    'background-color:#161b22 !important; color:#f3f4f6 !important; border:1px solid #2a2f3a !important;}'
    '[data-baseweb="select"] * {background-color:#161b22 !important; color:#f3f4f6 !important;}'
    '[data-testid="stForm"] {background-color:#161b22 !important; border:1px solid #2a2f3a !important; '
    'border-radius:12px !important; padding:1rem !important;}'
    '.stAlert, .stAlert p, .stSuccess, .stError, .stCaption, .stCaption p {color:#f3f4f6 !important;}'
    # --- Dialogs/modals and date-picker calendars render in their own portal
    # layer -- keep them dark too, matching the rest of the app now. ---
    '[data-testid="stDialog"], div[role="dialog"], [data-testid*="Modal"], [data-testid*="modal"] '
    '{background-color:#161b22 !important;}'
    '[data-testid="stDialog"] *, div[role="dialog"] *, [data-testid*="Modal"] *, [data-testid*="modal"] * '
    '{color:#f3f4f6 !important;}'
    '[data-testid="stDialog"] h1, [data-testid="stDialog"] h2, [data-testid="stDialog"] h3, '
    'div[role="dialog"] h1, div[role="dialog"] h2, div[role="dialog"] h3 {color:#e8a33d !important;}'
    '[data-testid="stDialog"] input, [data-testid="stDialog"] textarea, '
    'div[role="dialog"] input, div[role="dialog"] textarea, '
    '[data-testid="stDialog"] [data-baseweb="select"] *, div[role="dialog"] [data-baseweb="select"] * '
    '{background-color:#0d1117 !important; color:#f3f4f6 !important; border-color:#2a2f3a !important;}'
    '[data-testid="stDialog"] div.stButton > button, div[role="dialog"] div.stButton > button '
    '{background-color:#e8a33d !important; color:#1a1206 !important; border:none !important; font-weight:700 !important;}'
    '[data-baseweb="popover"], [data-baseweb="calendar"] '
    '{background-color:#161b22 !important; color:#f3f4f6 !important;}'
    '[data-baseweb="calendar"] *, [data-baseweb="popover"] * {color:#f3f4f6 !important;}'
    '[data-baseweb="calendar"] button svg, [data-baseweb="popover"] button svg '
    '{fill:#e8a33d !important; stroke:#e8a33d !important; opacity:1 !important;}'
    '[data-baseweb="calendar"] button {background-color:#161b22 !important;}'
    '</style>',
    unsafe_allow_html=True,
)


def pencil_css(key):
    st.markdown(
        '<style>.st-key-' + key + ' button {padding:0.02rem 0.5rem !important; font-size:1rem !important; '
        'min-height:0 !important; line-height:1.6 !important; background:#1f2530 !important; color:#e8a33d !important; '
        'border:1px solid #3a4150 !important;}</style>',
        unsafe_allow_html=True,
    )


def small_remove_css(key):
    st.markdown(
        '<style>.st-key-' + key + ' button {padding:0.02rem 0.5rem !important; font-size:0.72rem !important; '
        'min-height:0 !important; background:#2a1418 !important; color:#f87171 !important; '
        'border:1px solid #5c2a2e !important;}</style>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# Firebase
# ----------------------------------------------------------------------
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        if "firebase" not in st.secrets:
            st.error(
                "Firebase isn't configured yet. Add a [firebase] section with "
                "your service account JSON key to this app's Secrets."
            )
            st.stop()
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


db = get_db()
ADMIN_PIN = st.secrets.get("admin_pin", "2468")

# ----------------------------------------------------------------------
# Data access
# ----------------------------------------------------------------------
def bump_version():
    db.collection("meta").document("version").set(
        {"count": firestore.Increment(1)}, merge=True
    )


def get_version():
    doc = db.collection("meta").document("version").get()
    if doc.exists:
        return int(doc.to_dict().get("count", 0))
    return 0


def load_event():
    doc = db.collection("meta").document("event").get()
    data = DEFAULT_EVENT.copy()
    if doc.exists:
        stored = doc.to_dict()
        data.update(stored)
        if "categories" in stored:
            data["categories"] = stored["categories"]

    # Self-heal: drop any legacy free-text dates that aren't real ISO dates
    # (e.g. old "10/11/10/25" style strings from before the date picker).
    valid_dates = []
    for d in data.get("upcoming_dates", []):
        try:
            datetime.strptime(d, "%Y-%m-%d")
            valid_dates.append(d)
        except (ValueError, TypeError):
            pass
    valid_dates = [d for d in valid_dates if d >= date.today().isoformat()]
    data["upcoming_dates"] = sorted(valid_dates)

    # Fall back to the default background photo if none was set (or was
    # explicitly cleared), rather than showing nothing.
    if not data.get("hero_image_url"):
        data["hero_image_url"] = DEFAULT_HERO_IMAGE

    return data


def save_event(data):
    db.collection("meta").document("event").set(data, merge=True)
    bump_version()


def load_signups():
    docs = db.collection("signups").stream()
    return {d.id: d.to_dict() for d in docs}


def save_signup(family, category, count):
    db.collection("signups").document(family).set({"category": category, "count": count})
    bump_version()


def remove_signup(family):
    db.collection("signups").document(family).delete()
    bump_version()


def clear_all_signups():
    for doc in db.collection("signups").stream():
        doc.reference.delete()
    bump_version()


def load_allergies():
    docs = db.collection("allergies").stream()
    return {d.id: d.to_dict().get("note", "") for d in docs}


def save_allergy(family, note):
    db.collection("allergies").document(family).set({"note": note})
    bump_version()


def remove_allergy(family):
    db.collection("allergies").document(family).delete()
    bump_version()


# ----------------------------------------------------------------------
# Dialogs
# ----------------------------------------------------------------------
@st.dialog("Host PIN")
def admin_pin_dialog():
    pin = st.text_input("Enter host PIN", type="password", key="pin_dialog_input")
    c1, c2 = st.columns(2)
    if c1.button("Unlock", type="primary", use_container_width=True):
        if pin == str(ADMIN_PIN):
            st.session_state.admin_ok = True
            st.session_state.admin_open = True
            st.rerun()
        else:
            st.error("Incorrect PIN.")
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Sign up to bring something")
def sign_up_dialog(category_name, signed_families, allergies):
    st.markdown(f"Signing up for **{category_name}**")
    fam_names = list(FAMILIES.keys())
    last = st.session_state.get("last_family")
    default_idx = fam_names.index(last) if last in fam_names else 0
    family = st.selectbox("Your family", fam_names, index=default_idx, key="dlg_family")
    current = signed_families.get(family)
    default_count = current["count"] if current else 2
    count = st.number_input(
        "How many attending", min_value=0, max_value=15, value=default_count, step=1, key="dlg_count"
    )
    allergy_note = st.text_input(
        "Allergies / dietary notes (optional)", value=allergies.get(family, ""), key="dlg_allergy"
    )
    if current and current["category"] != category_name:
        st.caption(f"{family} is currently signed up for {current['category']}. Confirming moves them here.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_signup(family, category_name, count)
        save_allergy(family, allergy_note.strip())
        st.session_state.last_family = family
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()
    if current:
        if st.button("Remove this family's sign-up", use_container_width=True):
            remove_signup(family)
            st.rerun()


@st.dialog("Edit Next Meeting")
def edit_meeting_dialog(event):
    new_time = st.text_input("Time (e.g. '5:00 PM' or '5:00 - 7:00 PM')", value=event["time"])
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        save_event({"time": new_time})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Edit Banner")
def edit_hero_dialog(event):
    new_title = st.text_input("Title", value=event["hero_title"])
    new_sub = st.text_input("Subtitle", value=event["hero_sub"])
    new_verse_text = st.text_area("Verse text", value=event["hero_verse_text"], height=80)
    new_verse_ref = st.text_input("Verse reference (e.g. 'Acts 2:46')", value=event["hero_verse_ref"])
    new_image = st.text_input(
        "Background image URL (optional -- a photo you have the rights to use)",
        value=event.get("hero_image_url", ""),
    )
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        save_event({
            "hero_title": new_title,
            "hero_sub": new_sub,
            "hero_verse_text": new_verse_text,
            "hero_verse_ref": new_verse_ref,
            "hero_image_url": new_image.strip(),
        })
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Edit Location")
def edit_location_dialog(event):
    new_address = st.text_input("Address", value=event["address"])
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        save_event({"address": new_address})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def render_dates_editor(event):
    """Rendered inline (not as a modal) -- the date-picker's month header
    was getting clipped inside the dialog's fixed-height popup."""
    dates = sorted(event["upcoming_dates"])
    st.markdown("**Current dates**")
    if dates:
        for d in dates:
            r1, r2 = st.columns([3, 1])
            r1.write(fmt_date(d))
            rkey = f"rm_date_{d}"
            if r2.button("Remove", key=rkey):
                remaining = [x for x in dates if x != d]
                save_event({"upcoming_dates": remaining})
                st.rerun()
            small_remove_css(rkey)
    else:
        st.caption("No dates yet.")
    st.divider()
    new_d = st.date_input(
        "Add a date", value=date.today() + timedelta(days=7),
        min_value=date.today(), max_value=date.today() + timedelta(days=730),
        key="new_date_input",
    )
    if st.button("Add date", type="primary", key="add_date_btn"):
        iso = new_d.isoformat()
        if iso not in dates:
            dates.append(iso)
        save_event({"upcoming_dates": sorted(dates)})
        st.rerun()


@st.dialog("Edit Welcome Message")
def edit_callout_dialog(event):
    new_text = st.text_area("Message", value=event["callout_text"], height=120)
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        save_event({"callout_text": new_text})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
event = load_event()
signed_families = load_signups()
allergies = load_allergies()
active_allergies = {f: n for f, n in allergies.items() if n and n.strip()}

if "admin_open" not in st.session_state:
    st.session_state.admin_open = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "show_dates_editor" not in st.session_state:
    st.session_state.show_dates_editor = False

is_admin = st.session_state.admin_ok
admin_visible = is_admin and st.session_state.admin_open
total_people = sum(d["count"] for d in signed_families.values())

# ----------------------------------------------------------------------
# Brand bar + Admin
# ----------------------------------------------------------------------
b1, b2 = st.columns([4, 1])
with b1:
    st.markdown(
        '<div class="brand-row">' + ICON_LEAF +
        '<div><p class="brand-name">SBC Growth Group</p>'
        '<p class="brand-sub">Study &middot; Grow &middot; Belong</p>'
        '<div class="version-tag">v1.' + str(get_version()) + '</div></div></div>',
        unsafe_allow_html=True,
    )
with b2:
    if st.button("Host", key="admin_toggle_btn"):
        if is_admin:
            st.session_state.admin_open = not st.session_state.admin_open
        else:
            admin_pin_dialog()

if st.session_state.admin_open:
    st.markdown(
        '<style>.st-key-admin_toggle_btn button {background-color:#161b22 !important; '
        'color:#e8a33d !important; border:2px solid #e8a33d !important; '
        'box-shadow: 0 0 0 2px rgba(232,163,61,0.25) !important;}</style>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<style>.st-key-admin_toggle_btn button {background-color:#161b22 !important; '
        'color:#f3f4f6 !important; border:2px solid #2a2f3a !important; box-shadow:none !important;}</style>',
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------
hero_style = ""
if event.get("hero_image_url"):
    hero_style = " style=\"background-image: url('" + event["hero_image_url"] + "');\""
deco = "" if event.get("hero_image_url") else DECO_BOOK_CUP

st.markdown(
    '<div class="hero"' + hero_style + '>' + deco +
    '<div class="hero-overlay">'
    '<p class="hero-title">' + event["hero_title"] + '</p>'
    '<p class="hero-sub">' + event["hero_sub"] + '</p>'
    '<div class="hero-verse">&quot;' + event["hero_verse_text"] + '&quot;<br>-- ' + event["hero_verse_ref"] + '</div>'
    '</div></div>',
    unsafe_allow_html=True,
)

if admin_visible:
    hcol1, hcol2 = st.columns([5, 1])
    with hcol2:
        if st.button(PENCIL, key="edit_hero_btn", use_container_width=True):
            edit_hero_dialog(event)
        pencil_css("edit_hero_btn")

# ----------------------------------------------------------------------
# Stat cards: Next Meeting / Location / Families Attending
# ----------------------------------------------------------------------
sorted_dates = sorted(event["upcoming_dates"])
next_date = fmt_date(sorted_dates[0]) if sorted_dates else "Date TBD"

s1, s2, s3 = st.columns(3)
with s1:
    st.markdown(
        '<div class="stat-card"><div class="stat-row">' + ICON_CAL +
        '<div><div class="stat-label">Next Meeting</div>'
        '<div class="stat-value">' + next_date + '<br>' + event['time'] + '</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if admin_visible:
        if st.button(PENCIL, key="edit_meeting_btn"):
            edit_meeting_dialog(event)
        pencil_css("edit_meeting_btn")
with s2:
    st.markdown(
        '<div class="stat-card"><div class="stat-row">' + ICON_PIN +
        '<div><div class="stat-label">Location</div>'
        '<div class="stat-value">' + event['address'] + '</div></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if admin_visible:
        if st.button(PENCIL, key="edit_location_btn"):
            edit_location_dialog(event)
        pencil_css("edit_location_btn")
with s3:
    st.markdown(
        '<div class="stat-card"><div class="stat-row">' + ICON_PEOPLE +
        '<div><div class="stat-label">Families Attending</div>'
        '<div class="stat-value">' + str(len(signed_families)) + ' families<br>('
        + str(total_people) + ' people)</div></div></div></div>',
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Upcoming Dates strip
# ----------------------------------------------------------------------
dh1, dh2 = st.columns([3, 1])
with dh1:
    st.markdown('<div class="section-title">' + ICON_CAL + ' Upcoming Dates</div>', unsafe_allow_html=True)
with dh2:
    if admin_visible:
        if st.button(PENCIL, key="edit_dates_btn"):
            st.session_state.show_dates_editor = not st.session_state.get("show_dates_editor", False)
        pencil_css("edit_dates_btn")

if admin_visible and st.session_state.get("show_dates_editor"):
    with st.container(border=True):
        render_dates_editor(event)

if sorted_dates:
    pills = ""
    for i, d in enumerate(sorted_dates):
        cls = "date-pill next" if i == 0 else "date-pill"
        pills += ('<div class="' + cls + '"><div class="dow">' + weekday_of(d) +
                  '</div><div class="dnum">' + d + '</div></div>')
    st.markdown('<div class="dates-strip">' + pills + '</div>', unsafe_allow_html=True)
else:
    st.caption("No dates posted yet.")

# ----------------------------------------------------------------------
# Allergy / dietary notes (persistent -- never cleared for new night)
# ----------------------------------------------------------------------
if active_allergies:
    rows = ""
    for fam, note in active_allergies.items():
        rows += '<div class="allergy-row"><b>' + fam + ' Family:</b> ' + note + '</div>'
    st.markdown(
        '<div class="allergy-card"><div class="allergy-title">' + ICON_ALERT +
        ' Allergies &amp; Dietary Notes</div>' + rows + '</div>',
        unsafe_allow_html=True,
    )
    if admin_visible:
        for fam in active_allergies:
            rkey = f"rm_allergy_{fam}"
            if st.button(f"Remove {fam}'s note", key=rkey):
                remove_allergy(fam)
                st.rerun()
            small_remove_css(rkey)

# ----------------------------------------------------------------------
# Callout
# ----------------------------------------------------------------------
ch1, ch2 = st.columns([5, 1])
with ch1:
    st.markdown(
        '<div class="callout">' + ICON_LEAF +
        '<p><b>Let\'s Share a Meal!</b><br>' + event["callout_text"] + '</p></div>',
        unsafe_allow_html=True,
    )
with ch2:
    if admin_visible:
        if st.button(PENCIL, key="edit_callout_btn"):
            edit_callout_dialog(event)
        pencil_css("edit_callout_btn")

# ----------------------------------------------------------------------
# Food Sign Up section
# ----------------------------------------------------------------------
st.markdown('<div class="section-title">' + ICON_UTENSILS_D + ' Food Sign Up</div>', unsafe_allow_html=True)

for idx, cat in enumerate(event["categories"]):
    name, desc, slots = cat["name"], cat.get("desc", ""), cat.get("slots", 1)
    display_name = name if name else "Not set yet"
    matches = [f for f, d in signed_families.items() if d["category"] == name]
    filled = len(matches)
    remaining = max(slots - filled, 0)
    card_key = f"catcard_{idx}"

    st.markdown(
        '<style>.st-key-' + card_key + ', .st-key-' + card_key + ' > div, '
        '.st-key-' + card_key + ' [data-testid="stVerticalBlockBorderWrapper"], '
        '.st-key-' + card_key + ' [data-testid="stVerticalBlock"] '
        '{border:1.5px solid #2a2f3a !important; border-radius:12px !important; '
        'box-shadow: 0 2px 6px rgba(0,0,0,0.25) !important; '
        'background:#161b22 !important;}'
        '.st-key-' + card_key + ' [data-testid="stVerticalBlockBorderWrapper"] '
        '{padding:0.5rem 0.7rem !important; margin-bottom:0.5rem !important;}'
        '.st-key-' + card_key + ' [data-testid="stVerticalBlock"] {gap: 0.15rem !important;}'
        '.st-key-' + card_key + ' [data-testid="element-container"] {margin-bottom: 0 !important;}'
        '.st-key-' + card_key + ' [data-testid="column"]:last-child {display:flex !important; '
        'align-items:center !important; justify-content:center !important;}</style>',
        unsafe_allow_html=True,
    )

    with st.container(border=True, key=card_key):
        cc1, cc2 = st.columns([3, 1.1])
        with cc1:
            progress_class = "full" if remaining == 0 else ""
            st.markdown(
                '<div class="cat-row-slim"><div class="cat-avatar-sm">' + cat_icon(name) + '</div>'
                '<span class="cat-name-slim">' + display_name + '</span>'
                '<span class="cat-desc-slim">' + desc + '</span>'
                '<span class="cat-qty-slim ' + progress_class + '">' + str(filled) + '/' + str(slots) +
                ' needed</span></div>',
                unsafe_allow_html=True,
            )
        with cc2:
            btn_label = "Full" if remaining == 0 else "Sign Up"
            btn_key = f"signup_{idx}"
            if st.button(btn_label, key=btn_key, use_container_width=True):
                sign_up_dialog(name if name else display_name, signed_families, allergies)
            if remaining == 0:
                st.markdown(
                    '<style>.st-key-' + btn_key + ' button {background-color:#2a2f3a !important; '
                    'color:#9ca3af !important; border:1px solid #3a4150 !important; font-weight:700 !important;}</style>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<style>.st-key-' + btn_key + ' button {background-color:#e8a33d !important; '
                    'color:#1a1206 !important; border:none !important; font-weight:800 !important;}</style>',
                    unsafe_allow_html=True,
                )

        if matches:
            st.markdown('<div class="who-label">Who\'s bringing it</div>', unsafe_allow_html=True)
        for fam in matches:
            d = signed_families[fam]
            fcolor = FAMILY_COLORS.get(fam, "#9ca3af")
            row_html = (
                '<div class="signee-row"><span class="signee-left">'
                '<span class="signee-avatar" style="background:' + fcolor + ';">' + initials(fam) + '</span>'
                '<span class="signee-name">The ' + fam + ' Family</span></span>'
                '<span class="signee-detail">' + str(d['count']) + ' people</span></div>'
            )
            if admin_visible:
                r1, r2 = st.columns([4, 1])
                with r1:
                    st.markdown(row_html, unsafe_allow_html=True)
                with r2:
                    rkey = f"rm_cat_signee_{idx}_{fam}"
                    if st.button("Remove", key=rkey):
                        remove_signup(fam)
                        st.rerun()
                    small_remove_css(rkey)
            else:
                st.markdown(row_html, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Admin bottom strip: bulk food overview + clear-for-new-night + lock
# ----------------------------------------------------------------------
if admin_visible:
    st.divider()
    st.markdown("**Host Tools**")
    st.caption(
        f"Small {PENCIL} buttons appear next to Next Meeting, Location, Upcoming Dates, "
        "the welcome message, and each food category above for quick edits."
    )

    st.markdown("**Food Needed This Week** (changes save automatically)")
    name_options = ["Not set yet"] + TYPICAL_CATEGORIES
    total_cats = len(event["categories"])

    def _save_bulk_row(total=total_cats):
        cats = []
        for j in range(total):
            raw_name = st.session_state.get(f"bulk_name_{j}", "Not set yet")
            cats.append({
                "name": "" if raw_name == "Not set yet" else raw_name,
                "desc": st.session_state.get(f"bulk_desc_{j}", ""),
                "slots": int(st.session_state.get(f"bulk_qty_{j}", 1) or 0),
            })
        save_event({"categories": cats})

    for i, cat in enumerate(event["categories"]):
        rc1, rc2, rc3, rc4 = st.columns([1.6, 2.1, 0.8, 0.6])
        with rc1:
            cur_idx = name_options.index(cat["name"]) if cat["name"] in TYPICAL_CATEGORIES else 0
            st.selectbox(
                "Category", options=name_options, index=cur_idx,
                key=f"bulk_name_{i}", label_visibility="collapsed", on_change=_save_bulk_row,
            )
        with rc2:
            st.text_input(
                "Description", value=cat.get("desc", ""), key=f"bulk_desc_{i}",
                label_visibility="collapsed", on_change=_save_bulk_row,
            )
        with rc3:
            st.number_input(
                "Qty", min_value=0, max_value=50, value=int(cat.get("slots", 1)),
                step=1, key=f"bulk_qty_{i}", label_visibility="collapsed", on_change=_save_bulk_row,
            )
        with rc4:
            if st.button("X", key=f"bulk_del_{i}", use_container_width=True):
                cats = [dict(c) for j, c in enumerate(event["categories"]) if j != i]
                save_event({"categories": cats})
                st.rerun()
            small_remove_css(f"bulk_del_{i}")

    st.markdown("*Add a new category:*")
    ac1, ac2, ac3, ac4 = st.columns([1.4, 1.7, 0.8, 0.8])
    with ac1:
        new_name = st.selectbox("New category", options=name_options, key="new_cat_name", label_visibility="collapsed")
    with ac2:
        new_desc = st.text_input("New description", value="", key="new_cat_desc", label_visibility="collapsed")
    with ac3:
        new_qty = st.number_input("New qty", min_value=0, max_value=50, value=2, step=1, key="new_cat_qty", label_visibility="collapsed")
    with ac4:
        if st.button("Add", key="new_cat_add_btn", use_container_width=True):
            cats = [dict(c) for c in event["categories"]]
            cats.append({"name": "" if new_name == "Not set yet" else new_name, "desc": new_desc, "slots": int(new_qty)})
            save_event({"categories": cats})
            st.rerun()

    st.divider()
    st.markdown("**Start a new night**")
    st.caption(
        "Clears every family's sign-up so the board is empty for the next gathering. "
        "Allergy notes stay -- they're saved separately and don't get cleared."
    )
    confirm_clear = st.checkbox("I understand this clears all family sign-ups.")
    if st.button("Clear sign-ups for new night", disabled=not confirm_clear):
        clear_all_signups()
        st.success("Cleared! Ready for the next gathering.")
        st.rerun()

    st.divider()
    if st.button("Lock host panel"):
        st.session_state.admin_ok = False
        st.session_state.admin_open = False
        st.rerun()
