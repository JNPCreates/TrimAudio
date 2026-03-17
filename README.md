# Trim Audio File

A lightweight GUI tool for visually trimming WAV and MP3 audio files. Load a file, see the waveform, drag the start/end handles (or type exact timestamps), preview your selection, and export the trimmed result.

## Features

- **Waveform display** with draggable green (start) and red (end) trim handles
- **Mouse wheel zoom** on the time axis — zoom down to 5ms for precise editing
- **Shift+drag or middle-click panning** to navigate when zoomed in
- **Horizontal scrollbar** that scales with zoom level
- **Type exact timestamps** in the Start/End fields (formats: `1:23.45` or `83.45`)
- **"Set on Graph" mode** — click a button, then click the waveform to place a handle (useful when handles are off-screen)
- **Spacebar** toggles play/stop
- **Save As dialog** for export with format auto-detection (WAV/MP3)
- Fast preview playback using pre-cached raw audio bytes

## Dependencies

```
pip install pydub numpy simpleaudio matplotlib
```

**Note:** MP3 support requires [FFmpeg](https://ffmpeg.org/download.html) to be installed and available on your system PATH. WAV files work without FFmpeg.

## Usage

```
python TrimAudioFile.py
```

1. Click **Open File** and select a WAV or MP3 file
2. The waveform appears — drag the green/red handles or type times to set your trim region
3. Scroll to zoom in, shift+drag to pan
4. Click **Preview** (or press spacebar) to listen to the selection
5. Click **Export Trimmed** to save the result

## Requirements

- Python 3.8+
- Windows / macOS / Linux (uses tkinter, which is included with most Python installations)
