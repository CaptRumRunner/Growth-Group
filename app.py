"""
SBC Growth Group - Bible Study RSVP Coordinator
------------------------------------------------
Single-page, mobile-first, light "Faith Fellowship" styled RSVP app.

- Hero banner, stat cards (date/time/location/attending), a welcome
  callout, a live food-needed status table, per-family RSVP cards with
  color accents, and a thank-you footer -- all on one page, no side tabs.
- Admin (PIN protected, highlighted gold when unlocked) edits address,
  upcoming dates, host food, and the food-needed list with quantities.
- Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.

Note: all decorative icons are small inline SVGs (generic outline glyphs,
not copyrighted art) instead of emoji, so nothing can get corrupted when
pasted through GitHub's web editor.
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

SEED_DEFAULTS = {
    "Griffith": {"attending": True, "count": 5, "bringing": ""},
}

DEFAULT_EVENT = {
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "time": "5:00 PM",
    "upcoming_dates": [],
    "host_food": "",
    "food_needed": [],  # list of {"name": str, "qty": int}
}

NONE_OPTION = "-- nothing yet --"

# ----------------------------------------------------------------------
# Icons (generic outline glyphs, plain SVG - no emoji, no copyrighted art)
# ----------------------------------------------------------------------
ICON_BOOK = """<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="#f7f3ec" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>"""
ICON_CAL = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>"""
ICON_CLOCK = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>"""
ICON_PIN = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>"""
ICON_PEOPLE = """<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>"""
ICON_LEAF = """<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#1f4d3d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"></path><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 11 13.6 12 12"></path></svg>"""

# ----------------------------------------------------------------------
# Styling - light, warm "Faith Fellowship" palette
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700;900&family=Inter:wght@400;600;700&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .block-container {padding-top: 0.6rem; padding-bottom: 1.6rem; max-width: 560px;}

    .hero {
        background: linear-gradient(120deg, #5b3a29 0%, #7a5137 45%, #9c7248 100%);
        border-radius: 16px; padding: 1.4rem 1.3rem 1.2rem 1.3rem; margin-bottom: 0.8rem;
        color: #f7f3ec;
    }
    .hero-top {display:flex; align-items:center; gap:0.5rem; margin-bottom: 0.6rem;}
    .hero-brand {font-size: 0.95rem; font-weight: 700; letter-spacing: 0.03em;}
    .hero-title {
        font-family: 'Merriweather', serif; font-size: 1.8rem; font-weight: 900;
        margin: 0.1rem 0 0.1rem 0; line-height: 1.15;
    }
    .hero-sub {font-size: 1rem; opacity: 0.92; margin-bottom: 0.4rem;}
    .hero-tags {font-size: 0.85rem; opacity: 0.85;}

    .stat-card {
        background: #ffffff; border: 1px solid #e7ddce; border-radius: 12px;
        padding: 0.6rem 0.75rem; height: 100%;
    }
    .stat-label {font-size: 0.72rem; color: #8a8171; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;}
    .stat-value {font-size: 0.95rem; color: #1f2937; font-weight: 700; margin-top: 0.1rem;}
    .stat-row {display:flex; align-items:flex-start; gap:0.4rem;}

    .callout {
        background: #e8f3ea; border: 1px solid #bfe0c6; border-radius: 12px;
        padding: 0.85rem 1rem; margin: 0.7rem 0; display:flex; gap:0.6rem; align-items:flex-start;
    }
    .callout b {color:#1f4d3d;}
    .callout p {margin:0.2rem 0 0 0; font-size:0.92rem; color:#334034;}

    .section-title {
        font-family: 'Merriweather', serif; font-size: 1.15rem; font-weight: 700;
        color: #1f4d3d; margin: 0.9rem 0 0.4rem 0;
    }

    table.food-table {width:100%; border-collapse: collapse; font-size: 0.88rem; margin-bottom: 0.6rem;}
    table.food-table th {
        text-align:left; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.03em;
        color:#8a8171; border-bottom: 2px solid #e7ddce; padding: 0.4rem 0.3rem;
    }
    table.food-table td {padding: 0.5rem 0.3rem; border-bottom: 1px solid #f0ebe0; color:#1f2937;}
    .pill-open {background:#e8f3ea; color:#1f4d3d; padding:0.15rem 0.55rem; border-radius:999px; font-size:0.78rem; font-weight:700;}
    .pill-done {background:#f0ebe0; color:#8a8171; padding:0.15rem 0.55rem; border-radius:999px; font-size:0.78rem; font-weight:700;}

    .fam-name {font-weight: 800; font-size: 1.1rem; margin-bottom: 0.1rem; display:inline-block;}
    .fam-members {color: #8a8171; font-size: 0.8rem; margin-bottom: 0.3rem;}
    .field-label {color: #8a8171; font-size: 0.75rem; margin-bottom: -0.3rem; font-weight: 600;}
    .status-yes {background:#e8f3ea; color:#1f4d3d; padding:0.12rem 0.5rem; border-radius:999px; font-size:0.78rem; font-weight:700;}
    .status-no {background:#f0ebe0; color:#8a8171; padding:0.12rem 0.5rem; border-radius:999px; font-size:0.78rem; font-weight:700;}

    div.stButton > button {border-radius: 8px; font-weight: 700; font-size: 0.95rem;}

    .footer-card {
        background: #eef3fb; border: 1px solid #c9d9ee; border-radius: 12px;
        padding: 0.9rem 1.05rem; margin-top: 1rem; font-size: 0.9rem; color:#26344a;
    }
    .footer-verse {font-style: italic; color:#5a6a86; margin-top:0.4rem; text-align:right;}
    .version-tag {text-align:center; color:#c7bfae; font-size:0.7rem; margin-top:1rem;}
    </style>
    """,
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
def load_event():
    doc = db.collection("meta").document("event").get()
    data = DEFAULT_EVENT.copy()
    if doc.exists:
        stored = doc.to_dict()
        data.update(stored)
        fixed_food = []
        for item in data.get("food_needed", []):
            if isinstance(item, str):
                fixed_food.append({"name": item, "qty": 1})
            elif isinstance(item, dict):
                fixed_food.append({"name": item.get("name", ""), "qty": int(item.get("qty", 1))})
        data["food_needed"] = fixed_food
    return data


def save_event(data):
    db.collection("meta").document("event").set(data, merge=True)


def load_families():
    docs = db.collection("families").stream()
    return {d.id: d.to_dict() for d in docs}


def save_family(family, attending, count, bringing):
    db.collection("families").document(family).set(
        {"attending": attending, "count": count, "bringing": bringing}
    )


def get_family_data(family, families_data):
    if family in families_data:
        return families_data[family]
    return SEED_DEFAULTS.get(family, {"attending": False, "count": 0, "bringing": ""})


def all_family_data():
    fd = load_families()
    merged = {}
    for fam in FAMILIES:
        merged[fam] = get_family_data(fam, fd)
    return fd, merged


def claim_counts(merged_data):
    counts = {}
    for fam, d in merged_data.items():
        b = d.get("bringing")
        if b:
            counts[b] = counts.get(b, 0) + 1
    return counts


def food_options_for(family, food_needed, merged_data):
    counts = claim_counts(merged_data)
    own_pick = merged_data.get(family, {}).get("bringing", "")
    options = [NONE_OPTION]
    remaining_map = {NONE_OPTION: None}
    for item in food_needed:
        name, qty = item["name"], item["qty"]
        if not name:
            continue
        claimed = counts.get(name, 0)
        if name == own_pick:
            claimed -= 1
        remaining = qty - claimed
        if remaining > 0 or name == own_pick:
            options.append(name)
            remaining_map[name] = max(remaining, 0)
    return options, remaining_map


# ----------------------------------------------------------------------
# Confirmation dialog
# ----------------------------------------------------------------------
@st.dialog("Confirm your RSVP")
def confirm_rsvp(family, attending, count, bringing):
    st.markdown(f"Updating the RSVP for the **{family} family**.")
    if attending:
        st.markdown(f"Attending -- **{count}** coming")
    else:
        st.markdown("Not attending")
    if bringing and bringing != NONE_OPTION:
        st.markdown(f"Bringing: **{bringing}**")
    st.caption("Make sure this is really your family before confirming.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_family(family, attending, count, bringing if bringing != NONE_OPTION else "")
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
event = load_event()
raw_families_data, merged_families = all_family_data()

if "admin_open" not in st.session_state:
    st.session_state.admin_open = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

attending_families = [f for f, d in merged_families.items() if d.get("attending")]
attending_people = sum(merged_families[f].get("count", 0) for f in attending_families)

# ----------------------------------------------------------------------
# Hero banner
# ----------------------------------------------------------------------
top_c1, top_c2 = st.columns([3.6, 1])
with top_c2:
    admin_clicked = st.button("Admin", key="admin_toggle_btn", use_container_width=True)
    if admin_clicked:
        st.session_state.admin_open = not st.session_state.admin_open

if st.session_state.admin_open:
    st.markdown(
        """<style>
        .st-key-admin_toggle_btn button {
            background-color: #c9a227 !important; color: #2b2109 !important;
            border: 2px solid #8a6d16 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """<style>
        .st-key-admin_toggle_btn button {
            background-color: #1f4d3d !important; color: #f7f3ec !important; border: none !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

next_date = event["upcoming_dates"][0] if event["upcoming_dates"] else "Date TBD"

st.markdown(
    f"""<div class="hero">
    <div class="hero-top">{ICON_BOOK}<span class="hero-brand">SBC GROWTH GROUP</span></div>
    <div class="hero-title">Bible Study &amp; Fellowship</div>
    <div class="hero-sub">Food Brings Us Together</div>
    <div class="hero-tags">Good Food &nbsp;&bull;&nbsp; Great Fellowship &nbsp;&bull;&nbsp; A Deeper Walk with Christ</div>
    </div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Stat cards row
# ----------------------------------------------------------------------
s1, s2 = st.columns(2)
s3, s4 = st.columns(2)
with s1:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_CAL}
        <div><div class="stat-label">Date</div><div class="stat-value">{next_date}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
with s2:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_CLOCK}
        <div><div class="stat-label">Time</div><div class="stat-value">{event['time']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
with s3:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PIN}
        <div><div class="stat-label">Location</div><div class="stat-value">{event['address']}</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )
with s4:
    st.markdown(
        f"""<div class="stat-card"><div class="stat-row">{ICON_PEOPLE}
        <div><div class="stat-label">Families Attending</div>
        <div class="stat-value">{len(attending_families)} families ({attending_people} people)</div></div>
        </div></div>""",
        unsafe_allow_html=True,
    )

more_dates = event["upcoming_dates"][1:]
if more_dates or event["host_food"]:
    extra_bits = []
    if more_dates:
        extra_bits.append("Also coming up: " + "; ".join(more_dates))
    if event["host_food"]:
        extra_bits.append(f"Host is bringing: {event['host_food']}")
    st.caption("  |  ".join(extra_bits))

# ----------------------------------------------------------------------
# Welcome callout
# ----------------------------------------------------------------------
st.markdown(
    f"""<div class="callout">{ICON_LEAF}
    <p><b>Let's Share a Meal!</b><br>
    We're so excited to gather for Bible study and fellowship. Pick a family below to
    RSVP and choose what you'll bring. Thank you for helping make this a special time together!</p>
    </div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Food needed status table (read-only for everyone)
# ----------------------------------------------------------------------
st.markdown("<div class='section-title'>Food Needed</div>", unsafe_allow_html=True)

if event["food_needed"]:
    counts = claim_counts(merged_families)
    rows_html = ""
    for item in event["food_needed"]:
        if not item["name"]:
            continue
        claimed = counts.get(item["name"], 0)
        remaining = max(item["qty"] - claimed, 0)
        who = [f for f, d in merged_families.items() if d.get("bringing") == item["name"]]
        who_text = ", ".join(who) if who else "&mdash;"
        pill = f"<span class='pill-open'>{remaining} open</span>" if remaining > 0 else "<span class='pill-done'>All claimed</span>"
        rows_html += f"<tr><td><b>{item['name']}</b></td><td>{item['qty']} needed</td><td>{pill}</td><td>{who_text}</td></tr>"
    st.markdown(
        f"""<table class="food-table">
        <tr><th>Item</th><th>Needed</th><th>Status</th><th>Who's Bringing It</th></tr>
        {rows_html}
        </table>""",
        unsafe_allow_html=True,
    )
else:
    st.caption("Nothing posted yet -- check back soon.")

# ----------------------------------------------------------------------
# Family RSVP cards
# ----------------------------------------------------------------------
st.markdown("<div class='section-title'>Family RSVPs</div>", unsafe_allow_html=True)

for family, members in FAMILIES.items():
    existing = merged_families[family]
    color = FAMILY_COLORS.get(family, "#1f2937")
    card_key = f"card_{family}"

    st.markdown(
        f"""<style>
        .st-key-{card_key} {{
            border: none !important;
            border-left: 6px solid {color} !important;
            border-radius: 10px !important;
            padding: 0.7rem 0.9rem !important;
            margin-bottom: 0.6rem !important;
            background: #ffffff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.container(border=True, key=card_key):
        pill = "<span class='status-yes'>Attending</span>" if existing.get("attending") else "<span class='status-no'>No RSVP yet</span>"
        st.markdown(
            f"<span class='fam-name' style='color:{color};'>{family} Family</span> &nbsp; {pill}"
            f"<div class='fam-members'>{' &amp; '.join(members)}</div>",
            unsafe_allow_html=True,
        )

        r1c1, r1c2 = st.columns([1, 1.4])
        with r1c1:
            st.markdown("<div class='field-label'>Attending</div>", unsafe_allow_html=True)
            attending = st.checkbox(
                "Attending", value=bool(existing.get("attending", False)),
                key=f"chk_{family}", label_visibility="collapsed",
            )
        with r1c2:
            st.markdown("<div class='field-label'>How many coming</div>", unsafe_allow_html=True)
            count_text = st.text_input(
                "How many", value=str(existing.get("count", 0)),
                key=f"cnt_{family}", label_visibility="collapsed",
            )

        options, remaining_map = food_options_for(family, event["food_needed"], merged_families)
        st.markdown("<div class='field-label'>Bringing</div>", unsafe_allow_html=True)
        existing_bringing = existing.get("bringing", "")
        default_index = options.index(existing_bringing) if existing_bringing in options else 0

        def _fmt(name, rm=remaining_map):
            if name == NONE_OPTION:
                return name
            r = rm.get(name)
            return f"{name} ({r} left)" if r is not None else name

        bringing = st.selectbox(
            "Bringing", options=options, index=default_index, format_func=_fmt,
            key=f"food_{family}", label_visibility="collapsed",
        )

        if st.button("Save RSVP", key=f"save_{family}", use_container_width=True):
            try:
                count_val = int(count_text)
            except ValueError:
                count_val = 0
            confirm_rsvp(family, attending, count_val, bringing)

# ----------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------
st.markdown(
    """<div class="footer-card">
    <b>Thank you!</b> Your willingness to RSVP and bring a dish helps make our
    Growth Group a warm and welcoming place for everyone.
    <div class="footer-verse">"For where two or three gather in my name, there am I with them."<br>Matthew 18:20</div>
    </div>""",
    unsafe_allow_html=True,
)

st.markdown("<div class='version-tag'>v3.0</div>", unsafe_allow_html=True)

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
            host_food = st.text_area("What is the host bringing?", value=event["host_food"], height=70)
            if st.form_submit_button("Save details"):
                dates_list = [d.strip() for d in dates_text.splitlines() if d.strip()]
                save_event({
                    "address": new_address,
                    "time": new_time,
                    "upcoming_dates": dates_list,
                    "host_food": host_food,
                })
                st.rerun()

        with st.form("food_form"):
            st.markdown("**Food needed this week** (set quantity needed per item)")
            existing_rows = event["food_needed"] if event["food_needed"] else [{"name": "", "qty": 1}]
            df = pd.DataFrame(existing_rows)
            edited = st.data_editor(
                df, num_rows="dynamic", hide_index=True, use_container_width=True,
                column_config={
                    "name": st.column_config.TextColumn("Item"),
                    "qty": st.column_config.NumberColumn("Qty Needed", min_value=0, step=1),
                },
                key="food_editor",
            )
            if st.form_submit_button("Save food list"):
                items = []
                for _, row in edited.iterrows():
                    name = str(row.get("name", "")).strip()
                    if name:
                        qty = int(row.get("qty", 1) or 1)
                        items.append({"name": name, "qty": qty})
                save_event({"food_needed": items})
                st.rerun()

        st.divider()
        if st.button("Lock admin panel"):
            st.session_state.admin_ok = False
            st.session_state.admin_open = False
            st.rerun()
