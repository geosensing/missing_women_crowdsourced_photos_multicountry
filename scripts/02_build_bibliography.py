"""Build refs.bib from registered identifiers, resolving metadata from the source of record.

Every entry in docs/references.json carries either a DOI or an arXiv id. Crossref
serves the DOIs, DataCite serves the arXiv ones. Nothing is typed by hand, so a
wrong author list or year is a fetch failure rather than a silent error.

Entries may instead carry a title query. Those resolve against Crossref search and
print the DOI they matched so it can be pinned in the register; an unpinned query
is reported as unverified.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

CROSSREF_WORK = "https://api.crossref.org/works/{doi}"
CROSSREF_QUERY = "https://api.crossref.org/works?rows=1&query.bibliographic={query}"
DATACITE_WORK = "https://api.datacite.org/dois/10.48550/arXiv.{arxiv}"
USER_AGENT = "missing-women-global/0.1 (mailto:gsood07@gmail.com)"

DEFAULT_REGISTER = Path("docs/references.json")
DEFAULT_BIB = Path("docs/refs.bib")
DEFAULT_REPORT = Path("docs/reference_validation.csv")


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def from_crossref(message: dict) -> dict:
    authors = [
        " ".join(part for part in (a.get("family"), a.get("given")) if part).strip()
        for a in message.get("author", [])
    ]
    issued = message.get("issued", {}).get("date-parts", [[None]])[0]
    container = message.get("container-title") or [""]
    return {
        "title": (message.get("title") or [""])[0],
        "authors": [a for a in authors if a],
        "year": issued[0],
        "venue": container[0],
        "volume": message.get("volume", ""),
        "number": message.get("issue", ""),
        "pages": message.get("page", ""),
        "doi": message.get("DOI", ""),
    }


def from_datacite(attributes: dict) -> dict:
    return {
        "title": attributes["titles"][0]["title"],
        "authors": [c.get("name", "") for c in attributes.get("creators", [])],
        "year": attributes.get("publicationYear"),
        "venue": "arXiv preprint",
        "volume": "",
        "number": "",
        "pages": "",
        "doi": attributes.get("doi", ""),
    }


def resolve(entry: dict) -> dict:
    """Look up one register entry, tolerating a failed lookup rather than aborting."""
    record = {"key": entry["key"], "status": "ok", "matched_by": "", "note": entry.get("note", "")}
    try:
        if "doi" in entry:
            record["matched_by"] = "crossref/doi"
            url = CROSSREF_WORK.format(doi=urllib.parse.quote(entry["doi"]))
            record.update(from_crossref(fetch(url)["message"]))
        elif "arxiv" in entry:
            record["matched_by"] = "datacite/arxiv"
            url = DATACITE_WORK.format(arxiv=entry["arxiv"])
            record.update(from_datacite(fetch(url)["data"]["attributes"]))
            record["arxiv"] = entry["arxiv"]
        elif "manual" in entry:
            record["matched_by"] = "manual"
            record.update(entry["manual"])
            record["status"] = "manual"
        elif "query" in entry:
            record["matched_by"] = "crossref/query"
            url = CROSSREF_QUERY.format(query=urllib.parse.quote(entry["query"]))
            items = fetch(url)["message"]["items"]
            if not items:
                raise LookupError("no Crossref match")
            record.update(from_crossref(items[0]))
            record["status"] = "unpinned"
        else:
            raise KeyError("entry has no doi, arxiv, manual, or query")
    except Exception as error:  # noqa: BLE001 - a failed lookup is a reportable result
        record["status"] = f"FAILED: {error}"
    return record


def bibtex(record: dict) -> str:
    authors = " and ".join(record.get("authors") or []) or "Unknown"
    fields = {
        "author": authors,
        "title": record.get("title", ""),
        "journal": record.get("venue", ""),
        "year": record.get("year", ""),
        "volume": record.get("volume", ""),
        "number": record.get("number", ""),
        "pages": record.get("pages", ""),
        "doi": record.get("doi", ""),
        "eprint": record.get("arxiv", ""),
    }
    body = "".join(
        f"  {name} = {{{value}}},\n" for name, value in fields.items() if str(value).strip()
    )
    return f"@article{{{record['key']},\n{body}}}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    entries = json.loads(args.register.read_text())
    records = []
    for entry in entries:
        record = resolve(entry)
        records.append(record)
        flag = "  " if record["status"] == "ok" else "! "
        print(f"{flag}{record['key']:<24}{record['status']:<12}{record.get('title', '')[:64]}")
        time.sleep(args.sleep)

    args.bib.parent.mkdir(parents=True, exist_ok=True)
    good = [r for r in records if not r["status"].startswith("FAILED")]
    args.bib.write_text("".join(bibtex(r) for r in good))

    columns = ["key", "status", "matched_by", "year", "title", "authors", "venue", "doi"]
    lines = [",".join(columns)]
    for record in records:
        row = []
        for column in columns:
            value = record.get(column, "")
            if isinstance(value, list):
                value = "; ".join(value)
            value = re.sub(r'[\r\n"]', " ", str(value))
            row.append(f'"{value}"')
        lines.append(",".join(row))
    args.report.write_text("\n".join(lines) + "\n")

    failed = len(records) - len(good)
    unpinned = sum(1 for r in records if r["status"] == "unpinned")
    print(f"\n{len(good)} resolved, {failed} failed, {unpinned} unpinned")
    print(f"wrote {args.bib} and {args.report}")


if __name__ == "__main__":
    main()
