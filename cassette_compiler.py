#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
from pathlib import Path


AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".m4a", ".aac",
    ".ogg", ".opus", ".wma", ".aiff", ".aif"
}


def format_time(seconds):
    seconds = int(round(seconds))
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


def get_duration(path):
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def find_best_break(tracks, start, capacity):
    """
    Procura a maior quantidade possível de músicas que caiba
    no lado da fita sem cortar nenhuma faixa.
    """

    total = 0
    end = start

    while end < len(tracks):
        duration = tracks[end][1]

        if total + duration > capacity:
            break

        total += duration
        end += 1

    return end, total


def render_side(tracks, start, end, total_duration, output_file, fade_seconds):
    """
    Concatena as músicas e aplica fade-out na última faixa.
    """

    inputs = []

    for index in range(start, end):
        inputs.extend([
            "-i",
            str(tracks[index][0])
        ])

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

    # Fade somente no final do lado.
    if fade_seconds > 0 and total_duration > 0:
        fade = min(fade_seconds, total_duration)
        fade_start = max(0, total_duration - fade)

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

    filter_complex = ";".join(filters)

    command = [
        "ffmpeg",
        "-y",
        *inputs,

        "-filter_complex",
        filter_complex,

        "-map",
        output_label,

        "-ar", "48000",
        "-ac", "2",
        "-c:a", "pcm_s16le",

        str(output_file)
    ]

    subprocess.run(command, check=True)


def main():

    parser = argparse.ArgumentParser(
        description="Compilador de playlists para fitas K7."
    )

    parser.add_argument(
        "folder",
        type=Path,
        help="Pasta contendo as músicas."
    )

    parser.add_argument(
        "--tape",
        choices=["C60", "C90"],
        default="C60",
        help="Tipo de fita."
    )

    parser.add_argument(
        "--fade",
        type=float,
        default=5.0,
        help="Duração do fade-out em segundos."
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=Path("cassette_output"),
        help="Pasta de saída."
    )

    args = parser.parse_args()

    # ------------------------------------------------------------
    # Verificação do FFmpeg
    # ------------------------------------------------------------

    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ERRO: ffmpeg não encontrado no PATH."
        )

    if shutil.which("ffprobe") is None:
        raise SystemExit(
            "ERRO: ffprobe não encontrado no PATH."
        )

    # ------------------------------------------------------------
    # Capacidade
    # ------------------------------------------------------------

    capacity = {
        "C60": 30 * 60,
        "C90": 45 * 60
    }[args.tape]

    # ------------------------------------------------------------
    # Encontrar músicas
    # ------------------------------------------------------------

    if not args.folder.exists():
        raise SystemExit(
            f"Pasta não encontrada: {args.folder}"
        )

    files = sorted(
        [
            file
            for file in args.folder.iterdir()
            if (
                file.is_file()
                and file.suffix.lower() in AUDIO_EXTENSIONS
            )
        ],
        key=lambda file: file.name.lower()
    )

    if not files:
        raise SystemExit(
            "Nenhum arquivo de áudio encontrado."
        )

    # ------------------------------------------------------------
    # Analisar runtimes
    # ------------------------------------------------------------

    print()
    print("========================================")
    print("       CASSETTE COMPILER")
    print("========================================")
    print()
    print(f"Fita: {args.tape}")
    print(f"Capacidade por lado: {format_time(capacity)}")
    print(f"Fade: {args.fade:.1f}s")
    print()

    tracks = []

    print("Analisando músicas...")
    print()

    for number, file in enumerate(files, start=1):

        try:
            duration = get_duration(file)

        except Exception as error:
            print(
                f"ERRO ao ler {file.name}: {error}"
            )
            continue

        tracks.append((file, duration))

        print(
            f"{number:03d}. "
            f"{format_time(duration):>8}  "
            f"{file.name}"
        )

    if not tracks:
        raise SystemExit(
            "Nenhuma música pôde ser analisada."
        )

    # ------------------------------------------------------------
    # Criar pasta
    # ------------------------------------------------------------

    args.out.mkdir(
        parents=True,
        exist_ok=True
    )

    # ------------------------------------------------------------
    # Dividir em lados
    # ------------------------------------------------------------

    current_track = 0
    side_number = 0

    while current_track < len(tracks):

        end_track, total_duration = find_best_break(
            tracks,
            current_track,
            capacity
        )

        # Uma música individual maior que a capacidade.
        if end_track == current_track:

            end_track = current_track + 1
            total_duration = tracks[current_track][1]

            print()
            print(
                "AVISO: a música "
                f"'{tracks[current_track][0].name}' "
                "é maior que a capacidade do lado."
            )

        tape_number = side_number // 2 + 1

        if side_number % 2 == 0:
            side_name = "A"
        else:
            side_name = "B"

        print()
        print("----------------------------------------")
        print(
            f"Tape {tape_number:02d} - Side {side_name}"
        )
        print(
            f"Runtime: {format_time(total_duration)} "
            f"/ {format_time(capacity)}"
        )
        print("----------------------------------------")

        for index in range(current_track, end_track):

            print(
                f"  {index + 1:03d}. "
                f"{tracks[index][0].name} "
                f"({format_time(tracks[index][1])})"
            )

        # --------------------------------------------------------
        # Nome dos arquivos
        # --------------------------------------------------------

        base_name = (
            f"Tape {tape_number:02d} - Side {side_name}"
        )

        wav_file = args.out / f"{base_name}.wav"
        txt_file = args.out / f"{base_name}.txt"

        # --------------------------------------------------------
        # Renderizar
        # --------------------------------------------------------

        print()
        print("Renderizando...")

        render_side(
            tracks,
            current_track,
            end_track,
            total_duration,
            wav_file,
            args.fade
        )

        # --------------------------------------------------------
        # Tracklist
        # --------------------------------------------------------

        with open(
            txt_file,
            "w",
            encoding="utf-8"
        ) as playlist:

            playlist.write(
                f"{base_name}\n"
            )

            playlist.write(
                f"Type: {args.tape}\n"
            )

            playlist.write(
                f"Runtime: {format_time(total_duration)}\n"
            )

            playlist.write(
                f"Capacity: {format_time(capacity)}\n"
            )

            playlist.write(
                f"Fade: {args.fade:.1f}s\n"
            )

            playlist.write("\n")
            playlist.write("TRACKLIST\n")
            playlist.write("=" * 50)
            playlist.write("\n")

            for index in range(
                current_track,
                end_track
            ):

                playlist.write(
                    f"{index + 1:03d}. "
                    f"{tracks[index][0].name} "
                    f"[{format_time(tracks[index][1])}]\n"
                )

        print(
            f"Gerado: {wav_file.name}"
        )

        # Próxima música
        current_track = end_track
        side_number += 1

    # ------------------------------------------------------------
    # Resumo
    # ------------------------------------------------------------

    total_sides = side_number
    total_tapes = (total_sides + 1) // 2

    print()
    print("========================================")
    print("CONCLUÍDO")
    print("========================================")
    print()
    print(f"Músicas: {len(tracks)}")
    print(f"Lados:   {total_sides}")
    print(f"Fitas:   {total_tapes}")
    print()
    print(f"Saída: {args.out}")
    print()


if __name__ == "__main__":
    main()
