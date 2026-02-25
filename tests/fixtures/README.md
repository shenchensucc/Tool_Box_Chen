# Inspection Report Test Fixtures

## Training / Testing Data

- **inspection_report_52-021K.pdf** – Acuren UT report for Circuit 52-021K, CML 1.01 & 1.05

### Expected extraction (ground truth)

| Circuit  | CML   | Reading |
|----------|-------|---------|
| 52-021K  | 1.01-1| 0.285   |
| 52-021K  | 1.01-2| 0.299   |
| 52-021K  | 1.05-1| 0.456   |
| 52-021K  | 1.05-2| 0.450   |
| 52-021K  | 1.05-3| 0.393   |
| 52-021K  | 1.05-4| 0.405   |

Table structure (page 4): 8" section → CML 1.01, 6" section → CML 1.05. Row number = sub-CML suffix. Column A = reading.

### Parser logic (Acuren)

- Circuit base: "52-021K" from "52-021K 1-2"
- CML bases from header "CML 1.01 & 1.05"
- Table extraction: pdfplumber with `vertical_strategy='text', horizontal_strategy='text'`
- Row number: cell before diameter (8" or 6") in SECTION column
- 8" → CML 1.01, 6" → CML 1.05; sub-CML = base + "-" + row_num
