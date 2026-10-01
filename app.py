import glob
import io
import math
import os
import urllib.request

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from geometry import (
    parse_dxf_layers,
    parse_svg_geometry,
    parse_tap_geometry,
    recalculate_active_geometry,
)

# ------------------------------------------------------
# PAGE CONFIGURATION & LIGHT CATALOG STYLING
# ------------------------------------------------------
st.set_page_config(
    page_title="Warner Steel Sales, Inc. - Laser Quoting Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.markdown(
    """
    <style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Montserrat:wght@400;500;600;700;800&display=swap');

:root {
  --ink:#1a1a1a; --red:#cc1111; --red-dk:#a50d0d; --panel:#d9d9d9;
  --card:#ffffff; --brown:#5b4a38; --muted:#6b6b6b; --line:#e3e3e3;
  --display:'Syne','Arial Black','Segoe UI',sans-serif;
  --body:'Montserrat','Segoe UI',Roboto,Arial,sans-serif;
}

/* ---------- BASE ---------- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stMainBlockContainer"], .main {
  background:#ffffff !important; color:var(--ink) !important;
  font-family:var(--body) !important;
}
[data-testid="stHeader"] { background:transparent !important; }
[data-testid="stMainBlockContainer"] { max-width:1240px; padding-top:2.2rem; }
label, p, span, [data-testid="stWidgetLabel"], [data-testid="stMarkdownContainer"] p {
  color:var(--ink) !important; font-family:var(--body) !important;
  font-weight:600 !important; letter-spacing:.02em;
}
[data-testid="stWidgetLabel"] p { font-size:.78rem !important; text-transform:uppercase;
  letter-spacing:.09em; color:var(--brown) !important; font-weight:700 !important; }
[data-testid="stCaptionContainer"] p { color:var(--muted) !important; font-weight:500 !important; }
hr { border:none !important; border-top:1px solid var(--line) !important; margin:1.6rem 0 !important; }

/* ---------- HERO ---------- */
.ws-hero { display:flex; align-items:center; justify-content:space-between; gap:32px;
  padding:6px 4px 26px 4px; }
.ws-hero h1 { font-family:var(--display) !important; font-weight:800 !important;
  font-size:clamp(2.6rem,6vw,4.6rem) !important; line-height:.92 !important;
  letter-spacing:.01em; margin:0 !important; padding:0 !important;
  background:linear-gradient(90deg,#111 0%,#111 38%,#6a6a6a 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent !important;
  -webkit-text-fill-color:transparent; }
.ws-hero .sub { font-family:var(--body); font-weight:500; text-transform:uppercase;
  letter-spacing:.28em; color:var(--red); font-size:clamp(1rem,2.2vw,1.6rem);
  margin-top:14px; }
.ws-hero .addr { color:var(--muted); font-size:.78rem; letter-spacing:.06em; margin-top:10px;
  font-weight:500; }
.ws-hero img { width:150px; height:150px; border-radius:50%;
  box-shadow:0 8px 24px rgba(0,0,0,.18); flex:none; }
@media (max-width:700px){ .ws-hero img{ width:96px; height:96px; } }

/* ---------- SECTION TITLES ---------- */
.catalog-title { font-family:var(--display) !important; font-size:1.15rem !important;
  font-weight:800 !important; text-transform:uppercase; letter-spacing:.07em;
  color:var(--ink) !important; margin:6px 0 16px 0; display:flex; align-items:center; gap:10px; }
.catalog-star { color:var(--red) !important; font-size:1.4rem; line-height:1; }
h2, h3, [data-testid="stSubheader"] { font-family:var(--display) !important;
  text-transform:uppercase; letter-spacing:.05em; font-weight:800 !important; color:var(--ink) !important; }

/* ---------- INPUTS ---------- */
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] {
  background:#fff !important; border:1.5px solid #cfcfcf !important;
  border-radius:12px !important; font-weight:600 !important; color:var(--ink) !important;
  transition:border-color .15s, box-shadow .15s; }
div[data-baseweb="input"]:focus-within > div, div[data-baseweb="select"]:focus-within > div {
  border-color:var(--red) !important; box-shadow:0 0 0 3px rgba(204,17,17,.14) !important; }
input { color:var(--ink) !important; font-family:var(--body) !important; }
[data-testid="stNumberInput"] button { border-radius:10px !important; }
[data-testid="stCheckbox"] label span { font-weight:600 !important; text-transform:none; letter-spacing:.02em; }
[data-testid="stTooltipIcon"] svg { fill:var(--ink) !important; opacity:.7 !important; }
div[data-baseweb="tooltip"] { background:var(--ink) !important; border:1px solid var(--red) !important;
  border-radius:10px !important; box-shadow:0 8px 24px rgba(0,0,0,.3) !important; }
div[data-baseweb="tooltip"] * { color:#fff !important; font-weight:500 !important; }

/* ---------- ALERTS ---------- */
[data-testid="stAlert"] { background:#fff !important; border:none !important;
  border-left:5px solid var(--red) !important; border-radius:14px !important;
  box-shadow:0 2px 10px rgba(0,0,0,.06); }
[data-testid="stAlert"] p { font-weight:600 !important; font-size:.9rem !important; }

/* ---------- TABS + ARCHED PANEL (catalog signature) ---------- */
.stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:none !important; padding-bottom:0; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; }
.stTabs [data-baseweb="tab"] { background:#efefef !important; border:none !important;
  border-radius:16px 16px 0 0 !important; padding:12px 24px !important; height:auto !important; }
.stTabs [data-baseweb="tab"] p { color:var(--ink) !important; font-weight:700 !important;
  font-size:.82rem !important; text-transform:uppercase; letter-spacing:.08em; }
.stTabs [aria-selected="true"] { background:var(--panel) !important; }
.stTabs [aria-selected="true"] p { color:var(--red) !important; font-weight:800 !important; }
.stTabs [data-baseweb="tab-panel"] { background:var(--panel); padding:30px 32px 32px 32px !important;
  border-radius:0 120px 28px 28px; margin-top:0; }
@media (max-width:700px){ .stTabs [data-baseweb="tab-panel"]{ border-radius:0 40px 20px 20px; padding:20px !important; } }

/* ---------- FILE UPLOADER ---------- */
[data-testid="stFileUploader"] section { background:#fff !important; border:2px dashed #b9b9b9 !important;
  border-radius:18px !important; padding:22px !important; }
[data-testid="stFileUploader"] section:hover { border-color:var(--red) !important; }
[data-testid="stFileUploader"] * { color:var(--ink) !important; }
[data-testid="stFileUploader"] section button { background:var(--ink) !important; color:#fff !important;
  border:none !important; border-radius:999px !important; font-weight:700 !important;
  text-transform:uppercase; letter-spacing:.06em; padding:8px 18px !important; }
[data-testid="stFileUploader"] section button * { color:#fff !important; }
[data-testid="stFileUploader"] section button:hover { background:var(--red) !important; }

/* ---------- METRICS ---------- */
[data-testid="stMetric"] { background:#fff !important; border:1px solid var(--line) !important;
  border-top:4px solid var(--ink) !important; border-radius:16px !important;
  padding:14px 18px !important; box-shadow:0 4px 14px rgba(0,0,0,.05) !important; }
[data-testid="stMetricValue"] { font-family:var(--display) !important; font-size:1.55rem !important;
  font-weight:800 !important; color:var(--ink) !important; }
[data-testid="stMetricLabel"] p { color:var(--red) !important; font-size:.72rem !important;
  font-weight:800 !important; text-transform:uppercase; letter-spacing:.1em; }

/* ---------- COST + INFO CARDS ---------- */
.cost-card { background:linear-gradient(135deg,#fff 0%,#fbeaea 100%); border:1px solid #f1c9c9;
  border-radius:16px; padding:12px 18px; margin-bottom:12px; position:relative;
  box-shadow:0 4px 14px rgba(204,17,17,.10); overflow:hidden; }
.cost-card::before { content:"✦"; position:absolute; right:14px; top:8px; color:var(--red); opacity:.35; }
.cost-card label { color:var(--red) !important; font-weight:800 !important; text-transform:uppercase;
  font-size:.7rem; display:block; margin-bottom:2px; letter-spacing:.12em; }
.cost-card span { font-family:var(--display); font-weight:800; font-size:1.65rem; color:var(--ink) !important; }

.info-card { background:#fff; border:1px solid var(--line); border-radius:16px; padding:12px 18px;
  margin-bottom:10px; box-shadow:0 3px 12px rgba(0,0,0,.05); }
.info-card label { color:var(--red) !important; font-weight:800 !important; text-transform:uppercase;
  font-size:.68rem; display:block; margin-bottom:3px; letter-spacing:.12em; }
.info-card span { font-weight:700; font-size:1rem; color:var(--ink) !important; line-height:1.55; }
.tab-card { margin-top:24px; }

/* ---------- TOTAL BANNER ---------- */
.total-price-banner { background:var(--ink); padding:22px 30px 24px 30px; margin:18px 0 24px 0;
  border-radius:0 90px 24px 24px; box-shadow:0 10px 28px rgba(0,0,0,.22); position:relative; }
.total-price-banner::after { content:""; position:absolute; left:0; top:0; bottom:0; width:8px;
  background:var(--red); border-radius:0 0 0 24px; }
.total-price-banner .tp-label { display:block; color:var(--red) !important; font-weight:800;
  letter-spacing:.2em; text-transform:uppercase; font-size:.75rem; margin-bottom:6px; }
.total-price-banner .tp-value { font-family:var(--display); color:#fff !important; margin:0;
  font-size:clamp(1.9rem,4vw,2.9rem); font-weight:800; letter-spacing:.01em; line-height:1.05; }

/* ---------- BUTTONS ---------- */
.stButton > button { border-radius:999px !important; padding:12px 28px !important;
  font-family:var(--body) !important; font-weight:800 !important; text-transform:uppercase !important;
  letter-spacing:.09em !important; font-size:.8rem !important; transition:all .15s ease !important; }
.stButton > button p { font-weight:800 !important; letter-spacing:.09em !important; }
.stButton > button[kind="secondary"], [data-testid="stBaseButton-secondary"] {
  background:#fff !important; border:1.5px solid var(--ink) !important; color:var(--ink) !important;
  box-shadow:none !important; }
.stButton > button[kind="secondary"] p, [data-testid="stBaseButton-secondary"] p { color:var(--ink) !important; }
.stButton > button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {
  background:var(--ink) !important; }
.stButton > button[kind="secondary"]:hover p, [data-testid="stBaseButton-secondary"]:hover p { color:#fff !important; }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background:var(--red) !important; border:none !important; color:#fff !important;
  box-shadow:0 6px 16px rgba(204,17,17,.35) !important; }
.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p { color:#fff !important; }
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background:var(--red-dk) !important; transform:translateY(-1px); }

/* ---------- FOOTER ---------- */
.ws-footer { margin-top:44px; padding:22px 6px 6px 6px; border-top:3px solid var(--red);
  display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; }
.ws-footer .welding { font-family:var(--display); font-weight:800; color:var(--red);
  letter-spacing:.06em; text-transform:uppercase; font-size:.95rem; }
.ws-footer .contact { color:var(--muted); font-size:.8rem; letter-spacing:.05em; font-weight:500; text-align:right; }
.ws-footer .contact b { color:var(--ink); }
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------
# CACHED PARSING FUNCTION
# ------------------------------------------------------
@st.cache_data(show_spinner="Reading file…")
def parse_uploaded_file(filename, file_bytes, unit_scale):
  name = filename.lower()
  if name.endswith((".tap", ".nc", ".cnc")):
    return parse_tap_geometry(file_bytes, unit_scale)
  if name.endswith(".dxf"):
    return parse_dxf_layers(file_bytes, unit_scale)
  if name.endswith(".svg"):
    return parse_svg_geometry(file_bytes, unit_scale)
  return None, "Unsupported file format."


# ------------------------------------------------------
# LIVE GOOGLE SHEET CONNECTION
# ------------------------------------------------------
PUBLISHED_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSwuOZluQH2b4ODvc7dW3NZPIeYqJf7M7yuNGuKoWeo9L4zuJxLpPTgjFxLvpdrs5_51a80QNP7NZwL/pub?gid=1755421406&single=true&output=csv"


@st.cache_data(ttl=600)
def load_data():
  req = urllib.request.Request(
      PUBLISHED_CSV_URL,
      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
  )
  with urllib.request.urlopen(req) as response:
    csv_data = response.read()

  df = pd.read_csv(io.BytesIO(csv_data))
  df.columns = df.columns.astype(str).str.strip()
  return df


try:
  vlookup_data = load_data()
except Exception as e:
  st.error(f"Failed to load Google Sheet data: {e}")
  st.stop()

# ------------------------------------------------------
# HEADER & LOGO (ROBUST FILE MATCH & INLINE SVG FALLBACK)
# ------------------------------------------------------
import base64

def get_logo_file():
  for f in glob.glob("*"):
    if f.lower() in ("logo.png", "logo.jpg", "logo.jpeg", "warner_steel_1280x1280.png"):
      return f
  return None


def logo_data_uri():
  path = get_logo_file()
  if not path:
    return None
  mime = "image/png" if path.lower().endswith("png") else "image/jpeg"
  with open(path, "rb") as fh:
    return f"data:{mime};base64," + base64.b64encode(fh.read()).decode()


_logo_uri = logo_data_uri()
_logo_html = f'<img src="{_logo_uri}" alt="Warner Steel logo">' if _logo_uri else ""

st.markdown(
    '<div class="ws-hero"><div>'
    "<h1>WARNER<br>STEEL</h1>"
    '<div class="sub">Laser Quoting</div>'
    '<div class="addr">2623 E. Raymond St · Indianapolis, IN 46203 · (317) 789-1733 ·'
    " sales@warnersteel.com</div>"
    "</div>" + _logo_html + "</div>",
    unsafe_allow_html=True,
)

# ------------------------------------------------------
# SESSION STATE INITIALIZATION & RESET HANDLER
# ------------------------------------------------------
if "step" not in st.session_state:
  st.session_state.step = 1


def reset_quote_data():
  st.session_state.cut_length = 0.0
  st.session_state.pierces = 0
  st.session_state.length = 0.0
  st.session_state.width = 0.0
  st.session_state.qty = 1
  st.session_state.hull_ratio = 1.0
  st.session_state.subpaths_to_render = None
  st.session_state.part_w = 0.0
  st.session_state.part_h = 0.0
  st.session_state.min_x = 0.0
  st.session_state.min_y = 0.0
  st.session_state.parsed_layer_data = None
  st.session_state.layer_toggles = {}
  st.session_state.input_mode = "manual"
  st.session_state.selected_mat = None
  st.session_state.selected_thick = None
  st.session_state.manual_cut_len = None
  st.session_state.manual_pierces = None
  st.session_state.manual_len = None
  st.session_state.manual_wid = None
  st.session_state.manual_qty_val = None
  st.session_state.step = 1


if "cut_length" not in st.session_state:
  reset_quote_data()

# ------------------------------------------------------
# STEP 1: QUOTE INPUTS & LIVE INTERACTIVE CAD VIEWER
# ------------------------------------------------------
if st.session_state.step == 1:
  top_row1, top_row2, top_row3 = st.columns([3, 1.2, 1])
  with top_row1:
    st.markdown(
        '<div class="catalog-title"><span class="catalog-star">✦</span>STEP 1:'
        " ENTER QUOTE DETAILS</div>",
        unsafe_allow_html=True,
    )
  with top_row2:
    if st.button("📊 Reload Google Sheet"):
      st.cache_data.clear()
      st.rerun()
  with top_row3:
    if st.button("🔄 Reset Quote"):
      reset_quote_data()
      st.rerun()

  # 1. MATERIAL & THICKNESS INPUTS
  mats_list = ["Select Material..."] + list(vlookup_data["Material"].dropna().unique())
  
  sel_mat_idx = (
      mats_list.index(st.session_state.selected_mat)
      if st.session_state.get("selected_mat") in mats_list
      else 0
  )
  
  selected_mat = st.selectbox(
      "Material Choice", mats_list, index=sel_mat_idx
  )

  if selected_mat != "Select Material...":
    st.session_state.selected_mat = selected_mat
    available_thick_raw = (
        vlookup_data[vlookup_data["Material"] == selected_mat]["Thickness"]
        .dropna()
        .unique()
    )
    thick_list = ["Select Thickness..."] + list(available_thick_raw)
  else:
    st.session_state.selected_mat = None
    thick_list = ["Select Thickness..."]

  sel_thick_idx = (
      thick_list.index(st.session_state.selected_thick)
      if st.session_state.get("selected_thick") in thick_list
      else 0
  )

  selected_thick = st.selectbox(
      "Thickness Choice", thick_list, index=sel_thick_idx
  )
  
  if selected_thick != "Select Thickness...":
    st.session_state.selected_thick = selected_thick
  else:
    st.session_state.selected_thick = None

  st.divider()

  # 2. DEFAULT TO MANUAL DATA ENTRY TAB FIRST
  tab_manual, tab_upload = st.tabs(
      ["✏️ Manual Data Entry", "⚡ Upload File (.dxf / .svg / .tap)"]
  )

  # --- TAB 1: MANUAL DATA ENTRY ---
  with tab_manual:
    st.info(
        "💡 **Manual Entry Note:** Enter the **TOTAL Cut Length** and **TOTAL"
        " Pierces** for your full array layout. Quantity is optional and will"
        " divide totals for per-part unit metrics."
    )

    col_m1, col_m2 = st.columns([1.2, 1], gap="large")

    with col_m1:
      total_job_cut_len_input = st.number_input(
          "TOTAL Job Cut Length (Inches across ALL parts)",
          min_value=0.0,
          value=st.session_state.get("manual_cut_len", None),
          placeholder="Type cut length...",
          help="Enter the total linear cut length for the entire array/nest.",
      )
      total_job_pierces_input = st.number_input(
          "TOTAL Job Pierces (Across ALL parts)",
          min_value=0,
          value=st.session_state.get("manual_pierces", None),
          placeholder="Type pierces...",
          help="Enter the total pierces for the entire array/nest.",
      )

      raw_array_len_input = st.number_input(
          'Array Length (in, +1.5" alignment margin added)',
          min_value=0.0,
          value=st.session_state.get("manual_len", None),
          placeholder="Type array length...",
      )
      raw_array_wid_input = st.number_input(
          'Array Width (in, +1.5" alignment margin added)',
          min_value=0.0,
          value=st.session_state.get("manual_wid", None),
          placeholder="Type array width...",
      )

      manual_qty_input = st.number_input(
          "Total Order Quantity (pcs, Optional)",
          min_value=0,
          value=st.session_state.get("manual_qty_val", None),
          placeholder="1",
          step=1,
          key="manual_qty_input",
          help=(
              "Optional quantity. Used to compute per-part unit cost"
              " breakouts."
          ),
      )

      st.session_state.manual_cut_len = total_job_cut_len_input
      st.session_state.manual_pierces = total_job_pierces_input
      st.session_state.manual_len = raw_array_len_input
      st.session_state.manual_wid = raw_array_wid_input
      st.session_state.manual_qty_val = manual_qty_input

      total_job_cut_len = total_job_cut_len_input or 0.0
      total_job_pierces = total_job_pierces_input or 0
      raw_array_len = raw_array_len_input or 0.0
      raw_array_wid = raw_array_wid_input or 0.0
      manual_qty = manual_qty_input if manual_qty_input is not None else 1

      effective_qty = manual_qty if manual_qty > 0 else 1
      per_part_cut_len = total_job_cut_len / effective_qty
      per_part_pierces = int(round(total_job_pierces / effective_qty))

      array_len_with_margin = raw_array_len + 1.5 if raw_array_len > 0 else 0.0
      array_wid_with_margin = raw_array_wid + 1.5 if raw_array_wid > 0 else 0.0

    with col_m2:
      st.markdown(
          f"""
          <div class="info-card tab-card">
              <label>Calculated Unit & Footprint Summary</label>
              <span>Per Part Cut Length: {per_part_cut_len:.2f} in</span><br>
              <span>Per Part Pierces: {per_part_pierces}</span><br>
              <span>Effective Array Footprint (+1.5" Margin): {array_len_with_margin:.2f}" L × {array_wid_with_margin:.2f}" W</span>
          </div>
      """,
          unsafe_allow_html=True,
      )

  # --- TAB 2: FILE UPLOADER ---
  with tab_upload:
    uploaded_file = st.file_uploader(
        "Drop DXF, SVG, or TAP/G-code file here to extract geometry and cut layers",
        type=["dxf", "svg", "tap", "nc", "cnc"],
    )

    col_units, col_qty = st.columns(2)
    with col_units:
      cad_units = st.selectbox(
          "File Units",
          [
              "Auto-detect (from file)",
              "Inches",
              "Millimeters (mm)",
              "Screen Pixels (96 DPI)",
          ],
      )

    with col_qty:
      part_qty_upload = st.number_input(
          "Part Quantity",
          min_value=1,
          value=int(st.session_state.get("qty", 1)),
          step=1,
          key="upload_qty_input",
      )

    unit_scale = {
        "Auto-detect (from file)": None,
        "Inches": 1.0,
        "Millimeters (mm)": 1.0 / 25.4,
        "Screen Pixels (96 DPI)": 1.0 / 96.0,
    }[cad_units]

    if uploaded_file is not None:
      file_bytes = uploaded_file.getvalue()
      data, error = parse_uploaded_file(
          uploaded_file.name, file_bytes, unit_scale
      )

      if error:
        st.error(error)
      elif data:
        st.session_state.parsed_layer_data = data
        st.session_state.qty = part_qty_upload
        st.session_state.input_mode = "upload"

        if (
            "layer_toggles" not in st.session_state
            or not st.session_state.layer_toggles
        ):
          st.session_state.layer_toggles = {
              layer_name: (layer_name in data["default_layers"])
              for layer_name in data["all_layers"]
          }

    if st.session_state.get("parsed_layer_data") is not None:
      layer_info = st.session_state.parsed_layer_data
      all_layers = layer_info["all_layers"]
      layer_dict = layer_info["layer_dict"]

      st.markdown("---")
      st.subheader("Interactive Layer Controls & Live CAD Alignment Viewer")

      viewer_col1, viewer_col2 = st.columns([1, 1.3], gap="large")

      with viewer_col1:
        st.write("Toggle layers **ON** or **OFF** to select cut paths:")

        active_layers = []
        for l_name in all_layers:
          is_active = st.checkbox(
              f"Layer: {l_name}",
              value=st.session_state.layer_toggles.get(l_name, True),
              key=f"toggle_{l_name}",
          )
          st.session_state.layer_toggles[l_name] = is_active
          if is_active:
            active_layers.append(l_name)

        if "TAP Cut Toolpath" in all_layers:
          active_geom = {
              "cut_length": layer_info["cut_length"],
              "pierces": layer_info["pierces"],
              "length": layer_info["length"],
              "width": layer_info["width"],
              "hull_ratio": 0.95,
              "subpaths": layer_info["subpaths"],
              "part_w": layer_info["part_w"],
              "part_h": layer_info["part_h"],
              "min_x": layer_info["min_x"],
              "min_y": layer_info["min_y"],
          }
        else:
          active_geom = recalculate_active_geometry(
              layer_dict,
              active_layers,
              lead_in_per_pierce=layer_info.get("lead_in", 0.5),
              margin_per_side=0.75,
              stitch=layer_info.get("stitch", True),
          )

        st.session_state.cut_length = active_geom["cut_length"]
        st.session_state.pierces = active_geom["pierces"]
        st.session_state.length = active_geom["length"]
        st.session_state.width = active_geom["width"]
        st.session_state.hull_ratio = active_geom["hull_ratio"]
        st.session_state.subpaths_to_render = active_geom["subpaths"]
        st.session_state.part_w = active_geom["part_w"]
        st.session_state.part_h = active_geom["part_h"]
        st.session_state.min_x = active_geom["min_x"]
        st.session_state.min_y = active_geom["min_y"]

        st.markdown(
            f"""
            <div class="info-card tab-card" style="margin-top:12px;">
                <label>Active Geometry Summary (Incl. 0.5" Lead-In per Pierce)</label>
                <span>Active Cut Length (Per Part): {active_geom['cut_length']} in</span><br>
                <span>Active Pierces (Per Part): {active_geom['pierces']}</span><br>
                <span>Bounding Box (+1.5" Margin): {active_geom['length']}" L × {active_geom['width']}" W</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

      with viewer_col2:
        st.caption("Live Transformed CAD Preview (Active Layers Only)")
        fig_preview, ax_preview = plt.subplots(
            figsize=(6, 4.5), facecolor="#ffffff"
        )
        ax_preview.set_facecolor("#ffffff")

        if active_geom["subpaths"]:
          for xs, ys in active_geom["subpaths"]:
            ax_preview.plot(xs, ys, color="#cc1111", linewidth=1.2)
          ax_preview.set_aspect("equal", adjustable="datalim")
        else:
          ax_preview.text(
              0.5,
              0.5,
              "No active layers selected",
              ha="center",
              va="center",
              color="#cc1111",
              fontsize=12,
              weight="bold",
              transform=ax_preview.transAxes,
          )

        ax_preview.axis("off")
        st.pyplot(fig_preview, clear_figure=True)

  st.divider()

  if st.button("Calculate Quote & View Estimate →", type="primary"):
    if not st.session_state.selected_mat or not st.session_state.selected_thick:
      st.error("⚠️ Please select both a Material Choice and a Thickness Choice to generate a quote.")
    else:
      if (
          st.session_state.get("input_mode") == "upload"
          and st.session_state.get("parsed_layer_data") is not None
      ):
        qty = part_qty_upload
      else:
        qty = effective_qty
        st.session_state.cut_length = per_part_cut_len
        st.session_state.pierces = per_part_pierces
        st.session_state.length = array_len_with_margin
        st.session_state.width = array_wid_with_margin
        st.session_state.subpaths_to_render = None

      if (
          st.session_state.length == 0
          or st.session_state.width == 0
          or st.session_state.cut_length == 0
      ):
        st.warning(
            "Please select active CAD/TAP layers or enter valid total dimensions"
            " before continuing."
        )
      else:
        st.session_state.qty = qty
        if st.session_state.part_w == 0.0:
          st.session_state.part_w = st.session_state.length
        if st.session_state.part_h == 0.0:
          st.session_state.part_h = st.session_state.width
        st.session_state.step = 2
        st.rerun()

# ------------------------------------------------------
# STEP 2: ESTIMATE SUMMARY & COST PIE CHART
# ------------------------------------------------------
elif st.session_state.step == 2:
  nav_col1, nav_col2 = st.columns([4, 1])
  with nav_col1:
    if st.button("← Revise Quote Inputs"):
      st.session_state.step = 1
      st.rerun()
  with nav_col2:
    if st.button("🔄 Reset / Start New Quote"):
      reset_quote_data()
      st.rerun()

  selected_mat = st.session_state.selected_mat
  selected_thick = st.session_state.selected_thick
  cut_length = st.session_state.cut_length
  pierces = st.session_state.pierces
  length = st.session_state.length
  width = st.session_state.width
  qty = st.session_state.qty
  hull_ratio = st.session_state.hull_ratio
  subpaths_to_render = st.session_state.subpaths_to_render
  part_w = st.session_state.part_w
  part_h = st.session_state.part_h
  min_x = st.session_state.min_x
  min_y = st.session_state.min_y

  matched_rows = vlookup_data[
      (vlookup_data["Material"] == selected_mat)
      & (vlookup_data["Thickness"] == selected_thick)
  ]

  spacing_gap = 0.25

  is_already_array = False
  if st.session_state.get("input_mode") == "upload" and st.session_state.get("parsed_layer_data") is not None:
    if "TAP Cut Toolpath" in st.session_state.parsed_layer_data.get("all_layers", []):
      is_already_array = True

  if is_already_array:
    cols, rows = 1, 1
    display_qty = 1
  else:
    display_qty = qty
    if qty == 1:
      cols, rows = 1, 1
    else:
      cols = math.ceil(math.sqrt(qty * (part_h / part_w if part_w > 0 else 1.0)))
      cols = max(1, min(qty, cols))
      rows = math.ceil(qty / cols)

  array_width = (cols * part_w) + (max(0, cols - 1) * spacing_gap)
  array_height = (rows * part_h) + (max(0, rows - 1) * spacing_gap)

  out_col1, out_col2 = st.columns([1.1, 0.9], gap="large")

  with out_col1:
    st.markdown(
        '<div class="catalog-title"><span class="catalog-star">✦</span>CALCULATED'
        " QUOTE BREAKDOWN</div>",
        unsafe_allow_html=True,
    )

    if matched_rows.empty:
      st.warning("No pricing data found for this Material and Thickness.")
    else:
      row = matched_rows.iloc[0]

      base_part_area_sq_ft = (
          (length + spacing_gap) * (width + spacing_gap)
      ) / 144.0

      shape_discount_pct = 80.0
      if qty > 1 and not is_already_array:
        efficiency_multiplier = 1.0 - (
            (1.0 - hull_ratio) * (shape_discount_pct / 100.0)
        )
      else:
        efficiency_multiplier = 1.0

      total_area_sq_ft = base_part_area_sq_ft * (1 if is_already_array else qty) * efficiency_multiplier

      def clean_num(val):
        if pd.isna(val):
          return 0.0
        s = str(val).replace("$", "").replace(",", "").strip()
        try:
          return float(s)
        except ValueError:
          return 0.0

      cost_per_in = clean_num(row.get("Cost_per_in", 0))
      cost_per_pierce = clean_num(row.get("Pierce_Cost", 0))
      gas_rate = clean_num(row.get("Gas_Cost_per_in", 0))
      setup_sqft_rate = clean_num(row.get("Setup_cost_per_sqft", 0))
      laser_velocity = clean_num(row.get("Laser_Velocity", 0))

      total_cut_length = cut_length * (1 if is_already_array else qty)
      total_pierces = pierces * (1 if is_already_array else qty)

      cut_price = total_cut_length * cost_per_in
      pierce_price = total_pierces * cost_per_pierce
      gas_price = gas_rate * total_cut_length
      setup_price = setup_sqft_rate * total_area_sq_ft

      if laser_velocity > 0:
        est_cut_time_sec = (total_cut_length / laser_velocity) * 60.0
      else:
        est_cut_time_sec = 0.0

      total_price = cut_price + pierce_price + gas_price + setup_price

      # --- ROW 1: Cut Length ---
      r1_c1, r1_c2, r1_c3 = st.columns(3)
      r1_c1.metric("Cut Length (Total)", f"{total_cut_length:.1f} in")
      r1_c2.metric("Rate ($/in)", f"${cost_per_in:.3f}")
      with r1_c3:
        st.markdown(
            f"""
            <div class="cost-card">
                <label>Cut Price</label>
                <span>${cut_price:.2f}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

      # --- ROW 2: Pierces ---
      r2_c1, r2_c2, r2_c3 = st.columns(3)
      r2_c1.metric("Pierces (Total)", f"{total_pierces}")
      r2_c2.metric("Rate ($/pierce)", f"${cost_per_pierce:.3f}")
      with r2_c3:
        st.markdown(
            f"""
            <div class="cost-card">
                <label>Pierce Price</label>
                <span>${pierce_price:.2f}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

      # --- ROW 3: Gas ---
      r3_c1, r3_c2, r3_c3 = st.columns(3)
      r3_c1.metric("Gas Type", f"{row.get('Gas', 'N/A')}")
      r3_c2.metric("Rate ($/in)", f"${gas_rate:.3f}")
      with r3_c3:
        st.markdown(
            f"""
            <div class="cost-card">
                <label>Gas Price</label>
                <span>${gas_price:.2f}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

      # --- ROW 4: Material Footprint ---
      r4_c1, r4_c2, r4_c3 = st.columns(3)
      r4_c1.metric("Nestable Area", f"{total_area_sq_ft:.2f} sq ft")
      r4_c2.metric("Setup Rate ($/sq ft)", f"${setup_sqft_rate:.3f}")
      with r4_c3:
        st.markdown(
            f"""
            <div class="cost-card">
                <label>Setup Price</label>
                <span>${setup_price:.2f}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

      # TOTAL PRICE BANNER
      st.markdown(
          f"""
          <div class="total-price-banner">
              <span class="tp-label">Total Price &nbsp;·&nbsp; {qty} pc{"s" if qty > 1 else ""}</span>
              <h2 class="tp-value">${total_price:.2f}</h2>
          </div>
      """,
          unsafe_allow_html=True,
      )

      # --- SIDE-BY-SIDE: COST PIE CHART & JOB DETAILS ---
      info_col1, info_col2 = st.columns([0.45, 0.55], gap="small")

      with info_col1:
        st.caption("Cost Driver Distribution")

        cost_labels = ["Cut", "Pierce", "Gas", "Setup"]
        cost_values = [cut_price, pierce_price, gas_price, setup_price]

        filtered_labels = [
            label for label, val in zip(cost_labels, cost_values) if val > 0
        ]
        filtered_values = [val for val in cost_values if val > 0]

        if sum(filtered_values) > 0:
          fig_pie, ax_pie = plt.subplots(figsize=(3.8, 2.6), facecolor="none")
          ax_pie.set_facecolor("none")

          colors = ["#cc1111", "#1a1a1a", "#8a6d4b", "#a8a8a8"]

          wedges, texts, autotexts = ax_pie.pie(
              filtered_values,
              labels=filtered_labels,
              autopct="%1.0f%%",
              startangle=140,
              colors=colors[: len(filtered_values)],
              textprops=dict(color="#1a1a1a", fontsize=8, weight="bold"),
              wedgeprops=dict(width=0.42, edgecolor="#ffffff", linewidth=2),
          )

          for autotext in autotexts:
            autotext.set_fontsize(7.5)

          ax_pie.axis("equal")
          st.pyplot(fig_pie, clear_figure=True)

      with info_col2:
        st.caption("Job Specifications")
        st.markdown(
            f"""
            <div class="info-card">
                <label>Material & Thickness</label>
                <span>{selected_mat} — {selected_thick}</span>
            </div>
            <div class="info-card">
                <label>Single Part / Array Bounds</label>
                <span>{length:.2f}" L × {width:.2f}" W</span>
            </div>
            <div class="info-card">
                <label>Est. Total Cut Time</label>
                <span>{est_cut_time_sec:.1f} sec ({est_cut_time_sec/60.0:.2f} min)</span>
            </div>
            <div class="info-card">
                <label>Estimated Array Footprint ({cols} × {rows} Grid, 0.25" gap)</label>
                <span>{array_width:.2f}" W × {array_height:.2f}" H</span>
            </div>
        """,
            unsafe_allow_html=True,
        )

  with out_col2:
    st.markdown(
        f'<div class="catalog-title"><span class="catalog-star">✦</span>ARRAY'
        f" VIEW ({cols} × {rows} GRID)</div>",
        unsafe_allow_html=True,
    )

    fig, ax = plt.subplots(figsize=(7, 5), facecolor="#ffffff")
    ax.set_facecolor("#ffffff")

    cell_w = part_w + spacing_gap
    cell_h = part_h + spacing_gap

    for r in range(rows):
      for c in range(cols):
        if (r * cols + c) >= display_qty:
          break

        grid_x = c * cell_w
        grid_y = r * cell_h

        rect = plt.Rectangle(
            (grid_x, grid_y),
            part_w,
            part_h,
            fill=False,
            edgecolor="#cc1111",
            linestyle="--",
            linewidth=0.8,
        )
        ax.add_patch(rect)

        if subpaths_to_render:
          for xs, ys in subpaths_to_render:
            norm_xs = [x - min_x + grid_x for x in xs]
            norm_ys = [y - min_y + grid_y for y in ys]
            ax.plot(norm_xs, norm_ys, color="#111111", linewidth=1.1)
        else:
          rect_part = plt.Rectangle(
              (grid_x, grid_y),
              part_w,
              part_h,
              fill=True,
              facecolor="#fbeaea",
              edgecolor="#cc1111",
              linewidth=1.2,
          )
          ax.add_patch(rect_part)

    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    st.pyplot(fig, clear_figure=True)


# ------------------------------------------------------
# FOOTER
# ------------------------------------------------------
st.markdown(
    '<div class="ws-footer">'
    '<div class="welding">✦ Welding required on kits ✦</div>'
    '<div class="contact"><b>1-317-789-1733</b> &nbsp;·&nbsp; www.warnersteel.com<br>'
    "sales@warnersteel.com</div></div>",
    unsafe_allow_html=True,
)
