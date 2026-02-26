# Inspection Report Test Fixtures

## Training / Testing Data

### 1. inspection_report_52-021K.pdf

Acuren UT report for Circuit 52-021K, CML 1.01 & 1.05 (Format A: 8"/6").

| Circuit  | CML   | Reading |
|----------|-------|---------|
| 52-021K  | 1.01-1| 0.285   |
| 52-021K  | 1.01-2| 0.299   |
| 52-021K  | 1.05-1| 0.456   |
| 52-021K  | 1.05-2| 0.450   |
| 52-021K  | 1.05-3| 0.393   |
| 52-021K  | 1.05-4| 0.405   |

### 2. inspection_report_52-010B_1.29_1.37.pdf

Circuit 52-010B, CML 1.29 & 1.37. Expected: 6 rows (1.29-1..3, 1.37-1..3). **May require OCR** if results table is image-based.

### 3. inspection_report_57-008U_1.52_1.29_4.09.pdf

Multi-section Format B: Circuit 57-008U, CML 1.52, 1.29, 4.09. 16"/30"/8"/6" zones. 9 rows. Multiple readings per zone → min.

| Circuit  | CML   | Reading |
|----------|-------|---------|
| 57-008U  | 1.52-1| 0.357   |
| 57-008U  | 1.52-2| 0.358   |
| 57-008U  | 1.29-1| 0.342   |
| 57-008U  | 1.29-2| 0.287   |
| 57-008U  | 1.29-3| 0.372   |
| 57-008U  | 1.29-4| 0.382   |
| 57-008U  | 4.09-1| 0.296   |
| 57-008U  | 4.09-2| 0.326   |
| 57-008U  | 4.09-3| 0.318   |

### Parser logic

- Circuit: NN-NNNXX (e.g. 52-021K); "1-2", "2-3" are breakdown drawing numbers
- CML from header or filename
- Format A: 8"/6" → CML; row num → zone
- Format B: 16"/30"/8"/6" → CML; multiple readings per zone → min
