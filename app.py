"""
SBC Growth Group - RSVP Coordinator
------------------------------------
Single-page, mobile-first RSVP app for a church growth group.

- 5 family cards: check the box if attending, type in a headcount, submit.
- A confirmation dialog names the family before saving, so nobody
  accidentally RSVPs for the wrong household.
- Admin (PIN protected) can edit the event date/time/address and the
  "food needed" list, which changes week to week.
- Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="SBC Growth Group", page_icon="ðŸ²", layout="centered")

FAMILIES = {
    "Crissman": ["David Crissman", "Nicole Crissman"],
    "Griffith": ["Claire Griffith", "Shannon Griffith"],
    "Lee": ["Ben Lee", "Lisa Lee"],
    "Russell": ["Mark Russell", "Megan Russell"],
    "Siefert": ["Scott Siefert", "Susan Siefert"],
}

DEFAULT_EVENT = {
    "event_date": "",
    "event_time": "5:00 PM",
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "food_needed": [],
}

# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 480px;}
    .topbar-title {font-size: 1.5rem; font-weight: 800; margin: 0; line-height: 1.2;}
    div.stButton > button {border-radius: 10px; font-weight: 600;}
    .family-name {font-weight: 700; font-size: 1.05rem; margin-bottom: 0.1rem;}
    .family-members {color: #6b7280; font-size: 0.8rem; margin-bottom: 0.5rem;}
    .status-yes {color: #16a34a; font-weight: 700;}
    .status-no {color: #9ca3af; font-weight: 600;}
    .version-tag {text-align: center; color: #d1d5db; font-size: 0.7rem; margin-top: 1.2rem;}
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


def save_family(family, attending, count):
    db.collection("families").document(family).set(
        {"attending": attending, "count": count}
    )


# ----------------------------------------------------------------------
# Confirmation dialog
# ----------------------------------------------------------------------
@st.dialog("Confirm your RSVP")
def confirm_rsvp(family, attending, count):
    st.markdown(f"You're updating the RSVP for the **{family} family**.")
    if attending:
        st.markdown(f"âœ… Attending â€” **{count}** coming")
    else:
        st.markdown("âŒ Not attending")
    st.caption("Make sure this is really your family before confirming.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_family(family, attending, count)
        st.success(f"Saved RSVP for {family}!")
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
tcol1, tcol2 = st.columns([4, 1.3])
with tcol1:
    st.markdown("<p class='topbar-title'>ðŸ² SBC Growth Group</p>", unsafe_allow_html=True)
with tcol2:
    if st.button("ðŸ”’ Admin", use_container_width=True):
        st.session_state.admin_open = not st.session_state.admin_open

# ----------------------------------------------------------------------
# Event info card
# ----------------------------------------------------------------------
with st.container(border=True):
    date_line = event["event_date"] if event["event_date"] else "Date TBD"
    st.markdown(f"**ðŸ“… {date_line} &nbsp;Â·&nbsp; â° {event['event_time']}**")
    st.markdown(f"ðŸ“ {event['address']}")

# ----------------------------------------------------------------------
# Food needed card (read-only for everyone)
# ----------------------------------------------------------------------
with st.container(border=True):
    st.markdown("**ðŸ¥˜ Food needed this week**")
    if event["food_needed"]:
        for item in event["food_needed"]:
            st.markdown(f"- {item}")
    else:
        st.caption("Nothing posted yet â€” check back soon.")

st.markdown("#### Family RSVPs")

# ----------------------------------------------------------------------
# Family cards
# ----------------------------------------------------------------------
for family, members in FAMILIES.items():
    existing = families_data.get(family, {})
    with st.container(border=True):
        st.markdown(f"<div class='family-name'>{family} Family</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='family-members'>{' &amp; '.join(members)}</div>",
            unsafe_allow_html=True,
        )
        current_status = existing.get("attending")
        if current_status is True:
            st.markdown(
                f"<span class='status-yes'>âœ… Currently marked attending "
                f"({existing.get('count', 0)})</span>",
                unsafe_allow_html=True,
            )
        elif current_status is False:
            st.markdown("<span class='status-no'>Currently marked not attending</span>", unsafe_allow_html=True)

        attending = st.checkbox(
            "We're planning to attend",
            value=bool(existing.get("attending", False)),
            key=f"chk_{family}",
        )
        count = st.number_input(
            "How many are coming?",
            min_value=0,
            max_value=15,
            value=int(existing.get("count", 2 if attending else 0)),
            step=1,
            key=f"cnt_{family}",
        )
        if st.button(f"Submit RSVP for {family}", key=f"submit_{family}", use_container_width=True):
            confirm_rsvp(family, attending, count)

st.markdown("<div class='version-tag'>v1.0</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Admin panel
# ----------------------------------------------------------------------
if st.session_state.admin_open:
    st.divider()
    st.markdown("### âš™ï¸ Admin")

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
                st.success("Event details updated.")
                st.rerun()

        with st.form("food_form"):
            st.markdown("**Food needed this week** (one item per line)")
            current_food_text = "\n".join(event["food_needed"])
            new_food_text = st.text_area("Items", value=current_food_text, height=140)
            if st.form_submit_button("Save food list"):
                items = [line.strip() for line in new_food_text.splitlines() if line.strip()]
                save_event({"food_needed": items})
                st.success("Food list updated.")
                st.rerun()

        st.divider()
        if st.button("Lock admin panel"):
            st.session_state.admin_ok = False
            st.session_state.admin_open = False
            st.rerun()
