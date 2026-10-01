import math
import os
import re
import tempfile

# Geometry & Vector Libraries
try:
  import ezdxf
  from ezdxf import path

  EZDXF_AVAILABLE = True
except ImportError:
  EZDXF_AVAILABLE = False

try:
  from svgpathtools import svg2paths

  SVG_AVAILABLE = True
except ImportError:
  SVG_AVAILABLE = False

try:
  from shapely.geometry import MultiPoint

  SHAPELY_AVAILABLE = True
except ImportError:
  SHAPELY_AVAILABLE = False


# ------------------------------------------------------
# SPATIAL HASH CONTOUR STITCHING (O(N) EFFICIENCY)
# ------------------------------------------------------
def stitch_subpaths_into_contours(subpath_list, tolerance=0.005):
  """Stitches raw line/arc/spline segments into continuous closed/open contours using spatial indexing."""
  if not subpath_list:
    return [], 0

  segments = []
  for item in subpath_list:
    xs, ys = item["xs"], item["ys"]
    if len(xs) >= 2:
      segments.append({
          "xs": list(xs),
          "ys": list(ys),
          "start": (round(xs[0], 4), round(ys[0], 4)),
          "end": (round(xs[-1], 4), round(ys[-1], 4)),
          "length": item["length"],
      })

  contours = []
  point_map = {}

  for idx, seg in enumerate(segments):
    point_map.setdefault(seg["start"], []).append((idx, "start"))
    point_map.setdefault(seg["end"], []).append((idx, "end"))

  visited = set()

  for idx in range(len(segments)):
    if idx in visited:
      continue

    visited.add(idx)
    curr = segments[idx]
    curr_xs = list(curr["xs"])
    curr_ys = list(curr["ys"])

    changed = True
    while changed:
      changed = False
      head = (round(curr_xs[0], 4), round(curr_ys[0], 4))
      tail = (round(curr_xs[-1], 4), round(curr_ys[-1], 4))

      # Match Tail
      for n_idx, pos in point_map.get(tail, []):
        if n_idx not in visited:
          visited.add(n_idx)
          seg = segments[n_idx]
          if pos == "start":
            curr_xs.extend(seg["xs"][1:])
            curr_ys.extend(seg["ys"][1:])
          else:
            curr_xs.extend(seg["xs"][::-1][1:])
            curr_ys.extend(seg["ys"][::-1][1:])
          changed = True
          break

      if changed:
        continue

      # Match Head
      for n_idx, pos in point_map.get(head, []):
        if n_idx not in visited:
          visited.add(n_idx)
          seg = segments[n_idx]
          if pos == "end":
            curr_xs = seg["xs"][:-1] + curr_xs
            curr_ys = seg["ys"][:-1] + curr_ys
          else:
            curr_xs = seg["xs"][::-1][:-1] + curr_xs
            curr_ys = seg["xs"][::-1][:-1] + curr_ys
          changed = True
          break

    c_len = sum(
        math.hypot(curr_xs[i + 1] - curr_xs[i], curr_ys[i + 1] - curr_ys[i])
        for i in range(len(curr_xs) - 1)
    )

    contours.append({
        "xs": curr_xs,
        "ys": curr_ys,
        "length": c_len,
    })

  return contours, len(contours)


# ------------------------------------------------------
# DXF PARSER
# ------------------------------------------------------
def parse_dxf_layers(file_bytes, unit_scale=None):
  if not EZDXF_AVAILABLE:
    return None, "ezdxf library is not installed."

  try:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
      tmp.write(file_bytes)
      tmp_path = tmp.name

    doc = ezdxf.readfile(tmp_path)
    os.remove(tmp_path)

    # Auto-detect header units if requested ($INSUNITS: 4 = mm, 1 = inches)
    if unit_scale is None:
      insunits = doc.header.get("$INSUNITS", 1)
      unit_scale = 1.0 / 25.4 if insunits == 4 else 1.0

    msp = doc.modelspace()
    layer_dict = {}
    seen_signatures = set()

    non_cut_keywords = ["BEND", "EXTENT", "TEXT", "DIM", "MARK", "REF"]
    valid_types = (
        "LINE",
        "ARC",
        "CIRCLE",
        "ELLIPSE",
        "LWPOLYLINE",
        "POLYLINE",
        "SPLINE",
    )

    for entity in msp:
      dxftype = entity.dxftype()
      if dxftype not in valid_types:
        continue

      layer_name = str(entity.dxf.layer).strip()
      if any(kw in layer_name.upper() for kw in non_cut_keywords):
        continue

      if layer_name not in layer_dict:
        layer_dict[layer_name] = []

      extrusion_z = getattr(entity.dxf, "extrusion", (0, 0, 1))[2]
      flip_x = -1.0 if extrusion_z < 0 else 1.0

      try:
        p = path.make_path(entity)
        for single_p in path.single_paths([p]):
          vertices = list(single_p.flattening(distance=0.002 / unit_scale))
          if len(vertices) >= 2:
            px = [v.x * flip_x * unit_scale for v in vertices]
            py = [v.y * unit_scale for v in vertices]

            sig = (
                round(px[0], 3),
                round(py[0], 3),
                round(px[-1], 3),
                round(py[-1], 3),
                len(px),
            )
            rev_sig = (
                round(px[-1], 3),
                round(py[-1], 3),
                round(px[0], 3),
                round(py[0], 3),
                len(px),
            )

            if sig in seen_signatures or rev_sig in seen_signatures:
              continue

            seen_signatures.add(sig)

            p_len = sum(
                math.hypot(px[i + 1] - px[i], py[i + 1] - py[i])
                for i in range(len(px) - 1)
            )

            if p_len > 0.001:
              layer_dict[layer_name].append({
                  "xs": px,
                  "ys": py,
                  "length": p_len,
              })
      except Exception:
        pass

    layer_dict = {k: v for k, v in layer_dict.items() if len(v) > 0}

    if not layer_dict:
      return None, "No valid geometric entities found in DXF file."

    default_layers = list(layer_dict.keys())

    return {
        "all_layers": list(layer_dict.keys()),
        "default_layers": default_layers,
        "layer_dict": layer_dict,
        "lead_in": 0.5,
        "stitch": True,
    }, None

  except Exception as e:
    return None, f"Error parsing DXF file: {str(e)}"


# ------------------------------------------------------
# TAP / G-CODE PARSER
# ------------------------------------------------------
def parse_tap_geometry(file_bytes, unit_scale=None, margin_per_side=0.75):
  try:
    content = file_bytes.decode("utf-8", errors="ignore")
    lines = content.splitlines()

    total_cut_length = 0.0
    laser_on = False
    curr_x, curr_y = 0.0, 0.0
    active_g_mode = "G0"
    is_metric = False

    all_xs, all_ys = [], []
    subpaths = []
    current_subpath_x = []
    current_subpath_y = []
    pierces = 0

    word_pattern = re.compile(r"([A-Z])\s*(-?\d+\.?\d*)", re.IGNORECASE)

    def finalize_subpath():
      nonlocal current_subpath_x, current_subpath_y, subpaths
      if len(current_subpath_x) >= 2:
        sub_len = sum(
            math.hypot(
                current_subpath_x[k + 1] - current_subpath_x[k],
                current_subpath_y[k + 1] - current_subpath_y[k],
            )
            for k in range(len(current_subpath_x) - 1)
        )
        if sub_len > 0.001:
          subpaths.append((list(current_subpath_x), list(current_subpath_y)))
      current_subpath_x = []
      current_subpath_y = []

    for line in lines:
      line_clean = re.sub(r"\(.*?\)", "", line)
      line_clean = re.sub(r";.*$", "", line_clean).strip().upper()

      if not line_clean or line_clean.startswith("%"):
        continue

      tokens = word_pattern.findall(line_clean)
      if not tokens:
        continue

      words = {letter.upper(): float(val) for letter, val in tokens}

      if "G" in words:
        g_val = int(words["G"])
        if g_val == 20:
          is_metric = False
        elif g_val == 21:
          is_metric = True

      effective_scale = (
          (1.0 / 25.4 if is_metric else 1.0)
          if unit_scale is None
          else unit_scale
      )

      if "M" in words:
        m_val = int(words["M"])
        if m_val in (3, 4, 7, 8, 106):
          finalize_subpath()
          laser_on = True
          pierces += 1
          current_subpath_x = [curr_x]
          current_subpath_y = [curr_y]
        elif m_val in (5, 9, 107):
          finalize_subpath()
          laser_on = False

      if "G" in words:
        g_val = int(words["G"])
        if g_val == 0:
          finalize_subpath()
          active_g_mode = "G0"
        elif g_val == 1:
          active_g_mode = "G1"
        elif g_val == 2:
          active_g_mode = "G2"
        elif g_val == 3:
          active_g_mode = "G3"

      has_coords = any(k in words for k in ("X", "Y", "I", "J", "R"))

      if has_coords:
        new_x = words["X"] * effective_scale if "X" in words else curr_x
        new_y = words["Y"] * effective_scale if "Y" in words else curr_y

        if active_g_mode == "G0":
          finalize_subpath()
          curr_x, curr_y = new_x, new_y
          continue

        if laser_on and active_g_mode in ("G1", "G2", "G3"):
          if not current_subpath_x:
            current_subpath_x = [curr_x]
            current_subpath_y = [curr_y]

          if active_g_mode == "G1" or not ("I" in words or "J" in words):
            dist = math.hypot(new_x - curr_x, new_y - curr_y)
            if dist > 0:
              total_cut_length += dist
              current_subpath_x.append(new_x)
              current_subpath_y.append(new_y)
              all_xs.append(new_x)
              all_ys.append(new_y)
          else:
            i_val = words.get("I", 0.0) * effective_scale
            j_val = words.get("J", 0.0) * effective_scale

            center_x = curr_x + i_val
            center_y = curr_y + j_val

            radius = math.hypot(curr_x - center_x, curr_y - center_y)
            start_angle = math.atan2(curr_y - center_y, curr_x - center_x)

            if "X" not in words and "Y" not in words:
              angle_sweep = 2 * math.pi
              end_angle = (
                  start_angle - angle_sweep
                  if active_g_mode == "G2"
                  else start_angle + angle_sweep
              )
            else:
              end_angle = math.atan2(new_y - center_y, new_x - center_x)
              if active_g_mode == "G2":
                if end_angle >= start_angle:
                  end_angle -= 2 * math.pi
              else:
                if end_angle <= start_angle:
                  end_angle += 2 * math.pi
              angle_sweep = abs(end_angle - start_angle)

            arc_len = radius * angle_sweep

            if arc_len > 0:
              total_cut_length += arc_len
              num_steps = max(16, int(arc_len * 12))

              for s in range(1, num_steps + 1):
                t = start_angle + (end_angle - start_angle) * (s / num_steps)
                px = center_x + radius * math.cos(t)
                py = center_y + radius * math.sin(t)
                current_subpath_x.append(px)
                current_subpath_y.append(py)
                all_xs.append(px)
                all_ys.append(py)

        curr_x, curr_y = new_x, new_y

    finalize_subpath()

    if not all_xs or not subpaths:
      return None, "No active toolpath cutting moves found in TAP file."

    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)

    part_w = (max_x - min_x) + (margin_per_side * 2)
    part_h = (max_y - min_y) + (margin_per_side * 2)

    return {
        "all_layers": ["TAP Cut Toolpath"],
        "default_layers": ["TAP Cut Toolpath"],
        "layer_dict": {
            "TAP Cut Toolpath": [{
                "xs": xs,
                "ys": ys,
                "length": sum(
                    math.hypot(xs[k + 1] - xs[k], ys[k + 1] - ys[k])
                    for k in range(len(xs) - 1)
                ),
            } for xs, ys in subpaths]
        },
        "cut_length": round(total_cut_length, 2),
        "pierces": pierces,
        "length": round(max(part_w, part_h), 2),
        "width": round(min(part_w, part_h), 2),
        "subpaths": subpaths,
        "part_w": part_w,
        "part_h": part_h,
        "min_x": min_x - margin_per_side,
        "min_y": min_y - margin_per_side,
        "lead_in": 0.0,
        "stitch": False,
    }, None

  except Exception as e:
    return None, f"Error parsing TAP file: {str(e)}"


# ------------------------------------------------------
# SVG PARSER
# ------------------------------------------------------
def parse_svg_geometry(file_bytes, unit_scale=None):
  if not SVG_AVAILABLE:
    return None, "svgpathtools library is not installed."

  try:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as tmp:
      tmp.write(file_bytes)
      tmp_path = tmp.name

    paths, _ = svg2paths(tmp_path)
    os.remove(tmp_path)

    if not paths:
      return None, "No valid vector paths found in SVG file."

    scale = 1.0 if unit_scale is None else unit_scale
    total_length = 0.0
    subpaths_to_plot = []
    all_xs, all_ys = [], []

    for p in paths:
      try:
        total_length += p.length() * scale
        for subpath in p.continuous_subpaths():
          path_pts_x, path_pts_y = [], []
          num_samples = max(24, int(subpath.length() * scale * 10))

          for i in range(num_samples + 1):
            point = subpath.point(i / num_samples)
            px = point.real * scale
            py = -point.imag * scale
            path_pts_x.append(px)
            path_pts_y.append(py)
            all_xs.append(px)
            all_ys.append(py)

          subpaths_to_plot.append((path_pts_x, path_pts_y))
      except Exception:
        pass

    if not all_xs:
      return None, "Could not extract bounding box from SVG."

    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)

    part_w = max_x - min_x
    part_h = max_y - min_y

    return {
        "all_layers": ["SVG Profile"],
        "default_layers": ["SVG Profile"],
        "layer_dict": {
            "SVG Profile": [{
                "xs": xs,
                "ys": ys,
                "length": sum(
                    math.hypot(xs[k + 1] - xs[k], ys[k + 1] - ys[k])
                    for k in range(len(xs) - 1)
                ),
            } for xs, ys in subpaths_to_plot]
        },
        "lead_in": 0.5,
        "stitch": True,
    }, None

  except Exception as e:
    return None, f"Error parsing SVG file: {str(e)}"


# ------------------------------------------------------
# DYNAMIC RECALCULATION HELPER
# ------------------------------------------------------
def recalculate_active_geometry(
    layer_dict,
    selected_layers,
    lead_in_per_pierce=0.5,
    margin_per_side=0.75,
    stitch=True,
):
  raw_subpaths = []
  for layer_name in selected_layers:
    if layer_name in layer_dict:
      raw_subpaths.extend(layer_dict[layer_name])

  if not raw_subpaths:
    return {
        "cut_length": 0.0,
        "pierces": 0,
        "length": 0.0,
        "width": 0.0,
        "hull_ratio": 1.0,
        "subpaths": [],
        "part_w": 0.0,
        "part_h": 0.0,
        "min_x": 0.0,
        "min_y": 0.0,
    }

  if stitch:
    contours, total_pierces = stitch_subpaths_into_contours(
        raw_subpaths, tolerance=0.005
    )
  else:
    contours = [
        {"xs": s["xs"], "ys": s["ys"], "length": s["length"]}
        for s in raw_subpaths
    ]
    total_pierces = len(raw_subpaths)

  all_xs, all_ys = [], []
  raw_cut_length = 0.0
  active_subpaths = []

  for c in contours:
    raw_cut_length += c["length"]
    active_subpaths.append((c["xs"], c["ys"]))
    all_xs.extend(c["xs"])
    all_ys.extend(c["ys"])

  min_x, max_x = min(all_xs), max(all_xs)
  min_y, max_y = min(all_ys), max(all_ys)

  part_w = (max_x - min_x) + (margin_per_side * 2)
  part_h = (max_y - min_y) + (margin_per_side * 2)

  total_effective_cut_length = raw_cut_length + (
      total_pierces * lead_in_per_pierce
  )

  hull_ratio = 1.0
  if SHAPELY_AVAILABLE and len(all_xs) >= 3 and part_w > 0 and part_h > 0:
    try:
      pts = list(zip(all_xs, all_ys))
      mp = MultiPoint(pts)
      bbox_area = part_w * part_h
      if bbox_area > 0:
        hull_ratio = max(0.2, min(mp.convex_hull.area / bbox_area, 1.0))
    except Exception:
      hull_ratio = 1.0

  return {
      "cut_length": round(max(total_effective_cut_length, 0.0), 2),
      "pierces": max(total_pierces, 1),
      "length": round(max(part_w, part_h), 2),
      "width": round(min(part_w, part_h), 2),
      "hull_ratio": hull_ratio,
      "subpaths": active_subpaths,
      "part_w": part_w,
      "part_h": part_h,
      "min_x": min_x - margin_per_side,
      "min_y": min_y - margin_per_side,
  }