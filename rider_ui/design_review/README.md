# Editable UI review

Open **motomedic-editable.html** in your browser. It is a standalone page with no external dependencies, model calls or live rider API.

1. Click any UI text and edit it directly.
2. To remove a whole block, wrap its heading in parentheses, e.g. **(02 · Check)**. Parenthesizing or emptying a paragraph, caption, button label or other sub-item removes only that item. Main headings remove their whole block.
3. **Show changes** displays your edits and removal markers. **Preview layout** hides editing outlines.
4. Click **Save edited HTML**. Save as **motomedic-edited.html** in this folder. If your browser downloads the file instead, move that downloaded HTML here.
5. Ask Codex to compare and apply the edits. The original is in **original.html**, with an independent **baseline.json**. These files must remain unchanged.

You can also edit the HTML in a text editor. Preserve data-copy-id/data-block-id attributes so edits remain traceable.

Comparison:
```text
python rider_ui/design_review/compare_review.py rider_ui/design_review/motomedic-edited.html --output reports/rider_ui/copy_review_diff.json
```

The comparison distinguishes changed copy, remove_blocks (main-heading removal) and remove_fields (individual item removal). It does not alter the Streamlit app or push GitHub. After review, Codex applies the requested presentation changes to the app, checks them, then pushes the agreed version.

All 58 authored text fields from the current landing/sidebar and conversation/citation/error labels are included. Technical response content and server-issued choices are dynamic backend data, not editable mock repair instructions. The additional screen-state section contains labels only.


If you already edited an older copy, save it first, reopen the updated page, and use **Load saved edits** to bring its text edits into the fixed editor. Only text fields are imported; the older removal logic is not.

## Applied owner review v1

`owner-edited-v1.html` preserves the saved owner edits byte for byte. The six copy changes and two field removals were applied to `rider_ui/app.py`; the missing space in “resolution. If” was corrected. The topic label is visually collapsed while its accessible dropdown remains. The disconnected notice is removed while disconnected input stays disabled. No whole block was removed. See `reports/rider_ui/owner_copy_applied_v1.json` and the desktop/mobile browser checks in `reports/rider_ui/owner_copy/`.
