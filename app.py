"""
SBC Growth Group - RSVP Coordinator
------------------------------------
Single-page, mobile-first, colorful RSVP app for a church growth group.

Each family gets one compact row: name, "Going?" checkbox, headcount,
a dropdown to pick what food item they're bringing (from the admin's
weekly needed list), and a Save button that confirms before writing.

Admin (PIN protected) edits the event date/time/address and the
"food needed" list, which changes week to week.

Data lives in Firebase Firestore so it survives Streamlit Cloud reboots.
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

FAMILY_COLORS = {
    "Crissman": "#ef4444",   # red
    "Griffith": "#f59e0b",   # amber
    "Lee": "#10b981",        # green
    "Russell": "#3b82f6",    # blue
    "Siefert": "#a855f7",    # purple
}

DEFAULT_EVENT = {
    "event_date": "",
    "event_time": "5:00 PM",
    "address": "17136 Mark Dr, Macomb, MI 48044",
    "food_needed": [],
}

NONE_OPTION = "â€” nothing yet â€”"

# ----------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 520px;}

    .topbar-title {
        font-size: 1.5rem; font-weight: 800; margin: 0; line-height: 1.2;
        background: linear-gradient(90deg, #f97316, #ec4899, #8b5cf6);
        -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    div.stButton > button {
        border-radius: 10px; font-weight: 700; border: none;
    }
    div.stButton > button:has(span:contains("Admin")) {}
    .admin-btn button {
        background: linear-gradient(90deg, #6366f1, #a855f7) !important;
        color: white !important;
    }
    .event-card {
        border-radius: 14px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem;
        background: linear-gradient(135deg, #fff7ed, #ffedd5);
        border: 1px solid #fdba74;
    }
    .food-card {
        border-radius: 14px; padding: 0.9rem 1.1rem; margin-bottom: 1rem;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border: 1px solid #93c5fd;
    }
    .row-header {
        display:flex; font-size: 0.72rem; font-weight: 700; color:#6b7280;
        text-transform: uppercase; letter-spacing: 0.03em;
        padding: 0 0.2rem; margin-bottom: -0.4rem;
    }
    .fam-name {font-weight: 800; font-size: 0.98rem; padding-top: 0.5rem;}
    .fam-members {color:#9ca3af; font-size:0.68rem; margin-top:-0.35rem;}
    .status-yes {color:#16a34a; font-size:0.68rem; font-weight:700;}
    .status-no {color:#9ca3af; font-size:0.68rem;}
    .version-tag {text-align:center; color:#e5e7eb; font-size:0.7rem; margin-top:1.4rem;}
    hr {margin: 0.4rem 0;}
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
    st.markdown(f"You're updating the RSVP for the **{family} family**.")
    if attending:
        st.markdown(f"âœ… Attending â€” **{count}** coming")
    else:
        st.markdown("âŒ Not attending")
    if bringing and bringing != NONE_OPTION:
        st.markdown(f"ðŸ½ï¸ Bringing: **{bringing}**")
    st.caption("Make sure this is really your family before confirming.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm", type="primary", use_container_width=True):
        save_family(family, attending, count, bringing if bringing != NONE_OPTION else "")
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
tcol1, tcol2 = st.columns([3.2, 1.3])
with tcol1:
    st.markdown("<p class='topbar-title'>ðŸ² SBC Growth Group</p>", unsafe_allow_html=True)
with tcol2:
    st.markdown("<div class='admin-btn'>", unsafe_allow_html=True)
    if st.button("ðŸ”’ Admin", use_container_width=True):
        st.session_state.admin_open = not st.session_state.admin_open
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Event info card
# ----------------------------------------------------------------------
date_line = event["event_date"] if event["event_date"] else "Date TBD"
st.markdown(
    f"""<div class="event-card">
    <b>ðŸ“… {date_line} &nbsp;Â·&nbsp; â° {event['event_time']}</b><br>
    ðŸ“ {event['address']}
    </div>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Food needed card (read-only for everyone)
# ----------------------------------------------------------------------
food_html = "ðŸ¥˜ <b>Food needed this week</b><br>"
if event["food_needed"]:
    food_html += "<br>".join(f"â€¢ {item}" for item in event["food_needed"])
else:
    food_html += "<span style='color:#93a3b8;'>Nothing posted yet â€” check back soon.</span>"
st.markdown(f'<div class="food-card">{food_html}</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Family RSVP rows
# ----------------------------------------------------------------------
st.markdown("#### Family RSVPs")

food_options = [NONE_OPTION] + event["food_needed"]

st.markdown(
    """<div class="row-header">
    <div style="flex:2.3;">Family</div>
    <div style="flex:0.9;">Going</div>
    <div style="flex:0.9;"># </div>
    <div style="flex:1.9;">Bringing</div>
    <div style="flex:0.7;"></div>
    </div>""",
    unsafe_allow_html=True,
)

for family, members in FAMILIES.items():
    existing = families_data.get(family, {})
    color = FAMILY_COLORS.get(family, "#374151")

    c1, c2, c3, c4, c5 = st.columns([2.3, 0.9, 0.9, 1.9, 0.7])

    with c1:
        st.markdown(f"<div class='fam-name' style='color:{color};'>{family}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='fam-members'>{' & '.join(members)}</div>", unsafe_allow_html=True)

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
        options_for_family = food_options if existing_bringing in food_options or not existing_bringing else [existing_bringing] + food_options
        default_index = options_for_family.index(existing_bringing) if existing_bringing in options_for_family else 0
        bringing = st.selectbox(
            "Bringing", options=options_for_family, index=default_index,
            key=f"food_{family}", label_visibility="collapsed",
        )

    with c5:
        if st.button("ðŸ’¾", key=f"save_{family}", help=f"Save RSVP for {family}"):
            confirm_rsvp(family, attending, count, bringing)

    status_html = (
        f"<span class='status-yes'>âœ… {existing.get('count', 0)} coming"
        + (f" Â· bringing {existing.get('bringing')}" if existing.get("bringing") else "")
        + "</span>"
        if existing.get("attending")
        else "<span class='status-no'>No response yet</span>"
    )
    st.markdown(status_html, unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("<div class='version-tag'>v1.1</div>", unsafe_allow_html=True)

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
