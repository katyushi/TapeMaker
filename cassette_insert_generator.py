import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


# ============================================================
# Font
# ============================================================

# Use a real Unicode TTF whenever possible.  The PDF must not
# fall back to Helvetica for track titles containing characters
# such as "：" or other non-ASCII punctuation.

FONT_PATHS = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\verdana.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
]

FONT_BOLD_PATHS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\tahomabd.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\verdanab.ttf",
    r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
]


def find_font(paths):
    for path in paths:
        if Path(path).exists():
            return path
    return None


regular_font = find_font(FONT_PATHS)
bold_font = find_font(FONT_BOLD_PATHS)

if regular_font:
    try:
        pdfmetrics.registerFont(
            TTFont("TapeMaker-Regular", regular_font)
        )
        REGULAR = "TapeMaker-Regular"
    except Exception:
        REGULAR = "Helvetica"
else:
    REGULAR = "Helvetica"

if bold_font:
    try:
        pdfmetrics.registerFont(
            TTFont("TapeMaker-Bold", bold_font)
        )
        BOLD = "TapeMaker-Bold"
    except Exception:
        BOLD = "Helvetica-Bold"
else:
    BOLD = "Helvetica-Bold"


# ============================================================
# ============================================================

MM = 72.0 / 25.4

A4_W, A4_H = A4

CARD_H_MM = 102.0
BACK_W_MM = 63.0
SPINE_W_MM = 4.0
FRONT_W_MM = 63.0

CARD_W_MM = (
    BACK_W_MM
    + SPINE_W_MM
    + FRONT_W_MM
    + SPINE_W_MM
)

PAGE_MARGIN_MM = 10.0

CARD_H = CARD_H_MM * MM
BACK_W = BACK_W_MM * MM
SPINE_W = SPINE_W_MM * MM
FRONT_W = FRONT_W_MM * MM
CARD_W = CARD_W_MM * MM

PAGE_MARGIN = PAGE_MARGIN_MM * MM


SIDE_RE = re.compile(
    r"^Tape\s+(\d+)\s+-\s+Side\s+([AB])\.txt$",
    re.IGNORECASE,
)


# ============================================================
# Track title cleanup
# ============================================================

AUDIO_EXTENSIONS = (
    ".mp3",
    ".flac",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
)


def remove_audio_extension(title: str) -> str:
    """
    Removes an audio extension, including manifests where the
    filename ended up with repeated dots before the extension:

        Song.opus
        Song..opus
        Song...opus
    """

    title = title.strip()

    extensions = "|".join(
        re.escape(ext[1:])
        for ext in AUDIO_EXTENSIONS
    )

    return re.sub(
        rf"\.+(?:{extensions})$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()


def clean_track_title(title: str) -> str:
    """
    Real Compiler line:

        001. 001 - Red Army Choir： Partisan's Song..opus [2:51]

    Result:

        Red Army Choir： Partisan's Song
    """

    title = remove_audio_extension(title)

    # Remove the internal Compiler track number.
    # This is what prevents:
    #
    #     001. 001 - Title
    #
    # from becoming:
    #
    #     1. 001 - Title
    title = re.sub(
        r"^\s*\d+\s*[-.)]\s*",
        "",
        title,
    )

    return title.strip()


# ============================================================
# Manifest
# ============================================================

TRACK_LINE_RE = re.compile(
    r"^\s*(\d+)\.\s+(\d+)\s*[-.)]\s*(.*?)"
    r"\s*(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\])?\s*$"
)

SIDE_LINE_RE = re.compile(
    r"^Tape\s+(\d+)\s*-\s*Side\s+([AB])$",
    re.IGNORECASE,
)


def normalize_manifest_text(text: str) -> str:
    """
    Explicitly normalize Windows CRLF/CR to LF and preserve
    Unicode as Unicode.
    """

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    return text


def parse_manifest(path: Path) -> dict:
    """
    Parses the actual Compiler manifest format.

    The first non-empty line is the mixtape name.
    Tape/side are taken from their own exact line.
    Tracklist parsing is restricted to the TRACKLIST section.
    """

    text = path.read_text(
        encoding="utf-8-sig",
        errors="strict",
    )

    text = normalize_manifest_text(text)

    raw_lines = text.split("\n")

    # Keep the first non-empty line as the mixtape name.
    first_non_empty = next(
        (
            line.strip()
            for line in raw_lines
            if line.strip()
        ),
        None,
    )

    if not first_non_empty:
        raise ValueError(
            f"Manifest is empty: {path}"
        )

    data = {
        "name": first_non_empty,
        "tape": None,
        "side": None,
        "format": None,
        "runtime": None,
        "capacity": None,
        "fade": None,
        "tracks": [],
    }

    # Tape/side must come from the exact Tape XX - Side X line.
    for raw_line in raw_lines:
        line = raw_line.strip()

        match = SIDE_LINE_RE.match(line)

        if match:
            data["tape"] = int(match.group(1))
            data["side"] = match.group(2).upper()
            break

    if data["tape"] is None:
        raise ValueError(
            f"Could not find 'Tape XX - Side A/B' in: {path}"
        )

    # Metadata uses exact prefixes.
    for raw_line in raw_lines:
        line = raw_line.strip()

        if line.startswith("Format:"):
            data["format"] = line.split(":", 1)[1].strip()

        elif line.startswith("Runtime:"):
            data["runtime"] = line.split(":", 1)[1].strip()

        elif line.startswith("Capacity:"):
            data["capacity"] = line.split(":", 1)[1].strip()

        elif line.startswith("Fade:"):
            data["fade"] = line.split(":", 1)[1].strip()

    # Find TRACKLIST exactly.
    tracklist_index = None

    for index, raw_line in enumerate(raw_lines):
        if raw_line.strip().upper() == "TRACKLIST":
            tracklist_index = index
            break

    if tracklist_index is None:
        raise ValueError(
            f"TRACKLIST not found in: {path}"
        )

    # Parse only actual track lines.
    for raw_line in raw_lines[tracklist_index + 1:]:
        line = raw_line.strip()

        if not line:
            continue

        match = TRACK_LINE_RE.match(line)

        if not match:
            continue

        number = int(match.group(1))
        title = clean_track_title(
            match.group(3)
        )
        duration = match.group(4) or ""

        if not title:
            continue

        data["tracks"].append(
            (
                str(number),
                title,
                duration,
            )
        )

    if not data["tracks"]:
        raise ValueError(
            f"No tracks were parsed from: {path}"
        )

    return data


def scan_mixtape(
    folder: Path,
) -> dict[int, dict[str, dict]]:

    tapes = {}

    for path in sorted(
        folder.iterdir(),
        key=lambda p: p.name.lower(),
    ):

        if not path.is_file():
            continue

        match = SIDE_RE.match(
            path.name
        )

        if not match:
            continue

        tape_number = int(
            match.group(1)
        )

        side = match.group(2).upper()

        manifest = parse_manifest(path)

        if manifest["tape"] != tape_number:
            raise ValueError(
                f"Tape number mismatch in: {path}"
            )

        if manifest["side"] != side:
            raise ValueError(
                f"Side mismatch in: {path}"
            )

        tapes.setdefault(
            tape_number,
            {},
        )[side] = manifest

    return dict(sorted(tapes.items()))


# ============================================================
# ============================================================

def fit_text(
    c,
    text,
    max_width,
    font,
    max_size,
    min_size=5.0,
):

    size = max_size

    while (
        size > min_size
        and stringWidth(
            text,
            font,
            size,
        ) > max_width
    ):
        size -= 0.25

    if stringWidth(
        text,
        font,
        size,
    ) <= max_width:
        return text, size

    suffix = "..."

    available = (
        max_width
        - stringWidth(
            suffix,
            font,
            size,
        )
    )

    result = ""

    for char in text:

        candidate = result + char

        if stringWidth(
            candidate,
            font,
            size,
        ) > available:
            break

        result = candidate

    return result + suffix, size


def centered(
    c,
    text,
    x,
    y,
    width,
    font=REGULAR,
    size=8,
):

    text, size = fit_text(
        c,
        text,
        width,
        font,
        size,
    )

    c.setFont(
        font,
        size,
    )

    c.drawCentredString(
        x + width / 2,
        y,
        text,
    )


def wrap_text(
    c,
    text,
    font,
    size,
    max_width,
):

    if not text:
        return [""]

    lines = []

    current = ""

    for word in text.split():

        candidate = (
            word
            if not current
            else current + " " + word
        )

        if stringWidth(
            candidate,
            font,
            size,
        ) <= max_width:

            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        segment = word

        while (
            stringWidth(
                segment,
                font,
                size,
            ) > max_width
        ):

            cut = len(segment)

            while (
                cut > 1
                and stringWidth(
                    segment[:cut],
                    font,
                    size,
                ) > max_width
            ):
                cut -= 1

            lines.append(
                segment[:cut]
            )

            segment = segment[cut:]

        current = segment

    if current:
        lines.append(current)

    return lines or [""]


# ============================================================
# Marks
# ============================================================

def crop_marks(
    c,
    x,
    y,
    w,
    h,
):

    mark = 3 * MM
    gap = 1.5 * MM

    c.setLineWidth(0.5)

    c.line(
        x - gap - mark,
        y + h,
        x - gap,
        y + h,
    )

    c.line(
        x + w + gap,
        y + h,
        x + w + gap + mark,
        y + h,
    )

    c.line(
        x - gap - mark,
        y,
        x - gap,
        y,
    )

    c.line(
        x + w + gap,
        y,
        x + w + gap + mark,
        y,
    )

    c.line(
        x,
        y - gap - mark,
        x,
        y - gap,
    )

    c.line(
        x,
        y + h + gap,
        x,
        y + h + gap + mark,
    )

    c.line(
        x + w,
        y - gap - mark,
        x + w,
        y - gap,
    )

    c.line(
        x + w,
        y + h + gap,
        x + w,
        y + h + gap + mark,
    )


def fold_line(
    c,
    x,
    y,
    h,
):

    c.saveState()

    c.setDash(
        2,
        2,
    )

    c.setLineWidth(
        0.35
    )

    c.line(
        x,
        y,
        x,
        y + h,
    )

    c.restoreState()


# ============================================================
# Back / tracklist
# ============================================================

def draw_back_tracklists(
    c,
    x,
    y,
    mixtape_name,
    volume_label_text,
    sides,
):

    padding = 4.5 * MM

    centered(
        c,
        mixtape_name,
        x + padding,
        y + CARD_H - 9 * MM,
        BACK_W - 2 * padding,
        BOLD,
        10,
    )

    if volume_label_text:
        centered(
            c,
            volume_label_text,
            x + padding,
            y + CARD_H - 15 * MM,
            BACK_W - 2 * padding,
            REGULAR,
            6.5,
        )

    gap = 3 * MM

    column_width = (
        BACK_W
        - 2 * padding
        - gap
    ) / 2

    left_x = x + padding

    right_x = (
        left_x
        + column_width
        + gap
    )

    top_y = (
        y
        + CARD_H
        - (
            24 * MM
            if volume_label_text
            else 18 * MM
        )
    )

    bottom_y = (
        y
        + 7 * MM
    )

    def draw_side(
        side_name,
        column_x,
    ):

        side = sides.get(
            side_name,
            {},
        )

        tracks = side.get(
            "tracks",
            [],
        )

        c.setFont(
            BOLD,
            6.5,
        )

        c.drawString(
            column_x,
            top_y,
            f"SIDE {side_name}",
        )

        cursor_y = (
            top_y
            - 5 * MM
        )

        size = 5.8
        line_height = 3.25 * MM

        for number, title, duration in tracks:

            # Number is normalized to remove leading zeroes.
            # The internal duplicate number was already removed
            # by clean_track_title().
            prefix = f"{int(number)}. "

            duration_text = (
                f" [{duration}]"
                if duration
                else ""
            )

            available = (
                column_width
                - stringWidth(
                    prefix,
                    REGULAR,
                    size,
                )
                - stringWidth(
                    duration_text,
                    REGULAR,
                    size,
                )
                - 1.5 * MM
            )

            title_lines = wrap_text(
                c,
                title,
                REGULAR,
                size,
                max(10, available),
            )

            for line_index, title_line in enumerate(
                title_lines
            ):

                if cursor_y < bottom_y:
                    return

                if line_index == 0:
                    text = prefix + title_line

                    if duration_text:
                        # Duration is kept on the first line if it fits.
                        first_width = stringWidth(
                            text + duration_text,
                            REGULAR,
                            size,
                        )

                        if first_width <= column_width:
                            text += duration_text

                    c.setFont(
                        REGULAR,
                        size,
                    )

                    c.drawString(
                        column_x,
                        cursor_y,
                        text,
                    )

                else:
                    indent = stringWidth(
                        prefix,
                        REGULAR,
                        size,
                    )

                    c.setFont(
                        REGULAR,
                        size,
                    )

                    c.drawString(
                        column_x + indent,
                        cursor_y,
                        title_line,
                    )

                cursor_y -= line_height

            cursor_y -= 0.8 * MM

    draw_side(
        "A",
        left_x,
    )

    draw_side(
        "B",
        right_x,
    )


# ============================================================
# Spines
# ============================================================

def draw_spine(
    c,
    x,
    y,
    text,
):

    c.saveState()

    c.translate(
        x + SPINE_W / 2,
        y + CARD_H / 2,
    )

    c.rotate(90)

    # The 4 mm spine is extremely narrow, so fit the complete
    # "Mixtape — Volume 2" label into the available length.
    centered(
        c,
        text,
        -CARD_H / 2 + 4 * MM,
        -2,
        CARD_H - 8 * MM,
        BOLD,
        5.5,
    )

    c.restoreState()


# ============================================================
# Front
# ============================================================

def draw_front(
    c,
    x,
    y,
    mixtape_name,
    volume_label_text,
    tape_format,
    template,
):

    # --------------------------------------------------------
    # Minimal
    # --------------------------------------------------------

    if template == "Minimal":

        centered(
            c,
            mixtape_name,
            x + 4 * MM,
            y + CARD_H / 2,
            FRONT_W - 8 * MM,
            BOLD,
            13,
        )

        if volume_label_text:
            centered(
                c,
                volume_label_text,
                x + 4 * MM,
                y + CARD_H / 2 - 8 * MM,
                FRONT_W - 8 * MM,
                REGULAR,
                7,
            )

        return

    # --------------------------------------------------------
    # J-card / Full insert
    # --------------------------------------------------------

    centered(
        c,
        mixtape_name,
        x + 4 * MM,
        y + CARD_H - 12 * MM,
        FRONT_W - 8 * MM,
        BOLD,
        11,
    )

    if volume_label_text:
        centered(
            c,
            volume_label_text,
            x + 4 * MM,
            y + CARD_H - 19 * MM,
            FRONT_W - 8 * MM,
            REGULAR,
            7,
        )

    if template == "J-card":

        cassette_x = x + 10 * MM
        cassette_y = y + 27 * MM

        cassette_w = (
            FRONT_W
            - 20 * MM
        )

        cassette_h = 38 * MM

        c.setLineWidth(
            0.8
        )

        c.roundRect(
            cassette_x,
            cassette_y,
            cassette_w,
            cassette_h,
            3 * MM,
        )

        window_x = (
            cassette_x
            + 10 * MM
        )

        window_y = (
            cassette_y
            + 10 * MM
        )

        window_w = (
            cassette_w
            - 20 * MM
        )

        window_h = 12 * MM

        c.roundRect(
            window_x,
            window_y,
            window_w,
            window_h,
            2 * MM,
        )

        c.circle(
            window_x + 9 * MM,
            window_y + window_h / 2,
            4 * MM,
        )

        c.circle(
            window_x
            + window_w
            - 9 * MM,
            window_y + window_h / 2,
            4 * MM,
        )

    elif template == "Full insert":

        c.setLineWidth(
            0.6
        )

        c.rect(
            x + 5 * MM,
            y + 20 * MM,
            FRONT_W - 10 * MM,
            CARD_H - 46 * MM,
        )

        centered(
            c,
            "A",
            x + 5 * MM,
            y + 30 * MM,
            FRONT_W - 10 * MM,
            BOLD,
            18,
        )

    centered(
        c,
        tape_format or "CASSETTE",
        x + 4 * MM,
        y + 17 * MM,
        FRONT_W - 8 * MM,
        REGULAR,
        6,
    )


# ============================================================
# Complete insert
# ============================================================

def draw_insert(
    c,
    x,
    y,
    mixtape_name,
    volume_label_text,
    sides,
    tape_format,
    template,
):

    spine1_x = (
        x + BACK_W
    )

    front_x = (
        spine1_x + SPINE_W
    )

    spine2_x = (
        front_x + FRONT_W
    )

    c.setLineWidth(
        0.5
    )

    c.rect(
        x,
        y,
        CARD_W,
        CARD_H,
        stroke=1,
        fill=0,
    )

    fold_line(
        c,
        spine1_x,
        y,
        CARD_H,
    )

    fold_line(
        c,
        front_x,
        y,
        CARD_H,
    )

    fold_line(
        c,
        spine2_x,
        y,
        CARD_H,
    )

    crop_marks(
        c,
        x,
        y,
        CARD_W,
        CARD_H,
    )

    draw_back_tracklists(
        c,
        x,
        y,
        mixtape_name,
        volume_label_text,
        sides,
    )

    # Both spines carry the same physical identification.
    # For a multi-tape mixtape:
    #
    #     Sexy times — Volume 2
    #
    # For a single tape:
    #
    #     Sexy times
    spine_text = mixtape_name

    if volume_label_text:
        spine_text = (
            f"{mixtape_name} — "
            f"{volume_label_text}"
        )

    draw_spine(
        c,
        spine1_x,
        y,
        spine_text,
    )

    draw_front(
        c,
        front_x,
        y,
        mixtape_name,
        volume_label_text,
        tape_format,
        template,
    )

    draw_spine(
        c,
        spine2_x,
        y,
        spine_text,
    )


# ============================================================
# PDF
# ============================================================

def generate_pdf(
    folder,
    output_path,
    template,
):

    tapes = scan_mixtape(
        folder
    )

    if not tapes:
        raise ValueError(
            "No 'Tape XX - Side A/B.txt' manifests were found."
        )

    usable_width = (
        A4_W
        - 2 * PAGE_MARGIN
    )

    usable_height = (
        A4_H
        - 2 * PAGE_MARGIN
    )

    if CARD_W > usable_width:
        raise ValueError(
            "Insert is wider than the configured A4 safe area."
        )

    if CARD_H > usable_height:
        raise ValueError(
            "Insert is taller than the configured A4 safe area."
        )

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=A4,
    )

    pdf.setTitle(
        f"{folder.name} - TapeMaker Inserts"
    )

    pdf.setAuthor(
        "TapeMaker"
    )

    x = (
        A4_W - CARD_W
    ) / 2

    y = (
        A4_H - CARD_H
    ) / 2

    total_tapes = len(tapes)

    # Volume numbering is the physical page order, not the raw
    # compiler tape number.  This guarantees Volume 1, Volume 2,
    # etc. when multiple physical tapes exist.
    for volume_index, (
        tape_number,
        sides,
    ) in enumerate(
        tapes.items(),
        start=1,
    ):

        tape_format = (
            sides.get(
                "A",
                {},
            ).get(
                "format"
            )
            or
            sides.get(
                "B",
                {},
            ).get(
                "format"
            )
            or ""
        )

        if total_tapes > 1:
            volume_label_text = (
                f"Volume {volume_index}"
            )
        else:
            volume_label_text = ""

        draw_insert(
            pdf,
            x,
            y,
            folder.name,
            volume_label_text,
            sides,
            tape_format,
            template,
        )

        pdf.showPage()

    pdf.save()

    return len(tapes)


# ============================================================
# ============================================================
# GUI
# ============================================================

TEMPLATES = (
    "J-card",
    "Minimal",
    "Full insert",
)


class App:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "TapeMaker — Insert Generator"
        )

        self.root.geometry(
            "780x560"
        )

        self.root.minsize(
            700,
            500,
        )

        self.folder = None
        self.tapes = {}

        self.build()

    def build(self):

        outer = ttk.Frame(
            self.root,
            padding=16,
        )

        outer.pack(
            fill="both",
            expand=True,
        )

        ttk.Label(
            outer,
            text=(
                "TapeMaker — "
                "Insert / J-card Generator"
            ),
            font=(
                "TkDefaultFont",
                15,
                "bold",
            ),
        ).pack(
            anchor="w"
        )

        ttk.Label(
            outer,
            text=(
                "Select one compiled mixtape folder. "
                "TapeMaker will generate every tape "
                "as a real-size insert on A4."
            ),
            wraplength=720,
        ).pack(
            anchor="w",
            pady=(4, 16),
        )

        ttk.Label(
            outer,
            text="Mixtape folder:",
        ).pack(
            anchor="w"
        )

        folder_row = ttk.Frame(
            outer
        )

        folder_row.pack(
            fill="x",
            pady=(4, 0),
        )

        self.folder_var = tk.StringVar(
            value="No folder selected"
        )

        ttk.Entry(
            folder_row,
            textvariable=self.folder_var,
            state="readonly",
        ).pack(
            side="left",
            fill="x",
            expand=True,
        )

        ttk.Button(
            folder_row,
            text="Select folder…",
            command=self.select_folder,
        ).pack(
            side="left",
            padx=(8, 0),
        )

        template_box = ttk.LabelFrame(
            outer,
            text="Insert template",
            padding=10,
        )

        template_box.pack(
            fill="x",
            pady=(12, 0),
        )

        template_row = ttk.Frame(
            template_box
        )

        template_row.pack(
            fill="x"
        )

        ttk.Label(
            template_row,
            text="Type:",
        ).pack(
            side="left"
        )

        self.template_var = tk.StringVar(
            value="J-card"
        )

        self.template_combo = ttk.Combobox(
            template_row,
            textvariable=self.template_var,
            state="readonly",
            values=TEMPLATES,
            width=20,
        )

        self.template_combo.pack(
            side="left",
            padx=(8, 0),
        )

        ttk.Label(
            template_row,
            text=(
                f"  A4 • 100% / Actual Size • "
                f"{CARD_W_MM:.1f} × "
                f"{CARD_H_MM:.1f} mm"
            ),
        ).pack(
            side="left",
            padx=(12, 0),
        )

        tapes_box = ttk.LabelFrame(
            outer,
            text="Detected tapes",
            padding=10,
        )

        tapes_box.pack(
            fill="both",
            expand=True,
            pady=16,
        )

        self.tree = ttk.Treeview(
            tapes_box,
            columns=(
                "tape",
                "a",
                "b",
            ),
            show="headings",
            height=12,
        )

        self.tree.heading(
            "tape",
            text="Tape",
        )

        self.tree.heading(
            "a",
            text="Side A",
        )

        self.tree.heading(
            "b",
            text="Side B",
        )

        self.tree.column(
            "tape",
            width=90,
            anchor="center",
        )

        self.tree.column(
            "a",
            width=240,
        )

        self.tree.column(
            "b",
            width=240,
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            tapes_box,
            orient="vertical",
            command=self.tree.yview,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.status = tk.StringVar(
            value=(
                "Select a mixtape folder "
                "to begin."
            )
        )

        ttk.Label(
            outer,
            textvariable=self.status,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        self.generate_btn = ttk.Button(
            outer,
            text="Generate A4 PDF",
            command=self.generate,
            state="disabled",
        )

        self.generate_btn.pack(
            anchor="e"
        )

    def select_folder(self):

        selected = filedialog.askdirectory(
            title=(
                "Select compiled mixtape folder"
            )
        )

        if not selected:
            return

        folder = Path(selected)

        try:
            tapes = scan_mixtape(
                folder
            )
        except Exception as exc:
            messagebox.showerror(
                "TapeMaker",
                f"Could not read folder:\n\n{exc}",
            )
            return

        if not tapes:
            messagebox.showwarning(
                "TapeMaker",
                (
                    "No Tape XX - Side A/B "
                    ".txt manifests were found."
                ),
            )
            return

        self.folder = folder
        self.tapes = tapes

        self.folder_var.set(
            str(folder)
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, (tape_number, sides) in enumerate(
            tapes.items(),
            start=1,
        ):

            self.tree.insert(
                "",
                "end",
                values=(
                    (
                        f"Volume {index}"
                        if len(tapes) > 1
                        else "Single tape"
                    ),
                    (
                        "Found"
                        if "A" in sides
                        else "Missing"
                    ),
                    (
                        "Found"
                        if "B" in sides
                        else "Missing"
                    ),
                ),
            )

        self.status.set(
            f"{len(tapes)} tape(s) detected. "
            "Ready to generate."
        )

        self.generate_btn.configure(
            state="normal"
        )

    def generate(self):

        if not self.folder:
            return

        template = (
            self.template_var.get()
        )

        output = filedialog.asksaveasfilename(
            title="Save generated inserts",
            defaultextension=".pdf",
            initialfile=(
                f"{self.folder.name} - "
                "Inserts.pdf"
            ),
            filetypes=[
                (
                    "PDF files",
                    "*.pdf",
                )
            ],
        )

        if not output:
            return

        try:

            count = generate_pdf(
                self.folder,
                Path(output),
                template,
            )

        except Exception as exc:

            messagebox.showerror(
                "TapeMaker",
                (
                    "Could not generate PDF:"
                    f"\n\n{exc}"
                ),
            )

            return

        self.status.set(
            f"Generated {count} A4 page(s) "
            f"using {template}."
        )

        messagebox.showinfo(
            "TapeMaker",
            (
                f"Generated {count} A4 page(s).\n\n"
                f"Template: {template}\n"
                "Scale: 100% / Actual Size\n\n"
                "Do not use 'Fit to Page'."
            ),
        )


# ============================================================
# Parser self-test
# ============================================================

def parser_self_test(path: Path):
    """
    Useful for verifying the exact Compiler manifest without
    opening the GUI:

        python cassette_insert_generator.py --test "Tape 01 - Side A.txt"
    """

    manifest = parse_manifest(path)

    print(f"Mixtape: {manifest['name']}")
    print(f"Tape: {manifest['tape']}")
    print(f"Side: {manifest['side']}")
    print(f"Tracks: {len(manifest['tracks'])}")
    print()

    for number, title, duration in manifest["tracks"]:
        suffix = f" [{duration}]" if duration else ""
        print(f"{int(number)}. {title}{suffix}")


# ============================================================
# Main
# ============================================================

def main():

    root = tk.Tk()

    App(root)

    root.mainloop()


if __name__ == "__main__":
    main()