#!/usr/bin/env python3
"""
Convert enhanced-LRC word timing to QRC syntax.

Input line:   [mm:ss.xx]<mm:ss.xx>Word<mm:ss.xx>Word<mm:ss.xx>...
Output line:  [start_ms,duration_ms]Word (start_ms,duration_ms)Word(start_ms,duration_ms)

Usage:
    python lrc2qrc.py input.txt              -> writes input.qrc.txt
    python lrc2qrc.py input.txt -o out.txt
    python lrc2qrc.py < input.txt > out.txt  (stdin/stdout)
"""
import argparse
import re
import sys
from pathlib import Path

LINE_RE = re.compile(r"^\s*\[(\d+):(\d{2})\.(\d{1,3})\](.*)$")
TAG_RE = re.compile(r"<(\d+):(\d{2})\.(\d{1,3})>")
OPEN_PUNCT = set("([{\u00bf\u00a1")


def to_ms(m, s, f):
    return (int(m) * 60 + int(s)) * 1000 + int(f.ljust(3, "0")[:3])


def tokenize(rest):
    parts = TAG_RE.split(rest)
    tokens = []
    if parts[0].strip():
        tokens.append(("text", parts[0].strip()))
    for i in range(1, len(parts), 4):
        tokens.append(("time", to_ms(parts[i], parts[i + 1], parts[i + 2])))
        text = parts[i + 3].strip()
        if text:
            tokens.append(("text", text))
    return tokens


def convert_line(rest, bracket_start):
    words = []
    pending = None
    cur_start = None
    prefix = ""

    for kind, val in tokenize(rest):
        if kind == "time":
            if pending is not None:
                pending["end"] = val
                words.append(pending)
                pending = None
            cur_start = val
            continue

        text = val
        if not any(c.isalnum() for c in text):
            # punctuation-only chunk: glue it to a neighbouring word
            if text[0] in OPEN_PUNCT or (not words and pending is None):
                prefix += text
            else:
                target = pending if pending is not None else words[-1]
                target["text"] += text
            continue

        if pending is not None:  # two texts without a time tag between them
            pending["end"] = cur_start if cur_start is not None else pending["start"]
            words.append(pending)
        start = cur_start if cur_start is not None else bracket_start
        pending = {"text": prefix + text, "start": start, "end": None}
        prefix = ""

    if pending is not None:
        end = cur_start if (cur_start is not None and cur_start > pending["start"]) else pending["start"]
        pending["end"] = end
        words.append(pending)

    if not words:
        return None

    line_start = words[0]["start"]
    line_end = max(w["end"] for w in words)
    out = [f"[{line_start},{max(line_end - line_start, 0)}]"]
    for i, w in enumerate(words):
        dur = max(w["end"] - w["start"], 0)
        space = "" if i == len(words) - 1 else " "
        out.append(f"{w['text']}{space}({w['start']},{dur})")
    return "".join(out)


def convert(text):
    result = []
    for raw in text.splitlines():
        m = LINE_RE.match(raw)
        if not m:
            continue  # skip blank/metadata lines
        bracket_start = to_ms(m.group(1), m.group(2), m.group(3))
        line = convert_line(m.group(4), bracket_start)
        if line:
            result.append(line)
    return "\n".join(result) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", help="input file (default: stdin)")
    ap.add_argument("-o", "--output", help="output file (default: <input>.qrc.txt, or stdout for stdin)")
    args = ap.parse_args()

    if args.input:
        text = Path(args.input).read_text(encoding="utf-8-sig")
    else:
        text = sys.stdin.read()

    converted = convert(text)

    if args.output:
        Path(args.output).write_text(converted, encoding="utf-8")
    elif args.input:
        out = Path(args.input).with_suffix(".qrc.txt")
        out.write_text(converted, encoding="utf-8")
        print(f"Wrote {out}")
    else:
        sys.stdout.write(converted)


if __name__ == "__main__":
    main()
