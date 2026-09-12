# Cassette Compiler 📼

A small Python tool for preparing music playlists for recording onto
physical cassette tapes.

## Features

- Preserve playlist/file order
- Calculate track runtimes
- Support C60 and C90 tapes
- Automatically divide playlists into tape sides
- Generate as many tape sides as necessary
- Apply fade-out to the final track of each side
- Export continuous WAV files
- Generate tracklists for each side

## Requirements

### Python

Python 3.10 or newer.

No external Python packages are currently required.

### FFmpeg

Cassette Compiler requires FFmpeg and FFprobe.

Both executables must be available in the system `PATH`.

Verify the installation with:

```bash
ffmpeg -version
ffprobe -version