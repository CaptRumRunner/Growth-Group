"""
SBC Growth Group - Food Sign Up
---------------------------------
Single-page, mobile-first food sign-up board.

Signing a family up for a category IS their RSVP -- one active sign-up
per family (category + headcount); picking a new category moves them.

Admin PIN unlock happens in a popup. Once unlocked, small "Edit" buttons
appear next to each editable piece (meeting info, location, upcoming
dates, each food category) opening a focused pop-up dialog for that one
thing, instead of one big form.

Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
All icons are inline SVGs (no emoji), so nothing gets corrupted when
pasted through GitHub's editor.
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="SBC Growth Group", page_icon=":books:", layout="centered")

FAMILIES = {
    "Griffith": ["Claire Griffith", "Shannon Griffith"],
    "Crissman": ["David Crissman", "Nicole Crissman"],
    "Lee": ["Ben Lee", "Lisa Lee"],
    "Russell": ["Mark Russell", "Megan Russell"],
    "Siefert": ["Scott Siefert", "Susan Siefert"],
}

FAMILY_COLORS = {
    "Griffith": "#c9a227",
    "Crissman": "#c1573a",
    "Lee": "#4f8a68",
    "Russell": "#3b6ea5",
    "Siefert": "#8a5fa5",
}

TYPICAL_CATEGORIES = [
    "Main Dish", "Side Dish", "Salad", "Bread", "Appetizer",
    "Dessert", "Drinks", "Snacks", "Plates / Utensils", "Other",
]

DEFAULT_EVENT = {
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "time": "5:00 PM",
    "upcoming_dates": [],
    "hero_image_url": "",
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
# Icons (generic outline glyphs -- plain SVG, no emoji, no copyrighted art)
# ----------------------------------------------------------------------
ICON_LEAF = """<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"></path><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 11 13.6 12 12"></path></svg>"""
ICON_CAL = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>"""
ICON_PIN = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>"""
ICON_PEOPLE = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>"""
ICON_UTENSILS = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h1a2 2 0 0 0 2-2V2"></path><path d="M6 11v11"></path><path d="M18 2c-2 0-3 2-3 5v2c0 1 1 2 2 2h1v10"></path></svg>"""
ICON_UTENSILS_DARK = ICON_UTENSILS.replace('stroke="white"', 'stroke="#1f4d3d"')
ICON_PLATE = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="3.5"></circle></svg>"""
ICON_BOWL = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11h18a9 6.2 0 0 1-18 0z"></path><path d="M12 11V5"></path><path d="M8 7l4-2.5L16 7"></path></svg>"""
ICON_CUPCAKE = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 10h14l-1.4 9a2 2 0 0 1-2 1.7h-7.2a2 2 0 0 1-2-1.7z"></path><path d="M7 10a5 4 0 0 1 10 0"></path><path d="M12 3v3"></path></svg>"""
ICON_CUP = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3h13v9a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z"></path><path d="M17 7h2a3 3 0 0 1 0 6h-2"></path><line x1="6" y1="21" x2="14" y2="21"></line></svg>"""
ICON_BREAD = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12c0-5 3-9 8-9s8 4 8 9-3 6-8 6-8-1-8-6z"></path><path d="M9 11v3"></path><path d="M12 10v4"></path><path d="M15 11v3"></path></svg>"""
ICON_BOX = """<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8l-9-5-9 5 9 5 9-5z"></path><path d="M3 8v8l9 5 9-5V8"></path><path d="M12 13v8"></path></svg>"""
ICON_HEART = """<svg viewBox="0 0 24 24" width="22" height="22" fill="#3b6ea5" stroke="#3b6ea5" stroke-width="1"><path d="M12 21s-6.7-4.35-9.3-8.2C.8 9.7 1.9 6 5 5c1.9-.6 3.7.2 5 1.9C11.3 5.2 13.1 4.4 15 5c3.1 1 4.2 4.7 2.3 7.8C18.7 16.65 12 21 12 21z"></path></svg>"""

CATEGORY_ICONS = {
    "Main Dish": ICON_PLATE, "Side Dish": ICON_BOWL, "Salad": ICON_BOWL,
    "Dessert": ICON_CUPCAKE, "Drinks": ICON_CUP, "Snacks": ICON_BOX,
    "Bread": ICON_BREAD, "Appetizer": ICON_UTENSILS,
    "Plates / Utensils": ICON_UTENSILS, "Other": ICON_BOX,
}


def cat_icon(name):
    return CATEGORY_ICONS.get(name, ICON_UTENSILS)


def initials(name):
    letters = name.strip()
    return (letters[:2] if len(letters) >= 2 else letters).upper()


# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700;900&family=Inter:wght@400;600;700;800&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container {padding-top: 0.5rem; padding-bottom: 1.6rem; max-width: 560px;}

    .brand-row {display:flex; align-items:center; gap:0.5rem;}
    .brand-name {font-family:'Inter', sans-serif; font-size:1.4rem; font-weight:800; color:#14261d; margin:0;}
    .brand-sub {font-size:0.75rem; color:#6b6355; margin-top:-0.1rem;}

    .st-key-admin_toggle_btn button {
        padding: 0.2rem 0.7rem !important; font-size: 0.78rem !important;
        min-height: 0 !important; margin-top: 0.35rem;
    }

    .hero {
        position: relative; border-radius: 16px; overflow: hidden;
        margin: 0.6rem 0 0.8rem 0; color:#f7f3ec; min-height: 150px;
        background: linear-gradient(120deg, #5b3a29 0%, #7a5137 45%, #9c7248 100%);
        background-size: cover; background-position: center;
    }
    .hero-overlay {
        position: relative; z-index: 2;
        background: linear-gradient(180deg, rgba(30,20,12,0.35), rgba(30,20,12,0.65));
        padding: 1.3rem 1.2rem;
    }
    .hero-title {font-family:'Merriweather', serif; font-size:1.7rem; font-weight:900; line-height:1.2; margin:0; text-shadow: 0 2px 6px rgba(0,0,0,0.35);}
    .hero-sub {font-size:1.02rem; opacity:0.96; margin: 0.15rem 0 0.6rem 0; text-shadow: 0 1px 4px rgba(0,0,0,0.3);}
    .hero-verse {font-size:0.85rem; font-style:italic; opacity:0.94; border-left:3px solid #d4af37; padding-left:0.6rem;}
    .hero-deco {position:absolute; right:-10px; bottom:-10px; opacity:0.18; z-index:1;}

    .stat-card {background:#fff; border:1px solid #e7ddce; border-radius:12px; padding:0.65rem 0.75rem; height:100%;}
    .stat-label {font-size:0.7rem; color:#6b6355; font-weight:700; text-transform:uppercase; letter-spacing:0.03em;}
    .stat-value {font-size:0.92rem; color:#1a1f16; font-weight:800; margin-top:0.15rem; line-height:1.35;}
    .stat-row {display:flex; align-items:flex-start; gap:0.4rem;}

    .dates-header {display:flex; align-items:center; justify-content:space-between; margin: 0.7rem 0 0.35rem 0;}
    .dates-title {font-family:'Merriweather', serif; font-size:1rem; font-weight:700; color:#1f4d3d; display:flex; align-items:center; gap:0.4rem;}
    .dates-strip {display:flex; gap:0.5rem; overflow-x:auto; padding-bottom:0.3rem;}
    .date-pill {
        flex: 0 0 auto; min-width: 92px; text-align:center; border-radius:10px;
        padding:0.5rem 0.6rem; border:1px solid #e7ddce; background:#fff;
    }
    .date-pill.next {background:#e8f3ea; border-color:#8fc79c;}
    .date-pill .dow {font-size:0.68rem; color:#8a8171; font-weight:700; text-transform:uppercase;}
    .date-pill.next .dow {color:#1f4d3d;}
    .date-pill .dnum {font-size:0.88rem; font-weight:800; color:#1a1f16; margin-top:0.1rem;}

    .callout {background:#e8f3ea; border:1px solid #bfe0c6; border-radius:12px; padding:0.85rem 1rem; margin:0.7rem 0; display:flex; gap:0.6rem;}
    .callout b {color:#1f4d3d;}
    .callout p {margin:0.2rem 0 0 0; font-size:0.92rem; color:#2a352c;}

    .section-title {display:flex; align-items:center; gap:0.4rem; font-family:'Merriweather', serif; font-size:1.15rem; font-weight:700; color:#1f4d3d; margin:0.8rem 0 0.4rem 0;}

    .cat-card {background:#fff; border:1px solid #e7ddce; border-radius:12px; padding:0.75rem 0.9rem; margin-bottom:0.55rem;}
    .cat-row {display:flex; align-items:center; gap:0.7rem;}
    .cat-avatar {width:44px; height:44px; border-radius:10px; flex-shrink:0; display:flex; align-items:center; justify-content:center; background:#5b3a29;}
    .cat-name {font-weight:800; font-size:1.02rem; color:#1a1f16; margin:0;}
    .cat-desc {color:#4d473b; font-size:0.85rem; margin:0.1rem 0 0 0;}
    .cat-progress {font-size:0.8rem; color:#3d6b52; font-weight:700; margin-top:0.15rem;}
    .cat-progress.full {color:#6b6355;}

    .signee-row {display:flex; align-items:center; justify-content:flex-start; background:#f4f9f5; border-radius:8px; padding:0.4rem 0.65rem; margin-top:0.4rem; font-size:0.87rem;}
    .signee-avatar {width:26px; height:26px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; color:white; font-size:0.68rem; font-weight:800; margin-right:0.5rem; flex-shrink:0;}
    .signee-name {font-weight:700; color:#1a1f16;}
    .signee-detail {color:#4d473b;}

    div.stButton > button {border-radius:8px; font-weight:700; font-size:0.9rem;}
    .edit-btn button {padding: 0.1rem 0.5rem !important; font-size:0.72rem !important; min-height:0 !important; background:#f4f0e6 !important; color:#5b3a29 !important; border:1px solid #d9cdb8 !important;}

    .footer-card {background:#eef3fb; border:1px solid #c9d9ee; border-radius:12px; padding:0.9rem 1.05rem; margin-top:1rem; font-size:0.9rem; color:#26344a;}
    .footer-flourish {font-style:italic; color:#3b6ea5; text-align:right; margin-top:0.3rem;}
    .version-tag {text-align:center; color:#c7bfae; font-size:0.68rem; margin-top:1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

DECO_BOOK_CUP = """
<svg class="hero-deco" width="140" height="140" viewBox="0 0 100 100">
  <path d="M10 70h60l-4 22a4 4 0 0 1-4 3H18a4 4 0 0 1-4-3z" fill="none" stroke="#f7f3ec" stroke-width="3"/>
  <path d="M14 70c0-14 8-24 26-24s26 10 26 24" fill="none" stroke="#f7f3ec" stroke-width="3"/>
  <path d="M75 8L45 20v45l30-12z" fill="none" stroke="#f7f3ec" stroke-width="3"/>
  <path d="M75 8l25 12v45L75 53z" fill="none" stroke="#f7f3ec" stroke-width="3"/>
  <line x1="75" y1="8" x2="75" y2="53" stroke="#f7f3ec" stroke-width="3"/>
</svg>
"""


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
def load_event():
    doc = db.collection("meta").document("event").get()
    data = DEFAULT_EVENT.copy()
    if doc.exists:
        stored = doc.to_dict()
        data.update(stored)
        if "categories" in stored:
            data["categories"] = stored["categories"]
    return data


def save_event(data):
    db.collection("meta").document("event").set(data, merge=True)


def load_signups():
    docs = db.collection("signups").stream()
    return {d.id: d.to_dict() for d in docs}


def save_signup(family, category, count):
    db.collection("signups").document(family).set({"category": category, "count": count})


def remove_signup(family):
    db.collection("signups").document(family).delete()


def clear_all_signups():
    for doc in db.collection("signups").stream():
        doc.reference.delete()


# ----------------------------------------------------------------------
# Dialogs
# ----------------------------------------------------------------------
@st.dialog("Admin PIN")
def admin_pin_dialog():
    pin = st.text_input("Enter admin PIN", type="password", key="pin_dialog_input")
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
def sign_up_dialog(category_name, signed_families):
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
    if current and current["category"] != category_name:
        st.caption(f"{family} is currently signed up for {current['category']}. Confirming moves them here.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_signup(family, category_name, count)
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
    dates = event["upcoming_dates"][:]
    first = dates[0] if dates else ""
    new_first = st.text_input("Next meeting date (e.g. 'Wed, Jul 23, 2025')", value=first)
    new_time = st.text_input("Time (e.g. '5:00 PM' or '5:00 - 7:00 PM')", value=event["time"])
    new_image = st.text_input(
        "Hero background image URL (optional -- a photo you have the rights to use)",
        value=event.get("hero_image_url", ""),
    )
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        rest = dates[1:] if dates else []
        new_dates = ([new_first] if new_first.strip() else []) + rest
        save_event({"upcoming_dates": new_dates, "time": new_time, "hero_image_url": new_image.strip()})
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


@st.dialog("Edit Upcoming Dates")
def edit_dates_dialog(event):
    dates_text = st.text_area(
        "One date per line, soonest first", value="\n".join(event["upcoming_dates"]), height=140
    )
    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", use_container_width=True):
        dates_list = [d.strip() for d in dates_text.splitlines() if d.strip()]
        save_event({"upcoming_dates": dates_list})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Edit Category")
def edit_category_dialog(event, idx):
    cat = event["categories"][idx]
    options = ["(no type set)"] + TYPICAL_CATEGORIES
    current_index = options.index(cat["name"]) if cat["name"] in TYPICAL_CATEGORIES else 0
    name = st.selectbox("Category type", options=options, index=current_index)
    desc = st.text_input("Description", value=cat.get("desc", ""))
    qty = st.number_input("Qty needed", min_value=0, max_value=50, value=int(cat.get("slots", 1)), step=1)
    c1, c2, c3 = st.columns(3)
    if c1.button("Save", type="primary", use_container_width=True):
        cats = [dict(c) for c in event["categories"]]
        cats[idx] = {"name": "" if name == "(no type set)" else name, "desc": desc, "slots": int(qty)}
        save_event({"categories": cats})
        st.rerun()
    if c2.button("Remove", use_container_width=True):
        cats = [dict(c) for i, c in enumerate(event["categories"]) if i != idx]
        save_event({"categories": cats})
        st.rerun()
    if c3.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Add Category")
def add_category_dialog(event):
    options = ["(no type set)"] + TYPICAL_CATEGORIES
    name = st.selectbox("Category type", options=options)
    desc = st.text_input("Description", value="")
    qty = st.number_input("Qty needed", min_value=0, max_value=50, value=2, step=1)
    c1, c2 = st.columns(2)
    if c1.button("Add", type="primary", use_container_width=True):
        cats = [dict(c) for c in event["categories"]]
        cats.append({"name": "" if name == "(no type set)" else name, "desc": desc, "slots": int(qty)})
        save_event({"categories": cats})
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
event = load_event()
signed_families = load_signups()

if "admin_open" not in st.session_state:
    st.session_state.admin_open = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "show_attendees" not in st.session_state:
    st.session_state.show_attendees = False

is_admin = st.session_state.admin_ok
total_people = sum(d["count"] for d in signed_families.values())

# ----------------------------------------------------------------------
# Brand bar + Admin
# ----------------------------------------------------------------------
b1, b2 = st.columns([4, 1])
with b1:
    st.markdown(
        f"""<div class="brand-row">{ICON_LEAF}
        <div><p class="brand-name">SBC Growth Group</p><p class="brand-sub">Study &middot; Grow &middot; Belong</p></div>
        </div>""",
        unsafe_allow_html=True,
    )
with b2:
    if st.button("Admin", key="admin_toggle_btn"):
        if is_admin:
            st.session_state.admin_open = not st.session_state.admin_open
        else:
            admin_pin_dialog()

if st.session_state.admin_open:
    st.markdown(
        """<style>.st-key-admin_toggle_btn button {background-color:#c9a227 !important; color:#2b2109 !important; border:2px solid #8a6d16 !important;}</style>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """<style>.st-key-admin_toggle_btn button {background-color:#1f4d3d !important; color:#f7f3ec !important; border:none !important;}</style>""",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------
hero_style = ""
if event.get("hero_image_url"):
    hero_style = f'style="background-image: url(\'{event["hero_image_url"]}\');"'

st.markdown(
    f"""<div class="hero" {hero_style}>
    {DECO_BOOK_CUP if not event.get("hero_image_url") else ""}
    <div class="hero-overlay">
    <p class="hero-title">Bible Study &amp; Fellowship</p>
    <p class="hero-sub">Food Brings Us Together</p>
    <div class="hero-verse">"They broke bread in their homes and ate together with glad and sincere hearts."<br>-- Acts 2:46</div>
    </div></div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Stat cards: Next Meeting / Location / Families Attending
# ----------------------------------------------------------------------
next_date = event["upcoming_dates"][0] if event["upcoming_dates"] else "Date TBD"

s1, s2, s3 = st.columns(3)
with s1:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_CAL}
        <div><div class="stat-label">Next Meeting</div><div class="stat-value">{next_date}<br>{event['time']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
    if is_admin and st.session_state.admin_open:
        st.markdown('<div class="edit-btn">', unsafe_allow_html=True)
        if st.button("Edit", key="edit_meeting_btn", use_container_width=True):
            edit_meeting_dialog(event)
        st.markdown('</div>', unsafe_allow_html=True)
with s2:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PIN}
        <div><div class="stat-label">Location</div><div class="stat-value">{event['address']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
    if is_admin and st.session_state.admin_open:
        st.markdown('<div class="edit-btn">', unsafe_allow_html=True)
        if st.button("Edit", key="edit_location_btn", use_container_width=True):
            edit_location_dialog(event)
        st.markdown('</div>', unsafe_allow_html=True)
with s3:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PEOPLE}
        <div><div class="stat-label">Families Attending</div><div class="stat-value">{len(signed_families)} families<br>({total_people} people)</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Upcoming Dates strip
# ----------------------------------------------------------------------
dh1, dh2 = st.columns([3, 1])
with dh1:
    st.markdown(f"<div class='dates-title'>{ICON_CAL} Upcoming Dates</div>", unsafe_allow_html=True)
with dh2:
    if is_admin and st.session_state.admin_open:
        st.markdown('<div class="edit-btn">', unsafe_allow_html=True)
        if st.button("Edit", key="edit_dates_btn", use_container_width=True):
            edit_dates_dialog(event)
        st.markdown('</div>', unsafe_allow_html=True)

if event["upcoming_dates"]:
    pills = ""
    for i, d in enumerate(event["upcoming_dates"]):
        cls = "date-pill next" if i == 0 else "date-pill"
        pills += f'<div class="{cls}"><div class="dow">{"Next" if i == 0 else "Then"}</div><div class="dnum">{d}</div></div>'
    st.markdown(f'<div class="dates-strip">{pills}</div>', unsafe_allow_html=True)
else:
    st.caption("No dates posted yet.")

# ----------------------------------------------------------------------
# Callout
# ----------------------------------------------------------------------
st.markdown(
    f"""<div class="callout">{ICON_LEAF}
    <p><b>Let's Share a Meal!</b><br>
    Sign your family up below to bring a dish, drink, or item. Signing up also lets us know
    you're planning to be there -- thank you for helping make this a special time together!</p>
    </div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Food Sign Up section
# ----------------------------------------------------------------------
h1, h2 = st.columns([3, 1.3])
with h1:
    st.markdown(f"<div class='section-title'>{ICON_UTENSILS_DARK} Food Sign Up</div>", unsafe_allow_html=True)
with h2:
    if st.button("View Attendees", key="view_attendees_btn", use_container_width=True):
        st.session_state.show_attendees = not st.session_state.show_attendees

if st.session_state.show_attendees:
    if signed_families:
        for fam, d in signed_families.items():
            color = FAMILY_COLORS.get(fam, "#1f2937")
            st.markdown(
                f"""<div class="signee-row">
                <span class="signee-avatar" style="background:{color};">{initials(fam)}</span>
                <span class="signee-name">The {fam} Family</span>&nbsp;
                <span class="signee-detail">({d['count']} people -- {d['category'] or 'no category'})</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No one has signed up yet.")

for idx, cat in enumerate(event["categories"]):
    name, desc, slots = cat["name"], cat.get("desc", ""), cat.get("slots", 1)
    display_name = name if name else "(no type set)"
    matches = [f for f, d in signed_families.items() if d["category"] == name]
    filled = len(matches)
    remaining = max(slots - filled, 0)

    st.markdown('<div class="cat-card">', unsafe_allow_html=True)
    if is_admin and st.session_state.admin_open:
        top1, top2 = st.columns([4, 1])
        with top2:
            st.markdown('<div class="edit-btn">', unsafe_allow_html=True)
            if st.button("Edit", key=f"edit_cat_{idx}", use_container_width=True):
                edit_category_dialog(event, idx)
            st.markdown('</div>', unsafe_allow_html=True)

    cc1, cc2 = st.columns([3, 1.1])
    with cc1:
        progress_class = "full" if remaining == 0 else ""
        st.markdown(
            f"""<div class="cat-row">
            <div class="cat-avatar">{cat_icon(name)}</div>
            <div><p class="cat-name">{display_name}</p><p class="cat-desc">{desc}</p>
            <p class="cat-progress {progress_class}">{filled} / {slots} signed up</p></div>
            </div>""",
            unsafe_allow_html=True,
        )
    with cc2:
        btn_label = "Full" if remaining == 0 else "Sign Up"
        btn_key = f"signup_{idx}"
        if st.button(btn_label, key=btn_key, use_container_width=True):
            sign_up_dialog(name if name else display_name, signed_families)
        if remaining == 0:
            st.markdown(
                f"""<style>.st-key-{btn_key} button {{background-color:#f0ebe0 !important; color:#6b6355 !important; border:none !important;}}</style>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""<style>.st-key-{btn_key} button {{background-color:#4f8a68 !important; color:white !important; border:none !important;}}</style>""",
                unsafe_allow_html=True,
            )

    for fam in matches:
        d = signed_families[fam]
        fcolor = FAMILY_COLORS.get(fam, "#1f2937")
        st.markdown(
            f"""<div class="signee-row">
            <span class="signee-avatar" style="background:{fcolor};">{initials(fam)}</span>
            <span class="signee-name">The {fam} Family</span>&nbsp;<span class="signee-detail">({d['count']} people)</span>
            </div>""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

if is_admin and st.session_state.admin_open:
    if st.button("+ Add Category", key="add_cat_btn", use_container_width=True):
        add_category_dialog(event)

# ----------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------
st.markdown(
    f"""<div class="footer-card">
    <div style="display:flex; align-items:flex-start; gap:0.5rem;">{ICON_HEART}
    <div><b>Thank you!</b> Your willingness to serve helps make our Growth Group a warm
    and welcoming place for everyone.</div></div>
    <div class="footer-flourish">All are welcome!</div>
    </div>""",
    unsafe_allow_html=True,
)

st.markdown("<div class='version-tag'>v6.0</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Admin bottom strip: clear-for-new-night + lock
# ----------------------------------------------------------------------
if st.session_state.admin_open and is_admin:
    st.divider()
    st.markdown("**Admin**")
    st.caption(
        "Edit buttons now appear next to each item above (Next Meeting, Location, "
        "Upcoming Dates, and each food category)."
    )

    st.markdown("**Start a new night**")
    st.caption(
        "Clears every family's sign-up so the board is empty for the next gathering. "
        "Categories and quantities stay -- adjust them with their Edit buttons above."
    )
    confirm_clear = st.checkbox("I understand this clears all family sign-ups.")
    if st.button("Clear sign-ups for new night", disabled=not confirm_clear):
        clear_all_signups()
        st.success("Cleared! Ready for the next gathering.")
        st.rerun()

    st.divider()
    if st.button("Lock admin panel"):
        st.session_state.admin_ok = False
        st.session_state.admin_open = False
        st.rerun()
