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
