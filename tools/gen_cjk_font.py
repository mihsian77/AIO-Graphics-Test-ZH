#!/usr/bin/env python3
"""
Generate an embedded CJK font header for AIO Graphics Test.

Pipeline:
  1. Collect every character used in the project's source strings
     (CJK + ASCII printable + common CJK punctuation).
  2. Subset Noto Sans CJK SC (TTC index 2) to those glyphs with fonttools.
  3. Compile and run ImGui's official binary_to_compressed_c (-base85),
     which does stb_compress + ImGui base85 encoding.

The compression/encoding step MUST use the official tool. ImGui's base85 is
not standard Ascii85: Encode85Byte skips '\\' (0x5C) and the wire format is
stb_compress (not zlib). Hand-rolling either one produces a header that
compiles but decodes to garbage and crashes at startup.

Usage:
  python3 tools/gen_cjk_font.py \
      --ttc /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
      --font-number 2 \
      --src src \
      --out src/font_cjk.inc \
      --symbol CJKFont
"""
import argparse
import os
import subprocess
import sys
import tempfile

BTC_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "binary_to_compressed_c.cpp")


def collect_chars(src_dir):
    """Scan source files and return the set of chars to include."""
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
            for ch in text:
                cp = ord(ch)
                if cp >= 0x20 and cp < 0x7f:
                    chars.add(ch)
                elif cp >= 0x80:
                    chars.add(ch)
    # Always include the full ASCII printable range (dynamic text).
    for cp in range(0x20, 0x7f):
        chars.add(chr(cp))
    # Common CJK punctuation that may appear in runtime strings.
    for ch in "，。、；：？！“”‘’（）【】《》—…·～￥":
        chars.add(ch)
    return chars


def subset_font(ttc_path, font_number, chars, out_ttf):
    """Subset the TTC face to the given char set; returns output size."""
    from fontTools.subset import Subsetter, Options
    from fontTools.ttLib import TTFont

    opts = Options()
    opts.font_number = font_number
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.recalc_timestamp = True
    opts.drop_tables = ["DSIG"]

    font = TTFont(ttc_path, fontNumber=font_number)
    subsetter = Subsetter(options=opts)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    font.save(out_ttf)
    return os.path.getsize(out_ttf)


def build_btc(tool_path):
    """Compile binary_to_compressed_c.cpp if the binary is missing or older."""
    need_build = (not os.path.exists(tool_path)
                  or os.path.getmtime(tool_path) < os.path.getmtime(BTC_SRC))
    if need_build:
        subprocess.run(["g++", "-O2", "-o", tool_path, BTC_SRC], check=True)


def run_btc(tool_path, ttf_path, symbol):
    """Run official tool with -base85; return generated C source text."""
    proc = subprocess.run(
        [tool_path, "-base85", ttf_path, symbol],
        check=True, capture_output=True, text=True)
    return proc.stdout


def main():
    ap = argparse.ArgumentParser(description="Generate embedded CJK font header")
    ap.add_argument("--ttc", required=True, help="Path to NotoSansCJK-Regular.ttc")
    ap.add_argument("--font-number", type=int, default=2, help="TTC face index (2 = SC)")
    ap.add_argument("--src", default="src", help="Source directory to scan for chars")
    ap.add_argument("--out", default="src/font_cjk.inc", help="Output header path")
    ap.add_argument("--symbol", default="CJKFont",
                    help="Base symbol name (tool appends _compressed_data_base85)")
    ap.add_argument("--keep-ttf", default=None, help="Optional path to keep subsetted TTF")
    args = ap.parse_args()

    # 1. Collect chars.
    chars = collect_chars(args.src)
    print(f"[1/4] Collected {len(chars)} unique characters from {args.src}/")

    # 2. Subset font into a temp TTF (or user-provided path).
    tmp_ttf = args.keep_ttf or os.path.join(tempfile.gettempdir(), "aio_cjk_subset.ttf")
    raw_size = subset_font(args.ttc, args.font_number, chars, tmp_ttf)
    print(f"[2/4] Subsetted font: {raw_size} bytes -> {tmp_ttf}")

    # 3. Build + run the official ImGui compressor/encoder.
    tool_path = os.path.join(tempfile.gettempdir(), "aio_binary_to_compressed_c")
    build_btc(tool_path)
    print(f"[3/4] Ran binary_to_compressed_c -base85")
    inc_text = run_btc(tool_path, tmp_ttf, args.symbol)

    # 4. Replace the tool's generic header comment with provenance, write output.
    lines = inc_text.splitlines()
    # Drop the two "// File:" / "// Exported" lines the tool emits.
    while lines and lines[0].startswith("//"):
        lines.pop(0)
    header = [
        "// Noto Sans CJK SC (subsetted, SIL OFL 1.1), stb_compress + ImGui base85.",
        "// Regenerate with tools/gen_cjk_font.py; encoding is done by the official",
        "// binary_to_compressed_c.cpp (skips '\\\\', stb_compress not zlib) - do not hand-encode.",
    ]
    body = "\n".join(lines).lstrip("\n")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n" + body)
    print(f"[4/4] Header written: {args.out}")

    if not args.keep_ttf and os.path.exists(tmp_ttf):
        os.remove(tmp_ttf)
    var_name = f"{args.symbol}_compressed_data_base85"
    print(f"Done. Variable: {var_name}")


if __name__ == "__main__":
    main()
