#!/usr/bin/env python3
from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

MM = 72.0 / 25.4
A4_W, A4_H = A4

# Physical flat J-card dimensions, in millimetres.
# Change these constants if the physical cassette insert standard changes.
CARD_H_MM = 102.0
BACK_W_MM = 63.0
SPINE_W_MM = 4.0
FRONT_W_MM = 63.0

# Total flat insert width: back + spine + front + spine.
CARD_W_MM = BACK_W_MM + SPINE_W_MM + FRONT_W_MM + SPINE_W_MM

PAGE_MARGIN_MM = 10.0

CARD_H = CARD_H_MM * MM
BACK_W = BACK_W_MM * MM
SPINE_W = SPINE_W_MM * MM
FRONT_W = FRONT_W_MM * MM
PAGE_MARGIN = PAGE_MARGIN_MM * MM
CARD_W = BACK_W + SPINE_W + FRONT_W + SPINE_W

SIDE_RE = re.compile(r"^Tape\s+(\d+)\s+-\s+Side\s+([AB])\.txt$", re.I)


def parse_manifest(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    data = {
        "name": None, "tape": None, "side": None, "format": None,
        "runtime": None, "capacity": None, "fade": None, "tracks": []
    }

    lines = [line.strip() for line in text.splitlines()]

    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        if key in ("mixtape", "name", "title"):
            data["name"] = value
        elif key in ("tape", "cassette"):
            data["tape"] = value
        elif key == "side":
            data["side"] = value.upper()
        elif key == "format":
            data["format"] = value
        elif key == "runtime":
            data["runtime"] = value
        elif key == "capacity":
            data["capacity"] = value
        elif key == "fade":
            data["fade"] = value

    in_tracks = False
    for line in lines:
        if line.lower().startswith("tracklist"):
            in_tracks = True
            continue
        if not in_tracks or not line:
            continue

        match = re.match(r"^(\d+)\s*[.\-)]\s*(.+)$", line)
        if match:
            data["tracks"].append((match.group(1), match.group(2).strip()))

    return data


def scan_mixtape(folder: Path) -> dict[int, dict[str, dict]]:
    tapes: dict[int, dict[str, dict]] = {}

    for path in folder.iterdir():
        if not path.is_file():
            continue

        match = SIDE_RE.match(path.name)
        if not match:
            continue

        tape_no = int(match.group(1))
        side = match.group(2).upper()
        tapes.setdefault(tape_no, {})[side] = parse_manifest(path)

    return dict(sorted(tapes.items()))


def fit_text(c, text, max_width, font, max_size, min_size=5.5):
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.25

    if stringWidth(text, font, size) <= max_width:
        return text, size

    suffix = "..."
    available = max_width - stringWidth(suffix, font, size)
    result = ""
    for char in text:
        candidate = result + char
        if stringWidth(candidate, font, size) > available:
            break
        result = candidate
    return result + suffix, size


def centered(c, text, x, y, width, font="Helvetica", size=8):
    text, size = fit_text(c, text, width, font, size)
    c.setFont(font, size)
    c.drawCentredString(x + width / 2, y, text)


def wrap_text(c, text, font, size, max_width):
    words = text.split()
    if not words:
        return [""]
    lines = [words[0]]
    for word in words[1:]:
        candidate = lines[-1] + " " + word
        if stringWidth(candidate, font, size) <= max_width:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


def crop_marks(c, x, y, w, h):
    mark = 3 * MM
    gap = 1.5 * MM
    c.setLineWidth(0.5)

    c.line(x-gap-mark, y+h, x-gap, y+h)
    c.line(x+w+gap, y+h, x+w+gap+mark, y+h)
    c.line(x-gap-mark, y, x-gap, y)
    c.line(x+w+gap, y, x+w+gap+mark, y)

    c.line(x, y-gap-mark, x, y-gap)
    c.line(x, y+h+gap, x, y+h+gap+mark)
    c.line(x+w, y-gap-mark, x+w, y-gap)
    c.line(x+w, y+h+gap, x+w, y+h+gap+mark)


def fold_line(c, x, y, h):
    c.saveState()
    c.setDash(2, 2)
    c.setLineWidth(0.35)
    c.line(x, y, x, y+h)
    c.restoreState()


def draw_insert(c, x, y, mixtape_name, tape_no, sides, tape_format):
    back_x = x
    spine1_x = back_x + BACK_W
    front_x = spine1_x + SPINE_W
    spine2_x = front_x + FRONT_W

    c.setLineWidth(0.5)
    c.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)
    fold_line(c, spine1_x, y, CARD_H)
    fold_line(c, front_x, y, CARD_H)
    fold_line(c, spine2_x, y, CARD_H)
    crop_marks(c, x, y, CARD_W, CARD_H)

    padding = 5 * MM
    available = BACK_W - 2 * padding

    centered(c, mixtape_name, back_x + padding, y + CARD_H - 10*MM,
             available, "Helvetica-Bold", 11)
    centered(c, f"TAPE {tape_no:02d}", back_x + padding,
             y + CARD_H - 17*MM, available, "Helvetica", 7)

    def draw_side(side_key, title_y, start_y):
        side = sides.get(side_key, {})
        tracks = side.get("tracks", [])

        c.setFont("Helvetica-Bold", 7)
        c.drawString(back_x + padding, y + title_y, f"SIDE {side_key}")

        cursor = y + start_y
        for number, title in tracks:
            prefix = f"{number}. " if number else ""
            for line in wrap_text(c, prefix + title, "Helvetica", 6.7, available):
                if cursor < y + 8*MM:
                    return
                c.setFont("Helvetica", 6.7)
                c.drawString(back_x + padding, cursor, line)
                cursor -= 4*MM
            cursor -= 0.5*MM

    draw_side("A", CARD_H_MM - 28, CARD_H_MM - 34)
    draw_side("B", 44, 38)

    c.saveState()
    c.translate(spine1_x + SPINE_W/2, y + CARD_H/2)
    c.rotate(90)
    centered(c, mixtape_name, -CARD_H/2 + 5*MM, -2,
             CARD_H - 10*MM, "Helvetica-Bold", 6.5)
    c.restoreState()

    centered(c, mixtape_name, front_x + 4*MM,
             y + CARD_H - 12*MM, FRONT_W - 8*MM,
             "Helvetica-Bold", 12)
    centered(c, f"TAPE {tape_no:02d}", front_x + 4*MM,
             y + CARD_H - 20*MM, FRONT_W - 8*MM,
             "Helvetica", 7.5)

    # Simple cassette graphic on the front.
    cassette_x = front_x + 10*MM
    cassette_y = y + 28*MM
    cassette_w = FRONT_W - 20*MM
    cassette_h = 38*MM

    c.setLineWidth(0.8)
    c.roundRect(cassette_x, cassette_y, cassette_w, cassette_h, 3*MM)
    window_x = cassette_x + 10*MM
    window_y = cassette_y + 10*MM
    window_w = cassette_w - 20*MM
    window_h = 12*MM
    c.roundRect(window_x, window_y, window_w, window_h, 2*MM)
    c.circle(window_x + 9*MM, window_y + window_h/2, 4*MM)
    c.circle(window_x + window_w - 9*MM, window_y + window_h/2, 4*MM)

    centered(c, tape_format or "CASSETTE", front_x + 4*MM,
             y + 17*MM, FRONT_W - 8*MM, "Helvetica", 6)

    c.saveState()
    c.translate(spine2_x + SPINE_W/2, y + CARD_H/2)
    c.rotate(90)
    centered(c, f"TAPE {tape_no:02d}", -CARD_H/2 + 5*MM, -2,
             CARD_H - 10*MM, "Helvetica-Bold", 6.5)
    c.restoreState()


def generate_pdf(folder: Path, output_path: Path):
    tapes = scan_mixtape(folder)
    if not tapes:
        raise ValueError("No 'Tape XX - Side A/B.txt' manifests were found.")

    usable_w = A4_W - 2*PAGE_MARGIN
    usable_h = A4_H - 2*PAGE_MARGIN
    if CARD_W > usable_w or CARD_H > usable_h:
        raise ValueError("The configured insert does not fit inside the A4 safe area.")

    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    pdf.setTitle(f"{folder.name} - TapeMaker Inserts")
    pdf.setAuthor("TapeMaker")

    x = (A4_W - CARD_W) / 2
    y = (A4_H - CARD_H) / 2

    for tape_no, sides in tapes.items():
        tape_format = (
            sides.get("A", {}).get("format")
            or sides.get("B", {}).get("format")
            or ""
        )
        draw_insert(pdf, x, y, folder.name, tape_no, sides, tape_format)
        pdf.showPage()

    pdf.save()
    return len(tapes)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("TapeMaker — Insert Generator")
        self.root.geometry("760x520")
        self.folder = None
        self.tapes = {}
        self.build()

    def build(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="TapeMaker — Insert / J-card Generator",
            font=("TkDefaultFont", 15, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text="Select one compiled mixtape folder. Every detected tape gets a "
                 "print-ready A4 page at 100% physical scale.",
            wraplength=700,
        ).pack(anchor="w", pady=(4, 16))

        ttk.Label(outer, text="Mixtape folder:").pack(anchor="w")

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=(4, 0))

        self.folder_var = tk.StringVar(value="No folder selected")
        ttk.Entry(row, textvariable=self.folder_var,
                  state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Select folder…",
                   command=self.select_folder).pack(side="left", padx=(8, 0))

        box = ttk.LabelFrame(outer, text="Detected tapes", padding=10)
        box.pack(fill="both", expand=True, pady=16)

        self.tree = ttk.Treeview(box, columns=("tape", "a", "b"),
                                 show="headings", height=12)
        self.tree.heading("tape", text="Tape")
        self.tree.heading("a", text="Side A")
        self.tree.heading("b", text="Side B")
        self.tree.column("tape", width=80, anchor="center")
        self.tree.column("a", width=240)
        self.tree.column("b", width=240)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(box, orient="vertical",
                               command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        options = ttk.LabelFrame(outer, text="Print", padding=10)
        options.pack(fill="x")
        ttk.Label(
            options,
            text=f"Paper: A4  •  Scale: 100% / Actual Size  •  "
                 f"Insert: {CARD_W_MM:.1f} × {CARD_H_MM:.1f} mm",
        ).pack(anchor="w")

        self.status = tk.StringVar(value="Select a mixtape folder to begin.")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(10, 6))

        self.generate_btn = ttk.Button(
            outer, text="Generate A4 PDF",
            command=self.generate, state="disabled"
        )
        self.generate_btn.pack(anchor="e")

    def select_folder(self):
        selected = filedialog.askdirectory(title="Select compiled mixtape folder")
        if not selected:
            return

        folder = Path(selected)
        tapes = scan_mixtape(folder)

        if not tapes:
            messagebox.showwarning(
                "TapeMaker",
                "No Tape XX - Side A/B .txt manifests were found."
            )
            return

        self.folder = folder
        self.tapes = tapes
        self.folder_var.set(str(folder))

        for item in self.tree.get_children():
            self.tree.delete(item)

        for tape_no, sides in tapes.items():
            self.tree.insert(
                "", "end",
                values=(
                    f"Tape {tape_no:02d}",
                    "Found" if "A" in sides else "Missing",
                    "Found" if "B" in sides else "Missing",
                ),
            )

        self.status.set(f"{len(tapes)} tape(s) detected. Ready to generate.")
        self.generate_btn.configure(state="normal")

    def generate(self):
        if not self.folder:
            return

        output = filedialog.asksaveasfilename(
            title="Save generated inserts",
            defaultextension=".pdf",
            initialfile=f"{self.folder.name} - Inserts.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not output:
            return

        try:
            count = generate_pdf(self.folder, Path(output))
        except Exception as exc:
            messagebox.showerror("TapeMaker", f"Could not generate PDF:\n\n{exc}")
            return

        self.status.set(f"Generated {count} A4 page(s).")
        messagebox.showinfo(
            "TapeMaker",
            f"Generated {count} A4 page(s).\n\n"
            "Print using 100% / Actual Size.\n"
            "Do not use Fit to Page."
        )


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()