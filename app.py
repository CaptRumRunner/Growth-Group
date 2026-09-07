"""
SBC Growth Group - RSVP Coordinator
------------------------------------
Compact, single-page, mobile-first RSVP app for a church growth group.

Each family gets one row: name, "Going" checkbox, headcount, a dropdown
to pick a food item to bring (from the admin's weekly list), and a
Save button that confirms before writing.

Admin (PIN protected) edits the event date/time/address and the food
list, which changes week to week.

Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="SBC Growth Group", page_icon=":stew:", layout="centered")

FAMILIES = {
    "Crissman": ["David Crissman", "Nicole Crissman"],
    "Griffith": ["Claire Griffith", "Shannon Griffith"],
    "Lee": ["Ben Lee", "Lisa Lee"],
    "Russell": ["Mark Russell", "Megan Russell"],
    "Siefert": ["Scott Siefert", "Susan Siefert"],
}

FAMILY_COLORS = {
    "Crissman": "#f87171",
    "Griffith": "#fbbf24",
    "Lee": "#34d399",
    "Russell": "#60a5fa",
    "Siefert": "#c084fc",
}

DEFAULT_EVENT = {
    "event_date": "",
    "event_time": "5:00 PM",
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "food_needed": [],
}

NONE_OPTION = "-- nothing yet --"

# ----------------------------------------------------------------------
# Styling - compact, dark, no emoji (avoids copy/paste encoding issues)
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 0.8rem; padding-bottom: 1.5rem; max-width: 520px;}

    .topbar-title {
        font-size: 1.35rem; font-weight: 800; margin: 0.2rem 0;
        color: #f3f4f6;
    }
    .topbar-title span {color: #a855f7;}

    div.stButton > button {
        border-radius: 8px; font-weight: 600; padding: 0.25rem 0.6rem;
    }

    .info-strip {
        border-radius: 10px; padding: 0.6rem 0.85rem; margin-bottom: 0.5rem;
        background: #1c1f2b; border: 1px solid #333849; font-size: 0.85rem;
        line-height: 1.5;
    }
    .info-strip b {color: #fbbf24;}
    .food-strip b {color: #60a5fa;}

    .section-label {
        font-size: 0.75rem; font-weight: 700; color: #9ca3af;
        text-transform: uppercase; letter-spacing: 0.04em;
        margin: 0.6rem 0 0.1rem 0;
    }

    .fam-row {
        border-bottom: 1px solid #262a38; padding: 0.45rem 0;
    }
    .fam-name {font-weight: 700; font-size: 0.92rem; margin-bottom: 0.1rem;}
    .fam-members {color: #6b7280; font-size: 0.68rem;}
    .status-yes {color: #34d399; font-size: 0.68rem; font-weight: 600;}
    .status-no {color: #6b7280; font-size: 0.68rem;}

    div[data-testid="stVerticalBlock"] > div:has(> div.fam-row-marker) {
        gap: 0.1rem;
    }

    .version-tag {text-align:center; color:#4b5563; font-size:0.68rem; margin-top:1rem;}
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
        data.update(doc.to_dict())
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
tcol1, tcol2 = st.columns([3.3, 1.1])
with tcol1:
    st.markdown("<p class='topbar-title'>SBC <span>Growth Group</span></p>", unsafe_allow_html=True)
with tcol2:
    if st.button("Admin", use_container_width=True):
        st.session_state.admin_open = not st.session_state.admin_open

# ----------------------------------------------------------------------
# Event + food info (compact strips)
# ----------------------------------------------------------------------
date_line = event["event_date"] if event["event_date"] else "Date TBD"
st.markdown(
    f"""<div class="info-strip">
    <b>{date_line}</b> &nbsp;|&nbsp; <b>{event['event_time']}</b><br>
    {event['address']}
    </div>""",
    unsafe_allow_html=True,
)

if event["food_needed"]:
    items_line = "  \u2022  ".join(event["food_needed"])
else:
    items_line = "<span style='color:#6b7280;'>Nothing posted yet</span>"
st.markdown(
    f'<div class="info-strip food-strip"><b>Food needed:</b> {items_line}</div>',
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Family RSVP rows
# ----------------------------------------------------------------------
st.markdown("<div class='section-label'>Family RSVPs</div>", unsafe_allow_html=True)

food_options = [NONE_OPTION] + event["food_needed"]

for family, members in FAMILIES.items():
    existing = families_data.get(family, {})
    color = FAMILY_COLORS.get(family, "#e5e7eb")

    st.markdown("<div class='fam-row-marker'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([2.1, 0.75, 0.7, 1.7, 0.7])

    with c1:
        st.markdown(
            f"<div class='fam-name' style='color:{color};'>{family}</div>"
            f"<div class='fam-members'>{' & '.join(members)}</div>",
            unsafe_allow_html=True,
        )

    with c2:
        attending = st.checkbox(
            "Going", value=bool(existing.get("attending", False)),
            key=f"chk_{family}", label_visibility="collapsed",
        )

    with c3:
        count = st.number_input(
            "#", min_value=0, max_value=15,
            value=int(existing.get("count", 2 if attending else 0)),
            step=1, key=f"cnt_{family}", label_visibility="collapsed",
        )

    with c4:
        existing_bringing = existing.get("bringing", "")
        options_for_family = (
            food_options if existing_bringing in food_options or not existing_bringing
            else [existing_bringing] + food_options
        )
        default_index = options_for_family.index(existing_bringing) if existing_bringing in options_for_family else 0
        bringing = st.selectbox(
            "Bringing", options=options_for_family, index=default_index,
            key=f"food_{family}", label_visibility="collapsed",
        )

    with c5:
        if st.button("Save", key=f"save_{family}", use_container_width=True):
            confirm_rsvp(family, attending, count, bringing)

    status = (
        f"<span class='status-yes'>{existing.get('count', 0)} coming"
        + (f" -- bringing {existing.get('bringing')}" if existing.get("bringing") else "")
        + "</span>"
        if existing.get("attending")
        else "<span class='status-no'>No response yet</span>"
    )
    st.markdown(status, unsafe_allow_html=True)

st.markdown("<div class='version-tag'>v1.2</div>", unsafe_allow_html=True)

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

        with st.form("event_form"):
            st.markdown("**Event details**")
            new_date = st.text_input("Date (e.g. 'Saturday, Sept 13')", value=event["event_date"])
            new_time = st.text_input("Time", value=event["event_time"])
            new_address = st.text_input("Address", value=event["address"])
            if st.form_submit_button("Save event details"):
                save_event({"event_date": new_date, "event_time": new_time, "address": new_address})
                st.rerun()

        with st.form("food_form"):
            st.markdown("**Food needed this week** (one item per line)")
            current_food_text = "\n".join(event["food_needed"])
            new_food_text = st.text_area("Items", value=current_food_text, height=120)
            if st.form_submit_button("Save food list"):
                items = [line.strip() for line in new_food_text.splitlines() if line.strip()]
                save_event({"food_needed": items})
                st.rerun()

        st.divider()
        if st.button("Lock admin panel"):
            st.session_state.admin_ok = False
            st.session_state.admin_open = False
            st.rerun()
