# TapeMaker

A small toolkit for preparing and recording music onto physical cassette tapes.

TapeMaker is designed around the workflow of making real cassette mixtapes from digital music:

```text
Music library
     │
     ▼
┌──────────────────┐
│ Cassette Compiler│
└────────┬─────────┘
         │
         │ compiled WAV sides
         ▼
┌──────────────────┐
│ Cassette Recorder│
└────────┬─────────┘
         │
         │ dedicated audio output
         ▼
    Cassette Deck
         │
         ▼
        K7
```

The project is intentionally divided into two independent components:

* **Compiler** — prepares the audio for the physical tape.
* **Recorder** — plays the prepared sides through a selected audio output device.

---

## Features

### Cassette Compiler

The Compiler takes music files from mixtape folders and prepares them for recording.

It supports:

* C60 tapes — 30 minutes per side
* C90 tapes — 45 minutes per side
* Multiple tapes when a playlist does not fit on one tape
* Preservation of track order
* Automatic side splitting
* Tracks are never split between sides
* Fade-out at the end of each side
* WAV output suitable for cassette recording
* A TXT tracklist for every generated side
* Multiple mixtapes in a single source directory

### Cassette Recorder

The Recorder takes the WAV files produced by the Compiler and plays them to a selected audio output.

It supports:

* Selecting a compiled mixtape folder
* Automatic scanning of available tapes
* Selecting Tape 01, Tape 02, Tape 03, etc.
* Selecting Side A or Side B
* Displaying the side's tracklist
* Selecting the output audio device
* Play
* Pause / Resume
* Stop
* Independent playback volume
* Playback progress and elapsed time
* Direct WAV playback
* No system-audio capture

---

# Project Structure

```text
TapeMaker/
├── cassette_compiler.py
├── cassette_recorder.py
├── requirements.txt
└── README.md
```

The two programs have deliberately different responsibilities.

```text
cassette_compiler.py
    │
    └── prepares the tape

cassette_recorder.py
    │
    └── plays the prepared tape
```

---

# Requirements

## Python

TapeMaker requires Python 3.10 or newer.

Check your Python version:

```bash
python --version
```

## Python packages

It is recommended to use a Python virtual environment (`venv`) to keep TapeMaker's dependencies isolated from the system Python installation.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Activate it on Linux/macOS:

```bash
source .venv/bin/activate
```

Then install the Python dependencies:

```bash
pip install -r requirements.txt
```

The Recorder uses:

* `numpy`
* `sounddevice`
* `soundfile`

---

# FFmpeg

The Cassette Compiler requires:

* `ffmpeg`
* `ffprobe`

Both must be available in the system `PATH`.

Check that they are available:

```bash
ffmpeg -version
```

```bash
ffprobe -version
```

FFmpeg is a system dependency rather than a Python package, so it is **not** included in `requirements.txt`.

The Recorder does not require FFmpeg for playback of the compiled WAV files.

---

# Cassette Compiler

## Input Structure

The Compiler expects a parent directory containing one folder per mixtape.

For example:

```text
MUSIC/
├── Depeche Mode 101/
│   ├── 01.flac
│   ├── 02.flac
│   ├── 03.flac
│   └── ...
│
├── Duran Duran/
│   ├── 01.flac
│   ├── 02.flac
│   └── ...
│
└── Good Girls/
    ├── 01.flac
    ├── 02.flac
    └── ...
```

Each child directory is treated as a separate mixtape.

The filenames are used to determine track order.

---

## Tape Capacity

Tape formats are represented by their nominal total playing time:

| Format | Side A | Side B |  Total |
| ------ | -----: | -----: | -----: |
| C60    | 30 min | 30 min | 60 min |
| C90    | 45 min | 45 min | 90 min |

The Compiler does not split an individual track between sides.

If a playlist requires more space than one tape provides, additional tapes are generated automatically.

---

## Compiler Usage

For a C60:

```bash
python cassette_compiler.py "MUSIC" --tape C60
```

For a C90:

```bash
python cassette_compiler.py "MUSIC" --tape C90
```

The fade duration can be changed:

```bash
python cassette_compiler.py "MUSIC" --tape C60 --fade 7
```

The default fade duration is 5 seconds.

---

# Compiler Output

The output is organized first by cassette format and then by mixtape.

For example:

```text
cassette_output/
└── C60/
    ├── Depeche Mode 101/
    │   ├── Tape 01 - Side A.wav
    │   ├── Tape 01 - Side A.txt
    │   ├── Tape 01 - Side B.wav
    │   ├── Tape 01 - Side B.txt
    │   ├── Tape 02 - Side A.wav
    │   └── Tape 02 - Side A.txt
    │
    ├── Duran Duran/
    │   ├── Tape 01 - Side A.wav
    │   ├── Tape 01 - Side A.txt
    │   └── ...
    │
    └── Good Girls/
        ├── Tape 01 - Side A.wav
        └── ...
```

For C90:

```text
cassette_output/
└── C90/
    └── Depeche Mode 101/
        ├── Tape 01 - Side A.wav
        ├── Tape 01 - Side A.txt
        ├── Tape 01 - Side B.wav
        └── Tape 01 - Side B.txt
```

---

## WAV Output

The Compiler generates:

* WAV
* 48 kHz
* Stereo
* PCM 16-bit

These files are intended to be used as the source for the physical cassette recording stage.

---

## Side Tracklists

Each WAV side has a corresponding TXT file.

Example:

```text
Tape 01 - Side A.wav
Tape 01 - Side A.txt
```

The TXT file contains information about the generated side, including:

* Mixtape name
* Tape number
* Side
* Cassette format
* Runtime
* Nominal capacity
* Fade duration
* Tracklist

The Recorder can use this file to display the side contents.

---

# Cassette Recorder

The Recorder is a separate program from the Compiler.

It does not rebuild playlists, calculate cassette capacity, or modify the generated sides.

Its job is simply:

```text
Select compiled mixtape
        ↓
Select tape
        ↓
Select side
        ↓
Select audio output
        ↓
Play
```

---

## Recorder Input

The Recorder expects the **mixtape directory itself**, not the parent `MUSIC` directory and not the entire `cassette_output` directory.

For example:

```text
cassette_output/
└── C90/
    └── Depeche Mode 101/
        ├── Tape 01 - Side A.wav
        ├── Tape 01 - Side A.txt
        ├── Tape 01 - Side B.wav
        ├── Tape 01 - Side B.txt
        ├── Tape 02 - Side A.wav
        └── Tape 02 - Side B.wav
```

The folder supplied to the Recorder is:

```text
C90/Depeche Mode 101/
```

The Recorder scans that directory and automatically discovers:

```text
Tape 01
├── Side A
└── Side B

Tape 02
├── Side A
└── Side B
```

---

## Running the Recorder

```bash
python cassette_recorder.py
```

The application will open a graphical interface.

Select:

1. The compiled mixtape folder.
2. The tape number.
3. Side A or Side B.
4. The audio output device.

Then press **Play**.

---

# Audio Routing

The Recorder does **not** capture the Windows system audio.

It reads the compiled WAV file directly:

```text
Tape 01 - Side A.wav
        │
        ▼
Cassette Recorder
        │
        ▼
Selected audio device
        │
        ▼
Cassette deck
```

It does not use the Windows system mixer as an audio source.

This allows the computer to have a separate normal audio output while the Recorder sends the cassette signal to another device.

For example:

```text
                  ┌── Windows audio
                  │      │
                  │      ▼
PC ───────────────┤   Headphones
                  │
                  │
                  └── Cassette Recorder
                         │
                         ▼
                  USB audio interface
                         │
                         ▼
                    Cassette deck
```

A dedicated USB audio interface or DAC is recommended for the cassette deck.

This makes the physical recording chain independent from normal computer audio.

---

# Recorder Controls

The Recorder provides:

### Mixtape folder

Selects the directory containing the compiled WAV files.

### Tape

Lists all detected tape numbers.

For example:

```text
Tape 01
Tape 02
Tape 03
```

### Side

Selects:

```text
A
B
```

### Audio output

Lists available output devices detected by the system.

The selected device is used for playback.

### Play

Starts playback from the current position.

### Pause

Temporarily pauses playback.

### Resume

Continues playback from the paused position.

### Stop

Stops playback and returns to the beginning of the selected side.

### Volume

Controls the Recorder's playback level independently of the normal Windows volume controls.

---

# Recommended Recording Setup

For a physical cassette recording setup:

```text
PC
 │
 ├── Normal system audio
 │       └── headphones / speakers
 │
 └── TapeMaker Recorder
         │
         └── dedicated USB audio output
                  │
                  ▼
             Cassette deck
                  │
                  ▼
                 K7
```

The cassette deck should be connected to a dedicated output whenever possible.

This prevents unrelated system audio from becoming part of the recording signal.

---

# Supported Input Audio Formats

The Compiler supports:

```text
.mp3
.flac
.wav
.m4a
.aac
.ogg
.opus
.wma
.aiff
.aif
```

The Recorder itself operates on the WAV files generated by the Compiler.

---

# Workflow

A typical TapeMaker workflow is:

## 1. Organize the music

Create one folder for each mixtape:

```text
MUSIC/
└── My Mixtape/
    ├── 01.flac
    ├── 02.flac
    ├── 03.flac
    └── ...
```

## 2. Compile the cassette

```bash
python cassette_compiler.py "MUSIC" --tape C60
```

## 3. Inspect the generated sides

```text
cassette_output/
└── C60/
    └── My Mixtape/
        ├── Tape 01 - Side A.wav
        ├── Tape 01 - Side A.txt
        ├── Tape 01 - Side B.wav
        └── Tape 01 - Side B.txt
```

## 4. Start the Recorder

```bash
python cassette_recorder.py
```

## 5. Select the mixtape

Select:

```text
cassette_output/C60/My Mixtape/
```

## 6. Select the tape and side

For example:

```text
Tape 01
Side A
```

## 7. Select the recording output

Choose the audio interface connected to the cassette deck.

## 8. Start the cassette deck recording

Put the deck into record mode and start playback in TapeMaker.

---

# Design Philosophy

TapeMaker is intentionally built around the physical cassette workflow rather than treating a cassette as just another digital audio format.

The Compiler handles the planning and preparation:

```text
Digital music
     ↓
Track ordering
     ↓
Side allocation
     ↓
Fade
     ↓
WAV
```

The Recorder handles the physical playback stage:

```text
WAV
 ↓
Selected hardware output
 ↓
Cassette deck
 ↓
Magnetic tape
```

Keeping these stages separate makes it possible to prepare tapes in advance and record them later without having to run the compilation process again.

---

# License

Add the project's license here when one is selected.
