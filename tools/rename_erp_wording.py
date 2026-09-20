"""Calls the connected system ERP on screen, not by its product name.

KONSTRYX is sold to contractors, and a contractor's ERP is whatever they run.
Naming one vendor's product on a field label, a button or a message makes the
screen wrong for every customer on anything else, and reads as a plug-in for
that product rather than as a product of its own.

So every string a user can see says ERP. What does NOT change is anything that
has to stay technically true: service paths, communication scenario names, API
entity names, the class names of the connectors, and the comments that explain
which API a call actually goes to. A comment that renamed the API it documents
would be a comment that lies, and the next person to debug an integration
failure reads the comment.

Only string literals are rewritten, never identifiers. s4Key stays s4Key in the
model and reads "ERP key" on the screen.

    python tools/rename_erp_wording.py [--check]
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "--check" in sys.argv

# Longest first, so "S/4 system" is not left as "ERP system" by a shorter rule
# that matched inside it.
PHRASES = [
    ("SAP S/4HANA Public Cloud", "ERP"),
    ("SAP S/4HANA", "ERP"),
    ("S/4HANA", "ERP"),
    ("S/4", "ERP"),
]

SKIP_DIRS = {"node_modules", "dist", "target", "gen", ".git", "mta_archives",
             # Generated. Rewriting the output would be undone by the next
             # build; the wording is fixed in the sources they are generated
             # from, and tools/build_launchpad_site.py re-emits the site.
             "edmx", "launchpad-content", "appconfig"}

# Files whose strings are technical rather than shown to anyone. The connectors
# name real APIs and scenarios; renaming those would make the code describe a
# call it does not make.
TECHNICAL = {
    os.path.join("srv", "src", "main", "java", "com", "inflexion", "konstryx",
                 "s4", "S4Connection.java"),
}


def phrase_swap(text):
    for old, new in PHRASES:
        text = text.replace(old, new)
    return text


def in_strings(text, quote):
    """Rewrites only what sits inside quoted literals."""
    pattern = re.compile(r'%s((?:[^%s\\]|\\.)*)%s' % (quote, quote, quote))
    return pattern.sub(lambda m: quote + phrase_swap(m.group(1)) + quote, text)


SUFFIXES = (".java", ".cds", ".properties", ".json")


def rewrite(path):
    name = os.path.basename(path)
    if not name.endswith(SUFFIXES):
        return 0
    try:
        text = io.open(path, encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        # A file this tool cannot read is a file it must not rewrite. Binary
        # artefacts and anything in another encoding are left exactly as they
        # are rather than being guessed at.
        return 0
    if "S/4" not in text:
        return 0

    if name.endswith(".java"):
        updated = in_strings(text, '"')
    elif name.endswith(".cds"):
        # Line by line, and never a comment line. A doc comment containing an
        # apostrophe - "the tenant's own system" - unbalances single-quote
        # pairing for the whole rest of the file, so a whole-file pass renamed
        # the labels above it and silently skipped every label below.
        updated = "\n".join(
            line if line.lstrip().startswith(("*", "//", "/*"))
            else in_strings(line, "'")
            for line in text.split("\n"))
    elif name.endswith(".properties"):
        # key=value; only the value is read by anyone.
        updated = "\n".join(
            line if "=" not in line or line.lstrip().startswith("#")
            else line.split("=", 1)[0] + "=" + phrase_swap(line.split("=", 1)[1])
            for line in text.split("\n"))
    elif name.endswith(".json"):
        updated = in_strings(text, '"')
    else:
        return 0

    if updated == text:
        return 0
    changed = text.count("S/4") - updated.count("S/4")
    if not CHECK:
        io.open(path, "w", encoding="utf-8").write(updated)
    return changed


def main():
    total, files = 0, 0
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            path = os.path.join(folder, name)
            if os.path.relpath(path, ROOT) in TECHNICAL:
                continue
            changed = rewrite(path)
            if changed:
                total += changed
                files += 1
                print("  %-62s %d" % (os.path.relpath(path, ROOT), changed))
    print("\n  %d string(s) in %d file(s)%s"
          % (total, files, " would change" if CHECK else " now say ERP"))


main()
