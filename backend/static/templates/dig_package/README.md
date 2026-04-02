# Default Dig Package Template

Place the program **2026 Dig Package Template** here as:

`2026 Dig Package Template.xlsx`

The Dig Package Generator API uses this file when the client does **not** upload a template. Copy it from your reference folder, for example:

`Reference dig package/3-Dig Package Template/2026 Dig Package Template.xlsx`

If this file is missing, generation without an uploaded template returns HTTP **503** with a message to add the file or upload a template in the UI.

## Layout manifest (anchor + offset)

`dig_package_layout.json` in this folder defines **where to write** each field by finding **label text** on the sheet and applying a row/column offset. Edit the JSON when your template wording or layout changes; run `python tools/verify_dig_package_layout.py path/to/template.xlsx` to check every anchor resolves.
