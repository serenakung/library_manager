from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import json
import os
import datetime
import requests


"""
This is a minimal home‑library management server. It exposes a small web
application which allows you to catalogue your personal book collection
without relying on any external vendor. Key features include:

* Adding books by scanning a barcode or entering an ISBN manually.  When
  an ISBN is provided the server will attempt to fetch metadata from
  the Open Library ISBN API. If the look‑up fails or you are offline
  (this notebook environment does not have outbound internet access), you can
  supply the title, author and tags manually on the form.
* Tracking whether a book is currently “live” in your library (i.e. on
  the shelf) or stored away/donated. A live book can be toggled off when
  you pack it away.
* Recording when a book was last read.  You can mark a book as read
  with a single click from the list view.  This date is used to
  identify books that haven’t been touched in a while so you can
  consider making them live again or donating them.
* Flagging books that were gifts.  This allows you to avoid donating
  gifted books accidentally.

The data model is deliberately simple and persisted to a JSON file on disk.
If you restart the server your collection is restored.  For a more
production‑ready setup you might swap this for SQLite or another DB
engine.  See the README at the bottom of this file for details on
usage.
"""

app = Flask(__name__)

# Where to persist your book catalogue.  When run under agent
# constraints the current working directory is writeable.  Feel free
# to change this path.
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'books.json')


def ensure_data_file():
    """Ensure the data directory and file exist."""
    data_dir = os.path.dirname(DATA_FILE)
    os.makedirs(data_dir, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)


def load_books():
    """Load the list of books from the JSON file."""
    ensure_data_file()
    with open(DATA_FILE) as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_books(books):
    """Persist the current book list to disk."""
    ensure_data_file()
    with open(DATA_FILE, 'w') as f:
        json.dump(books, f, indent=2)


def fetch_book_data(isbn: str):
    """
    Attempt to fetch book metadata from the Open Library ISBN API.

    Open Library supports requests of the form
    https://openlibrary.org/isbn/{isbn}.json which return JSON metadata
    about a specific edition.  The documentation explains that by
    appending ".json" to an ISBN URL you get a machine‑readable
    response【822562277558833†L166-L181】.  We try to parse the fields we care
    about (title, authors and subjects) and fall back to None if
    anything goes wrong.  Because the environment used by this agent
    typically does not have outbound network access, this will always
    fail here.  However, the code is included for completeness so you
    can run the same project on your own machine and benefit from
    automatic metadata lookup.
    """
    url = f'https://openlibrary.org/isbn/{isbn}.json'
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        title = data.get('title', '')
        authors_field = data.get('by_statement') or ''
        # The Open Library Books API supports two modes via the
        # `jscmd` parameter: `viewapi` and `data`【822562277558833†L190-L239】.
        # If the ISBN endpoint returns subjects directly, use them.  Otherwise
        # leave the tags empty and let the user supply them.
        subjects = data.get('subjects') or []
        tags = []
        if subjects:
            # Subjects on Open Library include descriptive labels such as
            # "Money", "Quality of Life" and "Investing"【850938168933017†L95-L123】.
            # We preserve them as tags.
            tags = [subj.get('name') if isinstance(subj, dict) else str(subj)
                    for subj in subjects]
        return {
            'title': title,
            'authors': authors_field,
            'tags': tags,
        }
    except Exception:
        # In offline environments this will throw.  Return None so the
        # caller can fall back to manual entry.
        return None


@app.route('/')
def index():
    """Render the main page with the current list of books."""
    books = load_books()
    # Sort books alphabetically for a nicer UX
    books.sort(key=lambda b: b.get('title', '').lower())
    # Ensure read counters exist and compute today's reads for the UI
    today = datetime.date.today().isoformat()
    for b in books:
        # Backwards compatible defaults
        b.setdefault('read_count', 0)
        b.setdefault('read_log', {})
        b['reads_today'] = b['read_log'].get(today, 0)
    return render_template('index.html', books=books)


@app.route('/add', methods=['POST'])
def add_book():
    """
    Add a new book to the collection.  We accept the ISBN and gift flag
    plus optional manual metadata (title, authors, tags).  When
    possible we try to fetch metadata automatically from Open Library.
    """
    isbn = request.form.get('isbn', '').strip()
    # Whether this book was given as a gift.  When a book is a gift the
    # interface allows capturing who it came from via the ``gift_from``
    # field.
    gift = bool(request.form.get('gift'))
    # Name of the gift giver.  Default to empty string if not provided.
    gift_from = request.form.get('gift_from', '').strip()
    manual_title = request.form.get('title', '').strip()
    manual_authors = request.form.get('authors', '').strip()
    manual_tags = request.form.get('tags', '').strip()

    # Try automatic metadata lookup
    book_data = fetch_book_data(isbn) if isbn else None

    # If nothing came back or ISBN is missing, fall back to manual
    if book_data is None:
        book_data = {
            'title': manual_title,
            'authors': manual_authors,
            'tags': [t.strip() for t in manual_tags.split(',') if t.strip()],
        }

    # Load existing collection and allocate an ID.  Using a simple
    # incremental integer keeps things straightforward.  For a real
    # application you might use UUIDs instead.
    books = load_books()
    next_id = (max((b['id'] for b in books), default=0) + 1) if books else 1
    now = datetime.date.today().isoformat()
    book_entry = {
        'id': next_id,
        'isbn': isbn,
        'title': book_data.get('title', '') or 'Unknown title',
        'authors': book_data.get('authors', '') or '',
        'tags': book_data.get('tags', []),
        'is_live': True,
        'last_read_date': now,
        'is_gift': gift,
        # Record who gifted the book.  If ``gift`` is false this will
        # be an empty string.  This field is used for searching.
        'gift_from': gift_from,
    }
    books.append(book_entry)
    save_books(books)
    return redirect(url_for('index'))


@app.route('/update/<int:book_id>', methods=['POST'])
def update_book(book_id: int):
    """
    Update a book's boolean fields (live/gift) and optionally its
    last_read_date or tags.  The request must use form-encoded data.
    """
    books = load_books()
    updated = False
    for book in books:
        if book['id'] == book_id:
            # Toggle live state
            is_live = request.form.get('is_live')
            if is_live is not None:
                book['is_live'] = is_live == 'true'
            # Toggle gift state
            is_gift = request.form.get('is_gift')
            if is_gift is not None:
                book['is_gift'] = is_gift == 'true'
            # Update gift giver.  Only update if the key is present in
            # the submitted form.  Because gift giver names may contain
            # spaces we do not coerce the boolean flag here.
            gift_from = request.form.get('gift_from')
            if gift_from is not None:
                book['gift_from'] = gift_from.strip()
            # Update last read date
            last_read = request.form.get('last_read_date')
            if last_read:
                book['last_read_date'] = last_read
            # Update tags
            new_tags = request.form.get('tags')
            if new_tags is not None:
                book['tags'] = [t.strip()
                                for t in new_tags.split(',') if t.strip()]
            # Update title
            new_title = request.form.get('title')
            if new_title is not None:
                book['title'] = new_title.strip()
            # Update authors
            new_authors = request.form.get('authors')
            if new_authors is not None:
                book['authors'] = new_authors.strip()
            updated = True
            break
    if updated:
        save_books(books)
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Book not found'}), 404


@app.route('/read/<int:book_id>', methods=['POST'])
def mark_read(book_id: int):
    """Mark a book as read today by updating its last_read_date."""
    books = load_books()
    for book in books:
        if book['id'] == book_id:
            today = datetime.date.today().isoformat()
            book['last_read_date'] = today
            # Initialize read_count and log if they don't exist
            book.setdefault('read_count', 0)
            book.setdefault('read_log', {})
            # Increment total count and today's count
            book['read_count'] = book.get('read_count', 0) + 1
            book['read_log'][today] = book['read_log'].get(today, 0) + 1
            save_books(books)
            return jsonify({'status': 'ok'})
    return jsonify({'error': 'Book not found'}), 404


@app.route('/read_by_isbn', methods=['POST'])
def read_by_isbn():
    """Mark a book as read by supplying its ISBN (scanned value).

    Request form: isbn=...  Returns JSON {status: 'ok', book_id: id} or 404.
    """
    isbn = request.form.get('isbn', '').strip()
    if not isbn:
        return jsonify({'error': 'No ISBN provided'}), 400
    books = load_books()
    today = datetime.date.today().isoformat()
    for book in books:
        if book.get('isbn') == isbn:
            book['last_read_date'] = today
            book.setdefault('read_count', 0)
            book.setdefault('read_log', {})
            book['read_count'] = book.get('read_count', 0) + 1
            book['read_log'][today] = book['read_log'].get(today, 0) + 1
            save_books(books)
            return jsonify({'status': 'ok', 'book_id': book.get('id')})
    return jsonify({'error': 'Book not found'}), 404


@app.route('/export')
def export_live_books():
    """Export a summarized list of books that are currently live.

    Query parameters:
      - format: 'csv' (default) or 'json'

    CSV includes: id,title,authors,isbn,tags,last_read_date
    """
    fmt = request.args.get('format', 'csv').lower()
    books = load_books()
    live = [b for b in books if b.get('is_live')]
    today = datetime.date.today().isoformat()

    summary = []
    for b in live:
        summary.append({
            'id': b.get('id', ''),
            'title': b.get('title', ''),
            'authors': b.get('authors', ''),
            'isbn': b.get('isbn', ''),
            'tags': ','.join(b.get('tags', [])) if b.get('tags') else '',
            'last_read_date': b.get('last_read_date', ''),
            'read_count': int(b.get('read_count', 0)),
            'reads_today': int(b.get('read_log', {}).get(today, 0)),
        })

    if fmt == 'json':
        return jsonify(summary)

    if fmt == 'pdf':
        # Try to generate a simple PDF summary.  ReportLab is optional;
        # if it's not installed return a helpful error explaining how
        # to add it.
        try:
            from io import BytesIO
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
        except Exception:
            msg = (
                "PDF export requires the ReportLab package.\n"
                "Install it with: pip install reportlab"
            )
            resp = make_response(msg, 500)
            resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
            return resp

        # Use Platypus Table for nicer formatting and proper columns
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        except Exception:
            # If Platypus not available fall back to previous canvas output
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            c.setFont('Helvetica-Bold', 14)
            c.drawString(inch, height - inch, 'Live books summary')
            c.setFont('Helvetica', 10)
            y = height - inch - 20
            c.setFont('Helvetica-Bold', 9)
            c.drawString(inch, y, 'ID')
            c.drawString(inch + 40, y, 'Title')
            y -= 14
            c.setFont('Helvetica', 9)
            for row in summary:
                if y < inch:
                    c.showPage()
                    y = height - inch
                id_text = str(row.get('id', ''))
                title = (row.get('title') or '')[:60]
                authors = (row.get('authors') or '')[:30]
                isbn = (row.get('isbn') or '')[:20]
                tags = (row.get('tags') or '')[:30]
                last = (row.get('last_read_date') or '')
                c.drawString(inch, y, id_text)
                c.drawString(inch + 40, y, title)
                y -= 14
            c.save()
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=inch,
                                    leftMargin=inch, topMargin=inch, bottomMargin=inch)
            styles = getSampleStyleSheet()
            # Small paragraph style for wrapped cells
            small_style = ParagraphStyle(
                'small', parent=styles['Normal'], fontSize=8, leading=10)
            normal_style = ParagraphStyle(
                'normal', parent=styles['Normal'], fontSize=9, leading=11)
            title_para = Paragraph('Live books summary', styles['Title'])
            return resp

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=inch, leftMargin=inch,
                                topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        # Paragraph styles: normal for title, small for wrapped smaller cells
        normal_style = ParagraphStyle(
            'normal', parent=styles['Normal'], fontSize=9, leading=11)
        small_style = ParagraphStyle(
            'small', parent=styles['Normal'], fontSize=8, leading=10)
        title_para = Paragraph('Live books summary', styles['Title'])

        data = []
        # Use Paragraphs for header cells so long labels can wrap (multi-line)
        header_style = ParagraphStyle('header', parent=styles['Normal'], fontSize=8, leading=9)
        header = [
            Paragraph('ID', header_style),
            Paragraph('Title', header_style),
            Paragraph('Authors', header_style),
            Paragraph('ISBN', header_style),
            Paragraph('Tags', header_style),
            Paragraph('Last read', header_style),
            Paragraph('Total<br/>reads', header_style),
            Paragraph('Reads<br/>today', header_style),
        ]
        data.append(header)

        for row in summary:
            data.append([
                str(row.get('id', '')),
                Paragraph(row.get('title', ''), normal_style),
                Paragraph(row.get('authors', ''), small_style),
                row.get('isbn', ''),
                Paragraph(row.get('tags', ''), small_style),
                row.get('last_read_date', ''),
                str(row.get('read_count', 0)),
                str(row.get('reads_today', 0)),
            ])

        # Column widths (must fit the printable width of the page)
        # Adjusted column widths to prevent the rightmost columns from being squashed
        colWidths = [30, 150, 80, 60, 80, 50, 40, 40]
        table = Table(data, colWidths=colWidths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (6, 1), (7, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        flowables = [title_para, Spacer(1, 12), table]
        doc.build(flowables)
        buffer.seek(0)
        resp = make_response(buffer.getvalue())
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = 'attachment; filename=live_books.pdf'
        return resp

    # Default: CSV download
    import csv
    from io import StringIO

    si = StringIO()
    fieldnames = ['id', 'title', 'authors', 'isbn', 'tags',
                  'last_read_date', 'read_count', 'reads_today']
    writer = csv.DictWriter(si, fieldnames=fieldnames)
    writer.writeheader()
    for row in summary:
        writer.writerow(row)

    output = si.getvalue()
    resp = make_response(output)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename=live_books.csv'
    return resp


if __name__ == '__main__':
    # During development the server runs in debug mode.  In
    # production you would instead configure a proper WSGI server.
    # Run the development server on port 8080 instead of the default 5000.
    # Changing the port allows hosting on environments where 8080 is the
    # designated port, such as certain PaaS providers.
    app.run(host='0.0.0.0', port=8080, debug=True)

"""
README
======

This repository contains a simple personal library manager implemented
with Flask.  It is designed to be self‑hosted and respects your
privacy – your book catalogue stays on your machine.

Usage
-----

1. Install dependencies (Flask and requests).  In this notebook
   environment they are already available.  On your machine run:
   
       pip install flask requests

2. Start the server by executing `python app.py` from the `library_app`
   directory.  This will launch a development web server on
   http://localhost:5000.

3. Navigate to `http://localhost:5000` in your browser.  From here you
   can add books by scanning a barcode (requires camera access and
   internet to load the Html5‑Qrcode library) or by typing an ISBN and
   optional metadata.  When an ISBN is provided the app attempts to
   fetch metadata from Open Library’s ISBN API【822562277558833†L166-L181】.  If
   network access is unavailable or the lookup fails, you can supply
   the title, authors and tags manually.

4. The book list shows your collection along with last read dates and
   whether each book is currently live.  You can mark a book as read
   from the table and toggle its live status.  Gifted books are
   indicated and protected from accidental donation.  When a book is
   marked as a gift you can record who gifted it; this information is
   searchable from the collection view.

Notes
-----

* The Open Library subject system associates free‑form descriptive
  labels (e.g. "Money", "Quality of Life", etc.) with works【850938168933017†L95-L123】.
  If the API returns a list of subjects for a book the app uses
  them as initial tags.  Otherwise tags default to an empty list and
  you can assign your own categories.
* ISBNs are unique identifiers for each edition and variation of a
  book【189211911473509†L306-L316】.  Make sure you scan the correct edition if
  you care about format (hardcover, paperback, etc.).
* This is a prototype.  For a richer experience consider adding user
  accounts, search, filtering by tags, or migrating the storage to a
  relational database like SQLite.
"""
