# FILE: bin/batik_parser.py
# =============================================================================
# BATIK PARSER V20.1 (ROBUST SECTION DETECTION)
# =============================================================================
import re

def normalize_with_unit(val):
    """Menstandarisasi nilai agar memiliki satuan dengan spasi."""
    if not val or val.strip() in ["-", "", "_"]: return "-"
    val = val.strip()
    
    # Jika hanya huruf (seperti NORMAL, Enabled), biarkan
    if re.match(r"^[A-Za-z\s/]+$", val) and not any(c.isdigit() for c in val):
        return val

    # Tambahkan spasi sebelum satuan
    val = re.sub(r"\s*(Watts|Watt|W)\b", " W", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(Volts|Volt|V)\b", " V", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(Amps|Amp|A)\b", " A", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(degs|deg)\b", " deg", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(%)\b", " %", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(Hz)\b", "Hz", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(MHz)\b", " MHz", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(DDM)\b", " DDM", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(dB)\b", " dB", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(usec)\b", " usec", val, flags=re.IGNORECASE)
    val = re.sub(r"\s*(pp/s)\b", " pp/s", val, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", val).strip()

# =============================================================================
# DEFINISI URUTAN PARAMETER
# =============================================================================
ORDERED_PARAMS = {
    "DVOR": [
        "Active TX", 
        "Status", "IDENT Code", "CARRIER Frequency", "USB Frequency", "LSB Frequency",
        "CARRIER Output Power", "RF Input Level", "Azimuth", "9960Hz FM Index",
        "30Hz AM Modulation Depth", "9960Hz AM Modulation Depth", "1020Hz AM Modulation Depth",
        "USB SIN Output Power", "USB COS Output Power", "LSB SIN Output Power", "LSB COS Output Power",
        "CPA Temperature", "MSG Temperature",
        "DC +5V", "DC +7V", "DC +15V", "DC +28V", "DC -15V",
        "Current DC +5V", "Current DC +7V", "Current DC +15V", "Current DC +28V", "Current DC -15V",
        "AC +28V", "Current AC +28V", "Battery +24V", "Current Battery +24V"
    ],
    "DME": [
        "Active TX",
        "IDENT Code", "Output Power", "Frequency", "System Delay", "Reply Pulse Spacing",
        "Reply Efficiency", "Reply Pulse Rate", "Reply Pulse Rise Time", "Reply Pulse Decay Time",
        "Reply Pulse Duration", "HPA Temperature", "LPA Temperature",
        "AC/DC Status", "AC/DC Voltage", "AC/DC Current",
        "DC/DC Status", "DC/DC Voltage", "DC/DC Current",
        "Battery Status", "Battery Voltage", "Battery Current"
    ],
    "LOC": [
        "Antenna Select", "Main Select", "Transmitter On",
        "Course - Centerline RF Level", "Course - Centerline DDM", "Course - Centerline SDM",
        "Course - Ident Mod Percent", "Course - Width DDM", "Course - Ident Status",
        "Clearance - RF Level", "Clearance - Clearance 1 DDM", "Clearance - SDM",
        "Clearance - Ident Mod Percent", "Clearance - Clearance 2 DDM", "Clearance - Ident Status",
        "Clearance - RF Freq Difference", "Clearance - Antenna Fault",
        "Course CSB Forward Power", "Course CSB Reflected Power",
        "Course SBO Forward Power", "Course SBO Reflected Power",
        "Clearance CSB Forward Power", "Clearance CSB Reflected Power",
        "Clearance SBO Forward Power", "Clearance SBO Reflected Power",
        "Standby Course CSB Forward Power", "Standby Course SBO Forward Power",
        "Standby Clearance CSB Forward Power", "Standby Clearance SBO Forward Power"
    ],
    "GP": [
        "Antenna Select", "Main Select", "Transmitter On",
        "Course - Path RF Level", "Course - Path DDM", "Course - Path SDM", "Course - Width DDM",
        "Clearance - RF Level", "Clearance - 150Hz Mod Percent", "Clearance - Synth Lock", "Clearance - RF Freq Difference",
        "Course CSB Forward Power", "Course CSB Reflected Power",
        "Course SBO Forward Power", "Course SBO Reflected Power",
        "Clearance Forward Power", "Clearance Reflected Power",
        "Standby Course CSB Forward Power", "Standby Course SBO Forward Power",
        "Standby Clearance Forward Power",
        "Upper Antenna Forward Power", "Middle Antenna Forward Power", "Lower Antenna Forward Power"
    ],
    "MM": [
        "Antenna Select", "Main Select", "Transmitter On", "RF Level", "Ident Modulation",
        "Transmitter 1 Forward Power", "Transmitter 1 Reflected Power", "Transmitter 1 VSWR",
        "Transmitter 2 Forward Power", "Transmitter 2 Reflected Power", "Transmitter 2 VSWR"
    ],
    "OM": [
        "Antenna Select", "Main Select", "Transmitter On", "RF Level", "Ident Modulation",
        "Transmitter 1 Forward Power", "Transmitter 1 Reflected Power", "Transmitter 1 VSWR",
        "Transmitter 2 Forward Power", "Transmitter 2 Reflected Power", "Transmitter 2 VSWR"
    ]
}

# =============================================================================
# 1. PARSER MARU (DVOR & DME) - REVISED & ROBUST
# =============================================================================
def parse_maru_data(station_type, raw_text):
    data_pool = {}
    
    # Pre-processing untuk memperbaiki format LPA Temperature yang sering menempel
    if "DME" in station_type:
        raw_text = re.sub(r"(\d)\s*(LPA Temperature)", r"\1\n\2", raw_text)
    
    # Deteksi Active TX (Sederhana)
    active_tx = 1
    if re.search(r"Active\s*TX.*?TX2", raw_text, re.IGNORECASE): active_tx = 2
    if re.search(r"Active\s*TXP.*?TXP2", raw_text, re.IGNORECASE): active_tx = 2
    
    data_pool["Active TX"] = {"m1": str(active_tx), "m2": "-"}

    lines = raw_text.splitlines()
    current_section = "General"
    pattern_double = re.compile(r"^(.+?)\s{2,}(.+?)\s{2,}(.+)$")
    
    # [DAFTAR WAJIB] Parameter ini HANYA boleh diambil jika section mengandung kata "MON Major Measurement"
    # Ini mencegah data 'Output Power' tertimpa oleh nilai dari section lain (misal Configuration)
    strict_mon_params = [
        "IDENT Code", "Output Power", "Frequency", "System Delay",
        "Reply Pulse Spacing", "Reply Efficiency", "Reply Pulse Rate",
        "Reply Pulse Rise Time", "Reply Pulse Decay Time", "Reply Pulse Duration"
    ]
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"): continue
        
        # [FIX 1] Deteksi Section Header yang lebih ROBUST
        # Kita anggap semua baris yang diawali ";" adalah section header.
        # Kita buang tanda ";" dan karakter panah (jika ada, atau jika error encoding)
        if line.startswith(";"):
            # Ambil teks setelah tanda ;
            raw_sec = line.lstrip(";").strip()
            # Bersihkan karakter non-huruf di awal (misal sisa panah yang jadi kotak/tanda tanya)
            # Kita cukup ambil raw_sec, tapi untuk pastikan section match, kita pakai string matching
            current_section = raw_sec
            continue

        # Deteksi Section Utama [Nama Section]
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
            
        # Fallback untuk format lama (Status lines)
        if "Status" in line and ";" in line and not line.startswith(";"): 
            match = re.search(r"([A-Za-z0-9/]+\s+Status)", line)
            if match: current_section = match.group(1).strip(); continue
        
        # Parsing Data Nilai (DVOR Power Supply)
        if "DVOR" in station_type and ("Status" in current_section) and ("DC" in current_section or "Battery" in current_section):
            matches = re.findall(r"-\s+([A-Za-z0-9\+\-\s]+?)\s+([-\d\.]+\s*V)\s+([-\d\.]+\s*A)", line)
            if matches:
                for label, volt, ampere in matches:
                    clean_lbl = label.strip()
                    data_pool[clean_lbl] = {"m1": normalize_with_unit(volt), "m2": "-"}
                    data_pool[f"Current {clean_lbl}"] = {"m1": normalize_with_unit(ampere), "m2": "-"}
                continue 
        if "DVOR" in station_type and "AC" in current_section and "Status" in current_section:
             matches = re.findall(r"-\s+(AC \+28V)\s+([-\d\.]+\s*V)\s+([-\d\.]+\s*A)", line)
             for label, volt, ampere in matches:
                 data_pool[label] = {"m1": normalize_with_unit(volt), "m2": "-"}
                 data_pool[f"Current {label}"] = {"m1": normalize_with_unit(ampere), "m2": "-"}
             continue
        
        # Parsing Data Nilai (Umum: Parameter Value1 Value2)
        clean_line = line.replace("- ", "")
        match = pattern_double.match(clean_line)
        if match:
            p, v1, v2 = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            
            # [LOGIKA STRICT FILTER]
            if "DME" in station_type and p in strict_mon_params:
                # Cek apakah kita BENAR-BENAR ada di section MON Major Measurement
                # Kita gunakan 'in' agar tidak peduli karakter aneh di kiri/kanan nama section
                if "MON Major Measurement" not in current_section:
                    continue # Skip data ini karena bukan dari section yang diminta

            # Filter DVOR
            if "DVOR" in station_type and p == "CARRIER Output Power" and current_section == "Main Status": continue
            
            data_pool[p] = {"m1": normalize_with_unit(v1), "m2": normalize_with_unit(v2)}

    # Susun Hasil Akhir Sesuai Urutan
    final_rows = []
    key_list = ORDERED_PARAMS["DME"] if "DME" in station_type else ORDERED_PARAMS["DVOR"]
    for k in key_list:
        if k in data_pool:
            final_rows.append({"Parameter": k, "Monitor 1": data_pool[k]["m1"], "Monitor 2": data_pool[k]["m2"]})
        else:
            final_rows.append({"Parameter": k, "Monitor 1": "-", "Monitor 2": "-"})
            
    return final_rows, active_tx

# =============================================================================
# 2. PARSER PMDT (LOC/GP/MM/OM) - TETAP SAMA
# =============================================================================
def parse_pmdt_strict(tool_type, full_text):
    data_pool = {}
    
    # 1. PARSE RMS STATUS
    rms_params = ["Antenna Select", "Main Select", "Transmitter On"]
    header_block = full_text.split("RAW DATA DETAILS")[0] if "RAW DATA DETAILS" in full_text else full_text
    header_lines = header_block.splitlines()
    for p in rms_params:
        idx_found = -1
        for i, line in enumerate(header_lines):
            if p in line: idx_found = i; break
        if idx_found != -1:
            val1, val2 = "-", "-"
            for j in range(1, 5):
                if idx_found + j >= len(header_lines): break
                subline = header_lines[idx_found + j]
                if "Tx 1" in subline and "G" in subline.split("Tx 1")[0][-5:]: val1 = "Tx 1"
                if "Tx 2" in subline and "G" in subline.split("Tx 2")[0][-5:]: val2 = "Tx 2"
            data_pool[p] = {"m1": val1, "m2": val2}

    # 2. PARSE MONITOR DATA
    section = "General"
    lines = full_text.splitlines()
    
    if tool_type in ["MM", "OM"]:
        current_mon = None
        for line in lines:
            line = line.strip()
            if not line: continue
            if "Monitor 1" in line and "Enabled" not in line and "Status" not in line: current_mon = "m1"; continue
            elif "Monitor 2" in line and "Enabled" not in line and "Status" not in line: current_mon = "m2"; continue
            if current_mon:
                match = re.search(r"(RF Level|Ident Modulation)\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", line)
                if match:
                    param, val = match.group(1), match.group(4)
                    unit = line.split()[-1]
                    if unit in ["dB", "%"]: val = f"{val} {unit}"
                    if param not in data_pool: data_pool[param] = {"m1": "-", "m2": "-"}
                    data_pool[param][current_mon] = normalize_with_unit(val)
    else:
        reading_monitor = True
        for line in lines:
            line = line.strip()
            if "Transmitter Data" in line: reading_monitor = False
            if not reading_monitor: break
            if line in ["Course", "Clearance"]: section = line; continue
            if "RMS" in line or "SNAPSHOT" in line: continue
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 3 and "/" not in parts[0] and "Monitor" not in line and "Select" not in line:
                raw_p = parts[0]
                val1, val2 = "-", "-"
                if len(parts) == 3: val1, val2 = parts[1], parts[2]
                elif len(parts) == 4: val1, val2 = parts[1] + " " + parts[3], parts[2] + " " + parts[3]
                elif len(parts) == 5: val1, val2 = parts[1] + " " + parts[2], parts[3] + " " + parts[4]
                key = raw_p
                if section != "General": key = f"{section} - {raw_p}"
                data_pool[key] = {"m1": normalize_with_unit(val1), "m2": normalize_with_unit(val2)}

    # 3. PARSE TRANSMITTER DATA
    if "Transmitter Data" in full_text:
        try:
            tx_text = full_text.split("Transmitter Data")[1]
            tx_lines = tx_text.splitlines()
            
            if tool_type in ["LOC", "GP"]:
                context_left, context_right = "Course", "Clearance"
                for line in tx_lines:
                    line = line.strip()
                    if "Standby" in line: context_left, context_right = "Standby Course", "Standby Clearance"; continue
                    if "Watts" in line or "Watt" in line:
                        matches = re.findall(r"([A-Za-z\s]+?)\s+([-\d\.]+\s*(?:Watts|Watt|W))", line)
                        if len(matches) >= 1:
                            p, v = matches[0]
                            k = p.strip() if "Antenna" in p else f"{context_left} {p.strip()}"
                            data_pool[k] = {"m1": normalize_with_unit(v), "m2": "-"}
                        if len(matches) >= 2:
                            p, v = matches[1]
                            p = p.strip()
                            if tool_type == "GP" and "Forward Power" in p and "CSB" not in p and "SBO" not in p:
                                k_right = f"{context_right} Forward Power"
                            else:
                                k_right = f"{context_right} {p}"
                            data_pool[k_right] = {"m1": normalize_with_unit(v), "m2": "-"}

            elif tool_type in ["MM", "OM"]:
                current_tx = ""
                for line in tx_lines:
                    line = line.strip()
                    if "Transmitter 1" in line: current_tx = "Transmitter 1"
                    elif "Transmitter 2" in line: current_tx = "Transmitter 2"
                    elif "Watts" in line or " : 1" in line:
                        match = re.search(r"([A-Za-z\s]+)\s+([-\d\.]+.*)", line)
                        if match:
                            p_name = match.group(1).strip()
                            val = match.group(2).replace(": 1", "").strip()
                            key = f"{current_tx} {p_name}"
                            data_pool[key] = {"m1": normalize_with_unit(val), "m2": "-"}
        except: pass

    final_rows = []
    target_keys = ORDERED_PARAMS.get(tool_type, [])
    for k in target_keys:
        if k in data_pool:
            final_rows.append({"Parameter": k, "Monitor 1": data_pool[k]["m1"], "Monitor 2": data_pool[k]["m2"]})
        else:
            found = False
            for dp_k, dp_v in data_pool.items():
                if k.replace(" ", "").lower() == dp_k.replace(" ", "").lower():
                    final_rows.append({"Parameter": k, "Monitor 1": dp_v["m1"], "Monitor 2": dp_v["m2"]})
                    found = True; break
            if not found: final_rows.append({"Parameter": k, "Monitor 1": "-", "Monitor 2": "-"})

    active_tx = 1
    if "Transmitter On" in data_pool:
        if data_pool["Transmitter On"]["m2"] == "Tx 2": active_tx = 2
        
    return final_rows, active_tx

# --- WRAPPER ---
def parse_pmdt_common(tool_type, text): return parse_pmdt_strict(tool_type, text)
def parse_pmdt_loc_gp(tool_type, text):
    tool_type = tool_type.upper()
    if "LOCALIZER" in tool_type: tool_type = "LOC"
    if "GLIDE" in tool_type: tool_type = "GP"
    return parse_pmdt_strict(tool_type, text)
def parse_pmdt_mm_om(text):
    t_type = "MM"
    if "Outer" in text or "OUTER" in text: t_type = "OM"
    return parse_pmdt_strict(t_type, text)