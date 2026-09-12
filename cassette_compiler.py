#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
from pathlib import Path


AUDIO_EXTENSIONS = {
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
}


# ================================================================
# UTILIDADES
# ================================================================

def format_time(seconds):
    seconds = int(round(seconds))
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


def get_duration(path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    return float(data["format"]["duration"])


# ================================================================
# ENCONTRAR MELHOR PONTO DE QUEBRA
# ================================================================

def find_best_break(tracks, start, capacity):
    """
    Analisa os possíveis pontos de quebra a partir de 'start'
    e escolhe o conjunto consecutivo de músicas que mais se
    aproxima da capacidade do lado sem ultrapassá-la.

    Como as músicas precisam permanecer inteiras, o ponto de
    quebra sempre ocorre entre duas faixas.
    """

    total = 0.0
    best_end = start
    best_total = 0.0

    for index in range(start, len(tracks)):

        duration = tracks[index]["duration"]

        candidate_total = total + duration

        if candidate_total > capacity:
            break

        total = candidate_total

        best_end = index + 1
        best_total = total

    return best_end, best_total


# ================================================================
# RENDERIZAÇÃO
# ================================================================

def render_side(
    tracks,
    start,
    end,
    total_duration,
    output_file,
    fade_seconds,
):
    """
    Concatena todas as faixas do lado em um único WAV.

    O fade é aplicado somente no final do lado.
    """

    inputs = []

    for index in range(start, end):

        inputs.extend(
            [
                "-i",
                str(tracks[index]["path"]),
            ]
        )

    filters = []
    labels = []

    for i in range(end - start):

        filters.append(
            f"[{i}:a]"
            "aformat="
            "sample_fmts=fltp:"
            "sample_rates=48000:"
            "channel_layouts=stereo"
            f"[a{i}]"
        )

        labels.append(f"[a{i}]")

    filters.append(
        "".join(labels)
        + f"concat=n={end - start}:v=0:a=1[combined]"
    )

    if fade_seconds > 0 and total_duration > 0:

        fade = min(
            fade_seconds,
            total_duration,
        )

        fade_start = max(
            0,
            total_duration - fade,
        )

        filters.append(
            f"[combined]"
            f"afade=t=out:"
            f"st={fade_start:.3f}:"
            f"d={fade:.3f}"
            "[output]"
        )

        output_label = "[output]"

    else:

        output_label = "[combined]"

    command = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        output_label,
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(output_file),
    ]

    subprocess.run(
        command,
        check=True,
    )


# ================================================================
# PROCESSAR UMA MIXTAPE
# ================================================================

def process_mixtape(
    mixtape_folder,
    output_root,
    tape_type,
    fade_seconds,
):
    """
    Processa uma subpasta da pasta mãe como uma mixtape.
    """

    mixtape_name = mixtape_folder.name

    capacity = {
        "C60": 30 * 60,
        "C90": 45 * 60,
    }[tape_type]

    # ------------------------------------------------------------
    # Encontrar arquivos
    # ------------------------------------------------------------

    files = sorted(
        [
            file
            for file in mixtape_folder.iterdir()
            if (
                file.is_file()
                and file.suffix.lower()
                in AUDIO_EXTENSIONS
            )
        ],
        key=lambda file: file.name.lower(),
    )

    if not files:
        print(
            f"[SKIP] {mixtape_name}: "
            "nenhum arquivo de áudio."
        )
        return

    # ------------------------------------------------------------
    # Analisar runtimes
    # ------------------------------------------------------------

    print()
    print("=" * 60)
    print(f"MIXTAPE: {mixtape_name}")
    print("=" * 60)

    tracks = []

    for number, file in enumerate(
        files,
        start=1,
    ):

        try:

            duration = get_duration(file)

        except Exception as error:

            print(
                f"[ERRO] {file.name}: {error}"
            )

            continue

        tracks.append(
            {
                "path": file,
                "duration": duration,
                "number": number,
            }
        )

        print(
            f"{number:03d}. "
            f"{format_time(duration):>8}  "
            f"{file.name}"
        )

    if not tracks:
        print(
            "[SKIP] Nenhuma faixa pôde ser analisada."
        )
        return

    # ------------------------------------------------------------
    # Pasta da mixtape
    #
    # output/
    # └── C60/
    #     └── Nome da Mixtape/
    # ------------------------------------------------------------

    mixtape_output = (
        output_root
        / tape_type
        / mixtape_name
    )

    mixtape_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------
    # Divisão em lados
    # ------------------------------------------------------------

    current_track = 0
    side_number = 0

    while current_track < len(tracks):

        end_track, total_duration = (
            find_best_break(
                tracks,
                current_track,
                capacity,
            )
        )

        # --------------------------------------------------------
        # Uma faixa individual maior que a capacidade
        # --------------------------------------------------------

        if end_track == current_track:

            track = tracks[current_track]

            print()
            print(
                "[AVISO] "
                f"'{track['path'].name}' "
                f"tem {format_time(track['duration'])} "
                f"e excede a capacidade de "
                f"{format_time(capacity)}."
            )

            # Não há como dividir a música sem cortá-la.
            # Mantemos a faixa inteira.
            end_track = current_track + 1
            total_duration = track["duration"]

        # --------------------------------------------------------
        # Número da tape / lado
        # --------------------------------------------------------

        tape_number = (
            side_number // 2
        ) + 1

        side_name = (
            "A"
            if side_number % 2 == 0
            else "B"
        )

        print()
        print("-" * 60)
        print(
            f"Tape {tape_number:02d} "
            f"- Side {side_name}"
        )
        print(
            f"Runtime: "
            f"{format_time(total_duration)} / "
            f"{format_time(capacity)}"
        )
        print("-" * 60)

        for index in range(
            current_track,
            end_track,
        ):

            track = tracks[index]

            print(
                f"  {track['number']:03d}. "
                f"{track['path'].name} "
                f"({format_time(track['duration'])})"
            )

        # --------------------------------------------------------
        # Arquivos
        # --------------------------------------------------------

        base_name = (
            f"Tape {tape_number:02d} "
            f"- Side {side_name}"
        )

        wav_file = (
            mixtape_output
            / f"{base_name}.wav"
        )

        txt_file = (
            mixtape_output
            / f"{base_name}.txt"
        )

        # --------------------------------------------------------
        # Renderizar
        # --------------------------------------------------------

        print("Renderizando...")

        render_side(
            tracks,
            current_track,
            end_track,
            total_duration,
            wav_file,
            fade_seconds,
        )

        # --------------------------------------------------------
        # Tracklist
        # --------------------------------------------------------

        with open(
            txt_file,
            "w",
            encoding="utf-8",
        ) as playlist:

            playlist.write(
                f"{mixtape_name}\n"
            )

            playlist.write(
                f"Tape {tape_number:02d} "
                f"- Side {side_name}\n"
            )

            playlist.write(
                f"Format: {tape_type}\n"
            )

            playlist.write(
                f"Runtime: "
                f"{format_time(total_duration)}\n"
            )

            playlist.write(
                f"Capacity: "
                f"{format_time(capacity)}\n"
            )

            playlist.write(
                f"Fade: "
                f"{fade_seconds:.1f}s\n"
            )

            playlist.write("\n")
            playlist.write("TRACKLIST\n")
            playlist.write("=" * 60)
            playlist.write("\n")

            for index in range(
                current_track,
                end_track,
            ):

                track = tracks[index]

                playlist.write(
                    f"{track['number']:03d}. "
                    f"{track['path'].name} "
                    f"[{format_time(track['duration'])}]\n"
                )

        print(
            f"Gerado: {wav_file}"
        )

        # --------------------------------------------------------
        # Próximo lado
        # --------------------------------------------------------

        current_track = end_track
        side_number += 1

    # ------------------------------------------------------------
    # Resumo
    # ------------------------------------------------------------

    total_sides = side_number
    total_tapes = (
        total_sides + 1
    ) // 2

    print()
    print(
        f"[OK] {mixtape_name}: "
        f"{len(tracks)} músicas → "
        f"{total_tapes} fita(s), "
        f"{total_sides} lado(s)"
    )


# ================================================================
# MAIN
# ================================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Cassette Compiler — "
            "compila pastas de músicas em fitas K7."
        )
    )

    parser.add_argument(
        "folder",
        type=Path,
        help=(
            "Pasta mãe contendo as subpastas "
            "das mixtapes."
        ),
    )

    parser.add_argument(
        "--tape",
        choices=["C60", "C90"],
        default="C60",
        help="Formato da fita.",
    )

    parser.add_argument(
        "--fade",
        type=float,
        default=5.0,
        help=(
            "Duração do fade-out no final "
            "de cada lado, em segundos."
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("cassette_output"),
        help="Pasta raiz da saída.",
    )

    args = parser.parse_args()

    # ============================================================
    # Dependências
    # ============================================================

    if shutil.which("ffmpeg") is None:

        raise SystemExit(
            "ERRO: ffmpeg não encontrado no PATH."
        )

    if shutil.which("ffprobe") is None:

        raise SystemExit(
            "ERRO: ffprobe não encontrado no PATH."
        )

    # ============================================================
    # Pasta mãe
    # ============================================================

    if not args.folder.exists():

        raise SystemExit(
            f"Pasta não encontrada: {args.folder}"
        )

    if not args.folder.is_dir():

        raise SystemExit(
            f"O caminho não é uma pasta: {args.folder}"
        )

    # ============================================================
    # Encontrar mixtapes
    #
    # Cada subpasta = uma mixtape
    # ============================================================

    mixtapes = sorted(
        [
            folder
            for folder in args.folder.iterdir()
            if folder.is_dir()
        ],
        key=lambda folder: folder.name.lower(),
    )

    if not mixtapes:

        raise SystemExit(
            "Nenhuma subpasta encontrada na "
            "pasta mãe."
        )

    # ============================================================
    # Cabeçalho
    # ============================================================

    print()
    print("=" * 60)
    print("CASSETTE COMPILER v2")
    print("=" * 60)
    print()

    print(
        f"Pasta mãe: {args.folder}"
    )

    print(
        f"Formato: {args.tape}"
    )

    print(
        f"Capacidade por lado: "
        f"{format_time({'C60': 1800, 'C90': 2700}[args.tape])}"
    )

    print(
        f"Fade: {args.fade:.1f}s"
    )

    print(
        f"Mixtapes encontradas: "
        f"{len(mixtapes)}"
    )

    # ============================================================
    # Processar cada mixtape
    # ============================================================

    for mixtape in mixtapes:

        process_mixtape(
            mixtape,
            args.out,
            args.tape,
            args.fade,
        )

    # ============================================================
    # Final
    # ============================================================

    print()
    print("=" * 60)
    print("TODAS AS MIXTAPES FORAM PROCESSADAS")
    print("=" * 60)
    print()
    print(
        f"Saída: {args.out / args.tape}"
    )
    print()


if __name__ == "__main__":
    main()
