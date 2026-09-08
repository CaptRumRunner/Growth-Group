"""
SBC Growth Group - Bible Study RSVP Coordinator
------------------------------------------------
Single-page, mobile-first RSVP app for a church growth group.

- Compact, color-framed family cards: name, attending checkbox, headcount
  (as a text box), and a food item they're bringing (limited by quantity).
- Admin (PIN protected, highlighted when unlocked) edits address, upcoming
  meeting dates, what the host is bringing, and the food-needed list with
  quantities.
- Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.

Note: all decorative icons use numeric HTML entities (e.g. &#128214;)
instead of raw emoji characters. Raw emoji can get corrupted when pasted
through GitHub's web editor on some systems; HTML entities are plain
ASCII in the source file and always render correctly in the browser.
"""

import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="SBC Growth Group", page_icon=":books:", layout="centered")

# Griffith listed first per request, seeded as already attending with 5.
FAMILIES = {
    "Griffith": ["Claire Griffith", "Shannon Griffith"],
    "Crissman": ["David Crissman", "Nicole Crissman"],
    "Lee": ["Ben Lee", "Lisa Lee"],
    "Russell": ["Mark Russell", "Megan Russell"],
    "Siefert": ["Scott Siefert", "Susan Siefert"],
}

FAMILY_COLORS = {
    "Griffith": "#d4af37",   # gold - hosting family
    "Crissman": "#e07a5f",   # warm terracotta
    "Lee": "#81b29a",        # sage green
    "Russell": "#6d9dc5",    # soft blue
    "Siefert": "#b08bbb",    # muted purple
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
# Styling - bigger fonts, warm Bible-study palette, colored family frames
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@700&family=Inter:wght@400;600;700&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .block-container {padding-top: 0.8rem; padding-bottom: 1.6rem; max-width: 540px;}

    .header-row {display: flex; align-items: center; gap: 0.5rem;}
    .topbar-title {
        font-family: 'Merriweather', serif;
        font-size: 1.7rem; font-weight: 700; margin: 0;
        color: #f3ead3;
    }
    .topbar-title span {color: #d4af37;}
    .topbar-sub {font-size: 0.85rem; color: #a89f8c; margin-top: -0.2rem;}

    div.stButton > button {
        border-radius: 8px; font-weight: 700; font-size: 1rem;
        padding: 0.35rem 0.7rem;
    }

    .info-card {
        border-radius: 12px; padding: 0.9rem 1.05rem; margin-bottom: 0.6rem;
        background: #241a10; border: 1px solid #4a3a22; font-size: 1rem;
        line-height: 1.6; color: #f3ead3;
    }
    .info-card b {color: #d4af37;}
    .info-card .label {color: #a89f8c; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em;}

    .section-label {
        font-size: 0.95rem; font-weight: 700; color: #d4af37;
        margin: 0.7rem 0 0.3rem 0; font-family: 'Merriweather', serif;
    }

    .fam-name {font-weight: 800; font-size: 1.15rem; margin-bottom: 0.1rem;}
    .fam-members {color: #a89f8c; font-size: 0.8rem; margin-bottom: 0.3rem;}
    .field-label {color: #a89f8c; font-size: 0.78rem; margin-bottom: -0.3rem; font-weight: 600;}
    .status-yes {color: #81b29a; font-size: 0.85rem; font-weight: 700;}
    .status-no {color: #a89f8c; font-size: 0.85rem;}

    .version-tag {text-align:center; color:#4b4436; font-size:0.7rem; margin-top:1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Open book icon (generic geometric outline, not a copyrighted asset)
BOOK_ICON = """
<svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="#d4af37"
     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
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
        # backward compatibility: old food_needed was a plain list of strings
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


def claim_counts(families_data):
    counts = {}
    for fam, d in families_data.items():
        b = d.get("bringing")
        if b:
            counts[b] = counts.get(b, 0) + 1
    for fam, seed in SEED_DEFAULTS.items():
        if fam not in families_data and seed.get("bringing"):
            counts[seed["bringing"]] = counts.get(seed["bringing"], 0) + 1
    return counts


def food_options_for(family, food_needed, families_data):
    counts = claim_counts(families_data)
    own_pick = get_family_data(family, families_data).get("bringing", "")
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
families_data = load_families()

if "admin_open" not in st.session_state:
    st.session_state.admin_open = False
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False

# ----------------------------------------------------------------------
# Top bar
# ----------------------------------------------------------------------
tcol1, tcol2 = st.columns([3.4, 1.1])
with tcol1:
    st.markdown(
        f"""<div class="header-row">{BOOK_ICON}
        <div>
        <p class="topbar-title">SBC <span>Growth Group</span></p>
        <p class="topbar-sub">Bible Study &amp; Fellowship</p>
        </div></div>""",
        unsafe_allow_html=True,
    )
with tcol2:
    admin_clicked = st.button("Admin", key="admin_toggle_btn", use_container_width=True)
    if admin_clicked:
        st.session_state.admin_open = not st.session_state.admin_open

if st.session_state.admin_open:
    st.markdown(
        """<style>
        .st-key-admin_toggle_btn button {
            background-color: #d4af37 !important;
            color: #1a1206 !important;
            border: 2px solid #f3ead3 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

# ----------------------------------------------------------------------
# Details card (admin-editable, everyone can see)
# ----------------------------------------------------------------------
next_date = event["upcoming_dates"][0] if event["upcoming_dates"] else "TBD"
more_dates = event["upcoming_dates"][1:]

details_html = f"""<div class="info-card">
<span class="label">Next Gathering</span><br>
<b>{next_date}</b> at <b>{event['time']}</b><br>
{event['address']}
"""
if more_dates:
    details_html += "<br><br><span class='label'>Also Coming Up</span><br>"
    details_html += "<br>".join(more_dates)
if event["host_food"]:
    details_html += f"<br><br><span class='label'>Host Is Bringing</span><br>{event['host_food']}"
details_html += "</div>"
st.markdown(details_html, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Food needed strip
# ----------------------------------------------------------------------
if event["food_needed"]:
    counts = claim_counts(families_data)
    lines = []
    for item in event["food_needed"]:
        if not item["name"]:
            continue
        remaining = max(item["qty"] - counts.get(item["name"], 0), 0)
        lines.append(f"{item['name']} ({remaining} left)")
    food_line = "  &bull;  ".join(lines) if lines else "All items claimed!"
else:
    food_line = "<span style='color:#a89f8c;'>Nothing posted yet</span>"
st.markdown(
    f'<div class="info-card"><span class="label">Food Needed</span><br>{food_line}</div>',
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Family RSVP cards (color-framed, compact)
# ----------------------------------------------------------------------
st.markdown("<div class='section-label'>Family RSVPs</div>", unsafe_allow_html=True)

for family, members in FAMILIES.items():
    existing = get_family_data(family, families_data)
    color = FAMILY_COLORS.get(family, "#e5e7eb")
    card_key = f"card_{family}"

    st.markdown(
        f"""<style>
        .st-key-{card_key} {{
            border: 2px solid {color} !important;
            border-radius: 12px !important;
            padding: 0.7rem 0.9rem !important;
            margin-bottom: 0.6rem !important;
            background: rgba(255,255,255,0.02);
        }}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.container(border=True, key=card_key):
        st.markdown(
            f"<div class='fam-name' style='color:{color};'>{family} Family</div>"
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

        options, remaining_map = food_options_for(family, event["food_needed"], families_data)
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

        status = (
            f"<span class='status-yes'>{existing.get('count', 0)} coming"
            + (f" -- bringing {existing.get('bringing')}" if existing.get("bringing") else "")
            + "</span>"
            if existing.get("attending")
            else "<span class='status-no'>No response yet</span>"
        )
        st.markdown(status, unsafe_allow_html=True)

        if st.button("Save RSVP", key=f"save_{family}", use_container_width=True):
            try:
                count_val = int(count_text)
            except ValueError:
                count_val = 0
            confirm_rsvp(family, attending, count_val, bringing)

st.markdown("<div class='version-tag'>v2.0</div>", unsafe_allow_html=True)

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
