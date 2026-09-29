"""Quote every member of a `reads:` list so YAML never sees a bare `[` in a flow sequence.

`reads: [columns[].name, table.schema]` is the natural way to write a field path, and it is also
invalid YAML: the `[` after `columns` opens a nested sequence. A regex cannot fix it (`[^\\]]*`
stops at the first `]`), so this scans brackets.
"""
import sys


def quote_reads(text: str) -> str:
    out, i = [], 0
    key = "reads: ["
    while True:
        j = text.find(key, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k, depth = j + len(key), 1
        while k < len(text) and depth:
            if text[k] == "[":
                depth += 1
            elif text[k] == "]":
                depth -= 1
                if not depth:
                    break
            k += 1
        inner = text[j + len(key):k]
        parts, d, cur = [], 0, ""
        for ch in inner:
            if ch == "," and d == 0:
                parts.append(cur); cur = ""; continue
            if ch in "[{":
                d += 1
            elif ch in "]}":
                d -= 1
            cur += ch
        parts.append(cur)
        vals = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            vals.append(p if p.startswith(("'", '"')) else '"' + p.replace('"', "'") + '"')
        out.append("reads: [" + ", ".join(vals) + "]")
        i = k + 1
    return "".join(out)


if __name__ == "__main__":
    sys.stdout.write(quote_reads(sys.stdin.read()))


def quote_flow_mapping(line: str) -> str:
    """Re-emit one `- {k: v, k: v}` line with every scalar quoted.

    A field path (`columns[].name`), a route (`/quality/{d}/{ds}/register`) and a prose role with a
    comma in it are all natural things to write and all invalid inside a YAML flow mapping. Quoting
    per-key with a regex fails on every one of them, so this splits on TOP-LEVEL separators only,
    counting brackets and braces.
    """
    i = line.find("- {")
    if i < 0 or not line.rstrip().endswith("}"):
        return line
    indent, inner = line[:i], line[i + 3:line.rstrip().rfind("}")]
    pairs, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "," and depth == 0:
            pairs.append(cur); cur = ""; continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        cur += ch
    pairs.append(cur)
    out = []
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        k, _, v = pair.partition(":")
        k, v = k.strip(), v.strip()
        if not _:
            continue
        if v.startswith("[") or v.startswith(("'", '"')):
            out.append(f"{k}: {v}")
        else:
            out.append(f'{k}: "{v.replace(chr(34), chr(39))}"')
    return f"{indent}- {{{', '.join(out)}}}\n"


def repair(text: str) -> str:
    return "".join(quote_flow_mapping(ln) if "- {" in ln else ln
                   for ln in quote_reads(text).splitlines(keepends=True))
