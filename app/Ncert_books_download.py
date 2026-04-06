"""
NCERT English Medium Books Downloader - Grades 6 to 10
=======================================================
Downloads all available English medium NCERT textbooks (Grades 6-10)
from ncert.nic.in as individual chapter PDFs and organises them into:

  SchoolBell/ncert_books/
    Grade_6/Science/  Grade_6/Maths/  Grade_6/Social_Science/
    Grade_7/...
    ...
    Grade_10/...

After running, use SchoolBell's Bulk Import to load them into the app.

REQUIREMENTS:
  pip install requests

USAGE:
  python app/Ncert_books_download.py            # download / resume
  python app/Ncert_books_download.py --verify   # scan folder, list broken files
  python app/Ncert_books_download.py --retry    # re-download only broken/missing files
"""

import os
import sys
import time
import requests

# ── Save into the project's ncert_books/ staging folder ──────────────────────
BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ncert_books"
)
DELAY       = 0.8   # seconds between requests
MIN_PDF_KB  = 10    # files smaller than this are treated as broken (HTML error pages)
MAX_RETRIES = 3     # retry attempts per chapter

# ── Book catalogue ────────────────────────────────────────────────────────────
# Format: (grade_folder, subject_folder, ncert_code, num_chapters)
# Individual chapter PDFs are at:
#   https://ncert.nic.in/textbook/pdf/<code><chapter:02d>.pdf

BOOKS = [
    # ── Grade 4 ───────────────────────────────────────────────────────────────
    ("Grade_4", "EVS",     "deev1",  12),   # Our Wondrous World
    ("Grade_4", "Maths",   "demh1",  14),   # Math-Magic
    ("Grade_4", "English", "deen1",  10),   # Marigold

    # ── Grade 5 ───────────────────────────────────────────────────────────────
    ("Grade_5", "EVS",     "eeev1",  10),   # EVS
    ("Grade_5", "Maths",   "eemh1",  14),   # Math-Magic
    ("Grade_5", "English", "eeen1",  10),   # Marigold

    # ── Grade 6 (New NEP 2024 textbooks) ─────────────────────────────────────
    ("Grade_6", "Science",        "fecu1",  12),
    ("Grade_6", "Maths",          "fegp1",  10),
    ("Grade_6", "Social_Science", "fees1",  14),

    # ── Grade 7 (New NEP 2024 textbooks) ─────────────────────────────────────
    ("Grade_7", "Science",        "gecu1",  12),
    ("Grade_7", "Maths",          "gegp1",   8),
    ("Grade_7", "Social_Science", "gees1",  12),
    ("Grade_7", "English",        "gehc1",   8),

    # ── Grade 8 (New NEP 2024 textbooks) ─────────────────────────────────────
    ("Grade_8", "Science",        "hecu1",  13),
    ("Grade_8", "Maths_Part1",    "hegp1",   7),
    ("Grade_8", "Maths_Part2",    "hegp2",   7),
    ("Grade_8", "Social_Science", "hees1",   7),

    # ── Grade 9 ───────────────────────────────────────────────────────────────
    ("Grade_9", "Maths",          "iemh1",  12),
    ("Grade_9", "Science",        "iesc1",  12),
    ("Grade_9", "English",        "iemo1",   9),
    ("Grade_9", "Social_Science", "iess1",   6),
    ("Grade_9", "Social_Science", "iess2",   4),

    # ── Grade 10 ──────────────────────────────────────────────────────────────
    ("Grade_10", "Maths",          "jemh1",  14),
    ("Grade_10", "Science",        "jesc1",  13),
    ("Grade_10", "Social_Science", "jess1",   7),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def chapter_url(code, n):
    return "https://ncert.nic.in/textbook/pdf/" + code + "{:02d}".format(n) + ".pdf"


def is_good_pdf(path):
    """Return True if the file exists, is large enough, and starts with %PDF."""
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) < MIN_PDF_KB * 1024:
        return False
    try:
        with open(path, "rb") as fh:
            header = fh.read(5)
        return header == b"%PDF-"
    except OSError:
        return False


def download_pdf(url, dest_path, session):
    """Download url to dest_path. Returns True on success."""
    try:
        resp = session.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        tmp_path = dest_path + ".tmp"
        with open(tmp_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                fh.write(chunk)
        # Validate before committing
        if not is_good_pdf(tmp_path):
            os.remove(tmp_path)
            return False
        os.replace(tmp_path, dest_path)
        return True
    except requests.HTTPError:
        return False
    except requests.RequestException as e:
        print("    Network error: " + str(e))
        return False


def download_with_retry(url, dest_path, session):
    """Try downloading up to MAX_RETRIES times with exponential back-off."""
    for attempt in range(1, MAX_RETRIES + 1):
        ok = download_pdf(url, dest_path, session)
        if ok:
            return True
        if attempt < MAX_RETRIES:
            wait = attempt * 2
            print("    Retry " + str(attempt) + "/" + str(MAX_RETRIES - 1) +
                  " in " + str(wait) + "s ...", end=" ", flush=True)
            time.sleep(wait)
    return False


# ── Scan / verify mode ────────────────────────────────────────────────────────

def scan_broken():
    """Walk BASE_DIR and return list of (grade, subject, code, ch) for broken files."""
    broken = []
    for grade, subject, code, num_chapters in BOOKS:
        folder = os.path.join(BASE_DIR, grade, subject)
        for ch in range(1, num_chapters + 1):
            filename  = code + "{:02d}".format(ch) + ".pdf"
            dest_path = os.path.join(folder, filename)
            if not is_good_pdf(dest_path):
                broken.append((grade, subject, code, ch, dest_path))
    return broken


def cmd_verify():
    print("Scanning: " + BASE_DIR)
    broken = scan_broken()
    if not broken:
        print("All files look good.")
        return
    print("Broken / missing files (" + str(len(broken)) + "):")
    for grade, subject, code, ch, path in broken:
        size = os.path.getsize(path) if os.path.exists(path) else 0
        tag  = "MISSING" if not os.path.exists(path) else ("TINY " + str(size) + "B" if size < MIN_PDF_KB * 1024 else "BAD HEADER")
        print("  [" + tag + "] " + grade + "/" + subject + "/" + code + "{:02d}".format(ch) + ".pdf")


# ── Main download loop ────────────────────────────────────────────────────────

def run_download(force_list=None):
    """
    Download all chapters. If force_list is given (list of dest_paths),
    only those files are (re-)downloaded.
    """
    print("=" * 62)
    print("  NCERT English Books Downloader  (Grades 6-10)")
    print("=" * 62)
    print("  Saving to : " + BASE_DIR)
    total_chapters = sum(n for _, _, _, n in BOOKS)
    print("  Books: " + str(len(BOOKS)) + "   Chapters: " + str(total_chapters))
    if force_list is not None:
        print("  Mode: RETRY broken files (" + str(len(force_list)) + " targets)")
    print("=" * 62)

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    downloaded = 0
    skipped    = 0
    failed     = 0

    for grade, subject, code, num_chapters in BOOKS:
        folder = os.path.join(BASE_DIR, grade, subject)
        os.makedirs(folder, exist_ok=True)

        print("\n[" + grade + "] " + subject + "  (" + code + ", " + str(num_chapters) + " chapters)")

        for ch in range(1, num_chapters + 1):
            filename  = code + "{:02d}".format(ch) + ".pdf"
            dest_path = os.path.join(folder, filename)
            url       = chapter_url(code, ch)

            # Skip if already a good PDF (unless this file is in the force list)
            if force_list is not None:
                if dest_path not in force_list:
                    skipped += 1
                    continue
            else:
                if is_good_pdf(dest_path):
                    size_kb = os.path.getsize(dest_path) // 1024
                    print("  Ch" + str(ch) + " skip (exists, " + str(size_kb) + " KB)")
                    skipped += 1
                    continue
                elif os.path.exists(dest_path):
                    size = os.path.getsize(dest_path)
                    print("  Ch" + str(ch) + " broken (" + str(size) + " B) - re-downloading ...", end=" ", flush=True)
                else:
                    print("  Ch" + str(ch) + " downloading ...", end=" ", flush=True)

            ok = download_with_retry(url, dest_path, session)

            if ok:
                size_kb = os.path.getsize(dest_path) // 1024
                print("OK (" + str(size_kb) + " KB)")
                downloaded += 1
            else:
                print("FAILED - " + url)
                failed += 1

            time.sleep(DELAY)

    print("\n" + "=" * 62)
    print("  Done!")
    print("  Downloaded : " + str(downloaded))
    print("  Skipped    : " + str(skipped) + "  (already good)")
    print("  Failed     : " + str(failed))
    print("=" * 62)
    print("\nPDFs saved under: " + BASE_DIR)
    print("Run SchoolBell Bulk Import to load them into the app.\n")


def cmd_retry():
    broken = scan_broken()
    if not broken:
        print("Nothing to retry - all files look good.")
        return
    force_paths = set(path for _, _, _, _, path in broken)
    run_download(force_list=force_paths)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--verify":
        cmd_verify()
    elif arg == "--retry":
        cmd_retry()
    else:
        run_download()
