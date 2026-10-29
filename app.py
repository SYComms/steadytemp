# -*- coding: utf-8 -*-
"""SteadyTemp Air Conditioning - quotation & paperwork app (Streamlit).

Same method of sale as the SY Comms quoting tool: lease over a term (or cash sale), customer details,
products, and a signed paperwork pack. Own catalogue, own branding, own contract wording.
"""
import streamlit as st

st.set_page_config(page_title="SteadyTemp Quotes", page_icon="❄️", layout="wide")

import io, json, os, re, uuid, hmac, hashlib, html as html_lib
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fpdf import FPDF

try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_OK = True
except Exception:
    CANVAS_OK = False

# Full-width setting that works on old and new Streamlit versions
try:
    _ver = tuple(int(x) for x in st.__version__.split(".")[:2])
except Exception:
    _ver = (1, 40)
FW = {"width": "stretch"} if _ver >= (1, 49) else {"use_container_width": True}

# ───────────────────────────── helpers ─────────────────────────────
def _secret(key):
    try:
        return str(st.secrets.get(key, "") or "")
    except Exception:
        return ""

def esc(v):
    return html_lib.escape(str(v if v is not None else ""), quote=True)

def s(text):
    """Make text safe for the PDF fonts (latin-1 only)."""
    if text is None:
        return ""
    text = str(text)
    for a, b in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                 "…": "...", " ": " ", "®": "(R)", "©": "(C)", "•": "-"}.items():
        text = text.replace(a, b)
    return text.encode("latin-1", errors="replace").decode("latin-1")

def money(v, dp=2):
    try:
        return f"£{float(v):,.{dp}f}"
    except Exception:
        return "£0.00"

# ───────────────────────────── logins ─────────────────────────────
# Same user list format as the SY Comms quoting tool: [users."email"] name / role / hash in Streamlit Secrets.
def _load_users():
    try:
        raw = st.secrets.get("users")
        if not raw:
            return {}
        out = {}
        for k in raw:
            v = raw[k]
            out[str(k).strip().lower()] = {
                "name": str(v.get("name", "") or ""),
                "role": str(v.get("role", "consultant") or "consultant").strip().lower(),
                "hash": str(v.get("hash", "") or ""),
            }
        return out
    except Exception:
        return {}

def _verify_pw(pw, stored):
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False

_DUMMY_HASH = "pbkdf2_sha256$200000$" + "00" * 16 + "$" + "00" * 32
USERS = _load_users()

# ───────────────────────────── default config ─────────────────────────────
CATALOGUE_DEFAULT = json.loads(r'''[
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Midea Wall Mounted MA-09N8D0 2.5kw",
"desc": "Wall Mounted",
"rrp": 530.0,
"cost": 260.0
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Midea Wall Mounted MA-12NXD0 3.5kw",
"desc": "Wall Mounted",
"rrp": 610.0,
"cost": 305.0
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Midea Wall Mounted MA-18NXD0 5kw",
"desc": "Wall Mounted",
"rrp": 900.0,
"cost": 460.0
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Midea Wall Mounted MA-24NXD0 7kw",
"desc": "Wall Mounted",
"rrp": 1310.0,
"cost": 670.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Midea Ceiling Cassette MCA3U-12FNXD0 3.5kw",
"desc": "Ceiling Cassette",
"rrp": 1178.0,
"cost": 600.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Midea Ceiling Cassette MCA3U-18NXD0 5kw",
"desc": "Ceiling Cassette",
"rrp": 1560.0,
"cost": 800.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Midea Ceiling Cassette MCD-24FNXD0 7kw",
"desc": "Ceiling Cassette",
"rrp": 1986.0,
"cost": 993.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Midea Ceiling Cassette MCD-36FNXD0 10kw",
"desc": "Ceiling Cassette",
"rrp": 2498.0,
"cost": 1249.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Midea Ceiling Cassette MCD-42FNXD0 12kw",
"desc": "Ceiling Cassette",
"rrp": 2900.0,
"cost": 1450.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 3.5kw",
"desc": "A6 Ducted system",
"rrp": 1194.0,
"cost": 780.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 5kw",
"desc": "A6 Ducted system",
"rrp": 1524.0,
"cost": 940.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 7kw",
"desc": "A6 Ducted system",
"rrp": 1882.0,
"cost": 1113.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 10kw",
"desc": "A6 Ducted system",
"rrp": 2660.0,
"cost": 1512.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 12kw",
"desc": "A6 Ducted System",
"rrp": 2800.0,
"cost": 1585.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 14kw",
"desc": "A6 Ducted System",
"rrp": 3296.0,
"cost": 1845.0
},
{
"group": "Ducted",
"kind": "ducted",
"name": "Midea Ducted 16kw",
"desc": "A6 Ducted System",
"rrp": 3392.0,
"cost": 1896.0
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Mitsubishi SRK25ZSP 2.5kw Wall Mounted",
"desc": "Wall Mounted",
"rrp": 446.0,
"cost": 289.9
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Mitsubishi SRK35ZSP 3.5kw Wall Mounted",
"desc": "Wall Mounted",
"rrp": 515.0,
"cost": 334.75
},
{
"group": "Wall Mounted",
"kind": "wall",
"name": "Mitsubishi SRK50ZS 5kw Wall Mounted",
"desc": "Wall Mounted",
"rrp": 804.0,
"cost": 522.6
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi SRK71ZR 7kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 1252.0,
"cost": 813.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi FDTC_VH 2.5kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 742.0,
"cost": 550.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi FDTC-VH 3.5kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 863.46,
"cost": 639.6
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi FDTC-VH 5kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 1092.15,
"cost": 809.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi FDTC10-VH 10kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 1687.5,
"cost": 1250.0
},
{
"group": "Ceiling Cassette",
"kind": "ceiling",
"name": "Mitsubishi FDTC125-VH 12kw Ceiling Cassette",
"desc": "Ceiling Cassette",
"rrp": 2270.0,
"cost": 1475.0
},
{
"group": "Materials",
"kind": "material",
"name": "Copper - ¼” 15 metre Roll",
"desc": "¼” 15 metre Roll",
"rrp": 19.04,
"cost": 10.67
},
{
"group": "Materials",
"kind": "material",
"name": "Copper - 3/8” 15 metre Roll",
"desc": "3/8” 15 metre Roll",
"rrp": 33.59,
"cost": 18.82
},
{
"group": "Materials",
"kind": "material",
"name": "Copper - ½” 15 metre Roll",
"desc": "½” 15 metre Roll",
"rrp": 45.87,
"cost": 25.7
},
{
"group": "Materials",
"kind": "material",
"name": "Copper - 5/8” 15 metre Roll",
"desc": "5/8” 15 metre Roll",
"rrp": 64.93,
"cost": 36.38
},
{
"group": "Materials",
"kind": "material",
"name": "Insulation - ¼  15 metre Roll",
"desc": "¼  15 metre Roll",
"rrp": 11.03,
"cost": 6.13
},
{
"group": "Materials",
"kind": "material",
"name": "Insulation - 3/8” 15 metre Roll",
"desc": "3/8” 15 metre Roll",
"rrp": 11.55,
"cost": 6.42
},
{
"group": "Materials",
"kind": "material",
"name": "Insulation - ½” 15 metre Roll",
"desc": "½” 15 metre Roll",
"rrp": 11.79,
"cost": 6.55
},
{
"group": "Materials",
"kind": "material",
"name": "Insulation - 5/8” 15 metre Roll",
"desc": "5/8” 15 metre Roll",
"rrp": 12.2,
"cost": 6.78
},
{
"group": "Materials",
"kind": "material",
"name": "Tank Pump - Machine mounted pump",
"desc": "Machine mounted pump",
"rrp": 63.84,
"cost": 41.19
},
{
"group": "Materials",
"kind": "material",
"name": "Wall Pump - Wall mounted pump",
"desc": "Wall mounted pump",
"rrp": 129.23,
"cost": 83.38
},
{
"group": "Materials",
"kind": "material",
"name": "Drain Pipe - 3 metre water pipe",
"desc": "3 metre water pipe",
"rrp": 9.12,
"cost": 5.53
},
{
"group": "Materials",
"kind": "material",
"name": "3 core Flex cable - 100 metre 1.5 Roll",
"desc": "100 metre 1.5 Roll",
"rrp": 88.34,
"cost": 49.63
},
{
"group": "Materials",
"kind": "material",
"name": "Electric SY Cable - 100 metre roll",
"desc": "100 metre roll",
"rrp": 165.0,
"cost": 92.72
},
{
"group": "Materials",
"kind": "material",
"name": "Drain Hose - Water drain ¼ 15 metre roll",
"desc": "Water drain ¼ 15 metre roll",
"rrp": 13.74,
"cost": 8.33
},
{
"group": "Materials",
"kind": "material",
"name": "Drain Hose - Water drain 3/8 15 metre roll",
"desc": "Water drain 3/8 15 metre roll",
"rrp": 20.74,
"cost": 12.57
},
{
"group": "Materials",
"kind": "material",
"name": "Bracket - small",
"desc": "small",
"rrp": 47.6,
"cost": 28.85
},
{
"group": "Materials",
"kind": "material",
"name": "Bracket - medium",
"desc": "medium",
"rrp": 56.47,
"cost": 34.23
},
{
"group": "Materials",
"kind": "material",
"name": "Bracket - large",
"desc": "large",
"rrp": 73.93,
"cost": 44.81
},
{
"group": "Labour",
"kind": "labour",
"name": "Engineers Labour - 1 day",
"desc": "1 day",
"rrp": 300.0,
"cost": 300.0
},
{
"group": "Extras",
"kind": "extra",
"name": "Blue Science - Covid and flu prevention ultra violet tec strip",
"desc": "Covid and flu prevention ultra violet tec strip",
"rrp": 140.0,
"cost": 108.0
},
{
"group": "Extras",
"kind": "extra",
"name": "WIFI - Built in system wifi Midea",
"desc": "Built in system wifi Midea",
"rrp": 100.0,
"cost": 20.0
},
{
"group": "Extras",
"kind": "extra",
"name": "External trunking - 3 meter wall trunking to hide pipes",
"desc": "3 meter wall trunking to hide pipes",
"rrp": 30.0,
"cost": 10.0
},
{
"group": "Extras",
"kind": "extra",
"name": "External wall tray - 3 meter lengths 4”",
"desc": "3 meter lengths 4”",
"rrp": 11.48,
"cost": 6.11
},
{
"group": "Extras",
"kind": "extra",
"name": "External wall tray - 3 meter length 6”",
"desc": "3 meter length 6”",
"rrp": 14.28,
"cost": 7.6
},
{
"group": "Extras",
"kind": "extra",
"name": "Outdoor machine feet/stand - 1x set 450mm",
"desc": "1x set 450mm",
"rrp": 13.86,
"cost": 9.24
},
{
"group": "Extras",
"kind": "extra",
"name": "Outdoor machine feet/stand - 1x set 1000mm",
"desc": "1x set 1000mm",
"rrp": 28.8,
"cost": 19.2
},
{
"group": "Extras",
"kind": "extra",
"name": "WIFI - Mitsubishi system",
"desc": "Mitsubishi system",
"rrp": 80.0,
"cost": 65.0
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 150M3",
"desc": "Lossnay air exchange unit",
"rrp": 1194.0,
"cost": 780.0,
"tbc": true
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 250M3",
"desc": "Lossnay air exchange unit",
"rrp": 1524.0,
"cost": 940.0,
"tbc": true
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 350M3",
"desc": "Lossnay air exchange unit",
"rrp": 1882.0,
"cost": 1113.0,
"tbc": true
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 500M3",
"desc": "Lossnay air exchange unit",
"rrp": 2660.0,
"cost": 1512.0,
"tbc": true
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 800M3",
"desc": "Lossnay air exchange unit",
"rrp": 2800.0,
"cost": 1585.0,
"tbc": true
},
{
"group": "Lossnay Air Exchange",
"kind": "lossnay",
"name": "Lossnay 1000M3",
"desc": "Lossnay air exchange unit",
"rrp": 3296.0,
"cost": 1845.0,
"tbc": true
}
]''')

def default_config():
    return {
        "company": {
            "trading": "SteadyTemp Air Conditioning",
            "legal": "SY Comms Ltd",
            "legal_line": "SteadyTemp Air Conditioning is a trading name of SY Comms Ltd",
            "addr": ["Suite C Jupiter House", "Sitka Drive", "Shrewsbury Business Park", "Shropshire", "SY2 6LG"],
            "reg": "Registered in England 15722588",
            "vat": "VAT Registration No. Pending",
            "email": "hello@sycomms.co.uk",
            "phone": "",
            "web": "",
            "funder": "our finance partner",
            "logo_b64": "",
        },
        "catalogue": CATALOGUE_DEFAULT,
        # customer rate = what the customer pays per £1,000; funder rate = what the funder pays per £1,000
        "lease_rates": [
            {"months": 36, "label": "3 Year (1+35)", "rate": 37.0, "true_rate": 28.26},
            {"months": 60, "label": "5 Year (1+59)", "rate": 26.0, "true_rate": 18.65},
            {"months": 84, "label": "7 Year (1+83)", "rate": 23.0, "true_rate": 16.46},
        ],
        "costs": {
            "srrp_mult": 2.0,
            "maint_wall": 10.0, "maint_ceiling": 15.0, "maint_ducted": 25.0, "maint_lossnay": 25.0,
            "lab_wall": 650.0, "lab_ceiling": 1000.0, "lab_ducted": 2500.0, "lab_lossnay": 0.0,
            "electrician": 200.0, "cherry_picker": 700.0, "pump": 200.0,
            "telemarketing": 200.0, "sales_override": 100.0, "min_commission": 0.0,
            "cash_load": 1.0,
            "unit_size": 4000.0, "unit_value": 1000.0,
            "free_support_years": 1,
        },
        "terms": None,            # filled from TERMS_DEFAULT
        "terms_draft": True,      # shows a DRAFT banner on the Terms page until switched off in Admin
    }

TERMS_DEFAULT = [
    ["1. DEFINITIONS", "Order means the SteadyTemp order form signed by you. Equipment means the air conditioning units, controls and associated materials listed on the Order. We/us means {legal} trading as {trading}. You means the customer named on the Order. Site means the premises where the Equipment is to be installed. Funder means the third party finance provider that rents the Equipment to you. Initial Period means the first {free} year(s) of on-site support included in the price."],
    ["2. THE CONTRACT", "These terms and the Order form the whole agreement between us for the supply, installation and support of the Equipment. If you are renting the Equipment from a Funder, the Funder's rental agreement is a separate contract between you and the Funder and these terms do not replace it. Prices are quoted in pounds sterling and exclude VAT, which is added at the prevailing rate."],
    ["3. SUPPLY AND INSTALLATION", "We will supply and install the Equipment at the Site with reasonable skill and care, using suitably qualified engineers, and in line with the regulations that apply to refrigerant-containing equipment, including the F-Gas regulations. Installation dates are estimates and time is not of the essence. We will make good any damage we cause to the Site. Standard installation covers the pipework, cabling, drainage and fixings described in the Order; additional work found to be needed on the day (for example specialist access equipment, structural or electrical upgrades) will be agreed with you before it is carried out."],
    ["4. YOUR RESPONSIBILITIES", "You will give our engineers safe and timely access to the Site, provide a suitable electrical supply and any consents needed from your landlord or building owner, and tell us about hazards at the Site (including asbestos). You must not move, alter or repair the Equipment, or let anyone other than us or the Funder do so, without our written consent. You must use the Equipment in line with the manufacturer's instructions and keep filters clean as advised."],
    ["5. RENTAL THROUGH A FUNDER", "Where the Equipment is rented through a Funder, the rental is invoiced and collected by the Funder under its own agreement, for the term and at the monthly amount shown on the Order, plus VAT. We will help you apply for finance but approval is at the Funder's discretion; if the Funder declines, we may offer a different payment option or cancel the Order without liability on either side. The Equipment belongs to the Funder, and you must not sell, move or part with it. Rental payments must continue for the whole term whether or not you are using the Equipment."],
    ["6. CASH SALE", "Where you buy the Equipment outright, the price shown on the Order is payable as set out in the payment schedule. Ownership of the Equipment passes to you only when we have received payment in full; until then you must keep it insured, safe and identifiable as ours. Risk passes to you on delivery to the Site."],
    ["7. WARRANTY AND ON-SITE SUPPORT", "During the Initial Period we provide on-site warranty cover, including remote diagnostics and programming of faults, as described in the On-Site Support Agreement. Faulty Equipment will be repaired or replaced. Warranty and support do not cover damage caused by misuse, accident, unauthorised work, power faults, flooding or fair wear and tear on consumables. After the Initial Period the annual support charge shown on the Order applies for the term of the agreement. Equipment added later will be charged for, and its support premium added, by agreement."],
    ["8. CHARGES AND PAYMENT", "All charges exclude VAT. Our invoices are due within 14 days. A late payment fee of £25 applies after 7 days. Support and other charges that we bill are collected by Direct Debit through GoCardless; a direct debit cancellation fee of £50 applies. We may charge interest on overdue amounts at 4% above the Bank of England base rate. We may suspend support while an account is overdue."],
    ["9. TERM AND RENEWAL", "The support agreement runs for the term shown on the Order. At the end of the term the Equipment may be returned, renewed or replaced as set out in the Funder's agreement; our support continues year to year at our then-current annual charge unless either of us gives 90 days' written notice."],
    ["10. CANCELLATION", "Once installation has started, or the Equipment has been ordered specially for you, you cannot cancel the Order without paying our reasonable costs to that point. Rental and support commitments are for the full term shown on the Order. If you end the support agreement early, the remaining annual charges become due."],
    ["11. LIABILITY", "We are not liable for loss of profits, business opportunity, goodwill or indirect loss. Our total liability is capped at the amount you have paid us in the previous 12 months under the Order. Nothing in these terms limits liability for death or personal injury caused by negligence, fraud, or anything else that cannot be limited by law. Air conditioning does not guarantee a particular temperature in all conditions; performance depends on correct use and the building."],
    ["12. TERMINATION", "Either of us may end the contract if the other commits a serious breach that is not put right within 14 days of written notice, or becomes insolvent. We may end it at once if payment is more than 7 days overdue after a reminder. On ending, all unpaid sums become due, and we or the Funder may collect the Equipment from the Site."],
    ["13. DATA PROTECTION", "We use the personal details you give us to provide the Equipment and support, to arrange finance and to bill you, and share them with the Funder and our installers where needed. We keep them secure and do not sell them. See our privacy notice for your rights."],
    ["14. FORCE MAJEURE", "Neither of us is liable for delay or failure caused by events beyond our reasonable control, including severe weather, supply shortages, strikes, or failure of utilities."],
    ["15. GENERAL", "These terms and the Order are the whole agreement between us and are governed by the law of England and Wales, with the English courts having exclusive jurisdiction. We may change these terms by written notice; changes do not alter a signed Order. You may not transfer your rights without our written consent. If any clause is found unenforceable the rest remains in force."],
]

# ───────────────────────────── config load ─────────────────────────────
CONFIG_FILE = "config.json"

def load_config():
    cfg = default_config()
    try:
        if Path(CONFIG_FILE).exists():
            saved = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    except Exception:
        pass
    if not cfg.get("terms"):
        cfg["terms"] = [list(t) for t in TERMS_DEFAULT]
    return cfg

if "cfg" not in st.session_state:
    st.session_state.cfg = load_config()
CFG = st.session_state.cfg
CO = CFG["company"]
COST = CFG["costs"]

# ───────────────────────────── sign-in ─────────────────────────────
for _k, _v in (("authed", False), ("current_user", None)):
    st.session_state.setdefault(_k, _v)

def _login_screen():
    _l, _m, _r = st.columns([1, 1.2, 1])
    with _m:
        st.markdown(f"<div style='text-align:center;margin:2.5rem 0 1rem'><div style='font-size:2.4rem'>❄️</div>"
                    f"<div style='font-size:1.7rem;font-weight:800;color:#0B3C5D'>{esc(CO['trading'])}</div>"
                    f"<div style='color:#5B7A91'>Quotes &amp; paperwork</div></div>", unsafe_allow_html=True)
        with st.container(border=True):
            if USERS:
                em = st.text_input("Email", key="lg_email", placeholder="you@yourcompany.co.uk")
                pw = st.text_input("Password", type="password", key="lg_pw")
                if st.button("Sign in", type="primary", **FW):
                    import time as _t
                    if _t.time() < st.session_state.get("_lock_until", 0):
                        st.error("Too many attempts - please wait a minute and try again.")
                    else:
                        u = USERS.get((em or "").strip().lower())
                        ok = _verify_pw(pw or "", u["hash"] if u else _DUMMY_HASH) and bool(u)
                        if ok:
                            st.session_state._fails = 0
                            st.session_state.current_user = {"email": em.strip().lower(), "name": u["name"], "role": u["role"]}
                            if u["name"]:
                                st.session_state["q_rep"] = u["name"]
                            st.session_state.authed = True
                            st.rerun()
                        else:
                            f = st.session_state.get("_fails", 0) + 1
                            st.session_state._fails = f
                            if f >= 5:
                                st.session_state._lock_until = _t.time() + 60
                                st.session_state._fails = 0
                            _t.sleep(1)
                            st.error("Incorrect email or password - please try again.")
            else:
                shared = _secret("APP_PASSWORD")
                pw = st.text_input("Password", type="password", key="lg_pw")
                if st.button("Sign in", type="primary", **FW):
                    if not shared:
                        st.error("Sign-in isn't set up yet. Add the users list (or APP_PASSWORD) to the app's Secrets.")
                    elif hmac.compare_digest((pw or "").encode(), shared.encode()):
                        st.session_state.authed = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")

if not st.session_state.authed:
    _login_screen()
    st.stop()

ROLE = (st.session_state.current_user or {}).get("role")
IS_ADMIN = (ROLE == "admin") if USERS else True      # without individual logins everyone is treated as admin (as the old tool)

# ───────────────────────────── calculation engine ─────────────────────────────
GROUP_ORDER = ["Wall Mounted", "Ceiling Cassette", "Ducted", "Lossnay Air Exchange", "Extras", "Materials", "Labour"]
SYSTEM_KINDS = ("wall", "ceiling", "ducted", "lossnay")

def _num(key, default=0.0):
    try:
        v = st.session_state.get(key, default)
        return float(v) if v not in (None, "") else float(default)
    except Exception:
        return float(default)

def cat_key(item):
    return "eq_" + item["name"]

def srrp_of(item):
    return round(float(item["rrp"]) * float(COST["srrp_mult"]), 2)

def rate_row(months):
    for r in CFG["lease_rates"]:
        if int(r["months"]) == int(months):
            return r
    return CFG["lease_rates"][-1]

def calc():
    """The SteadyTemp price book, exactly as the Excel P&L sheet works (see the Air Con P & L Calcs sheet)."""
    C = COST
    qty, counts, equip_cost, equip_srrp = [], {k: 0 for k in SYSTEM_KINDS}, 0.0, 0.0
    for it in CFG["catalogue"]:
        q = int(_num(cat_key(it)))
        if q <= 0:
            continue
        qty.append((it, q))
        equip_cost += q * float(it["cost"])
        equip_srrp += q * srrp_of(it)
        if it["kind"] in counts:
            counts[it["kind"]] += q
    n_sys = counts["wall"] + counts["ceiling"] + counts["ducted"]
    maint_annual = 12.0 * (counts["wall"] * C["maint_wall"] + counts["ceiling"] * C["maint_ceiling"]
                           + counts["ducted"] * C["maint_ducted"] + counts["lossnay"] * C["maint_lossnay"])
    cherry = C["cherry_picker"] if st.session_state.get("q_cherry") == "Yes" else 0.0
    pump = int(_num("q_pumps")) * C["pump"]
    extras = cherry + pump
    install = (n_sys * C["electrician"] + counts["wall"] * C["lab_wall"] + counts["ceiling"] * C["lab_ceiling"]
               + counts["ducted"] * C["lab_ducted"] + counts["lossnay"] * C["lab_lossnay"])
    other = _num("q_cashback") + _num("q_other_costs")
    additional = C["telemarketing"] + C["sales_override"] + C["min_commission"]
    set_up = maint_annual + extras + install + equip_cost + other + additional       # "Set Up Costs & Equipment"
    subtotal = set_up + equip_srrp                                                    # "Sub Total for lease calcs"
    term = int(st.session_state.get("q_term", 84))
    rr = rate_row(term)
    rate, true_rate = float(rr["rate"]), float(rr["true_rate"])
    calc_rental = subtotal * rate / 1000.0
    desired = _num("q_desired_rental")
    rental = round(desired if desired > 0 else calc_rental, 2)
    funded = rental / true_rate * 1000.0 if true_rate > 0 else 0.0
    gp = funded - set_up
    units = gp / C["unit_size"] if C["unit_size"] else 0.0
    commission = units * C["unit_value"]
    # cash sale
    cash_list = subtotal * C["cash_load"]
    vol_disc = _num("q_vol_discount")
    cash_price = round(cash_list - vol_disc, 2)
    cash_gp = cash_price - set_up
    cash_units = cash_gp / C["unit_size"] if C["unit_size"] else 0.0
    cash_comm = cash_units * C["unit_value"]
    is_cash = st.session_state.get("q_pay_model") == "Cash sale"
    return dict(
        qty=qty, counts=counts, n_units=sum(counts.values()), n_all=sum(q for _, q in qty),
        equip_cost=equip_cost, equip_srrp=equip_srrp, maint_annual=maint_annual, extras=extras, install=install,
        other=other, additional=additional, set_up=set_up, subtotal=subtotal, term=term, term_label=rr["label"],
        profile=f"1+{term - 1}", rate=rate, true_rate=true_rate, calc_rental=round(calc_rental, 2), rental=rental,
        desired_on=desired > 0 and abs(desired - calc_rental) > 0.005, funded=funded, gp=gp, units=units,
        commission=commission, co_profit=gp - commission, cash_list=round(cash_list, 2), cash_price=cash_price,
        cash_gp=cash_gp, cash_units=cash_units, cash_comm=cash_comm, is_cash=is_cash,
        tbc=[it["name"] for it, _ in qty if it.get("tbc")],
    )

CALC = calc()

# ───────────────────────────── saved quote file ─────────────────────────────
_QUOTE_PREFIXES = ("q_", "eq_")

def quote_snapshot():
    out = {}
    for k, v in st.session_state.items():
        if k.startswith(_QUOTE_PREFIXES) and isinstance(v, (str, int, float, bool)) and not k.startswith("q_sig"):
            out[k] = v
    return out

def _load_quote_cb():
    f = st.session_state.get("up_quote")
    if not f:
        return
    try:
        data = json.loads(f.getvalue().decode("utf-8"))
        for k, v in data.items():
            if k.startswith(_QUOTE_PREFIXES):
                st.session_state[k] = v
        st.session_state["_quote_loaded"] = f.name
    except Exception:
        st.session_state["_quote_loaded"] = "ERR"

# ───────────────────────────── paperwork (PDF) ─────────────────────────────
NAVY, ACCENT, PALE = (11, 60, 93), (0, 160, 200), (234, 244, 250)

def Q(key, default=""):
    v = st.session_state.get(key, default)
    return "" if v is None else str(v).strip()

def cust_address_lines():
    return [x for x in (Q("q_addr1"), Q("q_addr2"), Q("q_town"), Q("q_county"), Q("q_postcode")) if x]

def split_name_pos(raw):
    parts = [p.strip() for p in str(raw or "").split(" - ", 1)]
    return parts[0], (parts[1] if len(parts) > 1 else "")

class DocPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(120, 130, 140)
        self.cell(0, 4, s(f"{CO['legal_line']}  |  {CO['reg']}"), align="C", ln=True)
        self.cell(0, 4, f"Page {self.page_no()} of {{nb}}", align="C")
        self.set_text_color(0, 0, 0)

def _logo_stream():
    b = CO.get("logo_b64") or ""
    if not b:
        return None
    try:
        import base64
        return io.BytesIO(base64.b64decode(b))
    except Exception:
        return None

def doc_header(pdf, title, subtitle=""):
    pdf.add_page()
    pdf.set_fill_color(*NAVY); pdf.rect(0, 0, 210, 34, "F")
    pdf.set_fill_color(*ACCENT); pdf.rect(0, 34, 210, 1.6, "F")
    x0 = 12
    lg = _logo_stream()
    if lg is not None:
        try:
            pdf.image(lg, x=10, y=5, h=24); x0 = 48
        except Exception:
            x0 = 12
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(x0, 8); pdf.set_font("Helvetica", "B", 19)
    pdf.cell(110, 9, s(CO["trading"].upper()), ln=True)
    pdf.set_x(x0); pdf.set_font("Helvetica", "", 9)
    pdf.cell(110, 6, s(subtitle or "Air conditioning supplied, installed and supported"), ln=True)
    pdf.set_xy(120, 8); pdf.set_font("Helvetica", "B", 13)
    pdf.cell(78, 8, s(title), align="R", ln=True)
    rep = Q("q_rep")
    if rep:
        pdf.set_xy(120, 17); pdf.set_font("Helvetica", "I", 8)
        pdf.cell(78, 5, s(f"Prepared by: {rep}"), align="R")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(42)

def band(pdf, text):
    pdf.ln(2)
    pdf.set_fill_color(*NAVY); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "  " + s(text), fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

def para(pdf, text, size=8.5, h=4.4, align="J", style=""):
    pdf.set_font("Helvetica", style, size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, h, s(text), align=align)

def kv(pdf, label, value, lw=42):
    pdf.set_font("Helvetica", "B", 8.5); pdf.set_text_color(90, 100, 110)
    pdf.cell(lw, 5.2, s(label), ln=False)
    pdf.set_font("Helvetica", "", 8.5); pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5.2, s(value), ln=True)

def company_block(pdf):
    pdf.set_font("Helvetica", "", 7.5); pdf.set_text_color(70, 80, 90)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 3.8, s(", ".join(x for x in CO["addr"] if x) + "  |  " + CO["reg"] + "  |  " + CO["vat"]))
    pdf.set_text_color(0, 0, 0)

def customer_block(pdf):
    band(pdf, "Customer details")
    kv(pdf, "Customer:", Q("q_company"))
    kv(pdf, "Company reg no:", Q("q_reg"))
    kv(pdf, "Address:", ", ".join(cust_address_lines()))
    kv(pdf, "Contact:", Q("q_contact") or split_name_pos(Q("q_signatory"))[0])
    if Q("q_tel") or Q("q_mobile"):
        kv(pdf, "Telephone:", " / ".join(x for x in (Q("q_tel"), Q("q_mobile")) if x))
    kv(pdf, "Customer email:", Q("q_email"))
    kv(pdf, "Billing email:", Q("q_bill_email") or Q("q_email"))
    if Q("q_inv_addr"):
        kv(pdf, "Invoice address:", Q("q_inv_addr").replace("\n", ", "))

def equipment_table(pdf, C):
    band(pdf, "Equipment")
    pdf.set_font("Helvetica", "B", 8); pdf.set_fill_color(*PALE)
    pdf.cell(118, 5.5, "  Item", fill=True); pdf.cell(48, 5.5, "Type", fill=True); pdf.cell(0, 5.5, "Qty", fill=True, ln=True, align="C")
    pdf.set_font("Helvetica", "", 8.5)
    shown = 0
    for it, q in C["qty"]:
        if it["group"] in ("Materials", "Labour"):
            continue
        pdf.cell(118, 5.4, "  " + s(it["name"])[:70], border="B")
        pdf.cell(48, 5.4, s(it["group"]), border="B")
        pdf.cell(0, 5.4, str(q), border="B", ln=True, align="C")
        shown += 1
    if not shown:
        pdf.set_text_color(160, 60, 60); pdf.cell(0, 6, "  (no equipment selected yet)", ln=True); pdf.set_text_color(0, 0, 0)

def sig_block(pdf, heading, sign, note=""):
    if pdf.get_y() > 243:
        pdf.add_page(); pdf.set_y(20)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 9); pdf.cell(0, 5, s(heading), ln=True)
    y = pdf.get_y()
    if sign and sign.get("bytes"):
        try:
            pdf.image(io.BytesIO(sign["bytes"]), x=pdf.l_margin, y=y + 0.5, w=52, h=17)
        except Exception:
            pass
        pdf.set_y(y + 18.5)
    else:
        pdf.set_y(y + 14)
    pdf.cell(80, 0.4, "", border="T", ln=True)
    pdf.ln(1)
    if sign:
        nm, ps = sign["name"], ""
        n2, p2 = split_name_pos(sign["name"])
        nm, ps = n2, p2
        when = sign.get("ts", "")
        co = sign.get("company", "")
    else:
        nm, ps = split_name_pos(Q("q_signatory"))
        when, co = "", Q("q_company")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.cell(95, 5, s(f"Name:  {nm or '____________________________'}"), ln=False)
    pdf.cell(0, 5, s(f"Date:  {when or '____ / ____ / ________'}"), ln=True)
    pdf.cell(95, 5, s(f"Position:  {ps or '____________________________'}"), ln=False)
    pdf.cell(0, 5, s(f"Company:  {co or '____________________________'}"), ln=True)
    if note:
        pdf.ln(1); pdf.set_font("Helvetica", "I", 7.5); pdf.set_text_color(110, 120, 130)
        pdf.multi_cell(pdf.epw, 3.8, s(note)); pdf.set_text_color(0, 0, 0)

def payment_text(C):
    t = CO["trading"]; cust = Q("q_company") or "the customer"
    if C["is_cash"]:
        return (f"{t} agrees to sell, and {cust} (the customer) agrees to buy, the equipment specified above for a price of "
                f"{money(C['cash_price'])} plus VAT, payable on the terms set out in our invoice. Ownership of the equipment passes to "
                f"the customer when payment is received in full.")
    n = C["term"] - 1
    return (f"{t} agrees with {cust}, the hirer, that the equipment specified above shall be rented to you by {CO['legal']} or a "
            f"3rd party finance provider, for an initial payment of {money(C['rental'])} plus VAT followed by {n} further payments of "
            f"{money(C['rental'])} plus VAT. {t} will assist with the application for 3rd party finance to facilitate {C['term']} "
            f"monthly payments of {money(C['rental'])} plus VAT and shall arrange for {CO['funder']} to enter into a rental agreement with the hirer.")

def existing_costs():
    rows = [("Existing running costs", Q("q_cur_running")), ("Existing service costs", Q("q_cur_service")),
            ("Existing equipment leasing costs", Q("q_cur_leasing")), ("Existing heating costs", Q("q_cur_heating")),
            ("Other", Q("q_cur_other"))]
    out = []
    for lbl, v in rows:
        try:
            f = float(v)
        except Exception:
            f = 0.0
        out.append((lbl, f))
    return out, sum(f for _, f in out)

def doc_proposal(pdf, C, sign):
    doc_header(pdf, "Air Conditioning Proposal")
    pdf.set_font("Helvetica", "", 9)
    kv(pdf, "Date:", date.today().strftime("%d/%m/%Y"))
    kv(pdf, "Prepared for:", Q("q_company"))
    kv(pdf, "Address:", ", ".join(cust_address_lines()))
    kv(pdf, "Proposed by:", CO["trading"])
    pdf.set_x(pdf.l_margin + 42); company_block(pdf)
    para(pdf, "Everything below is supplied, installed and supported by us, so there is one team to call.", h=4.6)
    equipment_table(pdf, C)
    names = " ".join(it["name"] for it, _ in C["qty"])
    if "Blue Science" in names:
        band(pdf, "Blue Science air sanitising")
        para(pdf, "Blue Science uses the disinfectant properties of UV-C light to turn an air conditioning unit into an air sanitiser. Warm, "
                  "contaminated air is pulled in through the top of the unit and cooled by the cooling coil, where the Blue Science UV-C strip "
                  "sanitises it. The cooled air is then released free of airborne viruses, bacteria, moulds and odours.")
    if C["counts"]["lossnay"]:
        band(pdf, "Lossnay air exchange")
        para(pdf, "A commercial ventilation system that extracts stale air and recovers the heating or cooling energy to warm or cool the "
                  "incoming fresh air, using the Lossnay core for high energy-recovery efficiency.")
    band(pdf, "Monthly quotation" if not C["is_cash"] else "Quotation")
    ex, ex_total = existing_costs()
    if ex_total > 0:
        pdf.set_font("Helvetica", "B", 8.5); pdf.cell(0, 5, "Your existing monthly air conditioning costs", ln=True)
        pdf.set_font("Helvetica", "", 8.5)
        for lbl, v in ex:
            if v:
                pdf.cell(120, 5, "  " + s(lbl), ln=False); pdf.cell(0, 5, money(v), ln=True, align="R")
        pdf.set_font("Helvetica", "B", 8.5); pdf.cell(120, 5.5, "  TOTAL existing", border="T", ln=False); pdf.cell(0, 5.5, money(ex_total), border="T", ln=True, align="R")
        pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8.5); pdf.cell(0, 5, "New air conditioning costs", ln=True)
    pdf.set_font("Helvetica", "", 8.5)
    if C["is_cash"]:
        pdf.cell(120, 5.2, "  Equipment, installation and set-up (one-off, plus VAT)", ln=False); pdf.cell(0, 5.2, money(C["cash_price"]), ln=True, align="R")
    else:
        pdf.cell(120, 5.2, "  Equipment rental charge per month (plus VAT)", ln=False); pdf.cell(0, 5.2, money(C["rental"]), ln=True, align="R")
    fy = int(COST["free_support_years"])
    pdf.cell(120, 5.2, s(f"  On-site support - first {fy} year{'s' if fy != 1 else ''}"), ln=False); pdf.cell(0, 5.2, "Included", ln=True, align="R")
    pdf.cell(120, 5.2, s(f"  On-site support after year {fy} (annual charge, plus VAT)"), ln=False); pdf.cell(0, 5.2, money(C["maint_annual"]), ln=True, align="R")
    if not C["is_cash"] and ex_total > 0:
        diff = ex_total - C["rental"]
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(120, 5.6, "  Estimated monthly difference", border="T", ln=False)
        pdf.cell(0, 5.6, (money(diff) + " saving") if diff >= 0 else (money(-diff) + " more"), border="T", ln=True, align="R")
    pdf.ln(1)
    band(pdf, "Your quotation includes")
    cash_back = _num("q_cashback")
    yes = [("Installation & set up", "Yes"), (f"{fy} year on-site support", "Yes"),
           ("Cherry picker / access equipment", Q("q_cherry") or "No")]
    if int(_num("q_pumps")):
        yes.append(("Condensate pump(s)", str(int(_num("q_pumps")))))
    if cash_back > 0:
        yes.append(("Cashback towards your requirements", money(cash_back)))
    for lbl, v in yes:
        pdf.set_font("Helvetica", "", 8.5); pdf.cell(120, 5, "  " + s(lbl), ln=False); pdf.cell(0, 5, s(v), ln=True, align="R")
    if not C["is_cash"]:
        pdf.ln(1)
        para(pdf, f"Equipment rental terms: monthly rental period of {C['profile']} ({C['term_label']}), plus VAT at the prevailing rate.", style="B")
    pdf.ln(1)
    para(pdf, "I confirm that I wish to proceed with the proposal above. I understand that I will be billed in line with "
              f"{CO['legal']}'s current Terms and Conditions" + ("" if C["is_cash"] else ", that the equipment rental is billed separately by a "
              "3rd party funder, and that support and all other costs are billed by us under a separate agreement") + ".", size=8)
    sig_block(pdf, "Signed on behalf of the customer", sign)

def doc_order(pdf, C, sign):
    doc_header(pdf, "Order Form")
    pdf.set_font("Helvetica", "", 8); company_block(pdf)
    kv(pdf, "Date:", date.today().strftime("%d/%m/%Y"))
    customer_block(pdf)
    equipment_table(pdf, C)
    if Q("q_special"):
        band(pdf, "Special conditions"); para(pdf, Q("q_special"))
    band(pdf, "Payment schedule")
    para(pdf, payment_text(C))
    pdf.ln(1)
    para(pdf, f"{CO['trading']} agrees to supply, install and decommission the above equipment, and the customer agrees to make the "
              "associated payments in accordance with the payment schedule above, subject to the terms and conditions"
              + ("" if C["is_cash"] else " and the terms of the hire agreement with the finance provider")
              + ". As a duly authorised representative of the customer, I confirm that I have read, understood and accept the terms and "
                "conditions of this agreement.")
    sig_block(pdf, "On behalf of (the customer)", sign)

def doc_support(pdf, C, sign):
    doc_header(pdf, "On-Site Support Agreement")
    kv(pdf, "Date:", date.today().strftime("%d/%m/%Y"))
    customer_block(pdf)
    equipment_table(pdf, C)
    fy = int(COST["free_support_years"])
    band(pdf, "Support terms")
    para(pdf, f"{CO['trading']} agrees to provide on-site warranty cover, to include remote diagnostics and programming of faults, for the "
              f"equipment listed above for an agreement term of {C['term']} months. Faulty equipment will be repaired or replaced. "
              "Additional equipment added later will be charged for, and its warranty premium added to this agreement.")
    pdf.ln(1)
    kv(pdf, "Inclusive period:", f"{fy} year{'s' if fy != 1 else ''} from installation", 42)
    kv(pdf, "Annual charge after:", f"{money(C['maint_annual'])} plus VAT per year, for the remainder of the term", 42)
    pdf.ln(1)
    para(pdf, f"{CO['trading']} agrees to provide remote and on-site maintenance cover for the equipment above, and the customer agrees to pay "
              "the annual charge set out above for the agreement term, subject to the terms and conditions. As a duly authorised representative "
              "of the customer, I confirm that I have read, understood and accept the terms and conditions of this agreement.")
    sig_block(pdf, "On behalf of (the customer)", sign)

def doc_dd(pdf, C, sign):
    doc_header(pdf, "Direct Debit Set-up")
    band(pdf, "Set up your bank or building society to pay by Direct Debit")
    para(pdf, f"Our support charges and any other amounts we bill are collected by Direct Debit through GoCardless. "
              + ("Your equipment rental is billed separately by the finance provider. " if not C["is_cash"] else "")
              + "It only takes a couple of minutes:", h=5)
    pdf.ln(2)
    steps = [("Step one", f"You will receive a GoCardless email from {CO['legal']} ({CO['trading']})."),
             ("Step two", "Set up your account by entering the account holder's name, sort code and account number."),
             ("Step three", "Once complete you will receive an email confirming your registration.")]
    for a, b in steps:
        pdf.set_fill_color(*PALE); pdf.set_font("Helvetica", "B", 9)
        pdf.cell(30, 9, "  " + a, fill=True, border="B"); pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 9, "  " + s(b), fill=True, border="B", ln=True)
        pdf.ln(1)
    pdf.ln(3)
    para(pdf, "Your payments are protected by the Direct Debit Guarantee. If anything changes, we will tell you in advance. If you need to "
              "cancel, contact your bank or us.", size=8, style="I")

def doc_terms(pdf, C, sign):
    doc_header(pdf, "Terms & Conditions")
    if CFG.get("terms_draft", True):
        pdf.set_fill_color(255, 240, 200); pdf.set_draw_color(230, 150, 30)
        pdf.set_font("Helvetica", "B", 8.5); pdf.set_text_color(130, 80, 0)
        pdf.cell(0, 7, "  DRAFT TERMS - NOT TO BE ISSUED UNTIL REVIEWED (switch off in Admin > Company & terms)", fill=True, border=1, ln=True)
        pdf.set_text_color(0, 0, 0); pdf.ln(2)
    fill = dict(legal=CO["legal"], trading=CO["trading"], free=int(COST["free_support_years"]))
    for title, text in CFG["terms"]:
        pdf.set_fill_color(*NAVY); pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 5, "  " + s(title), fill=True, ln=True); pdf.set_text_color(0, 0, 0)
        try:
            body = text.format(**fill)
        except Exception:
            body = text
        pdf.set_font("Helvetica", "", 7.4); pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 3.7, s(body), align="J"); pdf.ln(1.2)
    sig_block(pdf, "Confirmation - I have read and agree to these Terms & Conditions", sign)

def doc_certificate(pdf, C, sign):
    doc_header(pdf, "Certificate of Completion", "Electronic signing record")
    env = str(uuid.uuid4()).upper()
    import hashlib as _h
    kv(pdf, "Envelope ID:", env, 48)
    kv(pdf, "Status:", "COMPLETED", 48)
    kv(pdf, "Document:", f"{CO['trading']} proposal - {Q('q_company')}"[:80], 48)
    kv(pdf, "Signer:", sign["name"], 48)
    kv(pdf, "Company:", sign.get("company", ""), 48)
    kv(pdf, "Signed at:", sign.get("ts", ""), 48)
    kv(pdf, "IP address:", sign.get("ip", "Not captured"), 48)
    kv(pdf, "Signature fingerprint:", _h.sha256(sign["bytes"]).hexdigest().upper()[:48], 48)
    kv(pdf, "Time zone:", "UK (London)", 48)
    pdf.ln(4)
    para(pdf, "This record confirms that the signer above applied the signature shown in this document electronically, using a secure "
              "session, on the date and time shown. The same signature has been applied to each signature block in this pack.", size=8)

def build_pack(sign=None):
    C = calc()
    pdf = DocPDF()
    pdf.set_margins(15, 15, 15); pdf.set_auto_page_break(True, 16); pdf.alias_nb_pages()
    for fn in (doc_proposal, doc_order, doc_support, doc_dd, doc_terms):
        fn(pdf, C, sign)
    if sign and sign.get("bytes"):
        doc_certificate(pdf, C, sign)
    return bytes(pdf.output())

# ───────────────────────────── look & feel ─────────────────────────────
st.markdown("""
<style>
.block-container{padding-top:1.4rem;max-width:1250px}
.st-hero{background:linear-gradient(120deg,#0B3C5D 0%,#0E6E9C 100%);color:#fff;border-radius:16px;padding:1.1rem 1.4rem;margin-bottom:1rem}
.st-hero .t{font-size:1.5rem;font-weight:800;letter-spacing:.3px}.st-hero .s{opacity:.85;font-size:.9rem}
.st-card{border:1px solid #D5E3EE;border-radius:14px;padding:1rem 1.2rem;background:#fff}
.st-card .l{font-size:.72rem;font-weight:700;text-transform:uppercase;color:#5B7A91}
.st-card .v{font-size:1.9rem;font-weight:800;color:#0B3C5D}.st-card .x{font-size:.82rem;color:#5B7A91}
.st-warn{border-left:4px solid #E69B1E;background:#FFF6E3;border-radius:8px;padding:.6rem .9rem;margin:.4rem 0;color:#6B4400}
.st-bad{border-left:4px solid #D64545;background:#FDECEC;border-radius:8px;padding:.6rem .9rem;margin:.4rem 0;color:#7A1F1F}
</style>""", unsafe_allow_html=True)

def card(label, value, sub="", target=None):
    (target or st).markdown(f"<div class='st-card'><div class='l'>{esc(label)}</div><div class='v'>{esc(value)}</div>"
                            f"<div class='x'>{esc(sub)}</div></div>", unsafe_allow_html=True)

me = st.session_state.current_user or {}
st.markdown(f"<div class='st-hero'><div class='t'>❄️ {esc(CO['trading'])}</div>"
            f"<div class='s'>Quotes &amp; paperwork" + (f" · signed in as {esc(me.get('name') or me.get('email'))}" if me else "") + "</div></div>",
            unsafe_allow_html=True)

# ───────────────────────────── sidebar (customer-safe summary) ─────────────────────────────
with st.sidebar:
    st.markdown("### Quote summary")
    st.caption(Q("q_company") or "No customer yet")
    st.metric("Systems", CALC["n_units"])
    if CALC["is_cash"]:
        st.metric("Cash price (ex VAT)", money(CALC["cash_price"]))
    else:
        st.metric(f"Monthly rental · {CALC['term_label']}", money(CALC["rental"]))
        st.caption("plus VAT · billed by the funder")
    st.metric("Annual support (after year 1)", money(CALC["maint_annual"]))
    st.divider()
    if st.button("Sign out", **FW):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

tab_names = ["👤 Customer", "❄️ Equipment", "💷 Quote", "💼 Consultant", "📄 Paperwork", "✍️ Sign & Send"]
if IS_ADMIN:
    tab_names.append("🔐 Admin")
TABS = st.tabs(tab_names)
t_cust, t_eq, t_quote, t_cons, t_paper, t_sign = TABS[:6]
t_admin = TABS[6] if IS_ADMIN else None

# ───────────────────────────── customer ─────────────────────────────
with t_cust:
    st.markdown("#### Customer information")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Customer (full company name)", key="q_company")
        st.text_input("Company reg no", key="q_reg")
        st.selectbox("Business type", ["Limited Company", "Sole Trader", "Partnership", "LLP", "Charity / Other"], key="q_btype")
        st.text_input("Address line 1", key="q_addr1")
        st.text_input("Address line 2", key="q_addr2")
        a, b, c = st.columns(3)
        a.text_input("Town", key="q_town"); b.text_input("County", key="q_county"); c.text_input("Post code", key="q_postcode")
        st.text_area("Invoice address (if different)", key="q_inv_addr", height=70)
    with c2:
        st.text_input("Signatory name & position", key="q_signatory", placeholder="Jane Smith - Director",
                      help="Used on the paperwork. Format: Name - Position")
        st.text_input("Main contact name", key="q_contact")
        st.text_input("Contact tel no", key="q_tel")
        st.text_input("Contact mobile", key="q_mobile")
        st.text_input("Customer email", key="q_email")
        st.text_input("Billing email", key="q_bill_email")
        st.number_input("Number of existing air con units", min_value=0, step=1, key="q_existing_units")
        st.text_area("Notes to engineer & office", key="q_notes", height=90)
    st.text_input("Prepared by", key="q_rep", help="Shown on the paperwork. Filled from your login.")

# ───────────────────────────── equipment ─────────────────────────────
with t_eq:
    st.markdown("#### Equipment")
    st.caption("Enter how many of each. Only the systems and extras appear on the customer paperwork - materials and labour are costed in the background.")
    by_group = {}
    for it in CFG["catalogue"]:
        by_group.setdefault(it["group"], []).append(it)
    for g in GROUP_ORDER + [x for x in by_group if x not in GROUP_ORDER]:
        items = by_group.get(g)
        if not items:
            continue
        picked = sum(int(_num(cat_key(i))) for i in items)
        with st.expander(f"{g}  ·  {picked} selected" if picked else g, expanded=bool(picked) or g == "Wall Mounted"):
            for it in items:
                cols = st.columns([4, 1.1] if not IS_ADMIN else [4, 2, 1.1])
                cols[0].markdown(f"**{it['name']}**" + ("  ⚠️ *price to be confirmed*" if it.get("tbc") else ""))
                if IS_ADMIN:
                    cols[1].caption(f"RRP {money(it['rrp'])} · sell {money(srrp_of(it))} · cost {money(it['cost'])}")
                cols[-1].number_input("Qty", min_value=0, step=1, key=cat_key(it), label_visibility="collapsed")
    if CALC["tbc"]:
        st.markdown("<div class='st-warn'>⚠️ <b>Price to be confirmed:</b> " + esc(", ".join(CALC["tbc"])) +
                    " - the catalogue price is a placeholder. Check with the office before quoting.</div>", unsafe_allow_html=True)

# ───────────────────────────── quote ─────────────────────────────
with t_quote:
    st.markdown("#### Payment & terms")
    q1, q2 = st.columns(2)
    with q1:
        st.radio("Payment model", ["Lease (rental over term)", "Cash sale"], key="q_pay_model", horizontal=True)
        terms = [(int(r["months"]), r["label"]) for r in CFG["lease_rates"]]
        st.selectbox("Lease term", [m for m, _ in terms], index=len(terms) - 1, key="q_term",
                     format_func=lambda m: dict(terms).get(m, str(m)), disabled=CALC["is_cash"])
        st.radio("Cherry picker / access equipment needed?", ["No", "Yes"], key="q_cherry", horizontal=True)
        st.number_input("Condensate pumps (install charge)", min_value=0, step=1, key="q_pumps")
        st.text_area("Special conditions (printed on the order form)", key="q_special", height=100)
    with q2:
        st.markdown("**Customer's existing monthly costs** (optional - shown as a comparison on the proposal)")
        for lbl, key in (("Running costs", "q_cur_running"), ("Service costs", "q_cur_service"), ("Equipment leasing", "q_cur_leasing"),
                         ("Heating", "q_cur_heating"), ("Other", "q_cur_other")):
            st.number_input(lbl + " (£/month)", min_value=0.0, step=1.0, key=key)
    st.divider()
    m1, m2, m3 = st.columns(3)
    if CALC["is_cash"]:
        card("Cash price", money(CALC["cash_price"]), "plus VAT", m1)
    else:
        card("Monthly rental", money(CALC["rental"]), f"{CALC['term_label']} · plus VAT", m1)
    card("Annual support", money(CALC["maint_annual"]), "after the included period", m2)
    card("Systems", str(CALC["n_units"]), "units in this quote", m3)

# ───────────────────────────── consultant ─────────────────────────────
with t_cons:
    st.markdown("#### Deal tools")
    k1, k2 = st.columns(2)
    with k1:
        st.number_input("Target monthly rental £ (0 = use the calculated rental)", min_value=0.0, step=1.0, key="q_desired_rental")
        st.number_input("Cashback to customer £", min_value=0.0, step=10.0, key="q_cashback")
    with k2:
        st.number_input("Other costs £", min_value=0.0, step=10.0, key="q_other_costs")
        st.number_input("Volume discount on cash price £", min_value=0.0, step=10.0, key="q_vol_discount")
    st.divider()
    C = CALC
    if C["is_cash"]:
        comm_units, comm_val, gp = C["cash_units"], C["cash_comm"], C["cash_gp"]
    else:
        comm_units, comm_val, gp = C["units"], C["commission"], C["gp"]
    a, b, c, d = st.columns(4)
    card("Calculated rental", money(C["calc_rental"]), "price book" if not C["is_cash"] else "n/a (cash)", a)
    card("Rental used", money(C["rental"]) if not C["is_cash"] else money(C["cash_price"]), "your target" if C["desired_on"] else "calculated", b)
    card("Commission units", f"{comm_units:.2f}", f"£{COST['unit_size']:,.0f} profit = 1 unit", c)
    card("Commission", money(comm_val, 0), "estimated", d)
    if gp < 0:
        st.markdown("<div class='st-bad'>⛔ This deal is below cost - it makes a loss. Raise the rental/price.</div>", unsafe_allow_html=True)
    elif comm_units < 0.25:
        st.markdown("<div class='st-warn'>⚠️ Very low profit on this deal - check with the office.</div>", unsafe_allow_html=True)
    if IS_ADMIN:
        st.divider()
        st.markdown("##### Admin - full profit & loss")
        rows = [("Equipment cost", C["equip_cost"]), ("Equipment SRRP (selling price of equipment)", C["equip_srrp"]),
                ("Maintenance (annual)", C["maint_annual"]), ("Extras (cherry picker, pumps)", C["extras"]),
                ("Installation (labour + electrician)", C["install"]), ("Cashback + other costs", C["other"]),
                ("Telemarketing, override, min. commission", C["additional"]),
                ("Set-up costs & equipment", C["set_up"]), ("Sub total for lease calcs", C["subtotal"]),
                ("Customer rate / funder rate (per £1,000)", f"{C['rate']:.2f} / {C['true_rate']:.2f}"),
                ("Funder pays (rental ÷ funder rate × 1,000)", C["funded"]), ("Gross profit (lease)", C["gp"]),
                ("Commission (lease)", C["commission"]), ("Company profit after commission (lease)", C["co_profit"]),
                ("Cash list price", C["cash_list"]), ("Cash price after discount", C["cash_price"]),
                ("Gross profit (cash)", C["cash_gp"]), ("Commission (cash)", C["cash_comm"])]
        st.dataframe(pd.DataFrame([(a_, b_ if isinstance(b_, str) else f"{float(b_):,.2f}") for a_, b_ in rows],
                                  columns=["Line", "£"]), **FW, hide_index=True)

# ───────────────────────────── paperwork ─────────────────────────────
def _fname(ext):
    nm = re.sub(r"[^A-Za-z0-9]+", "_", Q("q_company") or "SteadyTemp_quote").strip("_")
    return f"{nm}_{date.today().isoformat()}.{ext}"

def _ready():
    miss = []
    if not Q("q_company"): miss.append("customer name")
    if not Q("q_signatory"): miss.append("signatory name & position")
    if CALC["n_units"] == 0: miss.append("at least one air conditioning system")
    return miss

with t_paper:
    st.markdown("#### Paperwork pack")
    st.caption("Proposal · Order form · On-site support agreement · Direct debit set-up · Terms & conditions")
    miss = _ready()
    if miss:
        st.markdown("<div class='st-warn'>Still needed: " + esc(", ".join(miss)) + "</div>", unsafe_allow_html=True)
    if CFG.get("terms_draft", True):
        st.markdown("<div class='st-warn'>The Terms & Conditions are still marked <b>DRAFT</b>. An admin switches this off in Admin → Company & terms once they've been reviewed.</div>", unsafe_allow_html=True)
    if st.button("Build the pack", type="primary", key="btn_build"):
        try:
            st.session_state["_pack_bytes"] = build_pack(None)
        except Exception as e:
            st.session_state.pop("_pack_bytes", None)
            st.error(f"Couldn't build the pack: {e}")
    if st.session_state.get("_pack_bytes"):
        st.download_button("⬇️ Download the unsigned pack (PDF)", st.session_state["_pack_bytes"], _fname("pdf"),
                           mime="application/pdf", **FW)
    st.divider()
    st.markdown("##### Save / load this quote")
    st.download_button("💾 Save this quote (JSON)", json.dumps(quote_snapshot(), indent=2), _fname("json"),
                       mime="application/json", key="dl_quote_json")
    st.file_uploader("Load a saved quote", type=["json"], key="up_quote", on_change=_load_quote_cb)
    ql = st.session_state.get("_quote_loaded")
    if ql == "ERR":
        st.error("That file couldn't be read.")
    elif ql:
        st.success(f"Loaded {ql}")

# ───────────────────────────── sign & send ─────────────────────────────
def _client_ip():
    try:
        h = st.context.headers
        for k in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP", "True-Client-IP"):
            if h.get(k, ""):
                return h.get(k).split(",")[0].strip()
    except Exception:
        pass
    return "Not captured"

with t_sign:
    st.markdown("#### Customer signature")
    miss = _ready()
    if miss:
        st.markdown("<div class='st-warn'>Still needed before signing: " + esc(", ".join(miss)) + "</div>", unsafe_allow_html=True)
    if not st.session_state.get("q_sign_name") and Q("q_signatory"):
        st.session_state["q_sign_name"] = Q("q_signatory")
    st.text_input("Name & position of the person signing", key="q_sign_name")
    method = st.radio("Signature", ["Draw on screen", "Upload photo of signature"], horizontal=True, key="q_sign_method")
    if method == "Upload photo of signature":
        up = st.file_uploader("Signature image (JPG or PNG)", type=["jpg", "jpeg", "png"], key="sig_up")
        if up:
            from PIL import Image as _I
            im = _I.open(up).convert("RGB").resize((400, 130))
            b = io.BytesIO(); im.save(b, format="PNG"); st.session_state["_sig_bytes"] = b.getvalue()
            st.image(up, width=260)
    elif not CANVAS_OK:
        st.warning("The drawing pad isn't available - please upload a photo of the signature instead.")
    else:
        res = st_canvas(fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000", background_color="#EAF4FB",
                        update_streamlit=True, height=170, width=500, drawing_mode="freedraw", key="sig_canvas")
        if st.button("✅ Save signature", key="btn_save_sig"):
            data = getattr(res, "image_data", None)
            if data is None:
                st.error("Please draw a signature first.")
            else:
                from PIL import Image as _I
                rgba = _I.fromarray(data.astype("uint8"), "RGBA")
                white = _I.new("RGBA", rgba.size, (255, 255, 255, 255)); white.paste(rgba, mask=rgba.split()[3])
                arr = np.array(white.convert("RGB")).astype("int16")
                arr[np.abs(arr - np.array([234, 244, 251])).max(axis=2) < 40] = 255
                b = io.BytesIO(); _I.fromarray(arr.astype("uint8"), "RGB").save(b, format="PNG")
                if np.count_nonzero(arr < 200) < 30:
                    st.error("The pad looks empty - please draw a signature first.")
                else:
                    st.session_state["_sig_bytes"] = b.getvalue(); st.success("Signature saved")
    have_sig = bool(st.session_state.get("_sig_bytes"))
    st.caption("Signature captured ✔" if have_sig else "No signature captured yet.")
    agree = st.checkbox("The signer confirms they have read and agree to the proposal, order form, support agreement and terms & conditions.", key="q_sign_agree")
    if st.button("Generate signed pack", type="primary", disabled=not (have_sig and agree and not miss and Q("q_sign_name"))):
        sign = {"bytes": st.session_state["_sig_bytes"], "name": Q("q_sign_name"), "company": Q("q_company"),
                "ts": datetime.now().strftime("%d/%m/%Y  %H:%M"), "ip": _client_ip()}
        try:
            st.session_state["_signed_pack"] = build_pack(sign)
            st.session_state["_signed_json"] = json.dumps({**quote_snapshot(), "_signed_at": sign["ts"], "_signed_by": sign["name"]}, indent=2)
        except Exception as e:
            st.error(f"Couldn't build the signed pack: {e}")
    if st.session_state.get("_signed_pack"):
        st.success("Signed pack ready.")
        st.download_button("⬇️ Download signed pack (PDF)", st.session_state["_signed_pack"], _fname("pdf").replace(".pdf", "_SIGNED.pdf"),
                           mime="application/pdf", **FW)
        st.download_button("💾 Download the saved quote (JSON)", st.session_state["_signed_json"], _fname("json"),
                           mime="application/json", **FW, key="dl_signed_json")

# ───────────────────────────── admin ─────────────────────────────
if IS_ADMIN and t_admin is not None:
    with t_admin:
        st.markdown("#### Admin")
        st.markdown("<div class='st-warn'>Changes here apply straight away but last only until the app restarts. "
                    "Use <b>Backup</b> to download <code>config.json</code> and upload it to GitHub to make them permanent.</div>",
                    unsafe_allow_html=True)
        a_cat, a_rates, a_costs, a_co, a_bk = st.tabs(["Catalogue", "Lease rates", "Costs & fees", "Company & terms", "Backup"])

        with a_cat:
            st.caption("Edit prices, add or remove lines. 'Sell' is RRP × the SRRP multiplier (Costs & fees). Tick 'Price TBC' to warn consultants.")
            groups = [g for g in GROUP_ORDER if any(i["group"] == g for i in CFG["catalogue"])]
            gsel = st.selectbox("Group", groups, key="adm_group")
            kind_of = {"Wall Mounted": "wall", "Ceiling Cassette": "ceiling", "Ducted": "ducted", "Lossnay Air Exchange": "lossnay",
                       "Materials": "material", "Labour": "labour", "Extras": "extra"}
            rows = [{"name": i["name"], "desc": i.get("desc", ""), "rrp": float(i["rrp"]), "cost": float(i["cost"]), "tbc": bool(i.get("tbc"))}
                    for i in CFG["catalogue"] if i["group"] == gsel]
            with st.form(f"adm_cat_form_{gsel}"):
                ed = st.data_editor(pd.DataFrame(rows), num_rows="dynamic", **FW, key=f"adm_ed_{gsel}",
                                    column_config={"name": st.column_config.TextColumn("Name"), "desc": st.column_config.TextColumn("Description"),
                                                   "rrp": st.column_config.NumberColumn("RRP £", format="%.2f", min_value=0.0),
                                                   "cost": st.column_config.NumberColumn("Cost £", format="%.2f", min_value=0.0),
                                                   "tbc": st.column_config.CheckboxColumn("Price TBC")})
                if st.form_submit_button("Save this group", type="primary"):
                    keep = [i for i in CFG["catalogue"] if i["group"] != gsel]
                    new = []
                    for _, r in ed.iterrows():
                        nm = str(r.get("name") or "").strip()
                        if not nm:
                            continue
                        new.append({"group": gsel, "kind": kind_of.get(gsel, "extra"), "name": nm, "desc": str(r.get("desc") or ""),
                                    "rrp": float(r.get("rrp") or 0), "cost": float(r.get("cost") or 0), "tbc": bool(r.get("tbc"))})
                    names = [i["name"] for i in keep + new]
                    if len(names) != len(set(names)):
                        st.error("Two lines have the same name - names must be unique.")
                    else:
                        order = {g: n for n, g in enumerate(GROUP_ORDER)}
                        CFG["catalogue"] = sorted(keep + new, key=lambda i: order.get(i["group"], 99))
                        st.success("Saved."); st.rerun()

        with a_rates:
            st.caption("Customer rate = what the customer's rental is worked out at (per £1,000). Funder rate = what the funder pays for the rental (per £1,000). "
                       "Please check these match your current funder rates.")
            with st.form("adm_rates_form"):
                ed = st.data_editor(pd.DataFrame(CFG["lease_rates"]), num_rows="dynamic", **FW,
                                    column_config={"months": st.column_config.NumberColumn("Months", step=1, min_value=1),
                                                   "label": st.column_config.TextColumn("Label"),
                                                   "rate": st.column_config.NumberColumn("Customer rate", format="%.2f", min_value=0.01),
                                                   "true_rate": st.column_config.NumberColumn("Funder rate", format="%.2f", min_value=0.01)})
                if st.form_submit_button("Save lease rates", type="primary"):
                    out = [{"months": int(r["months"]), "label": str(r["label"]), "rate": float(r["rate"]), "true_rate": float(r["true_rate"])}
                           for _, r in ed.iterrows() if r.get("months") and r.get("rate") and r.get("true_rate")]
                    if out:
                        CFG["lease_rates"] = sorted(out, key=lambda r: r["months"]); st.success("Saved."); st.rerun()
                    else:
                        st.error("Add at least one complete row.")

        with a_costs:
            labels = {"srrp_mult": "SRRP multiplier (selling price = RRP ×)", "maint_wall": "Maintenance £/month - wall unit",
                      "maint_ceiling": "Maintenance £/month - ceiling unit", "maint_ducted": "Maintenance £/month - ducted system",
                      "maint_lossnay": "Maintenance £/month - Lossnay unit", "lab_wall": "Install labour - wall unit £",
                      "lab_ceiling": "Install labour - ceiling unit £", "lab_ducted": "Install labour - ducted system £",
                      "lab_lossnay": "Install labour - Lossnay unit £ (0 in the price book - please confirm)", "electrician": "Electrician per system £",
                      "cherry_picker": "Cherry picker £", "pump": "Pump £ each", "telemarketing": "Telemarketing £", "sales_override": "Sales override £",
                      "min_commission": "Minimum sales commission £", "cash_load": "Cash price load (1.00 = list)", "unit_size": "Profit per commission unit £",
                      "unit_value": "Commission per unit £", "free_support_years": "Included support (years)"}
            with st.form("adm_costs_form"):
                cols = st.columns(3); vals = {}
                for n, (k, lbl) in enumerate(labels.items()):
                    vals[k] = cols[n % 3].number_input(lbl, value=float(COST[k]), step=1.0 if k != "cash_load" and k != "srrp_mult" else 0.05, key=f"adm_c_{k}")
                if st.form_submit_button("Save costs & fees", type="primary"):
                    for k, v in vals.items():
                        COST[k] = int(v) if k == "free_support_years" else float(v)
                    st.success("Saved."); st.rerun()

        with a_co:
            with st.form("adm_co_form"):
                c1, c2 = st.columns(2)
                trading = c1.text_input("Trading name", CO["trading"]); legal = c2.text_input("Legal company name", CO["legal"])
                legal_line = st.text_input("Footer line", CO["legal_line"])
                addr = st.text_area("Address (one line each)", "\n".join(CO["addr"]), height=110)
                r1, r2 = st.columns(2)
                reg = r1.text_input("Registration line", CO["reg"]); vat = r2.text_input("VAT line", CO["vat"])
                e1, e2, e3 = st.columns(3)
                email = e1.text_input("Email", CO["email"]); phone = e2.text_input("Phone", CO["phone"]); web = e3.text_input("Website", CO["web"])
                funder = st.text_input("Finance provider name used in the paperwork", CO["funder"])
                logo = st.file_uploader("Logo (PNG/JPG, optional)", type=["png", "jpg", "jpeg"])
                st.markdown("**Terms & Conditions** - one clause per row. `{legal}`, `{trading}` and `{free}` fill in automatically.")
                terms_df = st.data_editor(pd.DataFrame(CFG["terms"], columns=["Clause", "Text"]), num_rows="dynamic", **FW,
                                          column_config={"Text": st.column_config.TextColumn("Text", width="large")})
                draft = st.checkbox("Mark the Terms & Conditions page as DRAFT", value=bool(CFG.get("terms_draft", True)))
                if st.form_submit_button("Save company & terms", type="primary"):
                    CO.update(trading=trading, legal=legal, legal_line=legal_line, addr=[x.strip() for x in addr.splitlines() if x.strip()],
                              reg=reg, vat=vat, email=email, phone=phone, web=web, funder=funder)
                    if logo is not None:
                        import base64
                        CO["logo_b64"] = base64.b64encode(logo.getvalue()).decode()
                    CFG["terms"] = [[str(r["Clause"]), str(r["Text"])] for _, r in terms_df.iterrows() if str(r.get("Clause") or "").strip()]
                    CFG["terms_draft"] = bool(draft)
                    st.success("Saved."); st.rerun()

        with a_bk:
            st.download_button("⬇️ Download config.json", json.dumps(CFG, indent=1, ensure_ascii=False), "config.json", mime="application/json")
            st.caption("Upload this file to the root of the GitHub repo (replacing the old one) to make your changes permanent.")
            up = st.file_uploader("Restore from a config.json", type=["json"], key="adm_up_cfg")
            if up is not None and st.button("Restore this config"):
                try:
                    st.session_state.cfg = {**default_config(), **json.loads(up.getvalue().decode("utf-8"))}
                    st.success("Restored."); st.rerun()
                except Exception as e:
                    st.error(f"Couldn't read that file: {e}")
