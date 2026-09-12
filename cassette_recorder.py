import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


APP_TITLE = "Cassette Recorder"


class CassetteRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("850x650")
        self.root.minsize(750, 550)

        self.folder = None
        self.tapes = {}
        self.selected_tape = None
        self.selected_side = None

        self.audio_data = None
        self.sample_rate = None
        self.audio_position = 0
        self.audio_stream = None

        self.playing = False
        self.paused = False
        self.stop_requested = False

        self.volume = 1.0

        self.device_map = {}

        self.build_ui()
        self.refresh_devices()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill="both", expand=True)

        # --------------------------------------------------------------
        # Folder
        # --------------------------------------------------------------

        folder_frame = ttk.LabelFrame(
            main,
            text="Mixtape folder",
            padding=10
        )
        folder_frame.pack(fill="x", pady=(0, 10))

        self.folder_var = tk.StringVar()

        folder_entry = ttk.Entry(
            folder_frame,
            textvariable=self.folder_var,
            state="readonly"
        )
        folder_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 10)
        )

        ttk.Button(
            folder_frame,
            text="Browse...",
            command=self.choose_folder
        ).pack(side="right")

        # --------------------------------------------------------------
        # Tape / Side
        # --------------------------------------------------------------

        selection_frame = ttk.LabelFrame(
            main,
            text="Cassette",
            padding=10
        )
        selection_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            selection_frame,
            text="Tape:"
        ).grid(row=0, column=0, sticky="w")

        self.tape_var = tk.StringVar()

        self.tape_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.tape_var,
            state="readonly",
            width=20
        )
        self.tape_combo.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(10, 30)
        )
        self.tape_combo.bind(
            "<<ComboboxSelected>>",
            self.tape_changed
        )

        ttk.Label(
            selection_frame,
            text="Side:"
        ).grid(row=0, column=2, sticky="w")

        self.side_var = tk.StringVar()

        self.side_combo = ttk.Combobox(
            selection_frame,
            textvariable=self.side_var,
            state="readonly",
            values=["A", "B"],
            width=10
        )
        self.side_combo.grid(
            row=0,
            column=3,
            sticky="w",
            padx=(10, 0)
        )
        self.side_combo.bind(
            "<<ComboboxSelected>>",
            self.side_changed
        )

        selection_frame.columnconfigure(1, weight=1)

        # --------------------------------------------------------------
        # Tracklist
        # --------------------------------------------------------------

        tracks_frame = ttk.LabelFrame(
            main,
            text="Side contents",
            padding=10
        )
        tracks_frame.pack(
            fill="both",
            expand=True,
            pady=(0, 10)
        )

        self.track_text = tk.Text(
            tracks_frame,
            height=12,
            wrap="none",
            state="disabled"
        )
        self.track_text.pack(
            side="left",
            fill="both",
            expand=True
        )

        track_scroll = ttk.Scrollbar(
            tracks_frame,
            orient="vertical",
            command=self.track_text.yview
        )
        track_scroll.pack(side="right", fill="y")

        self.track_text.configure(
            yscrollcommand=track_scroll.set
        )

        # --------------------------------------------------------------
        # Output device
        # --------------------------------------------------------------

        output_frame = ttk.LabelFrame(
            main,
            text="Audio output",
            padding=10
        )
        output_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(
            output_frame,
            text="Device:"
        ).pack(side="left")

        self.device_var = tk.StringVar()

        self.device_combo = ttk.Combobox(
            output_frame,
            textvariable=self.device_var,
            state="readonly"
        )
        self.device_combo.pack(
            side="left",
            fill="x",
            expand=True,
            padx=10
        )

        ttk.Button(
            output_frame,
            text="Refresh",
            command=self.refresh_devices
        ).pack(side="right")

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        self.file_var = tk.StringVar(
            value="No side selected"
        )

        ttk.Label(
            main,
            textvariable=self.file_var,
            anchor="w"
        ).pack(fill="x")

        # --------------------------------------------------------------
        # Progress
        # --------------------------------------------------------------

        progress_frame = ttk.Frame(main)
        progress_frame.pack(
            fill="x",
            pady=(10, 0)
        )

        self.current_time_var = tk.StringVar(
            value="00:00"
        )

        self.total_time_var = tk.StringVar(
            value="00:00"
        )

        ttk.Label(
            progress_frame,
            textvariable=self.current_time_var,
            width=8
        ).pack(side="left")

        self.progress = ttk.Scale(
            progress_frame,
            from_=0,
            to=100,
            orient="horizontal"
        )
        self.progress.pack(
            side="left",
            fill="x",
            expand=True,
            padx=10
        )

        ttk.Label(
            progress_frame,
            textvariable=self.total_time_var,
            width=8
        ).pack(side="right")

        # --------------------------------------------------------------
        # Volume
        # --------------------------------------------------------------

        volume_frame = ttk.Frame(main)
        volume_frame.pack(
            fill="x",
            pady=(10, 0)
        )

        ttk.Label(
            volume_frame,
            text="Volume:"
        ).pack(side="left")

        self.volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            value=100,
            orient="horizontal",
            command=self.volume_changed
        )
        self.volume_scale.pack(
            side="left",
            fill="x",
            expand=True,
            padx=10
        )

        # --------------------------------------------------------------
        # Controls
        # --------------------------------------------------------------

        controls = ttk.Frame(main)
        controls.pack(
            fill="x",
            pady=(15, 0)
        )

        self.stop_button = ttk.Button(
            controls,
            text="■ Stop",
            command=self.stop,
            state="disabled"
        )
        self.stop_button.pack(
            side="left",
            padx=(0, 10)
        )

        self.pause_button = ttk.Button(
            controls,
            text="Ⅱ Pause",
            command=self.pause,
            state="disabled"
        )
        self.pause_button.pack(
            side="left",
            padx=(0, 10)
        )

        self.play_button = ttk.Button(
            controls,
            text="▶ Play",
            command=self.play,
            state="disabled"
        )
        self.play_button.pack(side="left")

        self.status_var = tk.StringVar(
            value="Ready"
        )

        ttk.Label(
            controls,
            textvariable=self.status_var
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Folder scanning
    # ------------------------------------------------------------------

    def choose_folder(self):
        folder = filedialog.askdirectory(
            title="Select compiled mixtape folder"
        )

        if not folder:
            return

        self.load_folder(Path(folder))

    def load_folder(self, folder):
        if not folder.is_dir():
            messagebox.showerror(
                "Error",
                "The selected path is not a folder."
            )
            return

        self.folder = folder
        self.folder_var.set(str(folder))

        self.scan_folder()

    def scan_folder(self):
        self.tapes.clear()

        pattern = re.compile(
            r"^Tape\s+(\d+)\s+-\s+Side\s+([AB])\.wav$",
            re.IGNORECASE
        )

        for path in self.folder.glob("*.wav"):
            match = pattern.match(path.name)

            if not match:
                continue

            tape_number = int(match.group(1))
            side = match.group(2).upper()

            if tape_number not in self.tapes:
                self.tapes[tape_number] = {}

            self.tapes[tape_number][side] = path

        tape_numbers = sorted(self.tapes.keys())

        self.tape_combo["values"] = [
            f"Tape {number:02d}"
            for number in tape_numbers
        ]

        self.side_combo["values"] = ["A", "B"]

        self.clear_side()

        if not tape_numbers:
            messagebox.showwarning(
                "No tapes found",
                "No files matching\n"
                "'Tape XX - Side A/B.wav'\n"
                "were found in this folder."
            )
            return

        first_tape = tape_numbers[0]

        self.tape_var.set(
            f"Tape {first_tape:02d}"
        )

        self.selected_tape = first_tape

        available_sides = self.tapes[first_tape].keys()

        if "A" in available_sides:
            self.side_var.set("A")
            self.selected_side = "A"
        elif "B" in available_sides:
            self.side_var.set("B")
            self.selected_side = "B"

        self.update_side()

    # ------------------------------------------------------------------
    # Tape / side selection
    # ------------------------------------------------------------------

    def tape_changed(self, event=None):
        value = self.tape_var.get()

        match = re.search(
            r"(\d+)",
            value
        )

        if not match:
            return

        self.selected_tape = int(
            match.group(1)
        )

        available_sides = self.tapes[
            self.selected_tape
        ].keys()

        if "A" in available_sides:
            self.side_var.set("A")
            self.selected_side = "A"
        elif "B" in available_sides:
            self.side_var.set("B")
            self.selected_side = "B"
        else:
            self.clear_side()
            return

        self.update_side()

    def side_changed(self, event=None):
        side = self.side_var.get()

        if side not in ("A", "B"):
            return

        self.selected_side = side
        self.update_side()

    def update_side(self):
        if self.selected_tape is None:
            return

        if self.selected_side is None:
            return

        tape = self.tapes.get(
            self.selected_tape,
            {}
        )

        wav_path = tape.get(
            self.selected_side
        )

        if wav_path is None:
            self.clear_side()

            self.file_var.set(
                f"Tape {self.selected_tape:02d} "
                f"- Side {self.selected_side}: "
                f"not found"
            )
            return

        self.file_var.set(
            str(wav_path)
        )

        self.load_tracklist(wav_path)
        self.prepare_audio(wav_path)

    def clear_side(self):
        self.audio_data = None
        self.sample_rate = None
        self.audio_position = 0

        self.play_button.configure(
            state="disabled"
        )

        self.pause_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.current_time_var.set("00:00")
        self.total_time_var.set("00:00")

        self.track_text.configure(
            state="normal"
        )
        self.track_text.delete(
            "1.0",
            "end"
        )
        self.track_text.configure(
            state="disabled"
        )

    # ------------------------------------------------------------------
    # Tracklist
    # ------------------------------------------------------------------

    def load_tracklist(self, wav_path):
        txt_path = wav_path.with_suffix(".txt")

        self.track_text.configure(
            state="normal"
        )

        self.track_text.delete(
            "1.0",
            "end"
        )

        if txt_path.exists():
            try:
                text = txt_path.read_text(
                    encoding="utf-8"
                )

                self.track_text.insert(
                    "1.0",
                    text
                )

            except Exception as exc:
                self.track_text.insert(
                    "1.0",
                    f"Could not read tracklist:\n{exc}"
                )
        else:
            self.track_text.insert(
                "1.0",
                "No tracklist TXT found."
            )

        self.track_text.configure(
            state="disabled"
        )

    # ------------------------------------------------------------------
    # Audio loading
    # ------------------------------------------------------------------

    def prepare_audio(self, wav_path):
        self.stop()

        try:
            data, sample_rate = sf.read(
                wav_path,
                dtype="float32",
                always_2d=True
            )

        except Exception as exc:
            messagebox.showerror(
                "Audio error",
                f"Could not open WAV:\n\n{exc}"
            )
            return

        self.audio_data = data
        self.sample_rate = sample_rate
        self.audio_position = 0

        duration = (
            len(data) / sample_rate
            if sample_rate
            else 0
        )

        self.current_time_var.set(
            "00:00"
        )

        self.total_time_var.set(
            self.format_time(duration)
        )

        self.progress.configure(
            from_=0,
            to=max(duration, 1)
        )

        self.progress.set(0)

        self.play_button.configure(
            state="normal"
        )

        self.status_var.set(
            "Ready"
        )

    # ------------------------------------------------------------------
    # Audio devices
    # ------------------------------------------------------------------

    def refresh_devices(self):
        self.device_map.clear()

        try:
            devices = sd.query_devices()

        except Exception as exc:
            messagebox.showerror(
                "Audio device error",
                str(exc)
            )
            return

        output_devices = []

        for index, device in enumerate(devices):
            if device["max_output_channels"] <= 0:
                continue

            name = device["name"]

            display_name = (
                f"{name} "
                f"[{device['hostapi']}]"
            )

            self.device_map[
                display_name
            ] = index

            output_devices.append(
                display_name
            )

        self.device_combo["values"] = output_devices

        if output_devices:
            self.device_var.set(
                output_devices[0]
            )

    def get_selected_device(self):
        name = self.device_var.get()

        if not name:
            return None

        return self.device_map.get(name)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self):
        if self.audio_data is None:
            return

        if self.playing:
            return

        device = self.get_selected_device()

        if device is None:
            messagebox.showwarning(
                "No output device",
                "Select an audio output device first."
            )
            return

        self.stop_requested = False
        self.playing = True
        self.paused = False

        self.play_button.configure(
            state="disabled"
        )

        self.pause_button.configure(
            state="normal",
            text="Ⅱ Pause"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.status_var.set(
            "Playing"
        )

        thread = threading.Thread(
            target=self.playback_worker,
            args=(device,),
            daemon=True
        )

        thread.start()

    def playback_worker(self, device):
        try:
            blocksize = 2048

            def callback(outdata, frames, time_info, status):
                if self.stop_requested:
                    raise sd.CallbackStop()

                start = self.audio_position
                end = min(
                    start + frames,
                    len(self.audio_data)
                )

                chunk = self.audio_data[
                    start:end
                ]

                volume = self.volume

                if len(chunk) > 0:
                    outdata[:len(chunk)] = (
                        chunk * volume
                    )

                if len(chunk) < frames:
                    outdata[len(chunk):] = 0
                    self.audio_position = len(
                        self.audio_data
                    )
                    raise sd.CallbackStop()

                self.audio_position = end

                self.root.after(
                    0,
                    self.update_progress
                )

            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.audio_data.shape[1],
                dtype="float32",
                device=device,
                blocksize=blocksize,
                callback=callback
            ) as stream:

                self.audio_stream = stream

                while (
                    self.playing
                    and not self.stop_requested
                    and self.audio_position
                    < len(self.audio_data)
                ):
                    if self.paused:
                        stream.stop()

                        while (
                            self.paused
                            and self.playing
                            and not self.stop_requested
                        ):
                            threading.Event().wait(
                                0.05
                            )

                        if (
                            not self.playing
                            or self.stop_requested
                        ):
                            break

                        stream.start()

                    threading.Event().wait(
                        0.05
                    )

        except Exception as exc:
            self.root.after(
                0,
                lambda: self.playback_error(exc)
            )
            return

        self.root.after(
            0,
            self.playback_finished
        )

    def playback_error(self, exc):
        self.playing = False
        self.paused = False
        self.audio_stream = None

        self.play_button.configure(
            state="normal"
        )

        self.pause_button.configure(
            state="disabled",
            text="Ⅱ Pause"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.status_var.set(
            "Playback error"
        )

        messagebox.showerror(
            "Playback error",
            str(exc)
        )

    def playback_finished(self):
        if self.stop_requested:
            return

        self.playing = False
        self.paused = False
        self.audio_stream = None

        if self.audio_data is not None:
            self.audio_position = len(
                self.audio_data
            )

        self.play_button.configure(
            state="normal"
        )

        self.pause_button.configure(
            state="disabled",
            text="Ⅱ Pause"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.update_progress()

        self.status_var.set(
            "Finished"
        )

    # ------------------------------------------------------------------
    # Pause / Stop
    # ------------------------------------------------------------------

    def pause(self):
        if not self.playing:
            return

        self.paused = not self.paused

        if self.paused:
            self.pause_button.configure(
                text="▶ Resume"
            )

            self.status_var.set(
                "Paused"
            )

        else:
            self.pause_button.configure(
                text="Ⅱ Pause"
            )

            self.status_var.set(
                "Playing"
            )

    def stop(self):
        self.stop_requested = True
        self.playing = False
        self.paused = False

        if self.audio_stream is not None:
            try:
                self.audio_stream.abort()
            except Exception:
                pass

            self.audio_stream = None

        self.audio_position = 0

        self.play_button.configure(
            state=(
                "normal"
                if self.audio_data is not None
                else "disabled"
            )
        )

        self.pause_button.configure(
            state="disabled",
            text="Ⅱ Pause"
        )

        self.stop_button.configure(
            state="disabled"
        )

        self.current_time_var.set(
            "00:00"
        )

        self.progress.set(0)

        self.status_var.set(
            "Stopped"
        )

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def volume_changed(self, value):
        try:
            self.volume = float(value) / 100.0
        except ValueError:
            self.volume = 1.0

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def update_progress(self):
        if (
            self.audio_data is None
            or self.sample_rate is None
        ):
            return

        current = (
            self.audio_position
            / self.sample_rate
        )

        total = (
            len(self.audio_data)
            / self.sample_rate
        )

        self.current_time_var.set(
            self.format_time(current)
        )

        self.total_time_var.set(
            self.format_time(total)
        )

        self.progress.set(
            min(current, total)
        )

    @staticmethod
    def format_time(seconds):
        seconds = max(
            0,
            int(seconds)
        )

        minutes = seconds // 60
        seconds = seconds % 60

        return f"{minutes:02d}:{seconds:02d}"

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def on_close(self):
        self.stop()

        try:
            sd.stop()
        except Exception:
            pass

        self.root.destroy()


def main():
    root = tk.Tk()

    try:
        CassetteRecorder(root)
        root.mainloop()

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()