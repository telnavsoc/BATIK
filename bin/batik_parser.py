# FILE: bin/batik_parser.py
# ================================================================
# BATIK PARSER V46 (HYBRID: V44 FOR LOC/GP + V40.1 INDEX FOR MM/OM)
# ================================================================
import re

def insert_space_unit(value):
    """Menambahkan spasi antara angka dan unit. Contoh: 30.0% -> 30.0 %"""
    if not value or value == "-": return value
    if " " in value: return value
    return re.sub(r"([\d\.]+)([a-zA-Z%°]+)", r"\1 \2", value)

def detect_active_tx(tool_type, raw_text):
    """Deteksi Tx Aktif."""
    if "DVOR" in tool_type or "220" in tool_type:
        if re.search(r"\[PDF_EVIDENCE\].*TX2", raw_text, re.IGNORECASE): return 2
        if re.search(r"\[PDF_EVIDENCE\].*TX1", raw_text, re.IGNORECASE): return 1
        if re.search(r"Active\s*TX\s*[:\-]?\s*2", raw_text, re.IGNORECASE): return 2
        return 1 
    elif "DME" in tool_type:
        lines = raw_text.splitlines()
        for i in range(min(10, len(lines))):
            line = lines[i]
            if "#Active" in line or "# Active" in line:
                if "TXP2" in line or "TX2" in line or "TXP 2" in line: return 2
                return 1 
        return 1
    if tool_type in ["LOCALIZER", "GLIDEPATH", "MM", "OM", "PMDT"]:
        if re.search(r"^\s*G\s+Tx\s+2", raw_text, re.MULTILINE): return 2
        elif re.search(r"^\s*G\s+Tx\s+1", raw_text, re.MULTILINE): return 1
    return 1

def parse_maru_data(tool_name, raw_text):
    active_tx = detect_active_tx(tool_name, raw_text)
    rows = []
    
    if "DVOR" in tool_name.upper() or "220" in tool_name:
        data = {}
        relevant_text = raw_text.split("MON Major Measurement")[-1] if "MON Major Measurement" in raw_text else raw_text
        lines = relevant_text.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith(("[", "#", ";")): continue
            parts = re.split(r'\s{2,}', line)
            if len(parts) >= 2:
                k = parts[0].strip()
                v1 = insert_space_unit(parts[1].strip())
                v2 = insert_space_unit(parts[2].strip()) if len(parts) > 2 else ""
                data[k.lower()] = {"m1": v1, "m2": v2}
        schema = ["Status", "IDENT Code", "CARRIER Frequency", "USB Frequency", "LSB Frequency", "CARRIER Output Power", "RF Input Level", "Azimuth", "9960Hz FM Index", "30Hz AM Modulation Depth", "9960Hz AM Modulation Depth", "1020Hz AM Modulation Depth"]
        for req in schema:
            for k_raw, vals in data.items():
                if req.lower() in k_raw:
                    if "LSB" in req and "lsb" not in k_raw: continue
                    if "USB" in req and "usb" not in k_raw: continue
                    if "CARRIER" in req and "carrier" not in k_raw: continue
                    rows.append({"Parameter": req, "Monitor 1": vals["m1"], "Monitor 2": vals["m2"]})
                    break
        return rows, active_tx

    if "DME" in tool_name or "320" in tool_name:
        data_map = {}
        lines = raw_text.splitlines()
        in_monitor_section = False
        target_params = ["IDENT Code", "Output Power", "Frequency", "System Delay", "Reply Pulse Spacing", "Reply Efficiency", "Reply Pulse Rate", "Reply Pulse Rise Time", "Reply Pulse Decay Time", "Reply Pulse Duration"]
        for line in lines:
            clean = line.strip()
            if "MON Major Measurement" in clean: in_monitor_section = True; continue
            if in_monitor_section and clean.startswith(";") and "MON Major" not in clean: in_monitor_section = False
            if in_monitor_section:
                parts = re.split(r'\s{2,}', clean)
                if len(parts) >= 2:
                    key = parts[0].strip()
                    val1 = parts[1].strip()
                    val2 = parts[2].strip() if len(parts) > 2 else "-"
                    data_map[key] = {"m1": insert_space_unit(val1), "m2": insert_space_unit(val2)}
        for p in target_params:
            found = False
            for k_log in data_map:
                if k_log.startswith(p):
                    rows.append({"Parameter": p, "Monitor 1": data_map[k_log]["m1"], "Monitor 2": data_map[k_log]["m2"]})
                    found = True; break
            if not found: rows.append({"Parameter": p, "Monitor 1": "-", "Monitor 2": "-"})
        return rows, active_tx

    if tool_name in ["LOCALIZER", "GLIDEPATH", "LOC", "GP"]:
        return parse_pmdt_loc_gp(tool_name, raw_text)
    else:
        return parse_pmdt_mm_om(raw_text)

# =========================================================================
# LOGIKA V44: Right-to-Left Parsing (Cocok untuk LOC & GP)
# =========================================================================
def parse_pmdt_loc_gp(tool_type, raw_text):
    active_tx = detect_active_tx(tool_type, raw_text)
    rows = []
    lines = raw_text.splitlines()
    section_lines = {"Course": [], "Clearance": [], "General": []}
    current_section = "General"
    
    for line in lines:
        clean = line.strip()
        if not clean: continue
        if clean.lower().startswith("course"): current_section = "Course"
        elif clean.lower().startswith("clearance"): current_section = "Clearance"
        section_lines[current_section].append(clean)
        section_lines["General"].append(clean)

    targets = []
    if tool_type == "LOCALIZER" or tool_type == "LOC":
        targets = [
            ("Centerline RF Level", "Centerline RF Level", "Course"),
            ("Centerline DDM", "Centerline DDM", "Course"),
            ("Centerline SDM", "Centerline SDM", "Course"),
            ("Ident Mod Percent", "Ident Mod Percent", "Course"),
            ("Width DDM", "Width DDM", "Course"),
            ("Ident Status", "Ident Status", "Course"),
            ("RF Level", "RF Level", "Clearance"),
            ("Clearance 1 DDM", "Clearance 1 DDM", "Clearance"),
            ("SDM", "SDM", "Clearance"),
            ("Ident Mod Percent", "Ident Mod Percent", "Clearance"),
            ("Clearance 2 DDM", "Clearance 2 DDM", "Clearance"),
            ("Ident Status", "Ident Status", "Clearance"),
            ("RF Freq Difference", "RF Freq Difference", "General"),
            ("Antenna Fault", "Antenna Fault", "General")
        ]
    else: # GLIDEPATH
        targets = [
            ("Path RF Level", "Path RF Level", "Course"),
            ("Path DDM", "Path DDM", "Course"),
            ("Path SDM", "Path SDM", "Course"),
            ("Width DDM", "Width DDM", "Course"),
            ("RF Level", "RF Level", "Clearance"),
            ("150Hz Mod Percent", "150", "Clearance"), 
            ("RF Freq Difference", "RF Freq Difference", "General")
        ]

    for sheet_key, file_key, section in targets:
        m1, m2 = "-", "-"
        found_line = None
        search_clean = file_key.lower().replace(" ", "")
        
        for line in section_lines.get(section, []):
            line_clean = line.lower().replace(" ", "")
            if line_clean.startswith(search_clean):
                found_line = line
                break
        
        if found_line:
            # LOGIKA V44: BACA DARI KANAN (AMPUH UNTUK 150 HZ)
            parts = [p for p in re.split(r'\s{2,}', found_line.strip()) if p.strip()]
            
            if len(parts) >= 3:
                last_token = parts[-1]
                is_value_pattern = r"^[-+]?[\d\.]+$"
                is_status_word = last_token in ["Normal", "Alarm", "Open", "Short", "_"]
                is_number = re.match(is_value_pattern, last_token)
                
                raw_v1, raw_v2, unit = "-", "-", ""

                if is_number or is_status_word:
                    raw_v2 = parts[-1]
                    raw_v1 = parts[-2]
                    unit = ""
                else:
                    if len(parts) >= 4:
                        raw_v2 = parts[-2]
                        raw_v1 = parts[-3]
                        unit = last_token
                    else:
                        raw_v2 = parts[-2]
                        raw_v1 = "-"
                        unit = last_token

                if raw_v1 in ["_", "-"] or raw_v1.isalpha(): m1 = raw_v1
                else: m1 = f"{raw_v1} {unit}".strip()
                
                if raw_v2 in ["_", "-"] or raw_v2.isalpha(): m2 = raw_v2
                else: m2 = f"{raw_v2} {unit}".strip()

                if "Status" in sheet_key or "Fault" in sheet_key:
                    m1 = raw_v1.capitalize()
                    m2 = raw_v2.capitalize()

        rows.append({"Parameter": sheet_key, "Monitor 1": m1, "Monitor 2": m2})

    return rows, active_tx

# =========================================================================
# LOGIKA V40.1 Modified: Index Selection (Cocok untuk MM & OM)
# =========================================================================
def parse_pmdt_mm_om(raw_text):
    active_tx = detect_active_tx("MM", raw_text)
    mon1, mon2 = {}, {}
    curr_mon = 0
    
    for line in raw_text.splitlines():
        if "Monitor 1" in line: curr_mon = 1; continue
        if "Monitor 2" in line: curr_mon = 2; continue
        
        # Cari baris yang mengandung Parameter
        if "RF Level" in line or "Ident Modulation" in line:
            # Ambil semua angka dalam baris
            floats = re.findall(r"[-+]?\d*\.\d+|\d+", line)
            
            # FORMAT MM/OM: [AlarmLow, PreLow, DATA, PreHigh, AlarmHigh]
            # Data ada di urutan ke-3 (Index 2)
            if len(floats) >= 3:
                data_val = floats[2] 
                
                unit = ""
                if line.strip().endswith("dB"): unit = "dB"
                elif line.strip().endswith("%"): unit = "%"
                full_val = f"{data_val} {unit}".strip()
                
                param = "RF Level" if "RF Level" in line else "Ident Modulation"
                if curr_mon == 1: mon1[param] = full_val
                elif curr_mon == 2: mon2[param] = full_val

    rows = []
    for req in ["RF Level", "Ident Modulation"]:
        v1 = mon1.get(req, "-")
        v2 = mon2.get(req, "-")
        rows.append({"Parameter": req, "Monitor 1": v1, "Monitor 2": v2})
        
    return rows, active_tx