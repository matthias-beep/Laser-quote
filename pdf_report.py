"""pdf_report.py - builds the downloadable Warner Steel estimate PDF.

Usage:
    pdf_bytes = build_estimate_pdf(data, logo_path="Logo.png")

`data` is a plain dict (see build_estimate_pdf docstring). The cut path preview
is drawn as vector lines so it stays sharp at any zoom level.
"""
import io
import math
import re

from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.lib.styles import ParagraphStyle

INK = HexColor("#1a1a1a")
RED = HexColor("#cc1111")
RED_DK = HexColor("#a50d0d")
PANEL = HexColor("#d9d9d9")
CARD_LINE = HexColor("#e3e3e3")
MUTED = HexColor("#6b6b6b")
BROWN = HexColor("#5b4a38")
PINK = HexColor("#fbeaea")
ZEBRA = HexColor("#f5f5f5")

PAGE_W, PAGE_H = letter
MARGIN = 36
CONTENT_W = PAGE_W - 2 * MARGIN

_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def plain(s):
  """Latin-1 safe text (built-in PDF fonts have no subscript/exotic glyphs)."""
  s = str(s).translate(_SUB).translate(_SUP)
  s = s.replace("\u2014", "-").replace("\u2013", "-").replace("\u2192", "->")
  s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
  return s.encode("latin-1", "replace").decode("latin-1")


def money(v):
  return f"${v:,.2f}"


# ------------------------------------------------------------------
# low-level drawing helpers
# ------------------------------------------------------------------
def text(c, x, y, s, font="Helvetica", size=9, color=INK, cs=0.0, align="left"):
  s = plain(s)
  w = stringWidth(s, font, size) + cs * max(len(s) - 1, 0)
  if align == "right":
    x -= w
  elif align == "center":
    x -= w / 2
  t = c.beginText(x, y)
  t.setFont(font, size)
  t.setFillColor(color)
  t.setCharSpace(cs)
  t.textOut(s)
  c.drawText(t)
  return w


def arch_path(c, x, y, w, h, tl=0, tr=0, br=0, bl=0):
  """Rectangle path with independent corner radii (the catalog's arched panels)."""
  p = c.beginPath()
  p.moveTo(x + bl, y)
  p.lineTo(x + w - br, y)
  if br:
    p.arcTo(x + w - 2 * br, y, x + w, y + 2 * br, startAng=-90, extent=90)
  p.lineTo(x + w, y + h - tr)
  if tr:
    p.arcTo(x + w - 2 * tr, y + h - 2 * tr, x + w, y + h, startAng=0, extent=90)
  p.lineTo(x + tl, y + h)
  if tl:
    p.arcTo(x, y + h - 2 * tl, x + 2 * tl, y + h, startAng=90, extent=90)
  p.lineTo(x, y + bl)
  if bl:
    p.arcTo(x, y, x + 2 * bl, y + 2 * bl, startAng=180, extent=90)
  p.close()
  return p


def star(c, cx, cy, r, color=RED):
  pts = []
  for i in range(8):
    ang = math.pi / 2 + i * math.pi / 4
    rad = r if i % 2 == 0 else r * 0.3
    pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
  p = c.beginPath()
  p.moveTo(*pts[0])
  for pt in pts[1:]:
    p.lineTo(*pt)
  p.close()
  c.setFillColor(color)
  c.drawPath(p, stroke=0, fill=1)


def round_logo(c, logo_path, cx, cy, r, ring=True):
  if ring:
    c.setFillColor(RED)
    c.circle(cx, cy, r + 5, stroke=0, fill=1)
    c.setFillColor(white)
    c.circle(cx, cy, r + 2.5, stroke=0, fill=1)
  if logo_path:
    try:
      c.drawImage(logo_path, cx - r, cy - r, 2 * r, 2 * r, mask="auto")
      return
    except Exception:
      pass
  c.setFillColor(INK)
  c.circle(cx, cy, r, stroke=0, fill=1)


def gradient_rule(c, x, y, w, h=3):
  c.saveState()
  p = c.beginPath()
  p.roundRect(x, y, w, h, h / 2)
  c.clipPath(p, stroke=0, fill=0)
  try:
    c.linearGradient(x, y, x + w, y, (RED, INK, white), (0, 0.55, 1))
  except Exception:
    c.setFillColor(RED)
    c.rect(x, y, w, h, stroke=0, fill=1)
  c.restoreState()


# ------------------------------------------------------------------
# page chrome (header / footer drawn on every page)
# ------------------------------------------------------------------
def _top_bar(c, ref, date_str):
  y = PAGE_H - MARGIN - 20
  c.setFillColor(RED)
  c.roundRect(MARGIN, y - 2, CONTENT_W, 22, 11, stroke=0, fill=1)
  c.setFillColor(INK)
  c.roundRect(MARGIN, y, CONTENT_W, 20, 10, stroke=0, fill=1)
  text(c, MARGIN + 14, y + 6.5, "Since 1995", "Times-BoldItalic", 10.5, white)
  text(c, MARGIN + CONTENT_W - 14, y + 7, f"ESTIMATE {ref}   |   {date_str}",
       "Helvetica-Bold", 6.3, HexColor("#bdbdbd"), cs=1.4, align="right")
  return y


def _footer(c, logo_path):
  h, y = 52, 20
  c.setFillColor(RED)
  c.drawPath(arch_path(c, MARGIN, y, CONTENT_W, h + 2.5, tl=44, tr=10, br=10, bl=10),
             stroke=0, fill=1)
  c.setFillColor(INK)
  c.drawPath(arch_path(c, MARGIN, y, CONTENT_W, h, tl=42, tr=9, br=10, bl=10),
             stroke=0, fill=1)
  round_logo(c, logo_path, MARGIN + 50, y + h / 2 - 1, 15, ring=False)
  c.setStrokeColor(RED)
  c.setLineWidth(1.2)
  c.circle(MARGIN + 50, y + h / 2 - 1, 15.5, stroke=1, fill=0)
  text(c, MARGIN + 74, y + 28, "Warner Steel", "Times-BoldItalic", 13, white)
  text(c, MARGIN + 74, y + 14, "SINCE 1995  ·  INDIANAPOLIS, IN", "Helvetica-Bold",
       5.6, HexColor("#a9a9a9"), cs=1.3)
  rx = MARGIN + CONTENT_W - 18
  text(c, rx, y + 34, "1-317-789-1733", "Helvetica-Bold", 8, HexColor("#ff5a5a"), align="right")
  text(c, rx, y + 23, "www.warnersteel.com", "Helvetica", 7, white, align="right")
  text(c, rx, y + 12, "sales@warnersteel.com", "Helvetica", 7, white, align="right")
  text(c, PAGE_W / 2 + 40, y + h + 10, f"Page {c.getPageNumber()}", "Helvetica", 6.5,
       MUTED, align="center")


def _first_page(logo_path, ref, date_str):
  def draw(c, doc):
    c.saveState()
    top = _top_bar(c, ref, date_str)
    # hero
    text(c, MARGIN + 2, top - 46, "WARNER", "Helvetica-Bold", 40, INK, cs=0.5)
    text(c, MARGIN + 2, top - 84, "STEEL", "Helvetica-Bold", 40, HexColor("#555555"), cs=0.5)
    text(c, MARGIN + 3, top - 104, "LASER CUTTING ESTIMATE", "Helvetica", 11, RED, cs=3.2)
    text(c, MARGIN + 3, top - 120,
         "2623 E. Raymond St  ·  Indianapolis, IN 46203  ·  (317) 789-1733  ·  sales@warnersteel.com",
         "Helvetica", 6.8, MUTED, cs=0.3)
    round_logo(c, logo_path, MARGIN + CONTENT_W - 52, top - 62, 40)
    gradient_rule(c, MARGIN, top - 130, CONTENT_W, 3.2)
    _footer(c, logo_path)
    c.restoreState()
  return draw


def _later_page(logo_path, ref, date_str):
  def draw(c, doc):
    c.saveState()
    _top_bar(c, ref, date_str)
    gradient_rule(c, MARGIN, PAGE_H - MARGIN - 32, CONTENT_W, 2.5)
    _footer(c, logo_path)
    c.restoreState()
  return draw


# ------------------------------------------------------------------
# flowables
# ------------------------------------------------------------------
class SectionTitle(Flowable):
  def __init__(self, title, width=CONTENT_W):
    super().__init__()
    self.title, self.width, self.height = title, width, 24

  def wrap(self, aw, ah):
    return self.width, self.height

  def draw(self):
    c = self.canv
    star(c, 7, 9, 6.5)
    w = text(c, 20, 5, self.title.upper(), "Helvetica-Bold", 10.5, INK, cs=1.3)
    c.setStrokeColor(CARD_LINE)
    c.setLineWidth(1)
    c.line(20 + w + 10, 8, self.width, 8)


class TotalBanner(Flowable):
  def __init__(self, total, qty, per_part, width=CONTENT_W):
    super().__init__()
    self.total, self.qty, self.per_part = total, qty, per_part
    self.width, self.height = width, 78

  def wrap(self, aw, ah):
    return self.width, self.height

  def draw(self):
    c, w, h = self.canv, self.width, self.height
    c.setFillColor(HexColor("#c4c4c4"))
    c.drawPath(arch_path(c, 0, -2, w, h, tr=58, br=12, bl=12), stroke=0, fill=1)
    c.saveState()
    p = arch_path(c, 0, 0, w, h, tr=58, br=12, bl=12)
    c.clipPath(p, stroke=0, fill=0)
    c.setFillColor(PANEL)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setFillColor(RED)
    c.rect(0, 0, 6, h, stroke=0, fill=1)
    c.restoreState()
    pcs = "pc" if self.qty == 1 else "pcs"
    text(c, 26, h - 26, f"TOTAL PRICE   ·   {self.qty} {pcs}".upper(), "Helvetica-Bold", 7.5, RED, cs=2.2)
    text(c, 25, 20, money(self.total), "Helvetica-Bold", 34, INK)
    text(c, w - 240, 43, "PER PART", "Helvetica-Bold", 6.5, RED, cs=1.6)
    text(c, w - 240, 27, money(self.per_part), "Helvetica-Bold", 14, INK)
    text(c, w - 130, 43, "QUANTITY", "Helvetica-Bold", 6.5, RED, cs=1.6)
    text(c, w - 130, 27, f"{self.qty} {pcs}", "Helvetica-Bold", 14, INK)


class CardGrid(Flowable):
  """Rounded white info cards (label in red caps, value in bold)."""

  def __init__(self, items, cols=3, width=CONTENT_W, card_h=38, gap=8):
    super().__init__()
    self.items, self.cols, self.width = items, cols, width
    self.card_h, self.gap = card_h, gap
    self.rows = math.ceil(len(items) / cols)
    self.height = self.rows * card_h + (self.rows - 1) * gap

  def wrap(self, aw, ah):
    return self.width, self.height

  def draw(self):
    c = self.canv
    cw = (self.width - (self.cols - 1) * self.gap) / self.cols
    for i, (label, value) in enumerate(self.items):
      r, k = divmod(i, self.cols)
      x = k * (cw + self.gap)
      y = self.height - (r + 1) * self.card_h - r * self.gap
      c.setFillColor(HexColor("#e9e9e9"))
      c.roundRect(x, y - 1.2, cw, self.card_h, 9, stroke=0, fill=1)
      c.setFillColor(white)
      c.setStrokeColor(CARD_LINE)
      c.setLineWidth(0.8)
      c.roundRect(x, y, cw, self.card_h, 9, stroke=1, fill=1)
      text(c, x + 10, y + self.card_h - 12, label.upper(), "Helvetica-Bold", 5.8, RED, cs=1.2)
      lines = simpleSplit(plain(value), "Helvetica-Bold", 9, cw - 20)[:2]
      for j, ln in enumerate(lines):
        text(c, x + 10, y + self.card_h - 24 - j * 10, ln, "Helvetica-Bold", 9, INK)


def _decimated(canv, pts, min_step=0.25):
  last = None
  for p in pts:
    if last is None or abs(p[0] - last[0]) + abs(p[1] - last[1]) >= min_step:
      yield p
      last = p


def draw_paths(c, subpaths, min_x, min_y, ox, oy, s, color=INK, lw=0.7):
  c.setStrokeColor(color)
  c.setLineWidth(lw)
  c.setLineJoin(1)
  c.setLineCap(1)
  for xs, ys in subpaths:
    pts = [(ox + (x - min_x) * s, oy + (y - min_y) * s) for x, y in zip(xs, ys)]
    pts = list(_decimated(c, pts))
    if len(pts) < 2:
      continue
    p = c.beginPath()
    p.moveTo(*pts[0])
    for pt in pts[1:]:
      p.lineTo(*pt)
    c.drawPath(p, stroke=1, fill=0)


def dim_lines(c, ox, oy, w_pt, h_pt, w_in, h_in):
  c.setStrokeColor(MUTED)
  c.setLineWidth(0.5)
  yb = oy - 9
  c.line(ox, yb, ox + w_pt, yb)
  for xx in (ox, ox + w_pt):
    c.line(xx, yb - 3, xx, yb + 3)
  text(c, ox + w_pt / 2, yb - 11, f'{w_in:.2f}"', "Helvetica-Bold", 7.5, INK, align="center")
  xl = ox - 9
  c.line(xl, oy, xl, oy + h_pt)
  for yy in (oy, oy + h_pt):
    c.line(xl - 3, yy, xl + 3, yy)
  c.saveState()
  c.translate(xl - 5, oy + h_pt / 2)
  c.rotate(90)
  text(c, 0, 0, f'{h_in:.2f}"', "Helvetica-Bold", 7.5, INK, align="center")
  c.restoreState()


class PreviewPanel(Flowable):
  """Grey arched panel containing a white card with the part (or array) drawing."""

  def __init__(self, title, caption, width, height, part_w, part_h, subpaths,
               min_x, min_y, cols=1, rows=1, qty=1, gap=0.25, manual=False,
               draw_geo=True):
    super().__init__()
    self.title, self.caption = title, caption
    self.width, self.height = width, height
    self.part_w, self.part_h = part_w, part_h
    self.subpaths, self.min_x, self.min_y = subpaths, min_x, min_y
    self.cols, self.rows, self.qty, self.gap = cols, rows, qty, gap
    self.manual, self.draw_geo = manual, draw_geo

  def wrap(self, aw, ah):
    return self.width, self.height

  def draw(self):
    c, W, H = self.canv, self.width, self.height
    c.setFillColor(PANEL)
    c.drawPath(arch_path(c, 0, 0, W, H, tr=70, br=16, bl=16, tl=0), stroke=0, fill=1)
    text(c, 18, H - 20, self.title.upper(), "Helvetica-Bold", 7.5, RED, cs=1.8)
    text(c, 18, H - 32, self.caption, "Helvetica", 7.2, BROWN)
    ix, iy, iw, ih = 14, 14, W - 28, H - 54
    c.setFillColor(white)
    c.roundRect(ix, iy, iw, ih, 14, stroke=0, fill=1)

    cols, rows, gap = self.cols, self.rows, self.gap
    total_w = cols * self.part_w + (cols - 1) * gap
    total_h = rows * self.part_h + (rows - 1) * gap
    pad = 30
    s = min((iw - 2 * pad) / total_w, (ih - 2 * pad) / total_h)
    ox = ix + (iw - total_w * s) / 2
    oy = iy + (ih - total_h * s) / 2
    pw, ph = self.part_w * s, self.part_h * s
    n = 0
    for r in range(rows):
      for k in range(cols):
        if n >= self.qty:
          break
        n += 1
        cx = ox + k * (self.part_w + gap) * s
        cy = oy + r * (self.part_h + gap) * s
        if self.subpaths and self.draw_geo:
          c.setStrokeColor(RED)
          c.setLineWidth(0.5)
          c.setDash(3, 2)
          c.rect(cx, cy, pw, ph, stroke=1, fill=0)
          c.setDash()
          draw_paths(c, self.subpaths, self.min_x, self.min_y, cx, cy, s,
                     lw=max(0.35, min(1.0, 0.7)))
        else:
          c.setFillColor(PINK)
          c.setStrokeColor(RED)
          c.setLineWidth(0.8)
          c.rect(cx, cy, pw, ph, stroke=1, fill=1)
          if self.qty > 1 and total_w * s > 60 and pw > 14:
            text(c, cx + pw / 2, cy + ph / 2 - 3, str(n), "Helvetica-Bold",
                 min(9, pw / 2.2), RED, align="center")
    if not self.subpaths and self.qty == 1:
      text(c, ox + pw / 2, oy + ph / 2 - 3, "Manual entry - no CAD geometry supplied",
           "Helvetica-Oblique", 8, MUTED, align="center")
    dim_lines(c, ox, oy, total_w * s, total_h * s, total_w, total_h)


# ------------------------------------------------------------------
# donut chart
# ------------------------------------------------------------------
def cost_donut(items, width=190, height=140):
  items = [(n, v, col) for n, v, col in items if v > 0]
  d = Drawing(width, height)
  if not items:
    return d
  dn = Doughnut()
  dn.x, dn.y, dn.width, dn.height = 46, 40, 98, 98
  dn.data = [v for _, v, _ in items]
  dn.startAngle, dn.direction = 90, "clockwise"
  for i, (_, _, col) in enumerate(items):
    dn.slices[i].fillColor = col
    dn.slices[i].strokeColor = white
    dn.slices[i].strokeWidth = 1.6
  try:
    dn.innerRadiusFraction = 0.55
  except Exception:
    pass
  d.add(dn)
  total = sum(v for _, v, _ in items)
  n = len(items)
  col_w = width / min(n, 2)
  for i, (name, v, col) in enumerate(items):
    cx = (i % 2) * col_w + 6
    cy = 24 - (i // 2) * 13
    d.add(Rect(cx, cy, 7, 7, fillColor=col, strokeColor=None))
    d.add(String(cx + 11, cy + 0.5, f"{name} {v / total * 100:.0f}%", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=INK))
  return d


# ------------------------------------------------------------------
# main entry
# ------------------------------------------------------------------
def build_estimate_pdf(d, logo_path=None):
  """d keys: ref, date, material, thickness, gas, qty, source, layers, units_note,
  length, width, part_w, part_h, cols, rows, array_w, array_h, spacing_gap,
  area_sqft, efficiency, cut_length_pp, pierces_pp, total_cut_length, total_pierces,
  cost_per_in, cost_per_pierce, gas_rate, setup_rate, cut_price, pierce_price,
  gas_price, setup_price, total_price, est_cut_time_sec, subpaths, min_x, min_y,
  is_array, lead_in, mode ('manual' | 'upload')."""
  buf = io.BytesIO()
  ref, date_str = d["ref"], d["date"]
  doc = BaseDocTemplate(
      buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
      topMargin=MARGIN, bottomMargin=MARGIN,
      title=f"Warner Steel Laser Cutting Estimate {ref}", author="Warner Steel Sales, Inc.")
  first = Frame(MARGIN, 90, CONTENT_W, PAGE_H - 90 - (MARGIN + 20 + 130 + 8), id="f1",
                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
  later = Frame(MARGIN, 90, CONTENT_W, PAGE_H - 90 - (MARGIN + 32 + 12), id="f2",
                leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
  doc.addPageTemplates([
      PageTemplate(id="first", frames=[first], onPage=_first_page(logo_path, ref, date_str)),
      PageTemplate(id="later", frames=[later], onPage=_later_page(logo_path, ref, date_str)),
  ])

  qty = int(d["qty"])
  per_part = d["total_price"] / qty if qty else d["total_price"]
  small = ParagraphStyle("small", fontName="Helvetica", fontSize=7.4, leading=10.6, textColor=MUTED)
  note_h = ParagraphStyle("noteh", fontName="Helvetica-Bold", fontSize=6.6, leading=9,
                          textColor=RED, spaceAfter=3)
  cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.2, leading=10, textColor=INK)
  cell_b = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")

  story = [Spacer(1, 2), TotalBanner(d["total_price"], qty, per_part), Spacer(1, 14)]

  # ---- job specifications
  story += [SectionTitle("Job Specifications"), Spacer(1, 6)]
  est_t = d["est_cut_time_sec"]
  src = d["source"] or "Manual entry"
  layers = ", ".join(d.get("layers") or []) or "-"
  if d["mode"] != "upload":
    layers = "Totals entered manually"
  elif len(layers) > 60:
    layers = layers[:57] + "..."
  grid_txt = f'{d["cols"]} x {d["rows"]} grid, {d["spacing_gap"]:.2f}" gap'
  items = [
      ("Material", d["material"]), ("Thickness", d["thickness"]), ("Assist Gas", d["gas"]),
      ("Quantity", f"{qty} pc{'s' if qty != 1 else ''}"), ("Input Source", src), ("Active Layers", layers),
      ("Part / Array Bounds", f'{d["length"]:.2f}" L x {d["width"]:.2f}" W'),
      ("Array Footprint", f'{d["array_w"]:.2f}" x {d["array_h"]:.2f}"  ({grid_txt})'),
      ("Nestable Area", f'{d["area_sqft"]:.2f} sq ft'),
      ("Cut Length (per part)", f'{d["cut_length_pp"]:,.2f} in'),
      ("Pierces (per part)", f'{d["pierces_pp"]:,}'),
      ("Est. Total Cut Time", f"{est_t:.1f} sec  ({est_t / 60.0:.2f} min)"),
  ]
  story += [CardGrid(items), Spacer(1, 14)]

  # ---- cost breakdown + donut
  story += [SectionTitle("Cost Breakdown"), Spacer(1, 6)]
  rows = [[Paragraph("<b>ITEM</b>", ParagraphStyle("h", parent=cell, textColor=white, fontSize=6.8)),
           Paragraph("<b>QUANTITY</b>", ParagraphStyle("h2", parent=cell, textColor=white, fontSize=6.8)),
           Paragraph("<b>RATE</b>", ParagraphStyle("h3", parent=cell, textColor=white, fontSize=6.8)),
           Paragraph("<b>PRICE</b>", ParagraphStyle("h4", parent=cell, textColor=white, fontSize=6.8, alignment=2))]]
  def row(name, qtxt, rtxt, price):
    return [Paragraph(name, cell_b), Paragraph(qtxt, cell), Paragraph(rtxt, cell),
            Paragraph(money(price), ParagraphStyle("p", parent=cell_b, alignment=2))]
  rows += [
      row("Laser Cutting", f'{d["total_cut_length"]:,.1f} in', f'${d["cost_per_in"]:.3f} / in', d["cut_price"]),
      row("Pierces", f'{d["total_pierces"]:,}', f'${d["cost_per_pierce"]:.3f} / pierce', d["pierce_price"]),
      row("Assist Gas", plain(d["gas"]), f'${d["gas_rate"]:.3f} / in cut', d["gas_price"]),
      row("Setup / Material Area", f'{d["area_sqft"]:.2f} sq ft', f'${d["setup_rate"]:.3f} / sq ft', d["setup_price"]),
      [Paragraph("<b>TOTAL</b>", ParagraphStyle("t", parent=cell_b, textColor=RED)), "", "",
       Paragraph(money(d["total_price"]), ParagraphStyle("tp", parent=cell_b, textColor=RED, alignment=2, fontSize=10))],
  ]
  tw = 338
  tbl = Table(rows, colWidths=[104, 78, 92, 64], hAlign="LEFT")
  tbl.setStyle(TableStyle([
      ("BACKGROUND", (0, 0), (-1, 0), INK),
      ("ROWBACKGROUNDS", (0, 1), (-1, -2), [white, ZEBRA]),
      ("BACKGROUND", (0, -1), (-1, -1), PANEL),
      ("LINEBELOW", (0, 1), (-1, -2), 0.5, CARD_LINE),
      ("SPAN", (0, -1), (2, -1)),
      ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
      ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
      ("ROUNDEDCORNERS", [8, 8, 8, 8]),
      ("BOX", (0, 0), (-1, -1), 0.6, CARD_LINE),
  ]))
  donut = cost_donut([
      ("Cut", d["cut_price"], RED), ("Pierce", d["pierce_price"], INK),
      ("Gas", d["gas_price"], HexColor("#8a6d4b")), ("Setup", d["setup_price"], HexColor("#a8a8a8"))])
  outer = Table([[tbl, donut]], colWidths=[tw + 8, CONTENT_W - tw - 8])
  outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
  story += [outer, Spacer(1, 6)]

  # ---- page 2: previews
  story += [NextPageTemplate("later"), PageBreak()]
  subpaths = d.get("subpaths")
  manual = not subpaths
  mode_txt = ("Cut paths from the uploaded file (active layers only)" if not manual
              else "Manual entry - outline shown at the entered dimensions")
  show_array = qty > 1 and not d["is_array"]
  story += [SectionTitle("Cut Path Preview"), Spacer(1, 6),
            PreviewPanel("Single part profile",
                         f'{mode_txt}.  Bounds include a 0.75" alignment margin per side.',
                         CONTENT_W, 250 if show_array else 340, d["part_w"], d["part_h"], subpaths,
                         d["min_x"], d["min_y"], manual=manual),
            Spacer(1, 12)]

  if show_array:
    npts = sum(len(x) for x, _ in subpaths) * qty if subpaths else 0
    draw_geo = bool(subpaths) and npts <= 250000
    story += [SectionTitle("Array Layout"), Spacer(1, 6),
              PreviewPanel(f'{d["cols"]} x {d["rows"]} grid  ·  {qty} parts',
                           f'{d["spacing_gap"]:.2f}" spacing between parts.  Footprint {d["array_w"]:.2f}" x {d["array_h"]:.2f}".',
                           CONTENT_W, 205, d["part_w"], d["part_h"], subpaths, d["min_x"], d["min_y"],
                           cols=d["cols"], rows=d["rows"], qty=qty, gap=d["spacing_gap"],
                           manual=manual, draw_geo=draw_geo),
              Spacer(1, 8)]
  elif d["is_array"]:
    story += [Paragraph("The uploaded toolpath already contains the full nest, so no additional array is applied.", small),
              Spacer(1, 10)]

  # ---- calculation notes
  notes = []
  if d["mode"] == "upload" and d.get("lead_in"):
    notes.append(f'Cut length includes a {d["lead_in"]:.2f}" lead-in allowance per pierce.')
  elif d["mode"] == "upload":
    notes.append("Cut length is taken directly from the toolpath (lead-ins already included).")
  else:
    notes.append("Cut length and pierces are the totals entered, divided by the order quantity.")
  notes.append('Part / array bounds include a 1.5" alignment margin (0.75" per side).')
  if qty > 1 and not d["is_array"]:
    notes.append(f'Nestable area applies a shape-efficiency factor of {d["efficiency"]:.3f} to the grid footprint.')
  if d.get("units_note"):
    notes.append(d["units_note"])
  notes.append("This is an estimate based on the supplied data; final pricing is subject to review by Warner Steel.")
  story.append(KeepTogether([Paragraph("CALCULATION NOTES", note_h)] +
                            [Paragraph("•&nbsp;&nbsp;" + plain(n).replace("&", "&amp;"), small) for n in notes]))

  doc.build(story)
  return buf.getvalue()
