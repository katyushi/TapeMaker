import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk, colorchooser

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


# ============================================================
# Font
# ============================================================

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
            TTFont(
                "TapeMaker-Regular",
                regular_font,
            )
        )
        REGULAR = "TapeMaker-Regular"
    except Exception:
        REGULAR = "Helvetica"
else:
    REGULAR = "Helvetica"


if bold_font:
    try:
        pdfmetrics.registerFont(
            TTFont(
                "TapeMaker-Bold",
                bold_font,
            )
        )
        BOLD = "TapeMaker-Bold"
    except Exception:
        BOLD = "Helvetica-Bold"
else:
    BOLD = "Helvetica-Bold"


# ============================================================
# Physical dimensions
# ============================================================

MM = 72.0 / 25.4

A4_W, A4_H = A4

# Standard Norelco J-card
#
# Height:
#     101.6 mm / 4"
#
# Width:
#     25.4 mm  J-flap
#     12.7 mm  spine
#     65.09 mm front
#
# Total:
#     103.19 × 101.6 mm
#
# This is the physical trim size.
# Bleed/crop marks are drawn outside this area.

CARD_H_MM = 101.6

J_FLAP_W_MM = 25.4
SPINE_W_MM = 12.7
FRONT_W_MM = 65.09

CARD_W_MM = (
    J_FLAP_W_MM
    + SPINE_W_MM
    + FRONT_W_MM
)

PAGE_MARGIN_MM = 10.0

CARD_H = CARD_H_MM * MM
J_FLAP_W = J_FLAP_W_MM * MM
SPINE_W = SPINE_W_MM * MM
FRONT_W = FRONT_W_MM * MM
CARD_W = CARD_W_MM * MM

PAGE_MARGIN = PAGE_MARGIN_MM * MM


# ============================================================
# File matching
# ============================================================

SIDE_RE = re.compile(
    r"^Tape\s+(\d+)\s+-\s+Side\s+([AB])\.txt$",
    re.IGNORECASE,
)


# ============================================================
# Audio extensions
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
    Remove audio extensions, including malformed cases
    such as:

        song.opus
        song..opus
        song...opus
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
    Remove duplicate internal track numbering.

    Example:

        001. 001 - Artist - Song..opus

    becomes:

        Artist - Song
    """

    title = remove_audio_extension(
        title
    )

    title = re.sub(
        r"^\s*\d+\s*[-.)]\s*",
        "",
        title,
    )

    return title.strip()


# ============================================================
# Manifest parser
# ============================================================

TRACK_LINE_RE = re.compile(
    r"^\s*(\d+)\.\s+"
    r"(\d+)\s*[-.)]\s*"
    r"(.*?)"
    r"\s*(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\])?"
    r"\s*$"
)


def parse_manifest(path: Path) -> dict:

    text = path.read_text(
        encoding="utf-8-sig",
        errors="strict",
    )

    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    raw_lines = text.split(
        "\n"
    )

    lines = [
        line.strip()
        for line in raw_lines
    ]

    data = {
        "name": None,
        "tape": None,
        "side": None,
        "format": None,
        "runtime": None,
        "capacity": None,
        "fade": None,
        "tracks": [],
    }

    # --------------------------------------------------------
    # Mixtape name
    # --------------------------------------------------------

    first_non_empty = next(
        (
            line
            for line in lines
            if line
        ),
        None,
    )

    data["name"] = (
        first_non_empty
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    for line in lines:

        if line.startswith(
            "Tape "
        ) and " - Side " in line:

            match = re.match(
                r"^Tape\s+(\d+)\s+-\s+Side\s+([AB])$",
                line,
                re.IGNORECASE,
            )

            if match:
                data["tape"] = int(
                    match.group(1)
                )

                data["side"] = (
                    match.group(2).upper()
                )

            continue

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        key = key.strip().lower()
        value = value.strip()

        if key in (
            "mixtape",
            "name",
            "title",
        ):
            data["name"] = value

        elif key in (
            "tape",
            "cassette",
        ):
            tape_match = re.search(
                r"(\d+)",
                value,
            )

            if tape_match:
                data["tape"] = int(
                    tape_match.group(1)
                )

        elif key == "side":
            data["side"] = (
                value.upper()
            )

        elif key == "format":
            data["format"] = value

        elif key == "runtime":
            data["runtime"] = value

        elif key == "capacity":
            data["capacity"] = value

        elif key == "fade":
            data["fade"] = value

    # --------------------------------------------------------
    # Tracklist
    # --------------------------------------------------------

    in_tracks = False

    for line in lines:

        if line.upper().startswith(
            "TRACKLIST"
        ):
            in_tracks = True
            continue

        if not in_tracks:
            continue

        if not line:
            continue

        match = TRACK_LINE_RE.match(
            line
        )

        if not match:
            continue

        number = int(
            match.group(1)
        )

        title = match.group(3).strip()

        duration = (
            match.group(4)
            or ""
        )

        title = clean_track_title(
            title
        )

        data["tracks"].append(
            (
                str(number),
                title,
                duration,
            )
        )

    return data


# ============================================================
# Mixtape scanner
# ============================================================

def scan_mixtape(
    folder: Path,
) -> dict:

    tapes = {}

    for path in folder.iterdir():

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

        manifest = parse_manifest(
            path
        )

        tapes.setdefault(
            tape_number,
            {},
        )[side] = manifest

    return dict(
        sorted(
            tapes.items()
        )
    )


# ============================================================
# Text helpers
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

        candidate = (
            result
            + char
        )

        if stringWidth(
            candidate,
            font,
            size,
        ) > available:
            break

        result = candidate

    return (
        result + suffix,
        size,
    )


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
            lines.append(
                current
            )

        current = ""

        segment = word

        while (
            stringWidth(
                segment,
                font,
                size,
            ) > max_width
        ):

            cut = len(
                segment
            )

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

            segment = segment[
                cut:
            ]

        current = segment

    if current:
        lines.append(
            current
        )

    return lines or [""]


# ============================================================
# Artwork helpers
# ============================================================

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
}


def draw_cover_image(
    c,
    image_path,
    x,
    y,
    width,
    height,
):
    """
    Draw an image using cover/crop behavior.

    The image completely fills the requested area.
    """

    if not image_path:
        return

    path = Path(
        image_path
    )

    if not path.is_file():
        return

    try:
        image = ImageReader(
            str(path)
        )

        image_width, image_height = (
            image.getSize()
        )

        if (
            image_width <= 0
            or image_height <= 0
        ):
            return

        scale = max(
            width / image_width,
            height / image_height,
        )

        draw_width = (
            image_width
            * scale
        )

        draw_height = (
            image_height
            * scale
        )

        draw_x = (
            x
            + (
                width
                - draw_width
            )
            / 2
        )

        draw_y = (
            y
            + (
                height
                - draw_height
            )
            / 2
        )

        c.saveState()

        clip = c.beginPath()

        clip.rect(
            x,
            y,
            width,
            height,
        )

        c.clipPath(
            clip,
            stroke=0,
            fill=0,
        )

        c.drawImage(
            image,
            draw_x,
            draw_y,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=False,
            mask="auto",
        )

        c.restoreState()

    except Exception:
        pass


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

    c.setLineWidth(
        0.5
    )

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
# J-flap / Tracklist
# ============================================================

def draw_back_tracklists(
    c,
    x,
    y,
    mixtape_name,
    volume_label,
    sides,
    font_color,
):

    # --------------------------------------------------------
    # The standard Norelco J-flap is only 25.4 mm wide.
    #
    # Keep this panel intentionally compact.
    # --------------------------------------------------------

    padding = 2.0 * MM

    usable_width = (
        J_FLAP_W
        - 2 * padding
    )

    c.setFillColor(
        font_color
    )

    # --------------------------------------------------------
    # Mixtape name
    # --------------------------------------------------------

    centered(
        c,
        mixtape_name,
        x + padding,
        y + CARD_H - 6 * MM,
        usable_width,
        BOLD,
        4.2,
    )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    if volume_label:

        centered(
            c,
            volume_label,
            x + padding,
            y + CARD_H - 10 * MM,
            usable_width,
            REGULAR,
            3.5,
        )

    # --------------------------------------------------------
    # Tracklist
    # --------------------------------------------------------

    cursor_y = (
        y
        + CARD_H
        - 16 * MM
    )

    bottom_y = (
        y
        + 3 * MM
    )

    track_font_size = 3.4

    line_height = (
        2.05 * MM
    )

    for side_name in (
        "A",
        "B",
    ):

        side = sides.get(
            side_name,
            {},
        )

        tracks = side.get(
            "tracks",
            [],
        )

        if not tracks:
            continue

        if cursor_y < bottom_y:
            break

        c.setFillColor(
            font_color
        )

        c.setFont(
            BOLD,
            4.0,
        )

        c.drawString(
            x + padding,
            cursor_y,
            f"SIDE {side_name}",
        )

        cursor_y -= (
            3.0 * MM
        )

        for (
            number,
            title,
            duration,
        ) in tracks:

            title = clean_track_title(
                title
            )

            text = (
                f"{number}. {title}"
            )

            if duration:

                text += (
                    f" [{duration}]"
                )

            lines = wrap_text(
                c,
                text,
                REGULAR,
                track_font_size,
                usable_width,
            )

            for line in lines:

                if cursor_y < bottom_y:
                    return

                c.setFillColor(
                    font_color
                )

                c.setFont(
                    REGULAR,
                    track_font_size,
                )

                c.drawString(
                    x + padding,
                    cursor_y,
                    line,
                )

                cursor_y -= (
                    line_height
                )

            cursor_y -= (
                0.25 * MM
            )

        cursor_y -= (
            1.2 * MM
        )


# ============================================================
# Spines
# ============================================================

def draw_spine(
    c,
    x,
    y,
    text,
    font_color,
):

    c.saveState()

    c.setFillColor(
        font_color
    )

    c.translate(
        x + SPINE_W / 2,
        y + CARD_H / 2,
    )

    c.rotate(90)

    centered(
        c,
        text,
        -CARD_H / 2 + 4 * MM,
        -2,
        CARD_H - 8 * MM,
        BOLD,
        6,
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
    volume_label,
    tape_format,
    template,
    foreground_path,
    background_path,
    font_color,
):

    c.setFillColor(
        font_color
    )

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

        if volume_label:

            centered(
                c,
                volume_label,
                x + 4 * MM,
                y + CARD_H / 2 - 8 * MM,
                FRONT_W - 8 * MM,
                REGULAR,
                7,
            )

        return

    # --------------------------------------------------------
    # Common title
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

    if volume_label:

        centered(
            c,
            volume_label,
            x + 4 * MM,
            y + CARD_H - 19 * MM,
            FRONT_W - 8 * MM,
            REGULAR,
            7,
        )

    # --------------------------------------------------------
    # J-card
    # --------------------------------------------------------

    if template == "J-card":

        cassette_x = (
            x + 8 * MM
        )

        cassette_y = (
            y + 27 * MM
        )

        cassette_w = (
            FRONT_W
            - 16 * MM
        )

        cassette_h = (
            38 * MM
        )

        c.setLineWidth(
            0.8
        )

        c.setStrokeColor(
            font_color
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
            + 9 * MM
        )

        window_y = (
            cassette_y
            + 10 * MM
        )

        window_w = (
            cassette_w
            - 18 * MM
        )

        window_h = (
            12 * MM
        )

        c.roundRect(
            window_x,
            window_y,
            window_w,
            window_h,
            2 * MM,
        )

        c.circle(
            window_x + 8 * MM,
            window_y + window_h / 2,
            4 * MM,
        )

        c.circle(
            window_x
            + window_w
            - 8 * MM,
            window_y + window_h / 2,
            4 * MM,
        )

    # --------------------------------------------------------
    # Full insert
    # --------------------------------------------------------

    elif template == "Full insert":

        artwork_x = (
            x + 5 * MM
        )

        artwork_y = (
            y + 20 * MM
        )

        artwork_w = (
            FRONT_W
            - 10 * MM
        )

        artwork_h = (
            CARD_H
            - 46 * MM
        )

        c.setLineWidth(
            0.6
        )

        c.setStrokeColor(
            font_color
        )

        # Sem background:
        # mantém o quadrado "A" original.
        #
        # Com background e sem foreground:
        # remove completamente o quadrado "A".
        #
        # Com foreground:
        # mantém a área delimitada para o foreground.
        if (
            not background_path
            or foreground_path
        ):

            c.rect(
                artwork_x,
                artwork_y,
                artwork_w,
                artwork_h,
            )

        if foreground_path:

            draw_cover_image(
                c,
                foreground_path,
                artwork_x,
                artwork_y,
                artwork_w,
                artwork_h,
            )

        elif not background_path:

            centered(
                c,
                "A",
                artwork_x,
                y + 30 * MM,
                artwork_w,
                BOLD,
                18,
            )

    # --------------------------------------------------------
    # Format
    # --------------------------------------------------------

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
    volume_label,
    sides,
    tape_format,
    template,
    foreground_path,
    background_path,
    font_color,
):

    # ========================================================
    # Standard Norelco J-card geometry
    #
    # J-flap | Spine | Front
    #
    # 25.4   | 12.7  | 65.09 mm
    # ========================================================

    spine_x = (
        x + J_FLAP_W
    )

    front_x = (
        spine_x
        + SPINE_W
    )

    # ========================================================
    # BACKGROUND
    #
    # This MUST be the first visual element.
    # ========================================================

    if background_path:

        draw_cover_image(
            c,
            background_path,
            x,
            y,
            CARD_W,
            CARD_H,
        )

    # ========================================================
    # Layout lines
    # ========================================================

    c.setStrokeColor(
        font_color
    )

    c.setFillColor(
        font_color
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

    # ========================================================
    # J-flap / Spine fold
    # ========================================================

    fold_line(
        c,
        spine_x,
        y,
        CARD_H,
    )

    # ========================================================
    # Spine / Front fold
    # ========================================================

    fold_line(
        c,
        front_x,
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

    # ========================================================
    # J-flap / Tracklist
    # ========================================================

    draw_back_tracklists(
        c,
        x,
        y,
        mixtape_name,
        volume_label,
        sides,
        font_color,
    )

    # ========================================================
    # Spine
    # ========================================================

    draw_spine(
        c,
        spine_x,
        y,
        (
            mixtape_name
            + (
                f" — {volume_label}"
                if volume_label
                else ""
            )
        ),
        font_color,
    )

    # ========================================================
    # Front
    # ========================================================

    draw_front(
        c,
        front_x,
        y,
        mixtape_name,
        volume_label,
        tape_format,
        template,
        foreground_path,
        background_path,
        font_color,
    )


# ============================================================
# PDF
# ============================================================

def generate_pdf(
    folder,
    output_path,
    template,
    foreground_path=None,
    background_path=None,
    font_color=(0, 0, 0),
):

    tapes = scan_mixtape(
        folder
    )

    if not tapes:
        raise ValueError(
            "No 'Tape XX - Side A/B.txt' "
            "manifests were found."
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
            "Insert is wider than the "
            "configured A4 safe area."
        )

    if CARD_H > usable_height:
        raise ValueError(
            "Insert is taller than the "
            "configured A4 safe area."
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
        A4_W
        - CARD_W
    ) / 2

    y = (
        A4_H
        - CARD_H
    ) / 2

    total_tapes = len(
        tapes
    )

    # Physical tapes are ordered by their
    # actual Tape XX number.
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

        # One physical tape:
        #
        #     no "Tape 01"
        #     no "Volume 1"
        #
        # Multiple physical tapes:
        #
        #     Volume 1
        #     Volume 2
        #     Volume 3
        #
        if total_tapes > 1:

            volume_label = (
                f"Volume {volume_index}"
            )

        else:

            volume_label = ""

        draw_insert(
            pdf,
            x,
            y,
            folder.name,
            volume_label,
            sides,
            tape_format,
            template,
            foreground_path,
            background_path,
            font_color,
        )

        pdf.showPage()

    pdf.save()

    return total_tapes


# ============================================================
# GUI
# ============================================================

TEMPLATES = (
    "J-card",
    "Minimal",
    "Full insert",
)


class App:

    def __init__(
        self,
        root,
    ):

        self.root = root

        self.root.title(
            "TapeMaker — Insert Generator v3"
        )

        self.root.geometry(
            "900x700"
        )

        self.root.minsize(
            800,
            600,
        )

        self.folder = None
        self.tapes = {}

        # ----------------------------------------------------
        # Artwork
        # ----------------------------------------------------

        self.foreground_path = None
        self.background_path = None

        # ----------------------------------------------------
        # Font color
        # ----------------------------------------------------

        self.font_color = (
            0,
            0,
            0,
        )

        self.font_color_hex = (
            "#000000"
        )

        self.build()


    # ========================================================
    # GUI
    # ========================================================

    def build(self):

        outer = ttk.Frame(
            self.root,
            padding=16,
        )

        outer.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        ttk.Label(
            outer,
            text=(
                "TapeMaker — "
                "Insert / J-card Generator v3"
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
                "TapeMaker will generate every physical "
                "tape as a real-size insert on A4."
            ),
            wraplength=820,
        ).pack(
            anchor="w",
            pady=(4, 16),
        )

        # ----------------------------------------------------
        # Folder
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Template
        # ----------------------------------------------------

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
                f"A4 • 100% / Actual Size • "
                f"{CARD_W_MM:.1f} × "
                f"{CARD_H_MM:.1f} mm"
            ),
        ).pack(
            side="left",
            padx=(16, 0),
        )

        # ----------------------------------------------------
        # Artwork
        # ----------------------------------------------------

        artwork_box = ttk.LabelFrame(
            outer,
            text="Artwork",
            padding=10,
        )

        artwork_box.pack(
            fill="x",
            pady=(12, 0),
        )

        # Foreground

        foreground_row = ttk.Frame(
            artwork_box
        )

        foreground_row.pack(
            fill="x",
            pady=(0, 6),
        )

        ttk.Button(
            foreground_row,
            text="Select foreground…",
            command=self.select_foreground,
        ).pack(
            side="left"
        )

        self.foreground_var = tk.StringVar(
            value="No foreground selected"
        )

        ttk.Label(
            foreground_row,
            textvariable=self.foreground_var,
            width=55,
        ).pack(
            side="left",
            padx=(10, 0),
        )

        # Background

        background_row = ttk.Frame(
            artwork_box
        )

        background_row.pack(
            fill="x"
        )

        ttk.Button(
            background_row,
            text="Select background…",
            command=self.select_background,
        ).pack(
            side="left"
        )

        self.background_var = tk.StringVar(
            value="No background selected"
        )

        ttk.Label(
            background_row,
            textvariable=self.background_var,
            width=55,
        ).pack(
            side="left",
            padx=(10, 0),
        )

        ttk.Label(
            artwork_box,
            text=(
                "Foreground replaces the A inside the front artwork box. "
                "Background is drawn underneath the entire insert."
            ),
        ).pack(
            anchor="w",
            pady=(7, 0),
        )

        # ----------------------------------------------------
        # Font color
        # ----------------------------------------------------

        color_box = ttk.LabelFrame(
            outer,
            text="Font / line color",
            padding=10,
        )

        color_box.pack(
            fill="x",
            pady=(12, 0),
        )

        color_row = ttk.Frame(
            color_box
        )

        color_row.pack(
            fill="x"
        )

        self.color_preview = tk.Label(
            color_row,
            text="     ",
            bg="#000000",
            relief="solid",
            borderwidth=1,
        )

        self.color_preview.pack(
            side="left"
        )

        ttk.Button(
            color_row,
            text="Choose color…",
            command=self.choose_font_color,
        ).pack(
            side="left",
            padx=(10, 8),
        )

        self.color_hex_var = tk.StringVar(
            value="#000000"
        )

        ttk.Label(
            color_row,
            textvariable=self.color_hex_var,
        ).pack(
            side="left"
        )

        # ----------------------------------------------------
        # Detected tapes
        # ----------------------------------------------------

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
            height=10,
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
            width=260,
        )

        self.tree.column(
            "b",
            width=260,
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

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Generate
        # ----------------------------------------------------

        self.generate_btn = ttk.Button(
            outer,
            text="Generate A4 PDF",
            command=self.generate,
            state="disabled",
        )

        self.generate_btn.pack(
            anchor="e"
        )


    # ========================================================
    # Image picker
    # ========================================================

    def select_image(
        self,
        title,
    ):

        return filedialog.askopenfilename(
            title=title,
            filetypes=[
                (
                    "Image files",
                    "*.png *.jpg *.jpeg *.webp "
                    "*.bmp *.gif *.tif *.tiff",
                ),
                (
                    "All files",
                    "*.*",
                ),
            ],
        )


    def select_foreground(
        self
    ):

        selected = self.select_image(
            "Select foreground artwork"
        )

        if not selected:
            return

        self.foreground_path = Path(
            selected
        )

        self.foreground_var.set(
            self.foreground_path.name
        )

        self.status.set(
            "Foreground selected."
        )


    def select_background(
        self
    ):

        selected = self.select_image(
            "Select background artwork"
        )

        if not selected:
            return

        self.background_path = Path(
            selected
        )

        self.background_var.set(
            self.background_path.name
        )

        self.status.set(
            "Background selected."
        )


    # ========================================================
    # Font color picker
    # ========================================================

    def choose_font_color(
        self
    ):

        result = colorchooser.askcolor(
            color=self.font_color_hex,
            title="Choose insert font color",
        )

        rgb, hex_value = result

        if not rgb or not hex_value:
            return

        self.font_color = (
            rgb[0] / 255.0,
            rgb[1] / 255.0,
            rgb[2] / 255.0,
        )

        self.font_color_hex = (
            hex_value
        )

        self.color_hex_var.set(
            hex_value
        )

        self.color_preview.configure(
            bg=hex_value
        )

        self.status.set(
            f"Font color: {hex_value}"
        )


    # ========================================================
    # Folder
    # ========================================================

    def select_folder(
        self
    ):

        selected = filedialog.askdirectory(
            title=(
                "Select compiled mixtape folder"
            )
        )

        if not selected:
            return

        folder = Path(
            selected
        )

        try:

            tapes = scan_mixtape(
                folder
            )

        except Exception as exc:

            messagebox.showerror(
                "TapeMaker",
                (
                    "Could not read folder:"
                    f"\n\n{exc}"
                ),
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

        for item in (
            self.tree.get_children()
        ):
            self.tree.delete(
                item
            )

        for tape_number, sides in (
            tapes.items()
        ):

            self.tree.insert(
                "",
                "end",
                values=(
                    f"Tape {tape_number:02d}",
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


    # ========================================================
    # Generate
    # ========================================================

    def generate(
        self
    ):

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
                foreground_path=(
                    self.foreground_path
                ),
                background_path=(
                    self.background_path
                ),
                font_color=(
                    self.font_color
                ),
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
                f"Font color: "
                f"{self.font_color_hex}\n"
                "Scale: 100% / Actual Size\n\n"
                "Do not use 'Fit to Page'."
            ),
        )


# ============================================================
# Main
# ============================================================

def main():

    root = tk.Tk()

    App(root)

    root.mainloop()


if __name__ == "__main__":
    main()