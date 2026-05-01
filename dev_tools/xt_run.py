import openpyxl, sys
p = open("dev_tools/xt_path.txt").read().strip()
wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
ws = wb["Pipe Tally"]
out = []
for i, row in enumerate(ws.iter_rows(min_row=1, max_row=50)):
    vals = [str(c.value)[:45] if c.value is not None else "" for c in row]
    if any(v.strip() for v in vals):
        out.append(f"R{i+1:02d}: {vals}")
wb.close()
open("dev_tools/xt_out.txt", "w").write("\n".join(out))
print("done")
