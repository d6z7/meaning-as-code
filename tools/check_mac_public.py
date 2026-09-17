#!/usr/bin/env python3
"""
check_mac_public.py — public-repo cleanliness gate for meaning-as-code.

meaning-as-code is a PUBLIC framework repository. It must never carry a token that identifies a
private estate the framework was applied to: an organisation, a brand or product, an internal
system, programme or repository, a person, an infrastructure handle, or a source-specific table,
column, measure, market or code. This gate matches every inspectable tracked file -- and every
tracked file NAME -- against a token register and fails (exit 1) on any hit.

It is domain-NEUTRAL by construction: the identities live in a GITIGNORED register, never in this
file, and this file is scanned exactly like every other file (it used to skip itself, which hid a
leak in its own docstring from the one instrument able to see it).

Usage:
  tools/check_mac_public.py [ROOT]                 ROOT defaults to the repo root
  tools/check_mac_public.py [ROOT] --commits RANGE also scan commit messages + author/committer
                                                   identities in RANGE (e.g. origin/develop..HEAD;
                                                   a range starting with `-` needs `--commits=--all`)
  tools/check_mac_public.py [ROOT] --refs          also scan branch and tag NAMES
  tools/check_mac_public.py --self-test
  --redact / --no-redact   print only path:line and a rule NUMBER, never the matched text or the
                           rule label. Default: on under CI ($CI or $GITHUB_ACTIONS), off locally.

Exit 0 = clean; 1 = at least one leak (each printed as path:line: [rule] text); 2 = could not run.

Escape hatch: append `mac-public-allow=<rule-label>` in a comment on a line to waive THAT rule on
THAT line for a genuine, reviewed use. A bare marker waives nothing.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from bisect import bisect_right
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT_DEFAULT = SELF.parent.parent

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache"}

# WHY THERE IS NO EXTENSION ALLOW-LIST ANY MORE. The gate used to read only files whose suffix sat in
# a hand-kept TEXT_EXT set, and still COUNTED every other file as "examined". Measured on the estate
# it guards: `.tsv`, `.jsx`, `.js`, `.svg`, `.mmd`, `.ttl`, `.mac`, `.css` were never read, and the two
# worst disclosures found in review were a pair of `.tsv` question catalogues the gate had printed
# PASS over. A file is now inspected by what it IS: anything that decodes as UTF-8 is text; a zip
# container (office documents included) is opened and its members inspected; a PDF is read through
# `pdftotext` when present; a PNG's text chunks are read. Whatever remains is reported as NOT
# INSPECTED -- disclosed in the verdict, never silently folded into the denominator.
ZIP_SUFFIXES = {".zip", ".xlsx", ".xlsm", ".docx", ".pptx", ".odt", ".ods", ".odp", ".jar", ".whl"}
MAX_BYTES = 50 * 1024 * 1024          # larger than this is disclosed as not inspected, not guessed at
MAX_ZIP_DEPTH = 3

ALLOW = "mac-public-allow"
ALLOW_RX = re.compile(r"mac-public-allow=([A-Za-z0-9_.,-]+)")

I = re.IGNORECASE

# THE PATTERN TABLE IS NOT IN THIS FILE. It was: every identity this gate exists to keep OUT of a
# public repository, listed inside that public repository. The gate's own source was the densest
# concentration in the tree of exactly what it scans for.
#
# It now loads from a GITIGNORED register. `registers/public_tokens.example.txt` ships with the
# format and no values. $MAC_PUBLIC_TOKENS overrides the path so CI -- which has no gitignored
# file -- can supply one without committing it.
#
# AN EMPTY REGISTER IS NOT A CLEAN TREE. With no patterns the gate examines NOTHING, and a
# zero-denominator pass is this estate's dominant defect, so it refuses rather than reporting green.
REGISTER = Path(os.environ.get("MAC_PUBLIC_TOKENS") or (SELF.parent.parent / "registers" / "public_tokens.txt"))


def load_register(register: Path | None = None):
    """(patterns, witnesses) from the register.

    patterns:  [(label, regex, flags)]
    witnesses: {label: {"+": [text...], "-": [text...]}}

    WHY WITNESSES LIVE IN THE REGISTER. A rule with no example that it catches is an untested rule,
    and a rule with no example it must NOT catch is how a token that doubles as an English word ends
    up flagging ordinary prose. The
    examples cannot live in this public file -- a positive example IS the leak -- so they sit beside
    their pattern in the gitignored register, and --self-test proves every rule against them.
    """
    reg = register if register is not None else REGISTER
    if not reg.is_file():
        return [], {}
    patterns, witnesses = [], {}
    for ln in reg.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln[0] in "+-" and "|" in ln:
            label, text = ln[1:].split("|", 1)
            witnesses.setdefault(label.strip(), {"+": [], "-": []})[ln[0]].append(text.strip())
            continue
        # Split on the FIRST and LAST delimiter only: a regex legitimately contains `|`
        # (alternation), and a naive 3-way split silently DROPPED every alternating pattern --
        # three identity rules vanished from the table that way, which is a gate going quietly blind.
        if ln.count("|") < 2:
            continue
        label, rest = ln.split("|", 1)
        rx, fl = rest.rsplit("|", 1)
        label, rx, fl = label.strip(), rx.strip(), fl.strip()
        patterns.append((label, rx, I if fl.lower() == "i" else 0))
    return patterns, witnesses


def load_patterns(register: Path | None = None):
    """[(label, regex, flags)] from the register, or [] when none is declared."""
    return load_register(register)[0]


# THE BUILT-IN TABLE — universal SHAPES, and why these may live in this file when no token may.
#
# The register above holds IDENTITIES. Those cannot be written here, because listing them inside the
# public repo IS the leak this gate exists to prevent.
#
# An absolute home path is a different kind of fact. It names a SHAPE -- "a path that carries some
# human's account name" -- not any particular human, so writing the shape down leaks nothing. And it
# MUST live in code rather than the register, because the register is gitignored: a fresh clone and
# CI carry `public_tokens.example.txt` with no values, so anything expressed only as a register entry
# is absent exactly where the going-public check matters most.
#
# MEASURED, and it is why this table exists. The gate printed
#     PASS: check_mac_public — 0 leak(s) over 613 tracked file(s) examined
# while a tracked `compile.json` carried an author's real home directory on line 3. The FILE
# denominator was complete; the PATTERN denominator was not: 16 register entries, all identity
# tokens, none matching a home path. That is a zero-denominator pass one level up.
#
# `(?!<)` IS LOAD-BEARING. Tracked lines legitimately quote `/Users/<someone>/dev/...` -- placeholders
# in protocol entries and wiki pages describing this very defect class. A pattern that flagged those
# would punish the documentation of the bug.
#
# THE CLOUD ACCOUNT SHAPE. A 12-digit account number inside a resource name is an identity whatever
# the account; the documented example account `123456789012` (and an all-zero one) is not. Review
# found a real production account number in a test fixture, which no identity token had covered.
BUILTIN_PATTERNS = [
    ("absolute home path (posix)", r"/(?:Users|home)/(?!<)[A-Za-z0-9._-]{2,}/", 0),
    ("absolute home path (windows)", r"C:\\Users\\(?!<)[A-Za-z0-9._-]{2,}", I),
    ("cloud account id in a resource name", r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(?!123456789012:|0{12}:)\d{12}:", 0),
]

PATTERNS, WITNESSES = load_register()


def _compile(patterns):
    return ([(label, re.compile(p, f)) for (label, p, f) in BUILTIN_PATTERNS]
            + [(label, re.compile(p, f)) for (label, p, f) in patterns])


# Built-ins FIRST, and never conditional on the register: the register may be absent, but these hold
# for any public tree. An empty register still refuses (see main) -- a shape floor is not a
# substitute for the identity table, only a guarantee that travels with a clone.
COMPILED = _compile(PATTERNS)


# ------------------------------------------------------------------------------------------------
# text preparation
# ------------------------------------------------------------------------------------------------

# WHY SUBRESOURCE-INTEGRITY VALUES ARE MASKED. A lockfile's `sha512-<base64>` is 88 random characters
# per dependency; across ten thousand lines a three-letter token turns up inside one by chance.
# Review measured exactly that: two "leaks" in a package lock that were hash bytes. A hash is provably
# not prose, so it is blanked (same length, so every offset and line number is unchanged) -- which is
# narrower than weakening a token pattern for every other file in the tree.
SRI_RX = re.compile(r"sha(?:1|256|384|512)-[A-Za-z0-9+/]{27,}={0,2}")

# WHY A BASE64 DATA URI IS DECODED, NOT MASKED. An inline `data:image/svg+xml;base64,...` is a whole
# document -- labels, titles, comments -- hidden from a line grep. Masking it would make it a hiding
# place; decoding it and scanning the payload makes it an ordinary file.
DATA_URI_RX = re.compile(r"data:[A-Za-z0-9.+/-]+(?:;[A-Za-z0-9=.-]+)*;base64,([A-Za-z0-9+/]+={0,2})")

# WHY A LINE BREAK IS NOT A BOUNDARY. Matching was per line, so a token wrapped by a docstring or a
# `#` comment across two lines (`... the first word` / `# second word ...`) was invisible to any
# multi-word rule. The text is flattened for matching: each line junction -- trailing blanks, the
# newline, the next line's indent and a leading comment marker -- becomes ONE space, exactly what a
# reader sees when the wrap is undone. A comment marker is consumed only when followed by whitespace,
# so a token that itself starts with `#` (a code like `#_X`) is left intact. Junction offsets are
# recorded so every match maps back to its original line.
_WRAP_RX = re.compile(r"[ \t]*\n[ \t]*(?:(?:#+|//+|\*+|>+|--|;+)[ \t]+)?")


def _flatten_map(text: str):
    """(flat_text, to_original_offset)."""
    parts, cpos, opos, last, c = [], [], [], 0, 0
    for m in _WRAP_RX.finditer(text):
        seg = text[last:m.start()]
        parts.append(seg)
        parts.append(" ")
        c += len(seg) + 1
        cpos.append(c)
        opos.append(m.end())
        last = m.end()
    parts.append(text[last:])

    def to_orig(p: int) -> int:
        k = bisect_right(cpos, p) - 1
        return p if k < 0 else opos[k] + (p - cpos[k])
    return "".join(parts), to_orig


def _flatten(text: str) -> str:
    return _flatten_map(text)[0]


def _mask(text: str) -> str:
    text = SRI_RX.sub(lambda m: "#" * len(m.group(0)), text)
    return DATA_URI_RX.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + "#" * len(m.group(1)), text)


def _data_uri_payloads(text: str):
    """(line_no, decoded_text) for every base64 data URI whose payload is UTF-8 text."""
    starts = _line_starts(text)
    for m in DATA_URI_RX.finditer(text):
        try:
            raw = base64.b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4), validate=False)
            yield bisect_right(starts, m.start()), raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue


def _line_starts(text: str):
    return [0] + [m.end() for m in re.finditer("\n", text)]


def _waived(line: str, label: str) -> bool:
    # WHY THE MARKER MUST NAME ITS RULE. A bare `mac-public-allow` used to waive EVERY rule on the
    # line, so a reviewed use of one token silently licensed any other identity that later joined it.
    return any(label in m.group(1).split(",") for m in ALLOW_RX.finditer(line))


def scan_text(text: str, where: str, compiled=None):
    """[(where, lineno, label, line)] — one finding per (line, rule), wrapped tokens included."""
    compiled = COMPILED if compiled is None else compiled
    # `split("\n")`, not `splitlines()`: line numbers are computed from newline offsets, and
    # splitlines() also breaks on form feeds and U+2028, which would shift every later line.
    lines = text.split("\n")
    starts = _line_starts(text)
    flat, to_orig = _flatten_map(_mask(text))
    hits, seen = [], set()
    for label, rx in compiled:
        if not rx.search(flat):            # one C-speed pass per rule before any per-line work
            continue
        for m in rx.finditer(flat):
            first = bisect_right(starts, to_orig(m.start()))
            last = bisect_right(starts, to_orig(max(m.start(), m.end() - 1)))
            key = (first, label)
            if key in seen:
                continue
            spanned = lines[first - 1: last]
            if any(_waived(ln, label) for ln in spanned):
                continue
            seen.add(key)
            shown = " ⏎ ".join(s.strip() for s in spanned)
            hits.append((where, first, label + (" (across a line break)" if last > first else ""), shown))
    for lineno, payload in _data_uri_payloads(text):
        for (_w, ln, label, _line) in scan_text(payload, where, compiled):
            hits.append((where, lineno, label + " (inside a base64 data URI)", f"<payload line {ln}>"))
    return hits


# ------------------------------------------------------------------------------------------------
# file inspection
# ------------------------------------------------------------------------------------------------

def _png_text(data: bytes) -> str | None:
    """Concatenated tEXt/iTXt/zTXt chunk text of a PNG, '' when it has none, None when not a PNG."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    out, i = [], 8
    while i + 8 <= len(data):
        (length,) = struct.unpack(">I", data[i:i + 4])
        ctype, body = data[i + 4:i + 8], data[i + 8:i + 8 + length]
        try:
            if ctype == b"tEXt":
                out.append(body.replace(b"\x00", b": ").decode("latin-1"))
            elif ctype == b"zTXt":
                key, rest = body.split(b"\x00", 1)
                out.append(key.decode("latin-1") + ": " + zlib.decompress(rest[1:]).decode("latin-1"))
            elif ctype == b"iTXt":
                key, rest = body.split(b"\x00", 1)
                compressed, rest = rest[0], rest[2:]
                _lang, rest = rest.split(b"\x00", 1)
                _tkey, txt = rest.split(b"\x00", 1)
                out.append(key.decode("latin-1") + ": "
                           + (zlib.decompress(txt) if compressed else txt).decode("utf-8", "replace"))
        except (ValueError, zlib.error):
            pass
        if ctype == b"IEND":
            break
        i += 12 + length
    return "\n".join(out)


def _pdf_text(path: Path) -> str | None:
    exe = shutil.which("pdftotext")
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, "-q", "-layout", str(path), "-"], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


_TAG_RX = re.compile(r"<[^>]{0,2000}>")


def _inspect_bytes(data: bytes, where: str, suffix: str, compiled, depth: int = 0):
    """(hits, inspected: bool). Never raises on content."""
    if suffix in ZIP_SUFFIXES or data[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            zf = None
        if zf is not None and depth < MAX_ZIP_DEPTH:
            hits = []
            for info in zf.infolist():
                if info.is_dir():
                    continue
                member = f"{where}!{info.filename}"
                hits += [(member, 0, label, "(member name)")
                         for (_w, _l, label, _t) in scan_text(info.filename, member, compiled)]
                if info.file_size > MAX_BYTES:
                    hits.append((member, 0, "NOT INSPECTED (member too large)", ""))
                    continue
                # WHY A MEMBER READ IS GUARDED. An encrypted member, a bad CRC or an unsupported
                # compression method raised out of the scan: the traceback exited 1 -- the FAIL code --
                # and every file after the container went unscanned. A member that cannot be read is
                # disclosed as not inspected, like any other unreadable content.
                try:
                    member_bytes = zf.read(info)
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, OSError,
                        ValueError, zlib.error):
                    hits.append((member, 0, "NOT INSPECTED (unreadable member)", ""))
                    continue
                sub, ok = _inspect_bytes(member_bytes, member, Path(info.filename).suffix.lower(),
                                         compiled, depth + 1)
                hits += sub
                if not ok:
                    hits.append((member, 0, "NOT INSPECTED (binary member)", ""))
            return hits, True
    png = _png_text(data)
    if png is not None:
        # The text chunks are read; the PIXELS are not. A screenshot's visible text is exactly where a
        # label, a figure or a name hides, and no OCR runs here -- so a PNG is reported as NOT
        # inspected (its chunk findings still count). It used to return True, and a site of sixteen
        # screenshots printed "inspected of 29" over images nobody had read.
        return scan_text(png, where, compiled), False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [], False
    hits = scan_text(text, where, compiled)
    if suffix in {".xml", ".html", ".htm", ".svg", ".drawio"} or "!" in where:
        # Office XML splits one visible word across runs (`<w:t>Wo</w:t><w:t>rd</w:t>`), so inside a
        # container the markup is removed OUTRIGHT and the runs re-join. In a web page a tag usually
        # separates words, so there it becomes a space. Either way a tag keeps the newlines it
        # spanned, so line numbers agree with the raw scan and one finding is not reported twice.
        glue = "" if "!" in where else " "
        stripped = _TAG_RX.sub(lambda m: "\n" * m.group(0).count("\n") or glue, text)
        if stripped != text:
            known = {(h[1], h[2]) for h in hits}
            hits += [h for h in scan_text(stripped, where, compiled) if (h[1], h[2]) not in known]
    return hits, True


def inspect_file(path: Path, rel: str, compiled=None):
    """(hits, inspected: bool) for one file: its NAME, then its content by what the bytes are."""
    compiled = COMPILED if compiled is None else compiled
    # WHY THE NAME IS SCANNED. `test_<token>.py` or `questions_<token>_ontology.tsv` publishes the
    # identity in every directory listing whatever the file holds; a content grep never sees it.
    hits = [(rel, 0, label, "(file name)") for (_w, _l, label, _t) in scan_text(rel, rel, compiled)]
    try:
        size = path.stat().st_size
    except OSError:
        return hits, False
    if size > MAX_BYTES:
        return hits, False
    try:
        data = path.read_bytes()
    except OSError:
        return hits, False
    if path.suffix.lower() == ".pdf" or data[:5] == b"%PDF-":
        text = _pdf_text(path)
        if text is None:
            return hits, False
        return hits + scan_text(text, rel, compiled), True
    sub, ok = _inspect_bytes(data, rel, path.suffix.lower(), compiled)
    return hits + sub, ok


# The self-test builds non-git fixtures on purpose; the fallback NOTE is for a human scanning a real
# root, and repeating it for every fixture would bury the one line the self-test exists to print.
_QUIET_FALLBACK = False


def _candidates(root: Path):
    """The FILES this gate is entitled to judge: the ones git TRACKS.

    It used to walk the filesystem with `rglob`, and `SKIP_DIRS` omitted `build`. Measured on this
    repository: 311 of its 611 findings were in `build/`, which holds ZERO tracked files. A finding
    outside `git ls-files` is a gate bug, not a disclosure.

    Falls back to a filesystem walk only when git cannot answer -- and says so. The walk yields FILES
    ONLY: it used to return `rglob("*")` whole, so every directory was counted in the "tracked
    file(s) examined" denominator (measured: 155 reported for 136 files plus 19 directories).
    """
    try:
        # `-z`: without it git QUOTES any path holding a non-ASCII byte ("dir/\303\244.md"), the quoted
        # string names no file, and the file silently leaves the denominator -- an umlaut in a file
        # name was enough to take that file out of the scan.
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, text=True, timeout=120)
        tracked = [ln for ln in out.stdout.split("\0") if ln.strip()]
    except Exception:
        tracked = []
    if not tracked:
        if root.is_dir() and not _QUIET_FALLBACK:
            print("  NOTE: `git ls-files` yielded nothing — falling back to a filesystem walk of "
                  "FILES, which may include untracked build output", file=sys.stderr)
        return sorted(p for p in root.rglob("*")
                      if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts))
    return [root / rel for rel in sorted(tracked)]


def scan(root: Path, compiled=None, stats: dict | None = None):
    """Findings over every candidate file. `stats` (when given) receives the true denominators."""
    hits, inspected, not_inspected, present = [], 0, [], 0
    for path in _candidates(root):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if not path.is_file():          # a deleted-but-tracked path or a submodule is not a file
            continue
        present += 1
        rel = "/".join(rel_parts)
        file_hits, ok = inspect_file(path, rel, compiled)
        for h in file_hits:
            if h[2].startswith("NOT INSPECTED"):
                not_inspected.append(h[0])
            else:
                hits.append(h)
        if ok:
            inspected += 1
        else:
            not_inspected.append(rel)
    if stats is not None:
        stats.update(files=present, inspected=inspected, not_inspected=not_inspected)
    return hits


# ------------------------------------------------------------------------------------------------
# history surfaces (opt-in)
# ------------------------------------------------------------------------------------------------

def scan_commits(root: Path, rev_range: str, compiled=None):
    """(hits, commits) over commit messages and author/committer identities in `rev_range`.

    WHY. The file tree is only one of the surfaces a push publishes. Review found an organisation's
    internal system named in a commit message, a corporate domain in author e-mails, and neither is
    visible to any file grep -- and unlike a file, a pushed message cannot be edited afterwards.
    """
    compiled = COMPILED if compiled is None else compiled
    fmt = "%H%x00%an <%ae>%x00%cn <%ce>%x00%B%x1e"
    out = subprocess.run(["git", "-C", str(root), "log", f"--format={fmt}", rev_range],
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git log failed")
    hits, n = [], 0
    for rec in out.stdout.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        n += 1
        sha, author, committer, body = (rec.split("\x00") + ["", "", ""])[:4]
        short = sha[:9]
        for who, ident in (("author", author), ("committer", committer)):
            hits += [(f"commit {short} {who}", 0, label, "(identity)")
                     for (_w, _l, label, _t) in scan_text(ident, "", compiled)]
        hits += [(f"commit {short} message", ln, label, line)
                 for (_w, ln, label, line) in scan_text(body, "", compiled)]
    return hits, n


def scan_refs(root: Path, compiled=None):
    compiled = COMPILED if compiled is None else compiled
    out = subprocess.run(["git", "-C", str(root), "for-each-ref", "--format=%(refname)"],
                         capture_output=True, text=True, timeout=120)
    refs = [r for r in out.stdout.splitlines() if r.strip()]
    hits = []
    for r in refs:
        hits += [("ref", 0, label, r) for (_w, _l, label, _t) in scan_text(r, "", compiled)]
    return hits, len(refs)


# ------------------------------------------------------------------------------------------------
# verdict
# ------------------------------------------------------------------------------------------------

#: The ratchet floor: the measured count this tree is allowed to carry, and never more.
FLOOR_FILE = SELF.parent / "mac_public_floor.txt"


def _floor(root: Path) -> int | None:
    """The declared floor, or None when none is declared (then any finding fails)."""
    if not FLOOR_FILE.is_file():
        return None
    for line in FLOOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.isdigit():
            return int(line)
    return None


def _default_redact() -> bool:
    return bool(os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"))


def format_hit(hit, redact: bool, rule_numbers: dict) -> str:
    rel, lineno, label, line = hit
    # WHY REDACTION EXISTS. A public CI log is a publication. This gate printed every line it caught,
    # labelled with the register's own rule names, into run logs anyone could download -- so the
    # instrument re-published each leak it found. Redacted output names a location and a rule NUMBER
    # (an index into the private register), which lets the owner find the line and tells a reader
    # nothing.
    if redact:
        base = label
        for suffix in (" (across a line break)", " (inside a base64 data URI)"):
            base = base.replace(suffix, "")
        return f"{rel}:{lineno}: [rule {rule_numbers.get(base, '?')}]"
    return f"{rel}:{lineno}: [{label}] {line}"


def _builtins_only(root: Path, redact: bool, compiled=None) -> int:
    """The verdict when NO register is present: the built-in SHAPES still run.

    WHY. The shapes live in code precisely because a fresh clone and CI carry no register -- and the
    gate used to return "could not run" BEFORE scanning, so on exactly those checkouts the shapes never
    ran at all. Now a shape finding is a FAIL (a genuine finding outranks a could-not-run), and a clean
    shape scan is still COULD NOT RUN: the identity table was never applied, so it is not a clean tree.
    """
    compiled = _compile([]) if compiled is None else compiled
    stats: dict = {}
    hits = scan(root, compiled, stats)
    rule_numbers = {label: i for i, (label, _rx) in enumerate(compiled, 1)}
    denom = f"{stats.get('inspected', 0)} file(s) inspected of {stats.get('files', 0)}"
    if hits:
        print(f"check_mac_public: {len(hits)} leak(s) from the built-in shapes (no token register at "
              f"{REGISTER}, so identity tokens were NOT checked):\n", file=sys.stderr)
        for h in hits:
            print("  " + format_hit(h, redact, rule_numbers), file=sys.stderr)
        print(f"\nFAIL: check_mac_public — {len(hits)} leak(s) from {len(BUILTIN_PATTERNS)} built-in "
              f"shape(s) over {denom}; the identity register was absent")
        return 1
    print(f"could not run: check_mac_public — no token register at {REGISTER}; the "
          f"{len(BUILTIN_PATTERNS)} built-in shape(s) found 0 leak(s) over {denom}, but identity tokens "
          "were NOT checked, which is not the same as clean. Copy registers/public_tokens.example.txt, "
          "or set $MAC_PUBLIC_TOKENS.", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=str(ROOT_DEFAULT))
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--commits", metavar="RANGE", help="also scan commit messages + identities in RANGE")
    ap.add_argument("--refs", action="store_true", help="also scan branch and tag names")
    ap.add_argument("--redact", dest="redact", action="store_true", default=None)
    ap.add_argument("--no-redact", dest="redact", action="store_false")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()

    # It used to read `sys.argv[1]` as a path, so `--root src` globbed a directory literally named
    # "--root", found nothing, and printed "clean" with exit 0.
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    redact = _default_redact() if a.redact is None else a.redact

    if not PATTERNS:
        return _builtins_only(root, redact)

    rule_numbers = {label: i for i, (label, _rx) in enumerate(COMPILED, 1)}

    stats: dict = {}
    hits = scan(root, stats=stats)
    extra = []
    if a.commits:
        try:
            chits, ncommits = scan_commits(root, a.commits)
        except RuntimeError as e:
            print(f"could not run: check_mac_public --commits {a.commits}: {e}", file=sys.stderr)
            return 2
        hits += chits
        extra.append(f"{ncommits} commit(s)")
    if a.refs:
        rhits, nrefs = scan_refs(root)
        hits += rhits
        extra.append(f"{nrefs} ref name(s)")

    examined = stats["inspected"]
    ni = stats["not_inspected"]
    # THE DENOMINATOR IS FILES WHOSE CONTENT WAS READ. It used to be the length of the candidate
    # list -- directories included on a filesystem walk, and files skipped by extension or decode
    # failure counted as "examined". Both inflated the number a PASS was quoted over.
    denom = (f"{examined} file(s) inspected of {stats['files']}"
             + (f", {len(ni)} file(s) or container member(s) NOT inspectable" if ni else "")
             + ("; plus " + ", ".join(extra) if extra else ""))
    if ni:
        print(f"  {len(ni)} file(s) could not be inspected (binary with no text layer, or too large) — "
              "a PASS says nothing about them:", file=sys.stderr)
        for rel in ni:
            print(f"    {rel}", file=sys.stderr)
    if examined == 0:
        print(f"could not run: {root} — 0 file(s) inspected, which is not the same as clean",
              file=sys.stderr)
        return 2
    if not hits:
        print(f"PASS: check_mac_public — 0 leak(s) over {denom}")
        return 0
    floor = _floor(root)
    if floor is not None and len(hits) <= floor:
        # The RATCHET. The criterion is ZERO NEW findings above a declared, measured floor.
        # THE WITNESSES TRAVEL WITH THE VERDICT: the count alone hid the debt the floor makes visible.
        print(f"  {len(hits)} finding(s) under the floor — still to scrub:", file=sys.stderr)
        for h in hits:
            print("    " + format_hit(h, redact, rule_numbers), file=sys.stderr)
        # A FLOOR THAT SITS ABOVE THE MEASUREMENT IS NOT A RATCHET: every finding between the count
        # and the floor could be re-introduced silently.
        slack = floor - len(hits)
        if slack > 0:
            print(f"  [RATCHET] the floor is {floor} but only {len(hits)} finding(s) remain — "
                  f"{slack} finding(s) of slack. Lower {FLOOR_FILE.name} to {len(hits)}.",
                  file=sys.stderr)
        print(f"PASS: check_mac_public — {len(hits)} leak(s) over {denom}, at or below the declared "
              f"floor of {floor} ({FLOOR_FILE.name} — lower it, never raise it)"
              + (f"  [{slack} of slack]" if slack > 0 else ""))
        return 0
    over = f", {len(hits) - floor} ABOVE the declared floor of {floor}" if floor is not None else ""
    print(f"check_mac_public: {len(hits)} leak(s){over} — a public repository must carry no token "
          f"from the private register:\n", file=sys.stderr)
    for h in hits:
        print("  " + format_hit(h, redact, rule_numbers), file=sys.stderr)
    print(f"\nScrub these, or (only for a genuine, reviewed use) append `{ALLOW}=<rule-label>` on the line.",
          file=sys.stderr)
    print(f"\nFAIL: check_mac_public — {len(hits)} leak(s) over {denom}")
    return 1


# -------------------------------------------------------------------------------------------------
# self-test: one seeded mutant per reject class, and one per false-positive class a fix could create.
# Every token below is SYNTHETIC (`zz...`) or derived at run time from the private register, so this
# file plants nothing it scans for.
# -------------------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _seed_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "clean.py").write_text("def build(name):\n    return name.lower()\n", encoding="utf-8")
    _git(root, "add", "-A")


def _token() -> str:
    """A string the REAL register catches, never typed here: the first positive witness of a
    register rule, else a word derived from the first pattern."""
    for label, _rx, _fl in PATTERNS:
        for text in WITNESSES.get(label, {}).get("+", []):
            return text
    for entry in PATTERNS:
        word = re.sub(r"[^A-Za-z0-9_]", "", entry[1])
        if len(word) >= 3:
            return word
    raise RuntimeError("no usable token in PATTERNS")


def check_witnesses(patterns, witnesses):
    """Failures: a rule with no positive witness, a missed positive, a matched negative."""
    failures = []
    for label, rx, fl in patterns:
        w = witnesses.get(label, {"+": [], "-": []})
        try:
            c = re.compile(rx, fl)
        except re.error as e:
            failures.append(f"register rule {label!r} does not compile: {e}")
            continue
        if not w["+"]:
            failures.append(f"register rule {label!r} has no positive witness (`+{label} | ...`)")
        for text in w["+"]:
            if not c.search(_flatten(text)):
                failures.append(f"register rule {label!r} misses its positive witness")
        for text in w["-"]:
            if c.search(_flatten(text)):
                failures.append(f"register rule {label!r} matches its NEGATIVE witness (false positive)")
    known = {label for label, _rx, _fl in patterns}
    for label in witnesses:
        if label not in known:
            failures.append(f"witness for unknown register rule {label!r}")
    return failures


def _png_with_text(text: str) -> bytes:
    def chunk(t: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", b"Comment\x00" + text.encode())
            + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b""))


def _self_test() -> int:
    import tempfile

    if shutil.which("git") is None:
        print("could not run: git is required for the self-test", file=sys.stderr)
        return 2

    global _QUIET_FALLBACK
    _QUIET_FALLBACK = True
    failures: list[str] = []
    checks = 0

    def expect(cond: bool, msg: str) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    SYN = "zzsynthleakzz"
    syn = _compile([("synthetic", SYN, I), ("synthetic-two-words", r"zzalpha zzbeta", 0)])
    have_register = bool(PATTERNS)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1 - a clean TRACKED tree passes, over a non-zero denominator.
        clean = base / "clean"
        _seed_repo(clean)
        st: dict = {}
        expect(not scan(clean, syn, st), "clean fixture produced a finding")
        expect(st.get("inspected") == 1, f"clean fixture inspected {st.get('inspected')} file(s), expected 1")

        # 2 - a REAL register token in a TRACKED file is a leak (skipped honestly with no register).
        if have_register:
            tracked = base / "tracked"
            _seed_repo(tracked)
            (tracked / "leak.py").write_text(f'TABLE = "{_token()}.orders"\n', encoding="utf-8")
            _git(tracked, "add", "-A")
            expect(bool(scan(tracked)), "mutant not caught: a register token in a tracked file")

        # 3 - the same token in an UNTRACKED, gitignored build directory is NOT reported.
        ignored = base / "ignored"
        _seed_repo(ignored)
        (ignored / ".gitignore").write_text("build/\n", encoding="utf-8")
        (ignored / "build").mkdir()
        (ignored / "build" / "copy.py").write_text(f'TABLE = "{SYN}.orders"\n', encoding="utf-8")
        _git(ignored, "add", "-A")
        expect(not any("build/" in str(h) for h in scan(ignored, syn)),
               "false positive: a gitignored build file was reported as a leak")

        # 4 - a nonexistent root yields no candidates.
        expect(not _candidates(base / "nope"), "candidates found files under a nonexistent root")

        # 5 - THE BUILT-IN CLASS: an absolute home path is a leak even with NO register. Assembled
        #     from parts so this source carries no such path of its own.
        home = base / "home"
        _seed_repo(home)
        sep = "/"
        (home / "diag.json").write_text(
            '{"bundle": "' + sep + "Users" + sep + "someuser" + sep + 'dev' + sep + 'x"}\n', encoding="utf-8")
        _git(home, "add", "-A")
        expect(any("home path" in h[2] for h in scan(home, _compile([]))),
               "mutant not caught: an absolute home path in a tracked file")

        # 6 - and the placeholder that documents it is NOT.
        ph = base / "placeholder"
        _seed_repo(ph)
        (ph / "entry.md").write_text("how " + sep + "Users" + sep + "<someone>" + sep + "dev came to sit inside\n",
                                     encoding="utf-8")
        _git(ph, "add", "-A")
        expect(not [h for h in scan(ph, _compile([])) if "home path" in h[2]],
               "false positive: a <placeholder> home path was reported as a leak")

        # 7 - BUILT-IN: a 12-digit account in a resource name is caught; the documented example is not.
        acct = scan_text("arn:aws:glue:region-x:" + "4" * 3 + "7" * 9 + ":table/x", "f", _compile([]))
        expect(any("account" in h[2] for h in acct), "mutant not caught: a 12-digit account id in an ARN")
        doc = scan_text("arn:aws:glue:region-x:" + "123456789012" + ":table/x", "f", _compile([]))
        expect(not doc, "false positive: the documented example account id was reported")

        # 8 - THE DENOMINATOR DEFECT: a filesystem walk over 3 files in 2 nested directories must
        #     report 3, not 5. It reported files + directories.
        walk = base / "walk"
        (walk / "a" / "b").mkdir(parents=True)
        for rel in ("top.txt", "a/mid.txt", "a/b/deep.txt"):
            (walk / rel).write_text("nothing here\n", encoding="utf-8")
        st = {}
        scan(walk, syn, st)
        expect(len(_candidates(walk)) == 3 and st.get("files") == 3 and st.get("inspected") == 3,
               f"denominator counts directories: candidates={len(_candidates(walk))} stats={st}")

        # 9 - EXTENSION BLINDNESS: the token in suffixes the old allow-list never read.
        ext = base / "ext"
        _seed_repo(ext)
        for name in ("q.tsv", "View.jsx", "d.svg", "b.mac", "x.mmd", "s.css", "n.ttl"):
            (ext / name).write_text(f"row\t{SYN}\n", encoding="utf-8")
        _git(ext, "add", "-A")
        caught = {h[0] for h in scan(ext, syn)}
        expect(len(caught) == 7, f"extension blindness: only {sorted(caught)} of 7 suffixes caught")

        # 10 - FILE NAMES: the token in a tracked path, content clean.
        name = base / "name"
        _seed_repo(name)
        (name / f"test_de{SYN}.py").write_text("x = 1\n", encoding="utf-8")
        _git(name, "add", "-A")
        expect(any(h[3] == "(file name)" for h in scan(name, syn)), "mutant not caught: a token in a file NAME")

        # 10b - A NON-ASCII FILE NAME stays in the denominator (git quotes such paths unless -z).
        uml = base / "uml"
        _seed_repo(uml)
        (uml / "stra\u00dfe.md").write_text(f"{SYN}\n", encoding="utf-8")
        _git(uml, "add", "-A")
        st = {}
        uh = scan(uml, syn, st)
        expect(st.get("files") == 2 and any(h[0] == "stra\u00dfe.md" for h in uh),
               f"a non-ASCII tracked file name fell out of the scan: {st}")

        # 11 - BINARY CONTAINERS: a spreadsheet-shaped zip, token in one cell and a second token split
        #      across two runs of one cell. Plus a nested zip.
        cont = base / "cont"
        _seed_repo(cont)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/sharedStrings.xml",
                       f"<sst><si><t>{SYN}</t></si><si><r><t>zzal</t></r><r><t>pha zzbeta</t></r></si></sst>")
        inner = buf.getvalue()
        (cont / "book.xlsx").write_bytes(inner)
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("deliverable/book.xlsx", inner)
        (cont / "bundle.zip").write_bytes(outer.getvalue())
        _git(cont, "add", "-A")
        ch = scan(cont, syn)
        expect(any(h[0].startswith("book.xlsx!") and h[2] == "synthetic" for h in ch),
               "mutant not caught: a token inside an office-document member")
        expect(any(h[0].startswith("book.xlsx!") and h[2].startswith("synthetic-two-words") for h in ch),
               "mutant not caught: a phrase split across two runs of one spreadsheet cell")
        expect(any(h[0].startswith("bundle.zip!deliverable/book.xlsx!") for h in ch),
               "mutant not caught: a token inside a zip nested in a zip")

        # 12 - PNG TEXT CHUNKS are read; an undecodable binary is NOT INSPECTED, never "examined".
        img = base / "img"
        _seed_repo(img)
        (img / "shot.png").write_bytes(_png_with_text(f"author {SYN}"))
        (img / "blob.bin").write_bytes(bytes(range(256)) * 4)
        _git(img, "add", "-A")
        st = {}
        ih = scan(img, syn, st)
        expect(any(h[0] == "shot.png" for h in ih), "mutant not caught: a token in a PNG text chunk")
        expect("blob.bin" in st.get("not_inspected", []) and st.get("inspected") == 1,
               f"an undecodable binary was counted as inspected: {st}")
        # 12b - A PNG's PIXELS are not read, so the image is disclosed as not inspected even when its
        #       text chunks were scanned. It was counted as inspected.
        expect("shot.png" in st.get("not_inspected", []),
               f"a pixel image was counted as inspected: {st}")

        # 12c - AN UNREADABLE CONTAINER MEMBER (bad CRC) must not crash the scan: it is disclosed, and a
        #       file sorted AFTER it is still scanned. It raised, exit 1, and the scan stopped there.
        brk = base / "brk"
        _seed_repo(brk)
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("m.txt", "padding text " * 40)
        zbytes = bytearray(zbuf.getvalue())
        zbytes[40] ^= 0xFF                       # corrupt the compressed payload of the only member
        (brk / "a_broken.zip").write_bytes(bytes(zbytes))
        (brk / "z_after.txt").write_text(f"{SYN}\n", encoding="utf-8")
        _git(brk, "add", "-A")
        st = {}
        try:
            bh = scan(brk, syn, st)
            crashed = None
        except Exception as e:  # noqa: BLE001
            bh, crashed = [], e
        expect(crashed is None and any(h[0] == "z_after.txt" for h in bh)
               and any(n.startswith("a_broken.zip!") for n in st.get("not_inspected", [])),
               f"an unreadable zip member crashed or hid the scan: crashed={crashed!r} stats={st}")

        # 12d - NO REGISTER: the built-in shapes still run. A home path is a FAIL (exit 1); a clean tree
        #       is COULD NOT RUN (exit 2). The gate used to return 2 before scanning anything.
        noreg = base / "noreg"
        _seed_repo(noreg)
        (noreg / "cfg.json").write_text('{"p": "' + "/" + "home" + "/" + "someuser" + "/" + 'x"}\n',
                                        encoding="utf-8")
        _git(noreg, "add", "-A")
        _out, _err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = io.StringIO()
        try:
            leak_code = _builtins_only(noreg, True, _compile([]))
            clean_code = _builtins_only(clean, True, _compile([]))
        finally:
            sys.stdout, sys.stderr = _out, _err
        expect(leak_code == 1 and clean_code == 2,
               f"no-register verdicts wrong: home path -> {leak_code} (want 1), clean -> {clean_code} (want 2)")

        # 13 - A LINE BREAK IS NOT A BOUNDARY: a two-word rule wrapped across a `#` comment.
        wrap = scan_text("# the zzalpha\n# zzbeta was here\n", "f", syn)
        expect(any("across a line break" in h[2] for h in wrap), "mutant not caught: a phrase wrapped across lines")
        expect(not scan_text("# zzalpha\nzzgamma zzbeta\n", "f", syn),
               "false positive: two unrelated lines were joined into a match")

        # 14 - SRI masking removes the lockfile false positive, and ONLY inside the hash.
        sri = f'"integrity": "sha512-AAAA{SYN}BBBBccccddddeeeeffffgggghhhhiiiijjjjkkkkllllmmmmnnnnoooo=="\n'
        expect(not scan_text(sri, "f", syn), "false positive: a token inside a lockfile integrity hash")
        expect(bool(scan_text(f'"resolved": "{SYN}"\n', "f", syn)), "over-masking: a token outside a hash was missed")

        # 15 - A BASE64 DATA URI is decoded and its payload scanned.
        b64 = base64.b64encode(f"<svg><text>{SYN}</text></svg>".encode()).decode()
        expect(bool(scan_text(f'<img src="data:image/svg+xml;base64,{b64}">\n', "f", syn)),
               "mutant not caught: a token inside a base64 data URI")

        # 16 - THE ALLOW MARKER IS SCOPED: bare waives nothing, a wrong label waives nothing, the right
        #      label waives only its rule.
        expect(bool(scan_text(f"{SYN}  # {ALLOW}\n", "f", syn)), "a bare allow marker waived a finding")
        expect(bool(scan_text(f"{SYN}  # {ALLOW}=other-rule\n", "f", syn)), "an allow marker for another rule waived a finding")
        expect(not scan_text(f"{SYN}  # {ALLOW}=synthetic\n", "f", syn), "a correctly scoped allow marker was ignored")

        # 17 - REDACTION: the redacted line carries neither the matched text nor the rule label.
        red = format_hit(("p.py", 3, "synthetic", f"x = '{SYN}'"), True, {"synthetic": 7})
        expect(SYN not in red and "synthetic" not in red and "rule 7" in red, f"redaction leaked: {red!r}")

        # 18 - COMMIT MESSAGES AND IDENTITIES are a publication surface too.
        hist = base / "hist"
        _seed_repo(hist)
        _git(hist, "commit", "-q", "-m", "init")
        (hist / "f.txt").write_text("clean\n", encoding="utf-8")
        _git(hist, "add", "-A")
        subprocess.run(["git", "-C", str(hist), "-c", f"user.email=me@{SYN}.dev", "commit", "-q",
                        "-m", f"fix: the {SYN} column"], check=True, stdout=subprocess.DEVNULL)
        chh, n = scan_commits(hist, "HEAD~1..HEAD", syn)
        expect(n == 1 and any("message" in h[0] for h in chh) and any("author" in h[0] for h in chh),
               f"mutant not caught in commit message/identity: n={n} hits={chh}")
        _git(hist, "branch", f"feat/{SYN}-x")
        rh, _nr = scan_refs(hist, syn)
        expect(bool(rh), "mutant not caught: a token in a branch name")

        # 19 - THIS FILE IS INSPECTED, and it is clean. It used to skip itself, which hid a customer
        #      name in its own docstring from the only instrument that could see it.
        self_hits, ok = inspect_file(SELF, "tools/check_mac_public.py")
        expect(ok and not self_hits, f"the gate's own source is skipped or not clean: ok={ok} hits={self_hits}")

        # 19b - AND THE SCAN DOES NOT SKIP IT. Check 19 calls inspect_file on this file directly, so it
        #       still passed when a self-exclusion was put back into scan() (measured: that mutant
        #       survived the self-test). A copy under this file's own tracked name, and a link to this
        #       very file, must both come out of scan() -- an exclusion by name or by resolved path
        #       fails one of the two.
        selfscan = base / "selfscan"
        _seed_repo(selfscan)
        (selfscan / "tools").mkdir()
        (selfscan / "tools" / SELF.name).write_text(f"{SYN}\n", encoding="utf-8")
        try:
            (selfscan / "linked_gate.py").symlink_to(SELF)
            have_link = True
        except OSError:
            have_link = False
        _git(selfscan, "add", "-A")
        seen_self = {h[0] for h in scan(selfscan, syn)}
        expect(f"tools/{SELF.name}" in seen_self and (not have_link or "linked_gate.py" in seen_self),
               f"scan() skipped a file named like this gate, or a link to it: {sorted(seen_self)}")

        # 20 - THE WITNESS DISCIPLINE catches a rule that misses its example and one that fires on prose.
        bad = check_witnesses([("r1", "zzone", 0), ("r2", r"\bzztwo\b", I), ("r3", "zzthree", 0)],
                              {"r1": {"+": ["zzONE"], "-": []}, "r2": {"+": ["zztwo"], "-": ["ZZTWO here"]}})
        expect(len(bad) == 3, f"witness check did not reject 3 seeded defects: {bad}")

    # 21 - and the REAL register holds to it: every rule has a positive witness, catches all of them,
    #      and matches none of its negatives.
    reg_fail = check_witnesses(PATTERNS, WITNESSES) if have_register else []
    checks += 1
    failures += reg_fail

    npos = sum(len(w["+"]) for w in WITNESSES.values())
    nneg = sum(len(w["-"]) for w in WITNESSES.values())
    if failures:
        print(f"FAIL: check_mac_public self-test — {len(failures)} failure(s) over {checks} check(s)")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    reg = (f"{len(PATTERNS)} register rule(s) proven against {npos} positive and {nneg} negative witness(es)"
           if have_register else "NO register present: register rules and witnesses were NOT exercised")
    print(f"PASS: check_mac_public self-test — {checks}/{checks} check(s) over {len(BUILTIN_PATTERNS)} "
          f"built-in shape(s); {reg}")
    return 0


if __name__ == "__main__":
    # An unexpected exception is COULD NOT RUN (exit 2), never the traceback's exit 1, which a caller
    # reads as "leaks found". Under redaction the message is withheld: it can quote a file name.
    try:
        _code = main()
    except Exception as _e:  # noqa: BLE001
        _detail = "" if _default_redact() else f": {_e}"
        print(f"could not run: check_mac_public — {type(_e).__name__}{_detail}", file=sys.stderr)
        _code = 2
    raise SystemExit(_code)
