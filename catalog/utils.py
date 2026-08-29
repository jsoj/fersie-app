"""
Catalog Utility Module for Fersie Ecosystem
Handles barcode/QR code generation, barcode normalization, and Elgin L42PRO FULL label command formatting (TSPL, EPL, ZPL).
"""

import re
import html
import qrcode
import qrcode.image.svg


def normalize_barcode(raw_input):
    """
    Normalizes barcode scanner input (removes CR/LF, spaces, leading/trailing whitespace).
    Returns normalized string.
    """
    if raw_input is None:
        return ""
    cleaned = str(raw_input).strip().replace('\r', '').replace('\n', '').replace(' ', '')
    return cleaned


def generate_elgin_tspl_label(cod_unico, description, price, barcode_type="128", size="", color="", width_mm=50, height_mm=30, quantity=1):
    """
    Generates TSPL command string for Elgin L42PRO FULL printer.
    """
    desc_clean = str(description)[:25].replace('"', '\\"')
    code_clean = str(cod_unico).replace('"', '\\"')
    if price is not None:
        try:
            price_val = float(price)
            price_fmt = f"R$ {price_val:.2f}".replace('.', ',')
        except (ValueError, TypeError):
            price_fmt = f"R$ {price}"
    else:
        price_fmt = "R$ 0,00"

    tspl_commands = [
        f"SIZE {width_mm} mm, {height_mm} mm",
        "GAP 2 mm, 0 mm",
        "DIRECTION 1",
        "CLS",
        f'TEXT 20,20,"3",0,1,1,"FERSIE - {desc_clean}"',
        f'BARCODE 20,60,"{barcode_type}",60,1,0,2,2,"{code_clean}"',
        f'TEXT 20,130,"3",0,1,1,"{price_fmt}"',
        f"PRINT {quantity},1"
    ]
    return "\n".join(tspl_commands)


def generate_elgin_epl_label(cod_unico, description, price, barcode_type="128", quantity=1):
    """
    Generates EPL2 command string for Elgin L42PRO / Eltron printers.
    """
    desc_clean = str(description)[:25].replace('"', '\\"')
    code_clean = str(cod_unico).replace('"', '\\"')
    if price is not None:
        try:
            price_val = float(price)
            price_fmt = f"R$ {price_val:.2f}".replace('.', ',')
        except (ValueError, TypeError):
            price_fmt = f"R$ {price}"
    else:
        price_fmt = "R$ 0,00"

    epl_commands = [
        "N",
        "q400",
        "Q240,24",
        f'A20,20,0,3,1,1,N,"FERSIE - {desc_clean}"',
        f'B20,60,0,1,2,2,60,B,"{code_clean}"',
        f'A20,140,0,3,1,1,N,"{price_fmt}"',
        f"P{quantity}"
    ]
    return "\n".join(epl_commands)


def generate_elgin_zpl_label(cod_unico, description, price, barcode_type="128", quantity=1):
    """
    Generates ZPL II command string for Elgin / Zebra printers.
    """
    desc_clean = str(description)[:25].replace('"', '\\"')
    code_clean = str(cod_unico).replace('"', '\\"')
    if price is not None:
        try:
            price_val = float(price)
            price_fmt = f"R$ {price_val:.2f}".replace('.', ',')
        except (ValueError, TypeError):
            price_fmt = f"R$ {price}"
    else:
        price_fmt = "R$ 0,00"

    zpl_commands = [
        "^XA",
        f"^FO20,20^A0N,25,25^FDFERSIE - {desc_clean}^FS",
        f"^FO20,60^BY2^BCN,60,Y,N,N^FD{code_clean}^FS",
        f"^FO20,145^A0N,25,25^FD{price_fmt}^FS",
        f"^PQ{quantity}^XZ"
    ]
    return "\n".join(zpl_commands)


# Code 128 B Canonical 103 Patterns (Indices 0..102), each 6 digits long and summing to 11 module widths.
CODE128_PATTERNS = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213', '122312',
    '132212', '221213', '221312', '231212', '112232', '122132', '122231', '113222',
    '123122', '123221', '223211', '221132', '221231', '213212', '223112', '312131',
    '311222', '321122', '321221', '312212', '322112', '322211', '212123', '212321',
    '232121', '111323', '131123', '131321', '112313', '132113', '132311', '211313',
    '231113', '231311', '112133', '112331', '132131', '113123', '113321', '133121',
    '313112', '314111', '331112', '311132', '311231', '312113', '312311', '332111',
    '311141', '311411', '311114', '111224', '111422', '121124', '121421', '141122',
    '141221', '112214', '112412', '122114', '122411', '142112', '142211', '241211',
    '221114', '411113', '411212', '411221', '421211', '221411', '431111', '312113',
    '311213', '321113', '112142', '114113', '114311', '411122', '411221', '421112',
    '421211', '212141', '214121', '412121', '111143', '111242', '111341', '113114',
    '114113', '114311', '411113', '411311', '113141', '114131', '311141'
]

START_B = '211214'
STOP_CODE = '2331112'


def generate_barcode_svg(code_text, width=220, height=70):
    """
    Generates a clean SVG string for a Code 128 barcode.
    """
    cleaned = str(code_text or "FERSIE").strip()
    pattern_sequence = [START_B]
    
    # Calculate checksum value
    checksum_val = 104  # Start B index
    for idx, char in enumerate(cleaned, start=1):
        c_code = ord(char) - 32 if 32 <= ord(char) <= 126 else 0
        checksum_val += c_code * idx
        pattern = CODE128_PATTERNS[c_code] if 0 <= c_code < len(CODE128_PATTERNS) else CODE128_PATTERNS[0]
        pattern_sequence.append(pattern)
        
    checksum_char_idx = checksum_val % 103
    # Append checksum pattern directly using checksum_char_idx for all 0..102
    pattern_sequence.append(CODE128_PATTERNS[checksum_char_idx])
    pattern_sequence.append(STOP_CODE)
    
    full_pattern = "".join(pattern_sequence)
    
    # Render SVG rects
    bar_rects = []
    x = 10
    is_bar = True
    module_width = max(1.5, (width - 20) / max(1, sum(int(d) for d in full_pattern)))
    
    for digit in full_pattern:
        w = int(digit) * module_width
        if is_bar:
            bar_rects.append(f'<rect x="{x:.2f}" y="10" width="{w:.2f}" height="{height-30}" fill="#000"/>')
        x += w
        is_bar = not is_bar
        
    total_svg_width = int(x + 10)
    escaped_text = html.escape(cleaned)
    svg_str = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_svg_width}" height="{height}" viewBox="0 0 {total_svg_width} {height}">
  <rect width="100%" height="100%" fill="#fff"/>
  {"".join(bar_rects)}
  <text x="{total_svg_width/2:.2f}" y="{height-8}" font-family="monospace" font-size="12" font-weight="bold" text-anchor="middle" fill="#000">{escaped_text}</text>
</svg>'''
    return svg_str


def generate_qr_code_svg(code_text, size=120):
    """
    Generates an SVG string for a QR Code using standard qrcode library.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=1,
    )
    qr.add_data(str(code_text or ""))
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
    output = img.to_string()
    if isinstance(output, bytes):
        return output.decode('utf-8')
    return output
