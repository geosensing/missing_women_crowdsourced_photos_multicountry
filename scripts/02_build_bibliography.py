"""Build the bibliography from Crossref, DataCite, and curated manual records.

A failed or incomplete lookup leaves the existing bibliography and report intact.
"""

from __future__ import annotations

import argparse
import csv
import html
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
    authors = []
    for author in message.get("author", []):
        family, given = author.get("family"), author.get("given")
        if family and given:
            authors.append(f"{family}, {given}")
        elif family or given:
            authors.append(family or given)
    date = message.get("published-print") or message.get("issued") or {}
    issued = date.get("date-parts", [[None]])[0]
    container = message.get("container-title") or [""]
    return {
        "title": (message.get("title") or [""])[0],
        "authors": [a for a in authors if a],
        "year": issued[0],
        "venue": container[0] or message.get("publisher", ""),
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
            if "arxiv" in record:
                arxiv = record["arxiv"]
                source = from_datacite(
                    fetch(DATACITE_WORK.format(arxiv=arxiv))["data"]["attributes"]
                )
                if source["doi"].lower() != record["doi"].lower():
                    raise ValueError("DataCite returned a different DOI")
                if source["title"].casefold().strip() != record["title"].casefold().strip():
                    raise ValueError("Manual arXiv title differs from the DataCite record")
                record["matched_by"] = "datacite/arxiv + manual authors"
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
        if not all(record.get(field) for field in ("year", "authors", "title")):
            raise ValueError("missing year, authors, or title")
        if "doi" in entry and record["doi"].casefold() != entry["doi"].casefold():
            raise ValueError("Crossref returned a different DOI")
        if "arxiv" in entry and record["doi"].lower() != f"10.48550/arxiv.{entry['arxiv']}":
            raise ValueError("DataCite returned a different DOI")
    except Exception as error:  # noqa: BLE001 - a failed lookup is a reportable result
        record["status"] = f"FAILED: {error}"
    return record


def bibtex(record: dict) -> str:
    authors = " and ".join(record.get("authors") or []) or "Unknown"
    entry_type = record.get("type", "article")
    fields = {
        "author": authors,
        "title": record.get("title", ""),
        "publisher" if entry_type == "book" else "journal": record.get("venue", ""),
        "year": record.get("year", ""),
        "volume": record.get("volume", ""),
        "number": record.get("number", ""),
        "pages": record.get("pages", ""),
        "doi": record.get("doi", ""),
        "eprint": record.get("arxiv", ""),
        "url": record.get("url", ""),
    }
    for name in ("title", "author", "journal", "publisher"):
        if name in fields:
            value = html.unescape(re.sub(r"<[^>]*>", "", fields[name]))
            value = re.sub(r"([&%_#$])", r"\\\1", value)
            fields[name] = "{" + value + "}" if name == "title" else value
    body = "".join(
        f"  {name} = {{{value}}},\n" for name, value in fields.items() if str(value).strip()
    )
    return f"@{entry_type}{{{record['key']},\n{body}}}\n"


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

    failed = [r for r in records if r["status"].startswith("FAILED")]
    if failed or not records or len({r["key"] for r in records}) != len(records):
        raise SystemExit("Bibliography rebuild failed; see lookup results above.")
    args.bib.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.bib.write_text("".join(bibtex(r) for r in records), encoding="utf-8")

    columns = ["key", "status", "matched_by", "year", "title", "authors", "venue", "doi"]
    with args.report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for record in records:
            writer.writerow({**record, "authors": "; ".join(record["authors"])})
    print(f"Wrote {len(records)} records to {args.bib} and {args.report}")


if __name__ == "__main__":
    main()
