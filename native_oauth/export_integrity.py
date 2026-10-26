"""Post-export structural/text coverage checks. These do not certify translation meaning."""
import posixpath
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


def verify_epub(path, chapters):
    ns = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "o": "http://www.idpf.org/2007/opf",
        "h": "http://www.w3.org/1999/xhtml",
    }
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt EPUB archive")
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        package = container.find(".//c:rootfile", ns).get("full-path")
        root = ET.fromstring(archive.read(package))
        folder = posixpath.dirname(package)
        items = {
            item.get("id"): posixpath.normpath(posixpath.join(folder, item.get("href")))
            for item in root.findall(".//o:manifest/o:item", ns)
        }
        spine = [items[item.get("idref")] for item in root.findall(".//o:spine/o:itemref", ns)]
        actual = [name for name in spine if re.fullmatch(r"chap_\d{4}\.xhtml", posixpath.basename(name))]
        expected = [f"chap_{c['num']:04d}.xhtml" for c in chapters]
        if [posixpath.basename(p) for p in actual] != expected:
            raise ValueError("EPUB chapter coverage/order mismatch")
        for chapter, name in zip(chapters, actual):
            node = ET.fromstring(archive.read(name))
            paras = [normalized("".join(p.itertext())) for p in node.findall(".//h:body//h:p", ns)]
            if paras != [normalized(p) for p in chapter["paragraphs"]]:
                raise ValueError(f"EPUB paragraph coverage mismatch: {chapter['num']}")
            headings = [normalized("".join(h.itertext())) for h in node.findall(".//h:h1", ns)]
            if headings != [normalized(chapter["title"])]:
                raise ValueError("EPUB chapter title mismatch")
    return {"chapters": len(chapters), "paragraphs": sum(len(c["paragraphs"]) for c in chapters)}


def verify_pdf(path, chapters):
    import fitz

    with fitz.open(path) as document:
        if not document.page_count:
            raise ValueError("Empty PDF")
        text = normalized(" ".join(page.get_text(sort=True) for page in document))
        bookmarks = [row[1] for row in document.get_toc()]
        for chapter in chapters:
            if normalized(chapter["title"]) not in [normalized(t) for t in bookmarks]:
                raise ValueError("PDF chapter bookmark missing")
        # Whitespace-normalized token subsequence permits page numbers/footer tokens
        # at page boundaries, while requiring every body token in source order.
        tokens = text.split()
        position = 0
        for chapter in chapters:
            for para in chapter["paragraphs"]:
                for word in normalized(para).split():
                    try:
                        position = tokens.index(word, position) + 1
                    except ValueError as error:
                        raise ValueError(f"PDF text coverage failed at chapter {chapter['num']}: {word}") from error
    return {"chapters": len(chapters), "paragraphs": sum(len(c["paragraphs"]) for c in chapters)}


def verify_roundtrip_epub(path, chapters):
    ns = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "o": "http://www.idpf.org/2007/opf",
        "h": "http://www.w3.org/1999/xhtml",
    }
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt EPUB archive")
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        package = container.find(".//c:rootfile", ns).get("full-path")
        root = ET.fromstring(archive.read(package))
        folder = posixpath.dirname(package)
        items = {
            item.get("id"): posixpath.normpath(posixpath.join(folder, item.get("href")))
            for item in root.findall(".//o:manifest/o:item", ns)
        }
        spine = [items[item.get("idref")] for item in root.findall(".//o:spine/o:itemref", ns)]

        actual = []
        for name in spine:
            if re.fullmatch(r"chap_\d{4}\.xhtml", posixpath.basename(name)):
                actual.append(name)
            else:
                try:
                    node = ET.fromstring(archive.read(name))
                    headings = [normalized("".join(h.itertext())) for h in node.findall(".//h:h1", ns)]
                    if headings and not headings[0].startswith("— TẬP"):
                        actual.append(name)
                except Exception:
                    pass

        if len(actual) != len(chapters):
            raise ValueError(f"Roundtrip chapter count mismatch: {len(actual)} != {len(chapters)}")
        for chapter, name in zip(chapters, actual):
            node = ET.fromstring(archive.read(name))
            paras = [normalized("".join(p.itertext())) for p in node.findall(".//h:body//h:p", ns)]
            if paras != [normalized(p) for p in chapter["paragraphs"]]:
                raise ValueError(f"EPUB paragraph coverage mismatch: {chapter['num']}")
            headings = [normalized("".join(h.itertext())) for h in node.findall(".//h:h1", ns)]
            if headings != [normalized(chapter["title"])]:
                raise ValueError(f"EPUB chapter title mismatch: {chapter['num']}")
    return {"chapters": len(chapters), "paragraphs": sum(len(c["paragraphs"]) for c in chapters)}


def verify_azw3(path, chapters):
    converter = shutil.which("ebook-convert")
    if not converter:
        raise RuntimeError("Calibre ebook-convert is required to verify AZW3")
    with tempfile.TemporaryDirectory(prefix="azw3-check-", dir=Path(path).parent) as temp:
        converted = Path(temp) / "verification.epub"
        result = subprocess.run(
            [converter, str(path), str(converted)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if result.returncode or not converted.exists():
            raise ValueError("AZW3 round-trip verification failed")
        return verify_roundtrip_epub(converted, chapters)
