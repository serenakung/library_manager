/* JavaScript for the personal library manager */

document.addEventListener('DOMContentLoaded', () => {
    const startScanButton = document.getElementById('start-scan');
    const stopScanButton = document.getElementById('stop-scan');
    const scannerContainer = document.getElementById('scanner-container');
    const scannerElem = document.getElementById('scanner');
    const isbnInput = document.getElementById('isbn');

    // Gift field elements for toggling
    const giftCheckbox = document.getElementById('gift');
    const giftFromGroup = document.getElementById('gift-from-group');
    const giftFromInput = document.getElementById('gift_from');
    // Generic search and live-only filter
    const searchInput = document.getElementById('search-input');
    const liveOnlyCheckbox = document.getElementById('live-only');
    // Error message container
    const errorMessageDiv = document.getElementById('error-message');

    /**
     * Display an error message to the user in a dedicated area.  The message
     * automatically hides after a few seconds.  If the container does not
     * exist, falls back to alert().
     * @param {string} msg
     */
    function showError(msg) {
        if (errorMessageDiv) {
            errorMessageDiv.textContent = msg;
            errorMessageDiv.style.display = 'block';
            // Hide after 6 seconds
            setTimeout(() => {
                errorMessageDiv.style.display = 'none';
                errorMessageDiv.textContent = '';
            }, 6000);
        } else {
            alert(msg);
        }
    }

    // Normalize an ISBN-like string for comparison: strip non-digits
    function normalizeIsbn(s) {
        if (!s) return '';
        return String(s).replace(/\D/g, '');
    }

    let html5QrCode;

    function startScanner(onDecoded) {
        // Perform offline and library checks before attempting to start the scanner
        if (!navigator.onLine) {
            showError('You appear to be offline. Barcode scanning requires an internet connection to load the scanning library.');
            return;
        }
        if (!window.Html5Qrcode) {
            showError('Barcode scanner library failed to load. Please check your internet connection or try again later.');
            return;
        }
        scannerContainer.style.display = 'block';
        html5QrCode = new Html5Qrcode('scanner');
        html5QrCode.start({ facingMode: 'environment' }, { fps: 10, qrbox: 250 },
            (decodedText) => {
                // If a callback was supplied use it, otherwise default to populating
                // the ISBN field and stopping the scanner (existing behaviour).
                if (typeof onDecoded === 'function') {
                    try {
                        onDecoded(decodedText);
                    } catch (err) {
                        console.error('Error in scan callback', err);
                    }
                } else {
                    // Default behaviour: if the scanned ISBN matches a book already
                    // in the table, mark that book as read via the server.  If no
                    // match is found, populate the Add form's ISBN field so the
                    // user can add the book.
                    const scanned = normalizeIsbn(decodedText);
                    let matched = null;
                    document.querySelectorAll('tbody tr').forEach((row) => {
                        const rowIsbn = normalizeIsbn(row.dataset.isbn || '');
                        if (rowIsbn && scanned && rowIsbn === scanned) {
                            matched = row;
                        }
                    });

                    if (matched) {
                        // Found an existing book — stop scanner and call server to
                        // increment read counts.
                        stopScanner();
                        fetch('/read_by_isbn', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                            body: `isbn=${encodeURIComponent(matched.dataset.isbn)}`,
                        }).then(async (resp) => {
                            if (!resp.ok) {
                                const txt = await resp.text();
                                showError('Failed to mark as read: ' + txt);
                                return;
                            }
                            // Success: reload to show updated counts and last read
                            window.location.reload();
                        }).catch((err) => {
                            console.error('Error marking read by ISBN', err);
                            showError('Network error while marking read.');
                        });
                    } else {
                        // No matching book — populate the add form so the user can
                        // add this scanned ISBN to their collection.
                        isbnInput.value = decodedText;
                        stopScanner();
                        // Informational message
                        showError('Scanned ISBN not found in your library — filled Add form.');
                    }
                }
            },
            (errorMessage) => {
                // scanning errors (not camera permission issues) can be ignored or logged
            }
        ).catch((err) => {
            console.error('Error starting scanner', err);
            scannerContainer.style.display = 'none';
            // Provide user feedback if camera is inaccessible or permission denied
            showError('Unable to access your camera. Please ensure a camera is available and that you have granted permission.');
        });
    }

    function stopScanner() {
        if (html5QrCode) {
            html5QrCode.stop().then(() => {
                html5QrCode.clear();
                scannerContainer.style.display = 'none';
            }).catch((err) => {
                console.error('Error stopping scanner', err);
            });
        } else {
            scannerContainer.style.display = 'none';
        }
    }

    startScanButton.addEventListener('click', () => {
        startScanner();
    });
    stopScanButton.addEventListener('click', () => {
        stopScanner();
    });

    // Show or hide the gift giver input based on whether the book is a gift
    if (giftCheckbox) {
        const toggleGiftFromVisibility = () => {
            if (giftCheckbox.checked) {
                giftFromGroup.style.display = 'block';
            } else {
                giftFromGroup.style.display = 'none';
                // Clear the field when hiding so stray values don't persist
                if (giftFromInput) giftFromInput.value = '';
            }
        };
        // Initialize visibility on page load
        toggleGiftFromVisibility();
        giftCheckbox.addEventListener('change', toggleGiftFromVisibility);
    }

    // Generic filter function combining search by title/authors/tags and live-only toggle
    function filterRows() {
        const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const liveOnly = liveOnlyCheckbox ? liveOnlyCheckbox.checked : false;
        document.querySelectorAll('tbody tr').forEach((row) => {
            const title = (row.dataset.title || '').toLowerCase();
            const authors = (row.dataset.authors || '').toLowerCase();
            const tags = (row.dataset.tags || '').toLowerCase();
            const isLive = (row.dataset.live || '').toLowerCase() === 'true';
            const matchesQuery = !query || title.includes(query) || authors.includes(query) || tags.includes(query);
            const passesLiveFilter = !liveOnly || isLive;
            if (matchesQuery && passesLiveFilter) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }
    // Attach listeners for search and live-only toggle
    if (searchInput) {
        searchInput.addEventListener('input', filterRows);
    }
    if (liveOnlyCheckbox) {
        liveOnlyCheckbox.addEventListener('change', filterRows);
    }

    // Attach event handlers for toggling live status and marking read
    document.querySelectorAll('.live-toggle').forEach((checkbox) => {
        checkbox.addEventListener('change', function () {
            const row = this.closest('tr');
            const id = row.dataset.id;
            const newState = this.checked;
            // Update the backend
            fetch(`/update/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `is_live=${newState}`
            }).then(() => {
                // Update the data-live attribute on the row so the filter works correctly
                row.dataset.live = newState ? 'true' : 'false';
                // Re-apply filtering in case only live books are being shown
                if (typeof filterRows === 'function') filterRows();
            });
        });
    });
    document.querySelectorAll('.mark-read').forEach((button) => {
        button.addEventListener('click', function () {
            const row = this.closest('tr');
            const id = row.dataset.id;
            fetch(`/read/${id}`, { method: 'POST' }).then(() => {
                // reload to update last read date
                window.location.reload();
            });
        });
    });

    // Scan-to-mark-read: when user clicks the button start scanner and POST
    // scanned ISBN to the server to mark the matching book as read.
    document.querySelectorAll('.scan-mark-read').forEach((button) => {
        button.addEventListener('click', function () {
            // Start scanner in "mark read" mode.  When a code is decoded
            // send it to the server and stop the scanner.
            startScanner(function (decodedText) {
                // Optionally show feedback while we contact the server
                stopScanner();
                fetch('/read_by_isbn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `isbn=${encodeURIComponent(decodedText)}`,
                }).then(async (resp) => {
                    if (!resp.ok) {
                        const txt = await resp.text();
                        showError('Failed to mark as read: ' + txt);
                        return;
                    }
                    // Success: reload to show updated counts and last read
                    window.location.reload();
                }).catch((err) => {
                    console.error('Error marking read by ISBN', err);
                    showError('Network error while marking read.');
                });
            });
        });
    });

    // Editing logic
    let editingRow = null;
    /**
     * Activate editing mode on a table row.  Replaces certain cells with
     * input fields so the user can modify title, authors, tags, gift status
     * and gift giver.  Provides Save and Cancel buttons.
     */
    function enableEditing(row) {
        // Prevent multiple rows editing simultaneously
        if (editingRow && editingRow !== row) {
            // Cancel editing on previous row before editing a new one
            cancelEditing(editingRow);
        }
        // If this row is already in editing mode, do nothing
        if (row.classList.contains('editing')) {
            return;
        }
        editingRow = row;
        row.classList.add('editing');
        // Capture current values for potential restoration
        const cells = Array.from(row.children);
        const originalValues = cells.map(cell => cell.innerHTML);
        row._originalValues = originalValues;

        // Extract current data from dataset and cells
        const title = row.dataset.title || cells[0].textContent;
        const authors = row.dataset.authors || cells[2].textContent;
        const tags = row.dataset.tags || cells[3].textContent;
        const giftFrom = row.dataset.giftFrom || cells[5].textContent;
        const isGift = row.querySelector('.gift-toggle') ? row.querySelector('.gift-toggle').checked : false;

        // Replace cells 0 (title), 2 (authors), 3 (tags), 5 (gifted by), 6 (gift?) and 8 (actions)
        // Title input
        cells[0].innerHTML = `<input type="text" class="edit-title" value="${escapeHtml(title)}">`;
        // ISBN (cells[1]) remains read‑only
        // Authors input
        cells[2].innerHTML = `<input type="text" class="edit-authors" value="${escapeHtml(authors)}">`;
        // Tags input
        cells[3].innerHTML = `<input type="text" class="edit-tags" value="${escapeHtml(tags)}">`;
        // Last read date (cells[4]) remains read‑only
        // Gifted by input
        cells[5].innerHTML = `<input type="text" class="edit-gift-from" value="${escapeHtml(giftFrom)}">`;
        // Gift? checkbox
        cells[6].innerHTML = `<input type="checkbox" class="edit-gift-toggle" ${isGift ? 'checked' : ''}>`;
        // Live? cell (cells[7]) remains read‑only for editing; toggled via separate control
        // Actions cell: Save/Cancel buttons
        cells[8].innerHTML = '';
        const saveBtn = document.createElement('button');
        saveBtn.textContent = 'Save';
        saveBtn.className = 'save-edit';
        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = 'Cancel';
        cancelBtn.className = 'cancel-edit';
        cells[8].appendChild(saveBtn);
        cells[8].appendChild(cancelBtn);

        // Save handler
        saveBtn.addEventListener('click', function () {
            const id = row.dataset.id;
            const newTitle = row.querySelector('.edit-title').value.trim();
            const newAuthors = row.querySelector('.edit-authors').value.trim();
            const newTags = row.querySelector('.edit-tags').value.trim();
            const newGiftFrom = row.querySelector('.edit-gift-from').value.trim();
            const newIsGift = row.querySelector('.edit-gift-toggle').checked;
            // Build form data
            const params = new URLSearchParams();
            params.append('title', newTitle);
            params.append('authors', newAuthors);
            params.append('tags', newTags);
            params.append('gift_from', newGiftFrom);
            params.append('is_gift', newIsGift);
            // Send update request
            fetch(`/update/${id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: params.toString(),
            }).then((response) => {
                if (!response.ok) {
                    showError('Failed to save changes.');
                    return;
                }
                // Reload the page to reflect changes; simpler than updating DOM manually
                window.location.reload();
            }).catch(() => {
                showError('An error occurred while saving changes.');
            });
        });
        // Cancel handler
        cancelBtn.addEventListener('click', function () {
            cancelEditing(row);
        });
    }

    /**
     * Cancel editing on the given row and restore its original cell content.
     */
    function cancelEditing(row) {
        if (!row.classList.contains('editing')) {
            return;
        }
        const cells = Array.from(row.children);
        const originalValues = row._originalValues || [];
        originalValues.forEach((html, idx) => {
            cells[idx].innerHTML = html;
        });
        row.classList.remove('editing');
        editingRow = null;
    }

    /**
     * Escape HTML special characters to prevent injection when inserting user
     * data into input values.
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // Attach click handlers for edit buttons
    document.querySelectorAll('.edit-book').forEach((button) => {
        button.addEventListener('click', function (e) {
            const row = this.closest('tr');
            enableEditing(row);
        });
    });

    // Apply initial filtering on page load so that only live books are shown by default
    if (typeof filterRows === 'function') {
        filterRows();
    }
});