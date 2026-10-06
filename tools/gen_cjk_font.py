#!/usr/bin/env python3
"""
Generate an embedded CJK font header for AIO Graphics Test.

Pipeline:
  1. Collect every character used in the project's source strings
     (CJK + ASCII printable + common punctuation).
  2. Subset Noto Sans CJK SC (TTC index 2) to those glyphs with pyftsubset.
  3. zlib-compress the subset TTF (prefix 4-byte little-endian uncompressed size,
     matching ImGui's binary_to_compressed_c wire format).
  4. Encode to ImGui's Ascii85 variant (charset '!'..'u', 4->5 grouping).
  5. Emit a C header compatible with AddFontFromMemoryCompressedBase85TTF.

Usage:
  python3 tools/gen_cjk_font.py \
      --ttc /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
      --font-number 2 \
      --src src \
      --out src/font_cjk.inc \
      --symbol CJKFont_compressed_data_base85
"""
import argparse
import os
import re
import struct
import sys
import zlib

# ImGui's base85 alphabet (from imgui misc/fonts/binary_to_compressed_c.cpp,
# function Encode85Byte: x = (x % 85) + 35).
# This is ASCII 35 ('#') through ASCII 119 ('w'), 85 consecutive chars.
# NOT standard Ascii85 (!..u) and NOT a custom permutation. The decoder in
# imgui_draw.cpp does (c - 35) to reverse it. Using any other alphabet produces
# garbage after decode -> zlib uncompress out-of-bounds -> instant crash on startup.
B85_CHARS = "".join(chr(35 + i) for i in range(85))
assert len(B85_CHARS) == 85, f"got {len(B85_CHARS)}"
assert B85_CHARS[0] == "#" and B85_CHARS[-1] == "w"


def collect_chars(src_dir):
    """Scan all .c/.cpp/.h files under src_dir and return the set of chars used."""
    chars = set()
    for root, _dirs, files in os.walk(src_dir):
        for fn in files:
            if not fn.endswith((".c", ".cpp", ".h", ".hpp", ".inc")):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            # Only collect characters that appear inside string literals.
            # Simple heuristic: keep all non-ASCII chars + ASCII printable from
            # the whole file (comments may contain useful chars too; the subset
            # is tiny either way).
            for ch in text:
                cp = ord(ch)
                if cp >= 0x20 and cp < 0x7f:  # ASCII printable
                    chars.add(ch)
                elif cp >= 0x80:  # any non-ASCII (CJK, punctuation, symbols)
                    chars.add(ch)
    # Always include basic ASCII printable even if not found (dynamic text).
    for cp in range(0x20, 0x7f):
        chars.add(chr(cp))
    # Common CJK punctuation and symbols that may appear in runtime strings.
    extra = "，。、；：？！“”‘’（）【】《》—…·～￥"
    for ch in extra:
        chars.add(ch)
    return chars


def write_char_file(chars, path):
    """Write chars one-per-line for pyftsubset --text-file."""
    with open(path, "w", encoding="utf-8") as f:
        for ch in sorted(chars):
            f.write(ch)
        f.write("\n")


def subset_font(ttc_path, font_number, char_file, out_ttf):
    """Run pyftsubset to produce a subsetted TTF."""
    from fontTools.subset import Subsetter, Options
    from fontTools.ttLib import TTFont

    opts = Options()
    opts.font_number = font_number
    opts.layout_features = ["*"]  # keep all OpenType features
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.recalc_timestamp = True
    opts.drop_tables = ["DSIG"]  # drop digital signature (invalid after subsetting)

    font = TTFont(ttc_path, fontNumber=font_number)
    subsetter = Subsetter(options=opts)

    with open(char_file, "r", encoding="utf-8") as f:
        text = f.read()
    subsetter.populate(text=text)
    subsetter.subset(font)
    font.save(out_ttf)
    return os.path.getsize(out_ttf)


def encode_base85(data):
    """Encode bytes to ImGui Ascii85 string (4 bytes -> 5 chars)."""
    out = []
    n = len(data)
    i = 0
    while i < n:
        chunk = data[i:i + 4]
        pad = 4 - len(chunk)
        if pad:
            chunk = chunk + b"\x00" * pad
        value = struct.unpack(">I", chunk)[0]
        encoded = ""
        for _ in range(5):
            encoded = B85_CHARS[value % 85] + encoded
            value //= 85
        # For the final partial chunk, drop (pad) trailing chars.
        if pad and i + 4 >= n:
            encoded = encoded[:5 - pad]
        out.append(encoded)
        i += 4
    return "".join(out)


def compress_for_imgui(ttf_data):
    """zlib-compress with 4-byte LE uncompressed-size prefix (ImGui format)."""
    compressed = zlib.compress(ttf_data, 9)
    # ImGui stores uncompressed size as the first 4 bytes (little-endian uint32),
    # then the zlib stream. Verified against binary_to_compressed_c.cpp output.
    return struct.pack("<I", len(ttf_data)) + compressed


def c_escape(s):
    """Escape characters that are special inside C string literals (backslash and quote)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def emit_header(data_b85, raw_size, compressed_size, symbol, out_path, source_note):
    """Write the C header file."""
    lines = []
    lines.append(f"// File: '{source_note}' ({raw_size} bytes original, subsetted)")
    lines.append("// Exported using tools/gen_cjk_font.py (ImGui base85 + zlib format)")
    lines.append(f"// Compressed payload: {compressed_size} bytes ({len(data_b85)} base85 chars)")
    lines.append(f"static const char {symbol}[{len(data_b85)}+1] =")
    # Split into ~120 char lines for readability.
    line_len = 120
    for start in range(0, len(data_b85), line_len):
        chunk = data_b85[start:start + line_len]
        lines.append(f'    "{c_escape(chunk)}"')
    lines.append("    ;")
    lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Generate embedded CJK font header")
    ap.add_argument("--ttc", required=True, help="Path to NotoSansCJK-Regular.ttc")
    ap.add_argument("--font-number", type=int, default=2, help="TTC font index (2=SC)")
    ap.add_argument("--src", default="src", help="Source directory to scan for chars")
    ap.add_argument("--out", default="src/font_cjk.inc", help="Output header path")
    ap.add_argument("--symbol", default="CJKFont_compressed_data_base85",
                    help="C variable name")
    ap.add_argument("--keep-ttf", default=None, help="Optional path to keep subsetted TTF")
    args = ap.parse_args()

    # 1. Collect chars
    chars = collect_chars(args.src)
    print(f"[1/5] Collected {len(chars)} unique characters from {args.src}/")

    # 2. Write char file for subsetting
    char_file = args.out + ".chars.txt"
    write_char_file(chars, char_file)

    # 3. Subset
    import tempfile
    tmp_ttf = args.keep_ttf or (args.out + ".ttf")
    raw_size = subset_font(args.ttc, args.font_number, char_file, tmp_ttf)
    print(f"[2/5] Subsetted font: {raw_size} bytes -> {tmp_ttf}")

    # 4. Compress + base85
    with open(tmp_ttf, "rb") as f:
        ttf_data = f.read()
    compressed = compress_for_imgui(ttf_data)
    b85 = encode_base85(compressed)
    print(f"[3/5] Compressed: {len(ttf_data)} -> {len(compressed)} bytes "
          f"({len(b85)} base85 chars)")

    # 5. Emit header
    source_note = os.path.basename(args.ttc) + f"#{args.font_number} (Noto Sans CJK SC)"
    emit_header(b85, raw_size, len(compressed), args.symbol, args.out, source_note)
    print(f"[4/5] Header written: {args.out}")

    # Cleanup temp files
    if os.path.exists(char_file):
        os.remove(char_file)
    if not args.keep_ttf and os.path.exists(tmp_ttf):
        os.remove(tmp_ttf)
    print(f"[5/5] Done. Variable: {args.symbol}")


if __name__ == "__main__":
    main()
