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
CATALOGUE_DEFAULT = json.loads(r'''[{"group": "Wall Mounted", "kind": "wall", "name": "Midea Wall Mounted 2.5kw", "desc": "Wall Mounted", "rrp": 530.0, "cost": 260.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Midea Wall Mounted 3.5kw", "desc": "Wall Mounted", "rrp": 610.0, "cost": 305.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Midea Wall Mounted 5kw", "desc": "Wall Mounted", "rrp": 900.0, "cost": 460.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Midea Wall Mounted 7kw", "desc": "Wall Mounted", "rrp": 1310.0, "cost": 670.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Midea Wall Mounted 10kw", "desc": "Wall Mounted", "rrp": 1925.0, "cost": 985.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Mitsubishi Wall Mounted 2.5kw", "desc": "Wall Mounted", "rrp": 530.0, "cost": 260.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Mitsubishi Wall Mounted 3.5kw", "desc": "Wall Mounted", "rrp": 610.0, "cost": 305.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Mitsubishi Wall Mounted 5kw", "desc": "Wall Mounted", "rrp": 900.0, "cost": 460.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Mitsubishi Wall Mounted 7kw", "desc": "Wall Mounted", "rrp": 1310.0, "cost": 670.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Mitsubishi Wall Mounted 10kw", "desc": "Wall Mounted", "rrp": 1925.0, "cost": 985.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Panasonic Wall Mounted 2.5kw", "desc": "Wall Mounted", "rrp": 530.0, "cost": 260.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Panasonic Wall Mounted 3.5kw", "desc": "Wall Mounted", "rrp": 610.0, "cost": 305.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Panasonic Wall Mounted 5kw", "desc": "Wall Mounted", "rrp": 900.0, "cost": 460.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Panasonic Wall Mounted 7kw", "desc": "Wall Mounted", "rrp": 1310.0, "cost": 670.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Panasonic Wall Mounted 10kw", "desc": "Wall Mounted", "rrp": 1925.0, "cost": 985.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Samsung Wall Mounted 2.5kw", "desc": "Wall Mounted", "rrp": 530.0, "cost": 260.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Samsung Wall Mounted 3.5kw", "desc": "Wall Mounted", "rrp": 610.0, "cost": 305.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Samsung Wall Mounted 5kw", "desc": "Wall Mounted", "rrp": 900.0, "cost": 460.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Samsung Wall Mounted 7kw", "desc": "Wall Mounted", "rrp": 1310.0, "cost": 670.0}, {"group": "Wall Mounted", "kind": "wall", "name": "Samsung Wall Mounted 10kw", "desc": "Wall Mounted", "rrp": 1925.0, "cost": 985.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 3.5kw", "desc": "Ceiling Cassette", "rrp": 1178.0, "cost": 600.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 5kw", "desc": "Ceiling Cassette", "rrp": 1560.0, "cost": 800.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 7kw", "desc": "Ceiling Cassette", "rrp": 1986.0, "cost": 993.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 10kw", "desc": "Ceiling Cassette", "rrp": 2498.0, "cost": 1249.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 12kw", "desc": "Ceiling Cassette", "rrp": 2900.0, "cost": 1450.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 16kw", "desc": "Ceiling Cassette", "rrp": 3704.0, "cost": 1852.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Midea Ceiling Cassette 18kw", "desc": "Ceiling Cassette", "rrp": 4106.0, "cost": 2053.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 3.5kw", "desc": "Ceiling Cassette", "rrp": 1178.0, "cost": 600.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 5kw", "desc": "Ceiling Cassette", "rrp": 1560.0, "cost": 800.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 7kw", "desc": "Ceiling Cassette", "rrp": 1986.0, "cost": 993.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 10kw", "desc": "Ceiling Cassette", "rrp": 2498.0, "cost": 1249.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 12kw", "desc": "Ceiling Cassette", "rrp": 2900.0, "cost": 1450.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 16kw", "desc": "Ceiling Cassette", "rrp": 3704.0, "cost": 1852.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Mitsubishi Ceiling Cassette 18kw", "desc": "Ceiling Cassette", "rrp": 4106.0, "cost": 2053.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 3.5kw", "desc": "Ceiling Cassette", "rrp": 1178.0, "cost": 600.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 5kw", "desc": "Ceiling Cassette", "rrp": 1560.0, "cost": 800.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 7kw", "desc": "Ceiling Cassette", "rrp": 1986.0, "cost": 993.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 10kw", "desc": "Ceiling Cassette", "rrp": 2498.0, "cost": 1249.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 12kw", "desc": "Ceiling Cassette", "rrp": 2900.0, "cost": 1450.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 16kw", "desc": "Ceiling Cassette", "rrp": 3704.0, "cost": 1852.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Panasonic Ceiling Cassette 18kw", "desc": "Ceiling Cassette", "rrp": 4106.0, "cost": 2053.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 3.5kw", "desc": "Ceiling Cassette", "rrp": 1178.0, "cost": 600.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 5kw", "desc": "Ceiling Cassette", "rrp": 1560.0, "cost": 800.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 7kw", "desc": "Ceiling Cassette", "rrp": 1986.0, "cost": 993.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 10kw", "desc": "Ceiling Cassette", "rrp": 2498.0, "cost": 1249.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 12kw", "desc": "Ceiling Cassette", "rrp": 2900.0, "cost": 1450.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 16kw", "desc": "Ceiling Cassette", "rrp": 3704.0, "cost": 1852.0}, {"group": "Ceiling Cassette", "kind": "ceiling", "name": "Samsung Ceiling Cassette 18kw", "desc": "Ceiling Cassette", "rrp": 4106.0, "cost": 2053.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 3.5kw", "desc": "A6 Ducted system", "rrp": 1194.0, "cost": 780.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 5kw", "desc": "A6 Ducted system", "rrp": 1524.0, "cost": 940.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 7kw", "desc": "A6 Ducted system", "rrp": 1882.0, "cost": 1113.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 10kw", "desc": "A6 Ducted system", "rrp": 2660.0, "cost": 1512.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 12kw", "desc": "A6 Ducted System", "rrp": 2800.0, "cost": 1585.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 14kw", "desc": "A6 Ducted System", "rrp": 3296.0, "cost": 1845.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 16kw", "desc": "A6 Ducted System", "rrp": 3392.0, "cost": 1896.0}, {"group": "Ducted", "kind": "ducted", "name": "Midea Ducted 20kw", "desc": "A6 Ducted System", "rrp": 3584.0, "cost": 1998.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 3.5kw", "desc": "Ducted system", "rrp": 1194.0, "cost": 780.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 5kw", "desc": "Ducted system", "rrp": 1524.0, "cost": 940.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 7kw", "desc": "Ducted system", "rrp": 1882.0, "cost": 1113.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 10kw", "desc": "Ducted system", "rrp": 2660.0, "cost": 1512.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 12kw", "desc": "Ducted system", "rrp": 2800.0, "cost": 1585.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 14kw", "desc": "Ducted system", "rrp": 3296.0, "cost": 1845.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 16kw", "desc": "Ducted system", "rrp": 3392.0, "cost": 1896.0}, {"group": "Ducted", "kind": "ducted", "name": "Mitsubishi Ducted 20kw", "desc": "Ducted system", "rrp": 3584.0, "cost": 1998.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 3.5kw", "desc": "Ducted system", "rrp": 1194.0, "cost": 780.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 5kw", "desc": "Ducted system", "rrp": 1524.0, "cost": 940.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 7kw", "desc": "Ducted system", "rrp": 1882.0, "cost": 1113.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 10kw", "desc": "Ducted system", "rrp": 2660.0, "cost": 1512.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 12kw", "desc": "Ducted system", "rrp": 2800.0, "cost": 1585.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 14kw", "desc": "Ducted system", "rrp": 3296.0, "cost": 1845.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 16kw", "desc": "Ducted system", "rrp": 3392.0, "cost": 1896.0}, {"group": "Ducted", "kind": "ducted", "name": "Panasonic Ducted 20kw", "desc": "Ducted system", "rrp": 3584.0, "cost": 1998.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 3.5kw", "desc": "Ducted system", "rrp": 1194.0, "cost": 780.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 5kw", "desc": "Ducted system", "rrp": 1524.0, "cost": 940.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 7kw", "desc": "Ducted system", "rrp": 1882.0, "cost": 1113.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 10kw", "desc": "Ducted system", "rrp": 2660.0, "cost": 1512.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 12kw", "desc": "Ducted system", "rrp": 2800.0, "cost": 1585.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 14kw", "desc": "Ducted system", "rrp": 3296.0, "cost": 1845.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 16kw", "desc": "Ducted system", "rrp": 3392.0, "cost": 1896.0}, {"group": "Ducted", "kind": "ducted", "name": "Samsung Ducted 20kw", "desc": "Ducted system", "rrp": 3584.0, "cost": 1998.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 150M3", "desc": "Lossnay air exchange unit", "rrp": 1194.0, "cost": 780.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 250M3", "desc": "Lossnay air exchange unit", "rrp": 1524.0, "cost": 940.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 350M3", "desc": "Lossnay air exchange unit", "rrp": 1882.0, "cost": 1113.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 500M3", "desc": "Lossnay air exchange unit", "rrp": 2660.0, "cost": 1512.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 800M3", "desc": "Lossnay air exchange unit", "rrp": 2800.0, "cost": 1585.0}, {"group": "Lossnay Air Exchange", "kind": "lossnay", "name": "Lossnay 1000M3", "desc": "Lossnay air exchange unit", "rrp": 3296.0, "cost": 1845.0}, {"group": "Materials", "kind": "material", "name": "Copper - ¼” 15 metre Roll", "desc": "¼” 15 metre Roll", "rrp": 19.04, "cost": 10.67}, {"group": "Materials", "kind": "material", "name": "Copper - 3/8” 15 metre Roll", "desc": "3/8” 15 metre Roll", "rrp": 33.59, "cost": 18.82}, {"group": "Materials", "kind": "material", "name": "Copper - ½” 15 metre Roll", "desc": "½” 15 metre Roll", "rrp": 45.87, "cost": 25.7}, {"group": "Materials", "kind": "material", "name": "Copper - 5/8” 15 metre Roll", "desc": "5/8” 15 metre Roll", "rrp": 64.93, "cost": 36.38}, {"group": "Materials", "kind": "material", "name": "Insulation - ¼  15 metre Roll", "desc": "¼  15 metre Roll", "rrp": 11.03, "cost": 6.13}, {"group": "Materials", "kind": "material", "name": "Insulation - 3/8” 15 metre Roll", "desc": "3/8” 15 metre Roll", "rrp": 11.55, "cost": 6.42}, {"group": "Materials", "kind": "material", "name": "Insulation - ½” 15 metre Roll", "desc": "½” 15 metre Roll", "rrp": 11.79, "cost": 6.55}, {"group": "Materials", "kind": "material", "name": "Insulation - 5/8” 15 metre Roll", "desc": "5/8” 15 metre Roll", "rrp": 12.2, "cost": 6.78}, {"group": "Materials", "kind": "material", "name": "Tank Pump - Machine mounted pump", "desc": "Machine mounted pump", "rrp": 63.84, "cost": 41.19}, {"group": "Materials", "kind": "material", "name": "Wall Pump - Wall mounted pump", "desc": "Wall mounted pump", "rrp": 129.23, "cost": 83.38}, {"group": "Materials", "kind": "material", "name": "Drain Pipe - 3 metre water pipe", "desc": "3 metre water pipe", "rrp": 9.12, "cost": 5.53}, {"group": "Materials", "kind": "material", "name": "3 core Flex cable - 100 metre 1.5 Roll", "desc": "100 metre 1.5 Roll", "rrp": 88.34, "cost": 49.63}, {"group": "Materials", "kind": "material", "name": "Electric SY Cable - 100 metre roll", "desc": "100 metre roll", "rrp": 165.0, "cost": 92.72}, {"group": "Materials", "kind": "material", "name": "Drain Hose - Water drain ¼ 15 metre roll", "desc": "Water drain ¼ 15 metre roll", "rrp": 13.74, "cost": 8.33}, {"group": "Materials", "kind": "material", "name": "Drain Hose - Water drain 3/8 15 metre roll", "desc": "Water drain 3/8 15 metre roll", "rrp": 20.74, "cost": 12.57}, {"group": "Materials", "kind": "material", "name": "Bracket - small", "desc": "small", "rrp": 47.6, "cost": 28.85}, {"group": "Materials", "kind": "material", "name": "Bracket - medium", "desc": "medium", "rrp": 56.47, "cost": 34.23}, {"group": "Materials", "kind": "material", "name": "Bracket - large", "desc": "large", "rrp": 73.93, "cost": 44.81}, {"group": "Labour", "kind": "labour", "name": "Engineers Labour - 1 day", "desc": "1 day", "rrp": 300.0, "cost": 300.0}, {"group": "Extras", "kind": "extra", "name": "WIFI - Built in system wifi Midea", "desc": "Built in system wifi Midea", "rrp": 100.0, "cost": 20.0}, {"group": "Extras", "kind": "extra", "name": "External trunking - 3 meter wall trunking to hide pipes", "desc": "3 meter wall trunking to hide pipes", "rrp": 30.0, "cost": 10.0}, {"group": "Extras", "kind": "extra", "name": "External wall tray - 3 meter lengths 4”", "desc": "3 meter lengths 4”", "rrp": 11.48, "cost": 6.11}, {"group": "Extras", "kind": "extra", "name": "External wall tray - 3 meter length 6”", "desc": "3 meter length 6”", "rrp": 14.28, "cost": 7.6}, {"group": "Extras", "kind": "extra", "name": "Outdoor machine feet/stand - 1x set 450mm", "desc": "1x set 450mm", "rrp": 13.86, "cost": 9.24}, {"group": "Extras", "kind": "extra", "name": "Outdoor machine feet/stand - 1x set 1000mm", "desc": "1x set 1000mm", "rrp": 28.8, "cost": 19.2}, {"group": "Extras", "kind": "extra", "name": "WIFI - Mitsubishi system", "desc": "Mitsubishi system", "rrp": 80.0, "cost": 65.0}]''')

# Product pictures from the price book (JPEG, base64) - shown on the equipment cards
PRODUCT_IMAGES = json.loads(r'''{"wall": "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", "ceiling": "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UVlCR9Gz6+uKj0yNvMmeKAma4bc+1ePau20rwVZQFZLljK3oOldJaWFpaqFggRMeg5p2A4ix8P6pdKAyC3jPJL9T+Fbun+E7GHDXLNcN6Hhfyro6KdgIbe2t7dAkESRqOyjFTUUUwCiiigAooooAKKKKACiiigAooooAKKKKACkNLSGgBaKKKACiiigAwKa0aMMMoI96dRQBmX2h6bdqRJapk9wKwr3wTATvs5nhYdMGuwopWA89m0jX7E/KRcoPXrSwa1c25Md7bSoO+5dy16CQKgntLeYESRK2fUUWA4CA+FtZvJ0jtLU3aJiR4l2uoPvXH+IPhBYalc/aLTWrqPnOyb5sDuM16/8A2FZxs7W8SRM/3sKOahbSGBwFU/TilZgeeeHfh54Y0MA/ZxdzqPvS9B+HetKDxFaOHtdOtpcxMUKCIoP8SK7OLSG35Kovv1NW4NKtY33mMMx6kiiwHCx2Gt6mQAvkxHsBitjTfBUKgPeSGQ+ldgiKgwoAFOp2Ao2OlWNooEUCgjuetXQAOlLRTAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKQ0tIaAFooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigApDS0hoAWiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACkNLSGgBaKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKQ0tIaAFooooAKKKKACiiigAoooJwOaACio/Oi/56L+dHnRf89F/OgCSimpIj/dYH6GnUAFFFFABRRRmgAoqN5o0+84H1NRteWyjmVPzoAsUVVN/bY4kBpp1G3HfNK4FyiqB1OEHhWP4Uw6on9w/nRdAaVFZR1XjhM/jUbavJ2QfnRdBY2aKwW1absq1E2rXPYr+VLmQ7HR5HrRkVysmrXeP9Yo/CqsusXYyftQH5Uc6Cx2e4etJvX1rgpNXuG63zfgagfUpT1vZT9GNLnQ+U9DMqf3hSiRT3rzKS+JU7ri5I9i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", "ducted": "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", "lossnay": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCACfASwDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD7KWlpOoIpaACiiigApDS0UAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFGRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAg4GaWk/hNKKACiiigAooooAKKKRmxQAtFRtKqLukZUX1JwKz77xDo9mpNxqNumP9sGlcdjUpCQOtcbf/EfQLfIhaW5I/uLxWTJ8VLfafK0uQv8AwhnFLmCzPSN3fBxRuG3JIArxvUfiXrs+RawW9sOzY3N+tc7feINZ1Fs3mo3Dj+6GwPyFLmDlZ7tqGt6VYg/ar+CI+hcE1gX/AMQtDgOLczXRH9xcD9a8a3Bmy2W92JJqRWHQ9PejmCx6NL8S5vN/d6YuzPd+asw/Eu2I/e6bMp74cV5oGB6E/wBKcvzd6OZhY9Ug+I+kOBvtrmP8iKuw+PvD7/fmlj+qV5AoUd6fwR/9ajmYj2eHxj4dl6aig/3gRVuLxBospAj1K2Of9vFeH7ASCeadtHcfrRzAe7pqVg/K3luR/wBdBU8c0b8q6keoYGvAsZGMnFSRyyx/clkX6MRTTA99z+NJn2NeHQ6pqMf+rvrhf+BmrcXiTXIvu6lP+JBp3A9mLAdeKM+leSReMNeT/l+3f7yA1aj8c60pAYwP9UxTuB6lmgHNeanx7qark2lsxHoSKtw/ECXrJp6H1w5oA7+iuJj+IFv/AMtLCQf7rCrEfj3S2OHguE/CgDrqK5uLxrobkAzSJ9UNWovFOhydL5B9QRQK5tUVmx69pEjAJqFuf+BgVZTULFxlLuA/SQUDLNFMSWN/uOjfQ5p9ACfwmjmgUSHCEjsKAFJxSbueOa+bvFv7UWl6b4ivNIs9InaO0laJ7iQ5yynBwKyz+0DZat8reIHsQ38KxFP1pXGfT9xdQQAtLNHGB13sBWFf+NfD9mSrX6SuO0Q3V89J428P6k+T4jt5i3/PWc5P51oW13ZXH/Hte20q/wCxIDmlzD5Ueqah8ToUyLLTpJDnhpG2iuev/HviK6ysTw2qntGmSPxNc0ImzkDdShG/uVN2VZEl9fajfEm8vricns0hx+VU/KPoM+verQRieVFLtI/hpFWKnknqRk00QEg9R9Ku4b+7Rtb0oEioISO1KIcdqtAetGB6UDZWEXtThHjrVgKTyKXafagRXCDsTS7PrVlF9QKcUB7UAVdppwBxVjy19DR5XpQKyIMt6GlVmz3qfbSbaAshm8jtQJPanFB6UbB6H8KLMOUQS47U8SLjrTdg9PzpNuKaFyknmLSs6nBU4weag20bPamHKWQ4I604N6VVAI6Gly46MaLisWhg9Rml/Cqm+UdGNKZZQuSc/WjmFYtqxXocUZ9aybvV4bb5WZWlxwi8k/hVLUdfaOx84RmMEcheW/PtVJisbt5d29nA0tzMkSL1LmuZ1HxZtjZLSPaTxuP/ANauV1aTUfEUV7aNOIoGj4Udcg5yTTfKCoo69s+tWkZqWp7l+z1PcXp1a6uJpWwY1VWfIHU9K9dFeWfs9QiLStT28r5qDP8AwGvU6TLQdqbJgRknsDTqZL/qWx6H+VJjPzG+IUiT+O9dlRdqtqExA/4EaxkXPTFafjIA+L9YJ/5/pv8A0M1lx8NgdTTRLH7WX2qWGW4jbdHLIp9VY0wsuPn4A96rS3yRsRGgY9OtVYRuWmva3asGg1e+THZZiMVsWnj/AMY22DHr12f9/BrjoLwyQzSPIiNGPkTnLfQ9sVJbXscvyuNvpS5Quz0G3+K3jWEAHUopR6PCvNa9p8afEcYVbiwsJ8dSAUJ/KvMtoHPUUoUdhip5UXzM9ktPjeuALvQjnv5cucfnWxafGbw26/6TZXsLeyhq8DKZ6GlCe9KwKVj6OtPit4LnbD3dzD/vxED9K2Lbx14LuPlj1uBc/wB7K/zr5Z2EnGaXZik4j5z69sdT0O7GbXVbOTPZZVJq+sUDD5JEb6MDXxmjSIcqSp9uKsx6lqUZymoXceOgWYgUuW4c59jC1GM800Qdfavk+x8Y+J7IZt9ev1A6BpC3863LX4seN4Mf8TRZQO0sQNHKHOfSohPalEQHUGvn63+NXixcebBp0w/2osGtW1+OeoKB9p0S3fjnZIR+lFh8x7Z5QpDGAK8mtvjpZMP9J0S4X/cmFaNr8avDUzATW13D9UBosw5j0jZTWUnpXJ2nxR8FXAGdRMLHrviIrYtPF3hW75g1y0Ye74osO5p7D3o2/Wmw6lpU4HkajaSZ9JRVlfKdfkkR/wDdYGgCvtpfLFWTGR1Q/lUc0kMKl5nWNQMkscCgCMRZpTGiKXcgKoznPSuJ8VfFXw/oxaG0Jv58kYThR9TXkPi/4ieINfkeMXH2O2P/ACxhOOPc0rXYm7HsviXx5oelTGzt3+3Xx+7FC2cH3asu28SX+qxRQXRS1lnbHlW/zNj3b+H8K8H0Fmk8R2mWPMgPJ5r17wxDjW7TjjzK0UDPmudnaaYEj+UFVzzydzH1ZjyazPEqNb6WWVM4YdK6wiMR4B7knPFcp4n1CCWNrWCUyEsCeOAPStLClIyfDsso068u2jPEZIyMZrHt9Xnfh7c8tkY7Cuj0qMwaPdEDohIzzV5LgG2TdbWxG0f8sx6VXK2jHnO8+E3jPTPD2gXJ1ON18yXcMHnAGOle26ZdR32nW97Fny541kXPXBGRXx5q7mSY8bUwMIOlfVHw4u7m78G6fJdWhtXWJUVD3UAYP41nJWN4O6Ojpkh/dtx2P8qeelcB468W+IrDWm0Hw74blv7s2TXAndtsQI425xyfapKPz88Y8+LtY9fts3H/AAM1m2qSzTLHAGaRjhQo5J9K3/iToetaH4rv4NdtRbXUkzSuFPy5Y5/rVvwPaRxW8moSgb23BD6KP8TVRJYaF4Jl1i9+yySuixLvn8scLnoM+taHiz4a6dovhefVpLq4Xb8sak/eavbPhT4XL+C01EoFnvWMzOw49ABXnP7SWreXYafosKPH5ZYyZGAW6ZqmgTR4IG+ZgBU0MgQjGCB1BpFTbk4qOQADPSmTc6WyQG1EkWWiPbun/wBapsYIFZPhu7SK8CSsfJcYYf571u3caR3LpGXZAflLdSO2amSCLIRj0pdvuRSge1O/CoKGqoHvSsB6U8dKCCe3SgCLb7UbB6VPjikx7UARlVK4xQUHTFSEDHPFIevBoAj2D3pCg6ZJp5PzYNRSXkMMixs4BJ5OM7RnqaYhSg9TS7D6D8Kz9RuFF5IsNy88QOFcLt3VXW6VGyS49MNV2JNkK3TPAo2t12g+nNRaXJJO+yOVWY9FfitGe2mg2+dC0RcZGRjI9aOUOYqxvLGQQ7qf9liKtw6rqcJAgv7uP/dlNQEcdATSgAHpU2Q02bdj418WWf8AqNfvQP8Aafd/Om6t4s8Sa0ixahq086DsxwD9cVjbVqVQF5FJxRSkxDFlyzMW+tRsmNxwBVorx1pkoyuKEkDE0dSut2TqcfvlH05r2exkSy1RJ9hKxOTtFeI2W46zZKpIJkXH517YEOBnknmqILepave3wZHcxwn+BT1+tZ8EeW54yetQ6lfW1hCZJ3A9u9JoF+up2hnRSgDFQOuaomTZ0cCH+xbsZ52gD8TT2G23GB2H8qSCPbotwcksdik+vNWJgPLIxzirRk3cw7xWa9jXGMso/Wvr/SE8vSrSPGNsKD9BXyW0Ym1uBMYzPGP1FfXVsu23jX0UD9KxnudMNiSmMoGWA5p9I/3D9Khln51/tJarpmqfFTW59NuLiYC5ZXMrZUEDBCjsMisrSJHj0JI4IzI7hEVR3LHAH5msv4mKR4819e41Cb/0M1P4fkluLaKKGV0YAFdv95eR+oq4MiR9peDdHu9M8F6VplzsSaG1VZFHZu9Z3ivwLpPiK3MGqWcVwvYkfMPoawvgTq+s6/4XkS91Cae6tpijvJySDyK9EWLUIx8xVvqK1uJI8L1j9njw7JuNnc3kB7AsGH8hXB+JvgHe2dtNPaassvloWCNFy2B0r6vMlyCd0Cms7U/KljdWtmXKnJP0o0HY/PKItE+M7XjO0j3710Wn3Jn25OTs/lWJq6ga7qAThFuZAB9GNaPhwHzAW5ATNTLYLGyBwMelOCn2pYx8tOC574rIY3HrRUgUY9aTbQAYwKTHtTgDmlNAEbjimPwalbkc1XnbA6ZpoTJLa2uL64W2tRmRzgE9BXuXgT4Q6DZ2EV5qtt9uvHG5jNkqv0H+Oa4T4H6ONU8W2MUgyvzTvkdQvT9a+o5LZIhjjgcU2hxscRL4O8PtHsbRrFlxjBgX/CuL8X/Bzw5qkLyaah0y6xlWi5Q/VTXrdy1tFkyXCp/wIVl3Gq6ZHx9pQ+uOafIyj4+8VeGdZ8H6sLTUIypJzHKv3ZB/T6Vp6NrUepqLG+A34xE+T8vtzmvoLx5baF4m0OfTLqJpNykxPt5RuxBr5Z1WzuNG1iawuAVlhfHPcdjWii1uZtI6a6ge3maJscDg+tRKMnrxUlrqC3umRyMcyxkKx77aU8ZHapaBEe0ZpxBzS4HpTlUuRgnpUsB/tTX4GalYAVE5IBI6gcVKGV9PwPENiXIwkik/TNei654rghVo7L5mBIzXmjZ/tBccfLWhGPkGetUKxZ1C9uL6UyTyM2eg9K9A+H6Y0JMdDI2PzrznAr1DwDDjwzC24g/OcgZPX0qkTUWh1RB/sN+2ZUH61ZuFO0HHPTimzxqNLjjQs6NOg3EYzWg9q4UMVb8q0Whgkc9pknneLbGLHW7jH/jwr64j+4BXzB4E8PXuq+N7aW0t2aK2uVklc/dUA55NfUCHK9Mc1hLc64bC0jjKEUtI/wB01DKPzI+KKkfEPxCAP+YhN/6EazvC979nvRG2Mqdyj1roPizA0XxL8RRSKVZb+Q4Pua4u4R0YOmVYHIb0NCdhNXPrP9nnW9Lt9UuYBmO7uhuh3N8kgHVcf3q90/tBcZlt1J78Yr4K8E+KFWaOCe4NvOrAo6ttYMOjKexHp3r6V8DfFENBHB4jjIfgC8hXKv7uOxrdSTItZnsBu7NvvwYrlPil4i0nw74G1bWJW2PDbOsSkfekIwo/M1W1vx74P0uNWv8AXbSEOuRljj/61fKn7QfxUPje/GlaM8seiWz5y3WduzfShtIpank0H+kXBLvtaZsknnk+tdRpln9maUFkYA7QVOQcdx7VjaRpzzzA7cRjkkjrXURRhQFA+UDAGKzbB7ibMnFSKBjpT9q+lOUccCpAYFOOKTHvUu3NMK80AMwo70cd6k2r6UpC+lMCF8Y4qjdsFjJPatCUDbwKytSDGNttC3Bns/7MsYfxwI8jnSgwz6ljmvRvi9eX1vrUVra3LxxmLLbTjvXiHwE14aV8RdEnncJFIDaS5OB83SvdPjVbNF4gt5GYbXh4x35ropJN6kSdkcVbJJJ/rJZH+rE1rWdsmSdvas+14wc8VsWRBwQeK6OUyuyQW4K4rxn9ojRUgnsNajTbvzDKfU44r3FRXnf7Q0SHwDvf7yXKFfrUzWg1ueDaJcFJzGGI3r0rqFy0aN6iua8MX8tjqCyJFDIByVkQMDwRj6V1CjEaZwDtzjGK5WzVCBSSAoJJ4AFaumaRqFxJ/wAe7rH1LuMAcUnhZJ2160+zPAJt+U877mfevRfibqUVt4eMM1zbPem0CfuuV3HrgfSpYzi18LapPKVgKSN36qP1rnLhXjZ42GGVipHpitLw34i1DT9Ins0kd3kZWRncnYR6Vm3LPIzyucsxJb60kBRXP9oc/wBwVpRqCgz1rMUZv29QBWunK5pgJjH0r1PwZmHw9a8kfKf515cPavavht4Y1DXNHsLWyhZ9yZYjoAe5NNMmfY3rLRtU8SWthpWkMsV1cymQzP0iRRkt7nmvZtI+H2k2ulwWt7Lc31wo/eXLuVZz6gDtVvwJ4Ms/DkET5868VCjSnoAeoA9K62pk9dCox0M7QdH0/RbIWmn26wxdTgcsT3J71o0UVJaVgBpretKtKelAHwR+0F4T8Sx/FTX9QbQb37HPc74ZkgJRxgcgivKby2lTKSxvGw6h1II/Ov1IeBJF2yhXX0IyKx9T8IeGdSBF9oWmzg/37Zc/niptYD8vZ7c5wqgg+naprTUdZsl8u2v7mFDwQkh/rX6Ga18B/hhqoYzeGoIGP8Vuxj/lXE61+yl4EuAzadqOq2DdsOHUfmKFoFj4nuZr2/cNeXU8xPHzuT+NSWdlCCPkz+NfUGr/ALJWoJuOkeLLaUdlubZgfzBrldS/Zu+JGngtBa2F+oH/ACxnAJ/Aiq3DY8nso1RcAY/CrSqM11WpfDHx7pAP23wrqQA6tHHvX8wawLrTb+0YrdWN1bsOokhZf6U3YkrbRSqAB0NICRxjn3NSIeOSPrSAQH2NG0c09Du68UEjJ4FAEYQA5yTSMM9sVLhe3WlVMnFNAVWQYPes+9jO08VtmPORiqV3BkHPah6DM7T3ZCskbMskTBlI6givcm8QTfELRtKmGpS2mpafbmC5RVDbznhua8FnZrS4EiBmX+IVu6Bqk9ncpfabMI5lPT19Qw71pCSIlE9bi0XxLA37rUrSZT0EkZUmoZNZ1vR5vK1LTQUzxJGSVP41peDvHWi6rGlvqLixvcAEP9xj6g9q7lLKyvLc4lhuIm/2gwrdTuQ4o4jT/F1lKvzxMh+tef8A7QXiW1vdLsNLtWLEyGaQemBx/OvQ/iDZ+EvC+my6jfzCKXH7qFDlnbsAtfN2rNearrMlzdxyKWPyo3BC9hUVKvRBCDTuxvhyzaaVTs+9+grqWX5uemMVHo1iLa3yT87DnHYelWZFA681kaFdV2sCvbuDipb25mugRPIX4AJI646Uu32psq4OKTEVkGzgdKc5wpz6Zp5GDUcjHBJxzxSWhRa8LQWd74gRbhS8flvke4XNIp4wOAP0FVNGjmje4mt9yOrBVI5JzxgCvoT4G/Au61jyNd8WQyW1gCGhtCcPN7n0FO4WOQ+EHwq1jxxeJOyvaaUrDzbhhjcB2XPWvsbwn4a0vwzpEGm6XAI4olC5PJb61oadYWmn2cVpZQRwQRLtRI1wqge1Wqm47AKKKKQwooooAQClpBS0AFFFFABRRRRYAxSbRjFLRQAhGRjkVWudPsboEXNpBMD1Dxg1aooA5HVvhp4E1QH7Z4Y05ierLEFP5iuR1b9nn4c3pJgsrqxJ/wCeE5wPwOa9cooA+dtV/Zg0ly39l+Jr+E/wrcQq4/MYrktW/Zo8XwAtp+raXej0YtGf1zX1tijAoA+HNU+CnxI00sW8OyXSrzutpFcVy+oeFfE2nZF/oGp2xH9+3bH5iv0KKgjBFNeKOQYdFYehGaAPzjkSWH5ZI2Vu+VIx+GKryKWB781+iGo+GdA1AYvNHsZs9d0Cn+lcpq/wb+Heo587w9BGx53Qkof0oA+B7uDdng4x3rJMMlu++IsjA9q+3dY/Zp8EXufsV7qdg3YrIHA/A1xOt/spXRLNpXiuJ8dFubcj+VID5fXU7pFAdUk92FWrfxDrcHy2lw8HHGxiMfrXsGr/ALNPxDtSWtYdO1BR08m4Ck/ga5HVfhL8QdKLfbPCeo4HVokEij8Vp3l3FZHB3C32pXAn1C7luJOgZ2yRWtZwFmEkjGSXgF2OScdKtNomqWTYutNu4COvmxMuPzFTW6oOW4Pp6U4oLkyREDPNOMGRjFSRthTzmlDj0qhEBhxVa7XDYFXHccHHGaq6k6eYFTJPFJsdrlckZ29z0966b4d/D/xD471hbLSINkAP7+7cfuoh357n2rsfgv8ABPVvGdwmqav5un6MpyWIw8/sB2HvX1/4X8PaT4c0mLTNIs47W2jGAEHJ9ye5qLjscB8PfgX4I8LG3uzZvfahEAWmnbcC/wDeC9BXqaIqKFXgDoKcABRTAKKKKACiiigAooooARaWkWloAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACjFFFABRRRQAm0YxgUoAAwKKKAK11YWVypW4s4JlPUPGD/ADrntU+HvgvUv+Prw1prn1EIU/pXVUUAeWan8B/h7e7vLsJ7Nj3hlIA/CuS1X9mjR33NpniK+tz2EyBwK+gKKAPlbVP2bPFEX/IP1zTLpPSVGQmul+GP7O8GlX66n4vuYNQlQ7o7WMHylPbJ7ivoSkzQBFawRW8SRRRqiKuFVRgAewqagGigAoooJoAKKTNGaAFopM0ZoAWijNIDmgD/2Q==", "bluescience": "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"}''')

# Plain, unbranded pictures shown until a manufacturer is chosen (and for brands we have no photo of)
GENERIC_IMAGES = json.loads(r'''{"wall": "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mjQNTc+1WH/Pxa/99r/jR9qsP+fi1/77X/GsP+xrH/nzh/75o/sax/584f8AvmjQNTc+1WH/AD8Wv/fa/wCNH2qw/wCfi1/77X/GsP8Asax/584f++aP7Gsf+fOH/vmjQNTc+1WH/Pxa/wDfa/40farD/n4tf++1/wAaw/7Gsf8Anzh/75o/sax/584f++aNA1Nz7VYf8/Fr/wB9r/jR9qsP+fm1/wC+1/xrD/sax/584f8Avmj+xrH/AJ84f++aNA1Ns3dgoJa6tQB38xf8ao3PiKxjJjs917N2SHlR9W6CqQ0ayzn7HD/3zVqOzVBtRAo9AMUtAKlvDcXF6b6+YPcEYUL92JfRf8a27dMYqKKDHar0UeKTY0WIxgVOOlRoOKkqRhRRRQMKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKAEIzUTJmpqTFAio0Oe1Rm3HpV4rSbKLgUfs3tR9m9qvbKNlO4FH7N7UfZvar2yjZRcCj9m9qPs3tV7ZRsouBR+ze1H2b2q9so2UXAo/Zvaj7N7Ve2UbKLgUfs3tR9m9qvbKNlFwKP2b2o+ze1XtlGyi4FH7N7UfZvar2yjZRcCj9m9qPs3tV7ZRsouBR+ze1H2b2q9so2UXAo/Zvaj7N7Ve2UbKLgUfs3tR9m9qvbKNlFwKP2b2o+ze1XtlGyi4FH7N7UfZvar2yjZRcCj9m9qUW49Ku7KNlFwK6wgdqmVMU/bTsUgEAxS0UUDCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAoopGOKAIbq8trK2a4u544Yl6u5wKxz4y8O9tQz9In/wAKzb4DU/GdxHdAPDYIgiiYZXewyWI7ntV7A/uj8qtRXUm4/wD4TLw9/wA/5/79P/hR/wAJl4e/5/z/AN+n/wAKbgeg/KjA9B+VFkLU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", "ceiling": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAQDAwMDAgQDAwMEBAQFBgoGBgUFBgwICQcKDgwPDg4MDQ0PERYTDxAVEQ0NExoTFRcYGRkZDxIbHRsYHRYYGRj/2wBDAQQEBAYFBgsGBgsYEA0QGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBj/wAARCAEsAeADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD7+ooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiig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", "ducted": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAQDAwMDAgQDAwMEBAQFBgoGBgUFBgwICQcKDgwPDg4MDQ0PERYTDxAVEQ0NExoTFRcYGRkZDxIbHRsYHRYYGRj/2wBDAQQEBAYFBgsGBgsYEA0QGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBj/wAARCAEsAeADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD7+ooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACkzTWbFQtLigRPupN/vVQzj1pv2getOwF3fRv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"}''')

BRANDS = ["Midea", "Mitsubishi", "Panasonic", "Samsung"]
BRAND_STYLE = {"Midea": "#00A0E9", "Mitsubishi": "#E60012", "Panasonic": "#0041C0", "Samsung": "#1428A0", "Lossnay": "#E60012"}

_IMG_DIR = Path(__file__).parent / "product_images"

@st.cache_data(show_spinner=False)
def _read_b64(path, mtime):
    import base64
    return base64.b64encode(Path(path).read_bytes()).decode()

def _file_image(stem):
    """A picture dropped into the product_images folder, e.g. samsung_wall.jpg or logo_samsung.png.
    File-name capitals and jpg/jpeg/png/webp don't matter, and the real format is detected from the file itself. Returns base64 or ''."""
    try:
        want = stem.lower()
        for f in sorted(_IMG_DIR.iterdir()):
            if f.is_file() and f.stem.lower() == want and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                return _read_b64(str(f), f.stat().st_mtime)
    except Exception:
        pass
    return ""

def logo_for(brand):
    return _file_image("logo_" + brand.lower())

def image_for(item):
    """Picture for an equipment line: a photo from the product_images folder if there is one, else the built-in Midea photo, else the plain generic picture."""
    n = item["name"].lower()
    brand = n.split(" ")[0]
    if item["kind"] == "lossnay":
        return _file_image("air_exchange") or _file_image("lossnay") or PRODUCT_IMAGES.get("lossnay")
    if item["kind"] in ("wall", "ceiling", "ducted"):
        own = _file_image(f"{brand}_{item['kind']}")
        if own:
            return own
        return PRODUCT_IMAGES.get(item["kind"]) if brand == "midea" else GENERIC_IMAGES.get(item["kind"])
    return None

def default_config():
    return {
        "company": {
            "trading": "SteadyTemp Air Conditioning",
            "legal": "SY Comms Ltd",
            "legal_line": "SteadyTemp Air Conditioning is a trading name of SY Comms Ltd",
            "addr": ["Suite C Jupiter House", "Sitka Drive", "Shrewsbury Business Park", "Shropshire", "SY2 6LG"],
            "reg": "Registered in England 15722588",
            "vat": "VAT Registration No. Pending",
            "email": "andy@steadytemp.co.uk",
            "phone": "01743 832049",
            "web": "www.steadytemp.co.uk",
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
            "install_day_rate": 500.0, "travel_hours": 2.0,
        },
        "terms": None,            # filled from TERMS_DEFAULT
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

# Contact details printed on paperwork are fixed, whoever is logged in or sells (overrides any saved config)
FIXED_CONTACT = {"email": "andy@steadytemp.co.uk", "phone": "01743 832049", "web": "www.steadytemp.co.uk"}

# ───────────────────────────── config load ─────────────────────────────
CONFIG_FILE = "config.json"

def load_config():
    cfg = default_config()
    ver = 4                                   # nothing saved yet = already the newest catalogue
    try:
        if Path(CONFIG_FILE).exists():
            saved = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
            ver = int(saved.get("catalogue_version", 1)) if "catalogue" in saved else 4
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
    except Exception:
        pass
    _sys = {"wall", "ceiling", "ducted", "lossnay"}
    _fresh = default_config()["catalogue"]
    if ver < 2:        # v2: manufacturer + kW sizes replace the old model-number system lines (extras/materials/labour edits are kept)
        _saved_other = [i for i in cfg.get("catalogue", []) if i.get("kind") not in _sys and "blue science" not in i.get("name", "").lower()]
        _other = _saved_other or [i for i in _fresh if i["kind"] not in _sys]
        cfg["catalogue"] = [i for i in _fresh if i["kind"] in _sys] + _other
    elif ver < 3:      # v3: more ducted makes - add any system lines that are missing, leave edited prices alone
        _have = {i["name"] for i in cfg["catalogue"]}
        cfg["catalogue"] = cfg["catalogue"] + [i for i in _fresh if i["kind"] in _sys and i["name"] not in _have]
    if ver < 4:        # v4: the "price to be confirmed" warnings have been checked - clear them once (admin can still tick them again)
        for _i in cfg["catalogue"]:
            _i["tbc"] = False
    cfg["catalogue_version"] = 4
    if not cfg.get("terms"):
        cfg["terms"] = [list(t) for t in TERMS_DEFAULT]
    return cfg

if "cfg" not in st.session_state:
    st.session_state.cfg = load_config()
CFG = st.session_state.cfg
CO = CFG["company"]
CO.update(FIXED_CONTACT)
COST = CFG["costs"]

# ───────────────────────────── sign-in ─────────────────────────────
for _k, _v in (("authed", False), ("current_user", None)):
    st.session_state.setdefault(_k, _v)

def _login_screen():
    _l, _m, _r = st.columns([1, 1.2, 1])
    with _m:
        st.markdown(f"<div style='text-align:center;margin:2.5rem 0 1rem'><div style='font-size:2.4rem'>❄️</div>"
                    f"<div style='font-size:1.7rem;font-weight:800;color:#FF8A2A'>{esc(CO['trading'])}</div>"
                    f"<div style='color:#7FC8EE'>Quotes &amp; paperwork</div></div>", unsafe_allow_html=True)
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

# ───────────────────────────── journey from the office (for extra install days) ─────────────────────────────
def _norm_pc(pc):
    return re.sub(r"\s+", "", (pc or "").upper())

def office_postcode():
    for line in reversed(CO.get("addr") or []):
        m = re.search(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", line.upper())
        if m:
            return m.group(0)
    return "SY2 6LG"

def _get_json(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "SteadyTemp-quotes/1.0"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)
def _journey(office_pc, site_pc):
    """Driving time and distance between two UK postcodes (free postcode + routing services). Raises if it can't be worked out, so failures are never cached."""
    import math
    pts = []
    for pc in (office_pc, site_pc):
        d = _get_json("https://api.postcodes.io/postcodes/" + _norm_pc(pc))
        pts.append((float(d["result"]["latitude"]), float(d["result"]["longitude"])))
    (la1, lo1), (la2, lo2) = pts
    try:
        r = _get_json(f"https://router.project-osrm.org/route/v1/driving/{lo1},{la1};{lo2},{la2}?overview=false")
        rt = r["routes"][0]
        return {"hours": rt["duration"] / 3600.0, "miles": rt["distance"] / 1609.34, "how": "driving route"}
    except Exception:
        p = math.pi / 180
        a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
        miles = 3958.8 * 2 * math.asin(math.sqrt(a)) * 1.3          # straight line x1.3 for roads
        return {"hours": miles / 40.0, "miles": miles, "how": "estimate from distance"}

def journey_for(site_pc):
    """None if there is no usable postcode or the lookup failed (not retried for a minute)."""
    if not re.search(r"\d[A-Za-z]{2}\s*$", (site_pc or "").strip()):
        return None
    import time as _t
    key = "_jfail_" + _norm_pc(site_pc)
    if _t.time() < st.session_state.get(key, 0):
        return None
    try:
        return _journey(office_postcode(), site_pc.strip())
    except Exception:
        st.session_state[key] = _t.time() + 60
        return None

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
    n_units = sum(counts.values())
    mode = st.session_state.get("q_days_mode", "Automatic (from the customer's address)")
    journey = journey_for(st.session_state.get("q_postcode", "")) if (mode.startswith("Automatic") and n_units > 0) else None
    far = bool(journey and journey["hours"] > float(C["travel_hours"]))
    if mode.startswith("Add"):
        extra_days = int(_num("q_days_manual"))
    elif mode.startswith("Automatic") and far:
        extra_days = n_units                                  # a day per unit, the first covering the travel
    else:
        extra_days = 0
    extra_days_cost = extra_days * C["install_day_rate"]
    set_up = maint_annual + extras + install + extra_days_cost + equip_cost + other + additional       # "Set Up Costs & Equipment"
    subtotal = set_up + equip_srrp                                                    # "Sub Total for lease calcs"
    term = int(st.session_state.get("q_term", 84))
    rr = rate_row(term)
    rate, true_rate = float(rr["rate"]), float(rr["true_rate"])
    calc_rental = subtotal * rate / 1000.0
    desired = _num("q_desired_rental")
    cp_rental, cp_cash, cp_support = _num("q_cp_rental"), _num("q_cp_cash"), _num("q_cp_support")   # admin "customer pays" prices
    rental = round(cp_rental if cp_rental > 0 else (desired if desired > 0 else calc_rental), 2)
    funded = rental / true_rate * 1000.0 if true_rate > 0 else 0.0
    gp = funded - set_up
    units = gp / C["unit_size"] if C["unit_size"] else 0.0
    commission = units * C["unit_value"]
    # cash sale
    cash_list = subtotal * C["cash_load"]
    vol_disc = _num("q_vol_discount")
    cash_price = round(cp_cash if cp_cash > 0 else cash_list - vol_disc, 2)
    cash_gp = cash_price - set_up
    cash_units = cash_gp / C["unit_size"] if C["unit_size"] else 0.0
    cash_comm = cash_units * C["unit_value"]
    is_cash = st.session_state.get("q_pay_model") == "Cash sale"
    return dict(
        qty=qty, counts=counts, n_units=sum(counts.values()), n_all=sum(q for _, q in qty),
        equip_cost=equip_cost, equip_srrp=equip_srrp, maint_annual=maint_annual, extras=extras, install=install,
        extra_days=extra_days, extra_days_cost=extra_days_cost, journey=journey, far=far, days_mode=mode,
        support=(cp_support if cp_support > 0 else maint_annual), cp_rental_on=cp_rental > 0, cp_cash_on=cp_cash > 0,
        cp_support_on=cp_support > 0, cash_calc=round(cash_list - vol_disc, 2),
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
        if k.startswith(_QUOTE_PREFIXES) and isinstance(v, (str, int, float, bool)) and not k.startswith(("q_sig", "q_bank")):    # bank details are never saved to the quote file:
            out[k] = v
    return out

def _load_quote_cb():
    f = st.session_state.get("up_quote")
    if not f:
        return
    try:
        data = json.loads(f.getvalue().decode("utf-8"))
        for k in [k for k in st.session_state.keys() if k.startswith(("w_", "sel_", "mfr_"))]:
            del st.session_state[k]                       # card widgets pick up the loaded quantities
        for k, v in data.items():
            if k.startswith(_QUOTE_PREFIXES):
                st.session_state[k] = v
        st.session_state["_quote_loaded"] = f.name
    except Exception:
        st.session_state["_quote_loaded"] = "ERR"

# ───────────────────────────── paperwork (PDF) ─────────────────────────────
NAVY, ACCENT, PALE = (16, 41, 74), (255, 138, 42), (232, 243, 251)

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
    pdf.cell(120, 5.2, s(f"  On-site support after year {fy} (annual charge, plus VAT)"), ln=False); pdf.cell(0, 5.2, money(C["support"]), ln=True, align="R")
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
    kv(pdf, "Annual charge after:", f"{money(C['support'])} plus VAT per year, for the remainder of the term", 42)
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
    pdf.ln(2)
    band(pdf, "Direct Debit mandate - your bank details")
    sc = re.sub(r"\D", "", Q("q_bank_sort"))
    sc = f"{sc[0:2]}-{sc[2:4]}-{sc[4:6]}" if len(sc) == 6 else Q("q_bank_sort")
    blank = "______________________"
    kv(pdf, "Bank / building society:", Q("q_bank_name") or blank, 52)
    kv(pdf, "Account holder name:", Q("q_bank_holder") or Q("q_company") or blank, 52)
    kv(pdf, "Account number:", Q("q_bank_acc") or blank, 52)
    kv(pdf, "Sort code:", sc or blank, 52)
    kv(pdf, "Billing email:", Q("q_bill_email") or Q("q_email") or blank, 52)
    pdf.ln(1)
    para(pdf, f"I/we authorise {CO['legal']} (trading as {CO['trading']}) to collect by Direct Debit, through GoCardless, the "
              + ("annual on-site support charge and any other amounts invoiced to us under this agreement. " if C["is_cash"] else
                 "annual on-site support charge and any other amounts invoiced to us under this agreement (the equipment rental itself is collected by the finance provider). ")
              + "Payments are collected on or around the due date shown on our invoice, and we will tell you in advance of any change to the amount or date. "
              "This mandate is subject to the Direct Debit Guarantee below.", size=8.3, h=4.2)
    sig_block(pdf, "Authorised signature (the account holder)", sign)
    pdf.ln(2)
    para(pdf, "THE DIRECT DEBIT GUARANTEE - The Guarantee is offered by all banks and building societies that accept instructions to pay Direct Debits. "
              "If there are any changes to the amount, date or frequency of your Direct Debit, the organisation will notify you (normally 10 working days) in advance "
              "of your account being debited or as otherwise agreed. If an error is made in the payment of your Direct Debit, you are entitled to a full and immediate "
              "refund of the amount paid from your bank or building society. You can cancel a Direct Debit at any time by simply contacting your bank or building society. "
              "Written confirmation may be required; please also notify us.", size=7, h=3.6, style="I")

def doc_terms(pdf, C, sign):
    doc_header(pdf, "Terms & Conditions")
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


from PIL import Image as _PIm

def _png_bytes(b64):
    """Any picture (jpg / png / webp, with or without transparency) -> plain PNG on white, safe for the PDF."""
    import base64
    im = _PIm.open(io.BytesIO(base64.b64decode(b64)))
    im = im.convert("RGBA"); bg = _PIm.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    out = io.BytesIO(); bg.convert("RGB").save(out, format="PNG"); return out.getvalue()

def quote_ref():
    import zlib
    base = (Q("q_company") or "quote").upper()
    return f"ST-{date.today():%y%m%d}-{zlib.crc32(base.encode()) % 10000:04d}"

def build_quote_pdf():
    """A clear, customer-facing quotation (not a contract): equipment, price, term and what happens next. No costs or margins."""
    import base64
    from datetime import timedelta
    C = calc()
    pdf = DocPDF()
    pdf.set_margins(15, 15, 15); pdf.set_auto_page_break(True, 16); pdf.alias_nb_pages()
    doc_header(pdf, "Quotation", "Air conditioning supplied, installed and supported")
    valid_days = int(COST.get("quote_valid_days", 30))
    kv(pdf, "Quotation ref:", quote_ref())
    kv(pdf, "Date:", date.today().strftime("%d/%m/%Y"))
    kv(pdf, "Valid until:", (date.today() + timedelta(days=valid_days)).strftime("%d/%m/%Y"))
    kv(pdf, "Prepared for:", Q("q_company"))
    addr = ", ".join(cust_address_lines())
    if addr:
        kv(pdf, "Address:", addr)
    contact = Q("q_contact") or split_name_pos(Q("q_signatory"))[0]
    if contact:
        kv(pdf, "Attention:", contact)
    if Q("q_rep"):
        kv(pdf, "Your contact:", " | ".join(x for x in (Q("q_rep"), CO.get("email"), CO.get("phone"), CO.get("web")) if x))
    pdf.ln(1)
    para(pdf, "Thank you for the opportunity to quote. Below is the system we recommend, what it will cost, and what is included. "
              "Everything is supplied, installed and supported by one team.", size=9, h=4.8)

    band(pdf, "Your proposed system")
    shown = 0
    for it, q in C["qty"]:
        if it["group"] in ("Materials", "Labour"):
            continue
        if pdf.get_y() > 250:
            pdf.add_page(); pdf.set_y(20)
        y = pdf.get_y()
        img = image_for(it)
        if img:
            try:
                _raw = _png_bytes(img); _w, _h = _PIm.open(io.BytesIO(_raw)).size
                _bw, _bh = 30.0, 14.0
                _sc = min(_bw / _w, _bh / _h)
                pdf.image(io.BytesIO(_raw), x=pdf.l_margin + 1 + (_bw - _w * _sc) / 2, y=y + 1 + (_bh - _h * _sc) / 2, w=_w * _sc, h=_h * _sc)
            except Exception:
                pass
        _lg = logo_for(it["name"].split(" ")[0]) if it["kind"] in ("wall", "ceiling", "ducted") else ""
        if _lg:
            try:
                _lraw = _png_bytes(_lg); _lw, _lh = _PIm.open(io.BytesIO(_lraw)).size
                _lsc = min(26.0 / _lw, 8.0 / _lh)
                pdf.image(io.BytesIO(_lraw), x=pdf.l_margin + 118, y=y + 4.5, w=_lw * _lsc, h=_lh * _lsc)
            except Exception:
                pass
        pdf.set_xy(pdf.l_margin + 34, y + 2)
        pdf.set_font("Helvetica", "B", 9); pdf.cell(105, 5, s(it["name"])[:62], ln=True)
        pdf.set_x(pdf.l_margin + 34); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(100, 110, 120)
        pdf.cell(105, 4.5, s(it.get("desc") or it["group"])[:70], ln=False); pdf.set_text_color(0, 0, 0)
        pdf.set_xy(pdf.l_margin + 150, y + 4); pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"x {q}", align="R")
        pdf.set_y(y + 17); pdf.set_draw_color(215, 225, 235); pdf.line(pdf.l_margin, pdf.get_y(), 195, pdf.get_y()); pdf.set_draw_color(0, 0, 0)
        shown += 1
    if not shown:
        para(pdf, "(equipment to be confirmed)", style="I")
    names = " ".join(it["name"] for it, _ in C["qty"])
    if "Blue Science" in names:
        pdf.ln(1)
        para(pdf, "Blue Science: UV-C air sanitising built into the unit - helps remove airborne viruses, bacteria, moulds and odours.", size=8, style="I")

    band(pdf, "Your price")
    fy = int(COST["free_support_years"])
    if pdf.get_y() > 215:
        pdf.add_page(); pdf.set_y(20)
    y = pdf.get_y()
    pdf.set_fill_color(*PALE); bh = 30 if C["is_cash"] else 23
    pdf.rect(pdf.l_margin, y, pdf.epw, bh, "F")
    pdf.set_fill_color(*ACCENT); pdf.rect(pdf.l_margin, y, 2.2, bh, "F")
    pdf.set_xy(pdf.l_margin + 8, y + 3); pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*NAVY)
    if C["is_cash"]:
        pdf.cell(0, 5, "ONE-OFF PRICE", ln=True)
        pdf.set_x(pdf.l_margin + 8); pdf.set_font("Helvetica", "B", 24); pdf.cell(0, 12, money(C["cash_price"]), ln=True)
        pdf.set_x(pdf.l_margin + 8); pdf.set_font("Helvetica", "", 9); pdf.set_text_color(70, 80, 90)
        pdf.cell(0, 5, "plus VAT - supplied, installed and commissioned", ln=True)
    else:
        pdf.cell(0, 5, "MONTHLY RENTAL", ln=True)
        pdf.set_x(pdf.l_margin + 8); pdf.set_font("Helvetica", "B", 24); pdf.cell(0, 12, money(C["rental"]) + " per month", ln=True)
    pdf.set_text_color(0, 0, 0); pdf.set_y(y + bh + 3)
    inc = [f"Supply and installation by qualified F-Gas engineers, including all materials",
           *([f"Estimated {C['extra_days']} day{'s' if C['extra_days'] != 1 else ''} install"] if C["extra_days"] > 0 else []),
           f"{fy} year{'s' if fy != 1 else ''} on-site support and warranty included",
           f"Then on-site support at {money(C['support'])} per year plus VAT for the rest of the agreement"]
    if _num("q_cashback") > 0:
        inc.append(f"Cashback of {money(_num('q_cashback'))} towards your requirements")
    if not C["is_cash"]:
        inc.append(f"plus VAT - over {C['term']} months, subject to finance approval")
    pdf.set_font("Helvetica", "B", 9); pdf.cell(0, 5, "Included", ln=True)
    for t in inc:
        pdf.set_font("Helvetica", "", 8.5); pdf.set_x(pdf.l_margin + 3); pdf.cell(0, 5, s("-  " + t), ln=True)
    ex, ex_total = existing_costs()
    if ex_total > 0 and not C["is_cash"]:
        diff = ex_total - C["rental"]
        pdf.ln(2); pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, s(f"Compared with your current monthly air conditioning costs of {money(ex_total)}: "
                         + (f"an estimated saving of {money(diff)} a month." if diff >= 0 else f"{money(-diff)} a month more, for new equipment and cover.")), ln=True)

    band(pdf, "What happens next")
    steps = ["We confirm the details with you and arrange a site visit if needed.",
             "You accept the quotation" + ("" if C["is_cash"] else "; we help with the finance application") + ".",
             "We install and commission the system at a time to suit you.",
             "Your on-site support starts from installation."]
    for n, t in enumerate(steps, 1):
        pdf.set_font("Helvetica", "B", 9); pdf.set_x(pdf.l_margin + 2); pdf.cell(7, 5.5, f"{n}.")
        pdf.set_font("Helvetica", "", 9); pdf.cell(0, 5.5, s(t), ln=True)
    pdf.ln(2)
    para(pdf, f"All prices exclude VAT. This quotation is valid for {valid_days} days and is subject to site survey, "
              + ("" if C["is_cash"] else "finance approval, ") + "and our terms and "
              "conditions, which we will send with your order documents.", size=7.5, style="I")
    return bytes(pdf.output())

# ───────────────────────────── look & feel ─────────────────────────────
st.markdown("""
<style>
.block-container{padding-top:3.4rem;max-width:1250px}
.st-hero{background:linear-gradient(120deg,#10294A 0%,#0F5C8C 100%);color:#fff;border-radius:16px;padding:1.1rem 1.4rem;margin-bottom:1rem;border-bottom:3px solid #FF8A2A}
.st-hero .t{font-size:1.5rem;font-weight:800;letter-spacing:.3px}.st-hero .s{color:#BFE6FA;font-size:.9rem}
.st-card{border:1px solid #223652;border-left:4px solid #FF8A2A;border-radius:14px;padding:1rem 1.2rem;background:#121D30}
.st-card .l{font-size:.72rem;font-weight:700;text-transform:uppercase;color:#7FC8EE;letter-spacing:.4px}
.st-card .v{font-size:1.9rem;font-weight:800;color:#FFFFFF}.st-card .x{font-size:.82rem;color:#8FA9BF}
.st-warn{border-left:4px solid #FF8A2A;background:rgba(255,138,42,.12);border-radius:8px;padding:.6rem .9rem;margin:.4rem 0;color:#FFD9B3}
.st-bad{border-left:4px solid #F25C5C;background:rgba(242,92,92,.14);border-radius:8px;padding:.6rem .9rem;margin:.4rem 0;color:#FFC9C9}
h4,h5{color:#7FC8EE !important}
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
    _none = CALC["n_all"] == 0
    if CALC["is_cash"]:
        st.metric("Cash price (ex VAT)", "-" if _none else money(CALC["cash_price"]))
    else:
        st.metric(f"Monthly rental · {CALC['term_label']}", "-" if _none else money(CALC["rental"]))
        st.caption("plus VAT · billed by the funder")
    st.metric("Annual support (after year 1)", "-" if _none else money(CALC["support"]))
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
    st.markdown("##### Direct Debit - customer's bank details")
    st.caption("Printed on the Direct Debit mandate in the paperwork pack. Leave blank to have the customer write them in. Not saved in the quote file.")
    b1, b2, b3, b4 = st.columns(4)
    b1.text_input("Bank / building society", key="q_bank_name")
    b2.text_input("Account holder name", key="q_bank_holder", placeholder="Defaults to the company name")
    b3.text_input("Account number", key="q_bank_acc", max_chars=8, placeholder="8 digits")
    b4.text_input("Sort code", key="q_bank_sort", max_chars=8, placeholder="00-00-00")
    _acc = re.sub(r"\D", "", Q("q_bank_acc")); _sort = re.sub(r"\D", "", Q("q_bank_sort"))
    if (Q("q_bank_acc") and len(_acc) != 8) or (Q("q_bank_sort") and len(_sort) != 6):
        st.warning("Check the bank details: an account number is 8 digits and a sort code is 6 digits.")
    st.text_input("Prepared by", key="q_rep", help="Shown on the paperwork. Filled from your login.")

# ───────────────────────────── equipment ─────────────────────────────
def _qty_cb(name):
    st.session_state["eq_" + name] = int(st.session_state.get("w_" + name, 0) or 0)

def _img_html(img):
    if not img:
        return ("<div style='height:150px;display:flex;align-items:center;justify-content:center;background:#16233A;border:1px dashed #2C4466;"
                "border-radius:10px;margin-bottom:.5rem;color:#6F8CA8;font-size:.8rem'>Photo to follow</div>")
    return (f"<div style='height:150px;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:10px;margin-bottom:.5rem'>"
            f"<img src='data:image/{'png' if img.startswith('iVBOR') else 'webp' if img.startswith('UklG') else 'jpeg'};base64,{img}' style='max-height:140px;max-width:92%;object-fit:contain'></div>")

def _variant_label(it, brand):
    n = it["name"]
    for pre in (brand + " " + it["group"] + " ", brand + " "):
        if n.startswith(pre):
            n = n[len(pre):]; break
    for suf in (" " + it["group"],):
        if n.endswith(suf):
            n = n[:-len(suf)]
    return n

SYSTEM_GROUPS = ["Wall Mounted", "Ceiling Cassette", "Ducted", "Lossnay Air Exchange"]

def system_cards():
    """One card per type (wall / cassette / ducted / Lossnay): choose the manufacturer, then the size in kW."""
    cards = {}
    for it in CFG["catalogue"]:
        if it["group"] in SYSTEM_GROUPS:
            brand = it["name"].split(" ")[0]
            cards.setdefault(it["group"], {}).setdefault(brand, []).append(it)
    return [(g, cards[g]) for g in SYSTEM_GROUPS if g in cards]

def _brand_badge(brand):
    _lg = logo_for(brand)
    if _lg:
        _t = 'png' if _lg.startswith('iVBOR') else 'webp' if _lg.startswith('UklG') else 'jpeg'
        return (f"<div style='display:inline-block;background:#fff;border-radius:8px;padding:.25rem .7rem;margin:.1rem 0 .4rem'>"
                f"<img src='data:image/{_t};base64,{_lg}' style='height:28px;max-width:150px;object-fit:contain'></div>")
    col = BRAND_STYLE.get(brand, "#7FC8EE")
    return (f"<div style='display:inline-block;background:#fff;border-radius:8px;padding:.1rem .7rem;margin:.1rem 0 .4rem;"
            f"font-weight:800;letter-spacing:.04em;color:{col};border:2px solid {col}'>{esc(brand.upper())}</div>")

with t_eq:
    st.markdown("#### Equipment")
    st.caption("Choose the manufacturer on each card, then the size, then how many. Everything you choose is listed under the card. "
               "Only systems and extras appear on the customer paperwork - materials and labour are costed in the background.")
    cards = system_cards()
    for r0 in range(0, len(cards), 3):
        cols = st.columns(3)
        for col, (grp, by_brand) in zip(cols, cards[r0:r0 + 3]):
            with col.container(border=True):
                brands = [b for b in BRANDS if b in by_brand] + [b for b in by_brand if b not in BRANDS]
                single = len(brands) == 1 and grp == "Lossnay Air Exchange"      # Lossnay is one make - no manufacturer step
                mk = f"mfr_{grp}"
                if mk not in st.session_state:                # reopen on a make that is already in the quote (e.g. after loading one)
                    st.session_state[mk] = next((b for b in brands for i in by_brand[b] if int(_num(cat_key(i))) > 0), None)
                if single:
                    brand = brands[0]
                else:
                    brand = None
                # the picture and title come first, but they depend on the manufacturer picked below - so read the saved choice
                _cur = brands[0] if single else st.session_state.get(mk)
                _kind = by_brand[brands[0]][0]["kind"]
                st.markdown(_img_html(image_for(by_brand[_cur][0]) if _cur in by_brand else GENERIC_IMAGES.get(_kind)), unsafe_allow_html=True)
                st.markdown(f"**{grp}**")
                if not single:
                    brand = st.selectbox("Manufacturer", brands, index=None, placeholder="Choose manufacturer...", key=mk,
                                         label_visibility="collapsed")
                else:
                    brand = brands[0]
                if brand:
                    st.markdown(_brand_badge(brand), unsafe_allow_html=True)
                    items = by_brand[brand]
                    labels = {it["name"]: _variant_label(it, brand) + (" ⚠️" if it.get("tbc") else "") for it in items}
                    names = list(labels)
                    _sk = f"sel_{brand}_{grp}"
                    if _sk not in st.session_state:
                        st.session_state[_sk] = next((i["name"] for i in items if int(_num(cat_key(i))) > 0), names[0])
                    pick = st.selectbox("Size", names, format_func=lambda n, _l=labels: _l[n], key=_sk, label_visibility="collapsed")
                    it = next(i for i in items if i["name"] == pick)
                    st.caption(f"{it.get('desc') or grp}  ·  RRP {money(it['rrp'])}" + ("  ·  price to be confirmed" if it.get("tbc") else ""))
                    st.number_input("Qty", min_value=0, step=1, value=int(_num(cat_key(it))), key="w_" + it["name"],
                                    on_change=_qty_cb, args=(it["name"],), label_visibility="collapsed")
                else:
                    st.caption("Choose a manufacturer to pick the size.")
                # everything chosen on this card, whatever the make
                chosen = [(i, int(_num(cat_key(i))), b) for b in brands for i in by_brand[b] if int(_num(cat_key(i))) > 0]
                if chosen:
                    st.markdown("<div style='font-size:.8rem;color:#FFB26B;margin-top:.2rem'>Selected</div>", unsafe_allow_html=True)
                    for i, q, b in chosen:
                        lab = _variant_label(i, b)
                        st.markdown(f"<div style='font-size:.84rem'>{q} × {esc(b)} {esc(lab)}</div>" if not single else
                                    f"<div style='font-size:.84rem'>{q} × {esc(lab)}</div>", unsafe_allow_html=True)
    st.markdown("&nbsp;")
    by_group = {}
    for it in CFG["catalogue"]:
        if it["group"] not in SYSTEM_GROUPS:
            by_group.setdefault(it["group"], []).append(it)
    for g in [x for x in GROUP_ORDER if x in by_group] + [x for x in by_group if x not in GROUP_ORDER]:
        items = by_group[g]
        picked = sum(int(_num(cat_key(i))) for i in items)
        # fixed label: a label that changes would make Streamlit treat it as a new expander and snap it shut
        with st.expander(g, expanded=False):
            if picked:
                st.markdown(f"<div style='font-size:.85rem;color:#FFB26B'>✔ {picked} selected in {esc(g)}</div>", unsafe_allow_html=True)
            ncol = 3
            for r0 in range(0, len(items), ncol):
                cols = st.columns(ncol)
                for col, it in zip(cols, items[r0:r0 + ncol]):
                    with col.container(border=True):
                        img = image_for(it)
                        if img:
                            st.markdown(_img_html(img), unsafe_allow_html=True)
                        st.markdown(f"**{it['name']}**")
                        sub = it.get("desc") or ""
                        st.caption((sub + "  ·  " if sub and sub != it["group"] else "") + f"RRP {money(it['rrp'])}")
                        st.number_input("Qty", min_value=0, step=1, key=cat_key(it), label_visibility="collapsed")
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
        st.radio("Extra install days (engineer time)", ["Automatic (from the customer's address)", "No extra days", "Add days manually"], key="q_days_mode")
        if st.session_state.get("q_days_mode", "").startswith("Add"):
            st.number_input("Extra install days", min_value=0, step=1, key="q_days_manual",
                            help=f"Each day is charged at {money(COST['install_day_rate'])}.")
        elif st.session_state.get("q_days_mode", "").startswith("Automatic"):
            _j = CALC["journey"]
            if not Q("q_postcode"):
                st.caption("Enter the customer's postcode on the Customer tab and the journey from our Shrewsbury office is worked out automatically.")
            elif _j is None:
                st.warning("Couldn't work out the journey for that postcode (check it, or choose 'Add days manually').")
            else:
                _hm = f"{int(_j['hours'])}h {int(round((_j['hours'] % 1) * 60)):02d}m"
                if CALC["far"]:
                    st.info(f"🚐 {_hm} ({_j['miles']:.0f} miles) from our office - more than {COST['travel_hours']:g} hours, so "
                            f"{CALC['extra_days']} extra install day{'s' if CALC['extra_days'] != 1 else ''} added "
                            f"({money(CALC['extra_days_cost'])}). Estimated {CALC['extra_days']} day{'s' if CALC['extra_days'] != 1 else ''} install.")
                else:
                    st.caption(f"🚐 {_hm} ({_j['miles']:.0f} miles) from our office - within {COST['travel_hours']:g} hours, so no extra days.")
        st.text_area("Special conditions (printed on the order form)", key="q_special", height=100)
    with q2:
        st.markdown("**Customer's existing monthly costs** (optional - shown as a comparison on the proposal)")
        for lbl, key in (("Running costs", "q_cur_running"), ("Service costs", "q_cur_service"), ("Equipment leasing", "q_cur_leasing"),
                         ("Heating", "q_cur_heating"), ("Other", "q_cur_other")):
            st.number_input(lbl + " (£/month)", min_value=0.0, step=1.0, key=key)
    st.divider()
    st.markdown("##### Customer quote")
    st.caption("A clear one-page quotation (equipment, price and term) you can email before visiting. It is not a contract and shows no costs or margins.")
    qb1, qb2 = st.columns([1, 1])
    if qb1.button("📧 Customer quote", type="primary", key="btn_cust_quote"):
        try:
            st.session_state["_quote_pdf"] = build_quote_pdf()
        except Exception as e:
            st.session_state.pop("_quote_pdf", None)
            st.error(f"Couldn't build the quote: {e}")
    if st.session_state.get("_quote_pdf"):
        qb2.download_button("⬇️ Download the quote (PDF)", st.session_state["_quote_pdf"], "SteadyTemp_Quote_" + re.sub(r"[^A-Za-z0-9]+", "_", Q("q_company") or "customer").strip("_") + ".pdf",
                            mime="application/pdf", key="dl_cust_quote")
        import urllib.parse as _up
        _to = Q("q_email")
        _sub = f"Your air conditioning quotation - {CO['trading']}"
        _body = (f"Dear {split_name_pos(Q('q_signatory'))[0] or Q('q_contact') or 'customer'},\n\nThank you for the opportunity to quote. "
                 f"Please find our quotation attached for {Q('q_company') or 'your premises'}.\n\nKind regards,\n{Q('q_rep')}\n{CO['trading']}")
        st.link_button("✉️ Open an email (attach the PDF)", f"mailto:{_to}?subject={_up.quote(_sub)}&body={_up.quote(_body)}")
        st.caption("Your email app opens with the message ready - attach the downloaded PDF before sending.")
    st.divider()
    m1, m2, m3 = st.columns(3)
    _none = CALC["n_all"] == 0
    if CALC["is_cash"]:
        card("Cash price", "-" if _none else money(CALC["cash_price"]), "plus VAT", m1)
    else:
        card("Monthly rental", "-" if _none else money(CALC["rental"]), f"{CALC['term_label']} · plus VAT", m1)
    card("Annual support", "-" if _none else money(CALC["support"]), "after the included period", m2)
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
    _cp_on = C["cp_cash_on"] if C["is_cash"] else C["cp_rental_on"]
    card("Rental used", money(C["rental"]) if not C["is_cash"] else money(C["cash_price"]),
         "set by admin" if _cp_on else ("your target" if C["desired_on"] else "calculated"), b)
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
                ("Installation (labour + electrician)", C["install"]), ("Extra install days", C["extra_days_cost"]), ("Cashback + other costs", C["other"]),
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
        _cv = dict(fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#000000", background_color="#EAF4FB",
                   update_streamlit=True, height=170, width=500, drawing_mode="freedraw", key="sig_canvas")
        try:
            res = st_canvas(return_image_data=True, **_cv)      # newer versions of the drawing pad need this
        except TypeError:
            res = st_canvas(**_cv)                               # older versions don't have the option
        if st.button("✅ Save signature", key="btn_save_sig"):
            try:
                data = getattr(res, "image_data", None)
            except Exception:                                    # pad hasn't sent a drawing yet
                data = None
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
        a_cp, a_cat, a_rates, a_costs, a_co, a_bk = st.tabs(["Customer prices", "Catalogue", "Lease rates", "Costs & fees", "Company & terms", "Backup"])

        def _reset_cp():
            for _k in ("q_cp_rental", "q_cp_cash", "q_cp_support"):
                st.session_state[_k] = 0.0

        with a_cp:
            Cc = CALC
            st.markdown("##### Customer pays - this deal")
            st.caption("Set what the customer actually pays, without touching individual costs or sell prices. Leave a box at 0 to use the calculated price. "
                       "These prices go straight onto the paperwork and into the profit figures below, and are saved with the quote.")
            h1, h2, h3 = st.columns([2.2, 1.4, 1.6])
            h1.markdown("**Item**"); h2.markdown("**Calculated**"); h3.markdown("**Customer pays**")
            r1, r2, r3 = st.columns([2.2, 1.4, 1.6])
            r1.markdown(f"Monthly rental · {Cc['term_label']} (plus VAT)"); r2.markdown(money(Cc["calc_rental"]))
            r3.number_input("Monthly rental", min_value=0.0, step=1.0, key="q_cp_rental", label_visibility="collapsed")
            r1, r2, r3 = st.columns([2.2, 1.4, 1.6])
            r1.markdown("Cash price (plus VAT)"); r2.markdown(money(Cc["cash_calc"]))
            r3.number_input("Cash price", min_value=0.0, step=10.0, key="q_cp_cash", label_visibility="collapsed")
            r1, r2, r3 = st.columns([2.2, 1.4, 1.6])
            r1.markdown("Annual support after the included period (plus VAT)"); r2.markdown(money(Cc["maint_annual"]))
            r3.number_input("Annual support", min_value=0.0, step=10.0, key="q_cp_support", label_visibility="collapsed")
            st.button("↩️ Reset to calculated prices", on_click=_reset_cp, key="btn_reset_cp")
            st.divider()
            y1, y2, y3 = st.columns(3)
            if Cc["is_cash"]:
                card("Customer pays", money(Cc["cash_price"]), "cash, plus VAT" + (" · admin price" if Cc["cp_cash_on"] else ""), y1)
                card("Gross profit", money(Cc["cash_gp"], 0), f"{Cc['cash_units']:.2f} commission units", y2)
                card("Commission", money(Cc["cash_comm"], 0), "estimated", y3)
                _loss = Cc["cash_gp"] < 0
            else:
                card("Customer pays", f"{money(Cc['rental'])}/mo", f"{Cc['term_label']} · total {money(Cc['rental'] * Cc['term'], 0)}"
                     + (" · admin price" if Cc["cp_rental_on"] else ""), y1)
                card("Gross profit", money(Cc["gp"], 0), f"funder pays {money(Cc['funded'], 0)} · {Cc['units']:.2f} units", y2)
                card("Commission", money(Cc["commission"], 0), f"company profit after commission {money(Cc['co_profit'], 0)}", y3)
                _loss = Cc["gp"] < 0
            if _loss:
                st.markdown("<div class='st-bad'>⛔ At this price the deal makes a loss.</div>", unsafe_allow_html=True)
            if Cc["cp_rental_on"] and not Cc["is_cash"]:
                st.caption("The monthly rental stays at the admin price if you change the lease term - re-check it after changing the term.")

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
                      "unit_value": "Commission per unit £", "free_support_years": "Included support (years)",
                      "install_day_rate": "Engineer install day rate £", "travel_hours": "Journey time (hours) before extra days are added"}
            with st.form("adm_costs_form"):
                cols = st.columns(3); vals = {}
                for n, (k, lbl) in enumerate(labels.items()):
                    vals[k] = cols[n % 3].number_input(lbl, value=float(COST[k]), step=1.0 if k not in ("cash_load", "srrp_mult", "travel_hours") else 0.05 if k != "travel_hours" else 0.25, key=f"adm_c_{k}")
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
                email = e1.text_input("Email (fixed)", CO["email"], disabled=True); phone = e2.text_input("Phone (fixed)", CO["phone"], disabled=True); web = e3.text_input("Website (fixed)", CO["web"], disabled=True)
                funder = st.text_input("Finance provider name used in the paperwork", CO["funder"])
                logo = st.file_uploader("Logo (PNG/JPG, optional)", type=["png", "jpg", "jpeg"])
                st.markdown("**Terms & Conditions** - one clause per row. `{legal}`, `{trading}` and `{free}` fill in automatically.")
                terms_df = st.data_editor(pd.DataFrame(CFG["terms"], columns=["Clause", "Text"]), num_rows="dynamic", **FW,
                                          column_config={"Text": st.column_config.TextColumn("Text", width="large")})
                if st.form_submit_button("Save company & terms", type="primary"):
                    CO.update(trading=trading, legal=legal, legal_line=legal_line, addr=[x.strip() for x in addr.splitlines() if x.strip()],
                              reg=reg, vat=vat, email=email, phone=phone, web=web, funder=funder)
                    if logo is not None:
                        import base64
                        CO["logo_b64"] = base64.b64encode(logo.getvalue()).decode()
                    CFG["terms"] = [[str(r["Clause"]), str(r["Text"])] for _, r in terms_df.iterrows() if str(r.get("Clause") or "").strip()]
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
