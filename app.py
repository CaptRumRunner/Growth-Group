"""
SBC Growth Group - Food Sign Up
---------------------------------
Single-page, mobile-first food sign-up board (Grace Fellowship style).

Signing a family up for a category IS their RSVP -- there's no separate
attendance step. Each family has one active sign-up (a category + a
headcount); picking a new category moves them there.

Admin (PIN protected, gold when unlocked) edits address, upcoming dates,
and the category list (name, description, how many families can sign up
for each).

Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
All decorative icons are inline SVGs (generic outline glyphs) instead of
emoji, so nothing gets corrupted when pasted through GitHub's editor.
"""

import streamlit as st
import pandas as pd
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

SEED_SIGNUPS = {
    "Griffith": {"category": "Main Dish", "count": 5},
}

DEFAULT_EVENT = {
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "time": "5:00 PM",
    "upcoming_dates": [],
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
ICON_UTENSILS = """<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h1a2 2 0 0 0 2-2V2"></path><path d="M6 11v11"></path><path d="M18 2c-2 0-3 2-3 5v2c0 1 1 2 2 2h1v10"></path></svg>"""
ICON_HEART = """<svg viewBox="0 0 24 24" width="22" height="22" fill="#3b6ea5" stroke="#3b6ea5" stroke-width="1"><path d="M12 21s-6.7-4.35-9.3-8.2C.8 9.7 1.9 6 5 5c1.9-.6 3.7.2 5 1.9C11.3 5.2 13.1 4.4 15 5c3.1 1 4.2 4.7 2.3 7.8C18.7 16.65 12 21 12 21z"></path></svg>"""

# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700;900&family=Inter:wght@400;600;700&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container {padding-top: 0.5rem; padding-bottom: 1.6rem; max-width: 560px;}

    .brand-row {display:flex; align-items:center; gap:0.5rem;}
    .brand-name {font-family:'Merriweather', serif; font-size:1.15rem; font-weight:700; color:#1f2937; margin:0;}
    .brand-sub {font-size:0.72rem; color:#8a8171; margin-top:-0.15rem;}

    .hero {
        background: linear-gradient(120deg, #5b3a29 0%, #7a5137 45%, #9c7248 100%);
        border-radius: 16px; padding: 1.3rem 1.2rem; margin: 0.6rem 0 0.8rem 0; color:#f7f3ec;
    }
    .hero-title {font-family:'Merriweather', serif; font-size:1.65rem; font-weight:900; line-height:1.2; margin:0;}
    .hero-sub {font-size:1rem; opacity:0.92; margin: 0.15rem 0 0.6rem 0;}
    .hero-verse {font-size:0.85rem; font-style:italic; opacity:0.88; border-left:3px solid #d4af37; padding-left:0.6rem;}

    .stat-card {background:#fff; border:1px solid #e7ddce; border-radius:12px; padding:0.55rem 0.7rem; height:100%;}
    .stat-label {font-size:0.68rem; color:#8a8171; font-weight:700; text-transform:uppercase; letter-spacing:0.03em;}
    .stat-value {font-size:0.85rem; color:#1f2937; font-weight:700; margin-top:0.1rem; line-height:1.3;}
    .stat-row {display:flex; align-items:flex-start; gap:0.35rem;}

    .callout {background:#e8f3ea; border:1px solid #bfe0c6; border-radius:12px; padding:0.85rem 1rem; margin:0.7rem 0; display:flex; gap:0.6rem;}
    .callout b {color:#1f4d3d;}
    .callout p {margin:0.2rem 0 0 0; font-size:0.9rem; color:#334034;}

    .section-title {display:flex; align-items:center; gap:0.4rem; font-family:'Merriweather', serif; font-size:1.1rem; font-weight:700; color:#1f4d3d; margin:0.8rem 0 0.4rem 0;}

    .cat-card {background:#fff; border:1px solid #e7ddce; border-radius:12px; padding:0.75rem 0.9rem; margin-bottom:0.55rem;}
    .cat-row {display:flex; align-items:center; gap:0.7rem;}
    .cat-avatar {
        width:44px; height:44px; border-radius:10px; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
        color:white; font-weight:800; font-size:0.95rem;
    }
    .cat-name {font-weight:800; font-size:1rem; color:#1f2937; margin:0;}
    .cat-desc {color:#8a8171; font-size:0.78rem; margin:0;}
    .cat-progress {font-size:0.78rem; color:#4f8a68; font-weight:600; margin-top:0.1rem;}
    .cat-progress.full {color:#8a8171;}

    .signee-row {
        display:flex; align-items:center; justify-content:space-between;
        background:#f4f9f5; border-radius:8px; padding:0.35rem 0.6rem; margin-top:0.4rem; font-size:0.85rem;
    }
    .signee-avatar {
        width:22px; height:22px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center;
        color:white; font-size:0.65rem; font-weight:800; margin-right:0.4rem;
    }

    div.stButton > button {border-radius:8px; font-weight:700; font-size:0.9rem;}

    .footer-card {background:#eef3fb; border:1px solid #c9d9ee; border-radius:12px; padding:0.9rem 1.05rem; margin-top:1rem; font-size:0.9rem; color:#26344a;}
    .footer-flourish {font-style:italic; color:#3b6ea5; text-align:right; margin-top:0.3rem;}
    .version-tag {text-align:center; color:#c7bfae; font-size:0.68rem; margin-top:1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def initials(name):
    return "".join(w[0] for w in name.split()[:2]).upper()


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


def merged_signups():
    raw = load_signups()
    merged = {}
    for fam in FAMILIES:
        merged[fam] = raw.get(fam, SEED_SIGNUPS.get(fam))
    return merged


def save_signup(family, category, count):
    db.collection("signups").document(family).set({"category": category, "count": count})


def remove_signup(family):
    db.collection("signups").document(family).delete()


# ----------------------------------------------------------------------
# Sign-up dialog
# ----------------------------------------------------------------------
@st.dialog("Sign up to bring something")
def sign_up_dialog(category_name, merged):
    st.markdown(f"Signing up for **{category_name}**")
    family = st.selectbox("Your family", list(FAMILIES.keys()), key="dlg_family")
    current = merged.get(family)
    default_count = current["count"] if current else 2
    count = st.number_input(
        "How many attending", min_value=0, max_value=15, value=default_count, step=1, key="dlg_count"
    )
    if current and current["category"] != category_name:
        st.caption(f"{family} is currently signed up for {current['category']}. Confirming moves them here.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_signup(family, category_name, count)
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()
    if current:
        if st.button("Remove this family's sign-up", use_container_width=True):
            remove_signup(family)
            st.rerun()


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
event = load_event()
merged = merged_signups()

if "admin_open" not in st.session_state:
    st.session_state.admin_open = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False
if "show_attendees" not in st.session_state:
    st.session_state.show_attendees = False

signed_families = {f: d for f, d in merged.items() if d}
total_people = sum(d["count"] for d in signed_families.values())

# ----------------------------------------------------------------------
# Brand bar + Admin
# ----------------------------------------------------------------------
b1, b2 = st.columns([3.3, 1])
with b1:
    st.markdown(
        f"""<div class="brand-row">{ICON_LEAF}
        <div><p class="brand-name">SBC Growth Group</p><p class="brand-sub">Study &middot; Grow &middot; Belong</p></div>
        </div>""",
        unsafe_allow_html=True,
    )
with b2:
    if st.button("Admin", key="admin_toggle_btn", use_container_width=True):
        st.session_state.admin_open = not st.session_state.admin_open

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
next_date = event["upcoming_dates"][0] if event["upcoming_dates"] else "Date TBD"
st.markdown(
    f"""<div class="hero">
    <p class="hero-title">Bible Study &amp; Fellowship</p>
    <p class="hero-sub">Food Brings Us Together</p>
    <div class="hero-verse">"They broke bread in their homes and ate together with glad and sincere hearts."<br>-- Acts 2:46</div>
    </div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Stat cards
# ----------------------------------------------------------------------
s1, s2, s3 = st.columns(3)
with s1:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_CAL}
        <div><div class="stat-label">When</div><div class="stat-value">{next_date}<br>{event['time']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
with s2:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PIN}
        <div><div class="stat-label">Where</div><div class="stat-value">{event['address']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
with s3:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PEOPLE}
        <div><div class="stat-label">Attending</div><div class="stat-value">{len(signed_families)} families<br>({total_people} people)</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )

if len(event["upcoming_dates"]) > 1:
    st.caption("Also coming up: " + "; ".join(event["upcoming_dates"][1:]))

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
    st.markdown(f"<div class='section-title'>{ICON_UTENSILS} Food Sign Up</div>", unsafe_allow_html=True)
with h2:
    if st.button("View Attendees", key="view_attendees_btn", use_container_width=True):
        st.session_state.show_attendees = not st.session_state.show_attendees

if st.session_state.show_attendees:
    if signed_families:
        for fam, d in signed_families.items():
            color = FAMILY_COLORS.get(fam, "#1f2937")
            st.markdown(
                f"""<div class="signee-row">
                <span><span class="signee-avatar" style="background:{color};">{initials(fam)}</span>
                <b>{fam} Family</b> ({d['count']}) -- {d['category']}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No one has signed up yet.")

for cat in event["categories"]:
    name, desc, slots = cat["name"], cat.get("desc", ""), cat.get("slots", 1)
    matches = [f for f, d in signed_families.items() if d["category"] == name]
    filled = len(matches)
    remaining = max(slots - filled, 0)
    color = "#5b3a29"

    st.markdown('<div class="cat-card">', unsafe_allow_html=True)
    cc1, cc2 = st.columns([3, 1.1])
    with cc1:
        progress_class = "full" if remaining == 0 else ""
        st.markdown(
            f"""<div class="cat-row">
            <div class="cat-avatar" style="background:{color};">{name[:2].upper()}</div>
            <div><p class="cat-name">{name}</p><p class="cat-desc">{desc}</p>
            <p class="cat-progress {progress_class}">{filled} / {slots} signed up</p></div>
            </div>""",
            unsafe_allow_html=True,
        )
    with cc2:
        btn_label = "Full -- Sign Up" if remaining == 0 else "Sign Up"
        if st.button(btn_label, key=f"signup_{name}", use_container_width=True):
            sign_up_dialog(name, merged)
        btn_key = f"signup_{name}"
        if remaining == 0:
            st.markdown(
                f"""<style>.st-key-{btn_key} button {{background-color:#f0ebe0 !important; color:#8a8171 !important; border:none !important;}}</style>""",
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
            <span><span class="signee-avatar" style="background:{fcolor};">{initials(fam)}</span>
            The {fam} Family ({d['count']})</span>
            </div>""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

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

st.markdown("<div class='version-tag'>v4.0</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Admin panel
# ----------------------------------------------------------------------
if st.session_state.admin_open:
    st.divider()
    st.markdown("**Admin**")

    if not st.session_state.admin_ok:
        pin = st.text_input("Enter admin PIN", type="password", key="pin_input")
        if st.button("Unlock"):
            if pin == str(ADMIN_PIN):
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Incorrect PIN.")
    else:
        st.success("Admin unlocked")

        with st.form("details_form"):
            st.markdown("**Gathering details**")
            new_address = st.text_input("Address", value=event["address"])
            new_time = st.text_input("Time", value=event["time"])
            dates_text = st.text_area(
                "Upcoming dates (one per line, soonest first)",
                value="\n".join(event["upcoming_dates"]), height=100,
            )
            if st.form_submit_button("Save details"):
                dates_list = [d.strip() for d in dates_text.splitlines() if d.strip()]
                save_event({"address": new_address, "time": new_time, "upcoming_dates": dates_list})
                st.rerun()

        with st.form("categories_form"):
            st.markdown("**Food categories** (edit names, descriptions, and how many families can sign up)")
            df = pd.DataFrame(event["categories"])
            edited = st.data_editor(
                df, num_rows="dynamic", hide_index=True, use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Category"),
                    "desc": st.column_config.TextColumn("Description"),
                    "slots": st.column_config.NumberColumn("Slots", min_value=0, step=1),
                },
                key="cat_editor",
            )
            if st.form_submit_button("Save categories"):
                cats = []
                for _, row in edited.iterrows():
                    name = str(row.get("name", "")).strip()
                    if name:
                        cats.append({
                            "name": name,
                            "desc": str(row.get("desc", "") or ""),
                            "slots": int(row.get("slots", 1) or 1),
                        })
                save_event({"categories": cats})
                st.rerun()

        st.divider()
        if st.button("Lock admin panel"):
            st.session_state.admin_ok = False
            st.session_state.admin_open = False
            st.rerun()
