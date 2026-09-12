"""sdk.acceptance.bundleio — the file-plane primitives every acceptance op shares.

Three concerns live here, each for a MEASURED reason. None of them belongs in an op, and a
second copy of any of them is a second thing to drift.

1. CONTAINMENT (``QID_RE`` / ``is_safe_qid`` / ``check_qid``). A question id is a FILENAME: it
   addresses ``acceptance/oracle/<id>.yaml`` and ``acceptance/answers/<id>.yaml``. An id of
   ``../../../tmp/pwn`` — which an operator's .xlsx can carry into the corpus without anything
   objecting — therefore writes OUTSIDE the bundle. That was a live hole; this is the single
   definition that closes it, so the ops, the projector and any future op check the same thing.

2. ATOMICITY (``atomic_write``). ``acceptance/questions_dashboard.json`` is rewritten by the
   projector while the wiki UI polls it every 2.5 s, and a "Run all" has two processes rewriting
   it in turn. ``Path.write_text`` truncates the destination and then streams into it, so a poll
   landing inside that window reads a short or empty file and the browser throws on
   ``JSON.parse``. Writing a sibling temp file and ``os.replace``-ing it means a reader sees
   either the whole old file or the whole new one — never a zero-length window.

3. DRIFT VISIBILITY (``acceptance_fingerprint``). The only staleness signal the board had was
   the ONTOLOGY tree hash, which does not move when an oracle or an anchor is edited. So every
   capture read "fresh" while the assertions it had been judged against were rewritten under it
   (measured: 24 captures all predating the oracle revisions of 2026-08-17, with ``stats.stale``
   sitting at 0). This fingerprint covers the AUTHORED acceptance plane — corpus + oracles +
   anchors — so a capture can record what it was judged against and the projector can say when
   that has since moved.

Stdlib only. No bundle literals: nothing here knows a column name, a question id or a source.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import tempfile
from pathlib import Path

# A safe question id: one plain path segment, starting alphanumeric, at most 64 chars, made of
# alphanumerics/underscore/dot/dash. Frozen by spec §4.5.3 — the wiki's HTTP handlers validate
# against the identical pattern (they cannot import sdk; see boundaries.yaml), so if this ever
# changes, that copy changes with it.
QID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def is_safe_qid(qid: object) -> bool:
    """True iff ``qid`` may be used to build a path inside ``acceptance/``.

    ``".."`` is rejected EXPLICITLY as well as by the pattern. The pattern has to allow dots
    (real ids look like ``ACME_C1.1``), and a dotted id is exactly the shape a traversal hides in,
    so the one check that is load-bearing for containment gets belt and braces rather than a
    lone regex that a later "harmless" widening could open up.
    """
    if not isinstance(qid, str):
        return False
    if ".." in qid:
        return False
    return bool(QID_RE.match(qid))


def check_qid(qid: object, *, where: str = "question id") -> str:
    """``is_safe_qid`` as a hard failure, for call sites that must not proceed with a bad id."""
    if not is_safe_qid(qid):
        raise ValueError(
            f"invalid {where}: {qid!r} — expected {QID_RE.pattern} and no '..' "
            "(a question id names a file under acceptance/)"
        )
    return qid  # type: ignore[return-value]


def atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` to ``path`` so a concurrent READER never observes a partial file.

    The temp file is created in the SAME directory as the destination: ``os.replace`` is only
    atomic within one filesystem, and a ``/tmp`` staging file would silently degrade to a
    copy+truncate on any machine where ``/tmp`` is a different mount.

    On any failure the temp file is removed and ``path`` is left exactly as it was — a refused
    or crashed write can never leave a half-written SSOT document behind.
    """
    p = Path(path)
    # Keep the destination's mode when it already exists: mkstemp creates 0600, and these files
    # are read back by the wiki server process, so silently tightening the mode on every write
    # would be a slow-burn permissions bug that only shows up under a different uid.
    mode = None
    with contextlib.suppress(OSError):
        mode = p.stat().st_mode & 0o777

    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        # newline="" — write the bytes we were handed, with no line-ending translation, so the
        # atomic path is byte-for-byte what Path.write_text produced before it.
        with os.fdopen(fd, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())  # content is on disk BEFORE the rename claims it is there
        if mode is None:
            # New file: fall back to the process umask so a fresh file lands with the same mode
            # the replaced Path.write_text would have given it (0666 & ~umask), not mkstemp's 0600.
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(tmp, 0o666 & ~umask)
        else:
            os.chmod(tmp, mode)
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    # Durability of the RENAME itself needs the directory synced. Best-effort: some filesystems
    # refuse an O_RDONLY fsync on a directory, and that must not fail an otherwise-good write.
    try:
        dfd = os.open(str(p.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass
    return p


# The authored acceptance plane: what a capture is judged AGAINST. Deliberately excludes
# answers/ (evidence, not authority) and questions_dashboard.json (a derived build artefact) —
# either would make the fingerprint move every time it is written and prove nothing.
_FINGERPRINT_TREES = ("oracle", "anchors")


def acceptance_fingerprint(bundle: Path) -> str:
    """Hash of the authored acceptance plane: ``questions.yaml`` + ``oracle/**`` + ``anchors/**``.

    sha256 over the sorted ``(bundle-relative path, sha256(bytes))`` pairs; first 16 hex chars.
    Sorting by path is what makes it reproducible — ``rglob`` order is filesystem order, not a
    contract. A bundle with no acceptance plane hashes the empty sequence, which is stable.
    """
    acc = Path(bundle) / "acceptance"
    files: list[tuple[str, Path]] = []
    corpus = acc / "questions.yaml"
    if corpus.is_file():
        files.append(("acceptance/questions.yaml", corpus))
    for sub in _FINGERPRINT_TREES:
        d = acc / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*.yaml"):
            if p.is_file():
                files.append((p.relative_to(acc.parent).as_posix(), p))

    h = hashlib.sha256()
    for rel, p in sorted(files, key=lambda t: t[0]):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()[:16]
