import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pydub import AudioSegment
import numpy as np
import simpleaudio as sa
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
import re


class AudioTrimmerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Trim Audio File")
        self.root.geometry("950x700")
        self.root.configure(bg="#f0f0f0")

        self.audio = None
        self.audio_path = ""
        self.play_obj = None
        self.start_time = 0.0
        self.end_time = 0.0
        self.duration = 0.0
        self.dragging = None
        self.span = None
        self.start_handle = None
        self.end_handle = None
        self.start_text = None
        self.end_text = None
        self.view_start = 0.0
        self.view_end = 0.0
        self._updating_scrollbar = False
        self._set_mode = None
        self._updating_entries = False
        self._panning = False
        self._pan_start_x = None

        # Pre-cached raw audio for fast preview
        self._raw_data = None
        self._raw_channels = 0
        self._raw_sample_width = 0
        self._raw_frame_rate = 0
        self._bytes_per_second = 0

        # --- Style ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Toolbar.TFrame", background="#f0f0f0")
        style.configure("TButton", padding=6, font=("Segoe UI", 10))
        style.configure("Small.TButton", padding=(4, 1), font=("Segoe UI", 9))
        style.configure("Info.TLabel", background="#f0f0f0", foreground="#333333",
                         font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f0f0f0", foreground="#222222",
                         font=("Segoe UI", 12, "bold"))

        # --- Toolbar ---
        toolbar = ttk.Frame(root, style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Button(toolbar, text="Open File", command=self.load_audio).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Preview", command=self.preview).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Stop", command=self.stop_playback).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Export Trimmed", command=self.export_trimmed).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side=tk.LEFT, padx=4)

        self.file_label = ttk.Label(toolbar, text="No file loaded", style="Title.TLabel")
        self.file_label.pack(side=tk.RIGHT, padx=10)

        # --- Handle controls bar (always visible) ---
        handle_bar = ttk.Frame(root, style="Toolbar.TFrame")
        handle_bar.pack(fill=tk.X, padx=10, pady=(8, 0))

        # Start handle controls
        start_frame = ttk.Frame(handle_bar, style="Toolbar.TFrame")
        start_frame.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(start_frame, text="Start:", style="Info.TLabel",
                   foreground="#2e7d32", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.start_entry = ttk.Entry(start_frame, width=10, font=("Segoe UI", 10))
        self.start_entry.pack(side=tk.LEFT, padx=2)
        self.start_entry.insert(0, "0:00.00")
        self.start_entry.bind("<Return>", lambda e: self._apply_typed_time("start"))
        self.start_entry.bind("<FocusOut>", lambda e: self._apply_typed_time("start"))
        self.start_set_btn = ttk.Button(start_frame, text="Set on Graph", style="Small.TButton",
                                         command=lambda: self._toggle_set_mode("start"))
        self.start_set_btn.pack(side=tk.LEFT, padx=2)

        # Selection duration
        self.sel_label = ttk.Label(handle_bar, text="Selection: --", style="Info.TLabel",
                                    font=("Segoe UI", 10))
        self.sel_label.pack(side=tk.LEFT, padx=20)

        # End handle controls
        end_frame = ttk.Frame(handle_bar, style="Toolbar.TFrame")
        end_frame.pack(side=tk.RIGHT, padx=(20, 0))

        self.end_set_btn = ttk.Button(end_frame, text="Set on Graph", style="Small.TButton",
                                       command=lambda: self._toggle_set_mode("end"))
        self.end_set_btn.pack(side=tk.RIGHT, padx=2)
        self.end_entry = ttk.Entry(end_frame, width=10, font=("Segoe UI", 10))
        self.end_entry.pack(side=tk.RIGHT, padx=2)
        self.end_entry.insert(0, "0:00.00")
        self.end_entry.bind("<Return>", lambda e: self._apply_typed_time("end"))
        self.end_entry.bind("<FocusOut>", lambda e: self._apply_typed_time("end"))
        ttk.Label(end_frame, text="End:", style="Info.TLabel",
                   foreground="#c62828", font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=(0, 4))

        # --- Set-mode status label ---
        self.set_mode_label = ttk.Label(root, text="", style="Info.TLabel",
                                         font=("Segoe UI", 10, "bold"), foreground="#1565c0")
        self.set_mode_label.pack(fill=tk.X, padx=10)

        # --- Total duration label ---
        total_bar = ttk.Frame(root, style="Toolbar.TFrame")
        total_bar.pack(fill=tk.X, padx=10)
        self.total_label = ttk.Label(total_bar, text="Total: --", style="Info.TLabel")
        self.total_label.pack(side=tk.RIGHT, padx=10)

        # --- Matplotlib waveform ---
        self.fig = Figure(figsize=(9, 3), dpi=100, facecolor="white")
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))

        # --- Scrollbar ---
        self.scrollbar = ttk.Scrollbar(root, orient=tk.HORIZONTAL, command=self._on_scrollbar)
        self.scrollbar.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Keyboard bindings
        self.root.bind("<space>", self._toggle_playback)

        # Mouse bindings
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)

    def _style_axes(self):
        self.ax.set_facecolor("white")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Amplitude")

    @staticmethod
    def _format_time(seconds):
        m, s = divmod(seconds, 60)
        return f"{int(m)}:{s:05.2f}"

    @staticmethod
    def _parse_time(text):
        text = text.strip()
        match = re.match(r'^(\d+):(\d{1,2}(?:\.\d*)?)$', text)
        if match:
            minutes = int(match.group(1))
            secs = float(match.group(2))
            return minutes * 60 + secs
        try:
            return float(text)
        except ValueError:
            return None

    def _update_entries(self):
        self._updating_entries = True
        self.start_entry.delete(0, tk.END)
        self.start_entry.insert(0, self._format_time(self.start_time))
        self.end_entry.delete(0, tk.END)
        self.end_entry.insert(0, self._format_time(self.end_time))
        self._updating_entries = False

    def _apply_typed_time(self, which):
        if not self.audio or self._updating_entries:
            return

        if which == "start":
            val = self._parse_time(self.start_entry.get())
            if val is None:
                messagebox.showwarning("Invalid Time", "Enter time as m:ss.xx or seconds (e.g. 1:23.45 or 83.45)")
                return
            val = max(0.0, min(val, self.end_time - 0.01))
            self.start_time = val
        else:
            val = self._parse_time(self.end_entry.get())
            if val is None:
                messagebox.showwarning("Invalid Time", "Enter time as m:ss.xx or seconds (e.g. 1:23.45 or 83.45)")
                return
            val = max(self.start_time + 0.01, min(val, self.duration))
            self.end_time = val

        self.update_lines()

    def _toggle_set_mode(self, which):
        if self._set_mode == which:
            self._set_mode = None
            self.set_mode_label.config(text="")
            self.canvas.get_tk_widget().config(cursor="")
        else:
            self._set_mode = which
            label = "Start" if which == "start" else "End"
            self.set_mode_label.config(
                text=f"Click on the waveform to set {label} position...",
                foreground="#2e7d32" if which == "start" else "#c62828")
            self.canvas.get_tk_widget().config(cursor="crosshair")

    def _update_info(self):
        sel = self.end_time - self.start_time
        self.sel_label.config(text=f"Selection: {self._format_time(sel)}")
        self.total_label.config(text=f"Total: {self._format_time(self.duration)}")
        self._update_entries()

    def _handle_grab_threshold(self):
        view_range = self.view_end - self.view_start
        return max(0.05, view_range * 0.03)

    def _update_scrollbar(self):
        if self.duration <= 0:
            return
        self._updating_scrollbar = True
        lo = self.view_start / self.duration
        hi = self.view_end / self.duration
        self.scrollbar.set(lo, hi)
        self._updating_scrollbar = False

    def _on_scrollbar(self, *args):
        if not self.audio or self._updating_scrollbar:
            return

        view_range = self.view_end - self.view_start

        if args[0] == "moveto":
            frac = float(args[1])
            self.view_start = max(0, frac * self.duration)
            self.view_end = self.view_start + view_range
            if self.view_end > self.duration:
                self.view_end = self.duration
                self.view_start = max(0, self.duration - view_range)
        elif args[0] == "scroll":
            delta = float(args[1])
            shift = delta * view_range * 0.1
            self.view_start += shift
            self.view_end += shift
            if self.view_start < 0:
                self.view_start = 0
                self.view_end = view_range
            if self.view_end > self.duration:
                self.view_end = self.duration
                self.view_start = max(0, self.duration - view_range)

        self.ax.set_xlim(self.view_start, self.view_end)
        self._update_scrollbar()
        self.canvas.draw_idle()

    def load_audio(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Audio files", "*.wav *.mp3"),
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("All files", "*.*")
            ]
        )
        if not path:
            return

        self.audio_path = path

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == '.mp3':
                self.audio = AudioSegment.from_mp3(path)
            elif ext == '.wav':
                self.audio = AudioSegment.from_wav(path)
            else:
                self.audio = AudioSegment.from_file(path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audio file:\n{e}")
            return

        self.duration = len(self.audio) / 1000.0
        self.start_time = 0.0
        self.end_time = self.duration
        self.view_start = 0.0
        self.view_end = self.duration

        # Pre-cache raw audio bytes for instant preview playback
        self._raw_data = self.audio.raw_data
        self._raw_channels = self.audio.channels
        self._raw_sample_width = self.audio.sample_width
        self._raw_frame_rate = self.audio.frame_rate
        self._bytes_per_second = self._raw_frame_rate * self._raw_channels * self._raw_sample_width

        samples = np.array(self.audio.get_array_of_samples())
        if self.audio.channels == 2:
            samples = samples.reshape((-1, 2))
            samples = samples.mean(axis=1)

        self.samples = samples
        self.times = np.linspace(0, self.duration, num=len(samples))

        self._redraw_waveform()

    def _redraw_waveform(self):
        self.ax.clear()
        self._style_axes()
        self.ax.plot(self.times, self.samples, color="steelblue", linewidth=0.5)
        self.ax.set_xlim(self.view_start, self.view_end)

        self.start_line = self.ax.axvline(self.start_time, color="#66bb6a", linewidth=2)
        self.end_line = self.ax.axvline(self.end_time, color="#ef5350", linewidth=2)

        self.span = self.ax.axvspan(self.start_time, self.end_time,
                                     alpha=0.2, color="steelblue")

        y_bottom = self.ax.get_ylim()[0]
        y_range = self.ax.get_ylim()[1] - y_bottom
        handle_y = y_bottom + y_range * 0.06
        self.start_handle, = self.ax.plot(self.start_time, handle_y, marker='^',
                                           color="#66bb6a", markersize=12,
                                           markeredgecolor="#2e7d32",
                                           markeredgewidth=1.5, zorder=10,
                                           clip_on=True)
        self.end_handle, = self.ax.plot(self.end_time, handle_y, marker='^',
                                         color="#ef5350", markersize=12,
                                         markeredgecolor="#c62828",
                                         markeredgewidth=1.5, zorder=10,
                                         clip_on=True)

        y_top = self.ax.get_ylim()[1]
        self.start_text = self.ax.text(self.start_time, y_top, self._format_time(self.start_time),
                                        color="#2e7d32", fontsize=9, fontweight="bold",
                                        ha="center", va="bottom", zorder=10,
                                        clip_on=True)
        self.end_text = self.ax.text(self.end_time, y_top, self._format_time(self.end_time),
                                      color="#c62828", fontsize=9, fontweight="bold",
                                      ha="center", va="bottom", zorder=10,
                                      clip_on=True)

        self.file_label.config(text=os.path.basename(self.audio_path))
        self._update_info()
        self._update_scrollbar()
        self.canvas.draw()

    # ---------- Mouse event handlers ----------
    def _is_handle_visible(self, handle_time):
        return self.view_start <= handle_time <= self.view_end

    def on_press(self, event):
        if not self.audio or not event.inaxes or event.xdata is None:
            return

        # Middle-click or shift+left-click to pan
        if event.button == 2 or (event.button == 1 and event.key == "shift"):
            self._panning = True
            self._pan_start_x = event.xdata
            self.canvas.get_tk_widget().config(cursor="fleur")
            return

        if self._set_mode == "start":
            self.start_time = max(0.0, min(event.xdata, self.end_time - 0.01))
            self._set_mode = None
            self.set_mode_label.config(text="")
            self.canvas.get_tk_widget().config(cursor="")
            self._clamp_times()
            self.update_lines()
            return
        elif self._set_mode == "end":
            self.end_time = max(self.start_time + 0.01, min(event.xdata, self.duration))
            self._set_mode = None
            self.set_mode_label.config(text="")
            self.canvas.get_tk_widget().config(cursor="")
            self._clamp_times()
            self.update_lines()
            return

        threshold = self._handle_grab_threshold()

        start_visible = self._is_handle_visible(self.start_time)
        end_visible = self._is_handle_visible(self.end_time)

        dist_start = abs(event.xdata - self.start_time) if start_visible else float('inf')
        dist_end = abs(event.xdata - self.end_time) if end_visible else float('inf')

        if dist_start < dist_end and dist_start < threshold:
            self.dragging = "start"
        elif dist_end <= dist_start and dist_end < threshold:
            self.dragging = "end"
        elif start_visible or end_visible:
            if dist_start < dist_end:
                self.dragging = "start"
                self.start_time = event.xdata
            else:
                self.dragging = "end"
                self.end_time = event.xdata
            self._clamp_times()
            self.update_lines()

    def on_motion(self, event):
        if not self.audio or event.xdata is None:
            return

        if self._set_mode:
            return

        if not self.dragging and event.inaxes:
            threshold = self._handle_grab_threshold()
            near_start = (self._is_handle_visible(self.start_time) and
                          abs(event.xdata - self.start_time) < threshold)
            near_end = (self._is_handle_visible(self.end_time) and
                        abs(event.xdata - self.end_time) < threshold)
            if near_start or near_end:
                self.canvas.get_tk_widget().config(cursor="sb_h_double_arrow")
            else:
                self.canvas.get_tk_widget().config(cursor="")

        if not event.inaxes:
            return

        # Handle panning
        if self._panning and self._pan_start_x is not None:
            dx = self._pan_start_x - event.xdata
            view_range = self.view_end - self.view_start
            new_start = self.view_start + dx
            new_end = self.view_end + dx
            if new_start < 0:
                new_start = 0
                new_end = view_range
            if new_end > self.duration:
                new_end = self.duration
                new_start = max(0, self.duration - view_range)
            self.view_start = new_start
            self.view_end = new_end
            self.ax.set_xlim(self.view_start, self.view_end)
            self._update_scrollbar()
            self.canvas.draw_idle()
            return

        if self.dragging == "start":
            self.start_time = max(0.0, min(event.xdata, self.end_time - 0.01))
            self.update_lines()
        elif self.dragging == "end":
            self.end_time = min(self.duration, max(event.xdata, self.start_time + 0.01))
            self.update_lines()

    def on_release(self, event):
        self.dragging = None
        self._panning = False
        self._pan_start_x = None
        if not self._set_mode:
            self.canvas.get_tk_widget().config(cursor="")

    def on_scroll(self, event):
        if not self.audio or not event.inaxes or event.xdata is None:
            return

        zoom_factor = 0.8 if event.button == "up" else 1.25

        view_range = self.view_end - self.view_start
        new_range = view_range * zoom_factor

        new_range = min(new_range, self.duration)
        new_range = max(new_range, 0.005)

        cursor_ratio = (event.xdata - self.view_start) / view_range
        self.view_start = event.xdata - cursor_ratio * new_range
        self.view_end = event.xdata + (1 - cursor_ratio) * new_range

        if self.view_start < 0:
            self.view_start = 0
            self.view_end = min(new_range, self.duration)
        if self.view_end > self.duration:
            self.view_end = self.duration
            self.view_start = max(0, self.duration - new_range)

        self.ax.set_xlim(self.view_start, self.view_end)
        self._update_scrollbar()
        self.canvas.draw_idle()

    def reset_zoom(self):
        if not self.audio:
            return
        self.view_start = 0.0
        self.view_end = self.duration
        self.ax.set_xlim(self.view_start, self.view_end)
        self._update_scrollbar()
        self.canvas.draw_idle()

    def _clamp_times(self):
        self.start_time = max(0.0, min(self.start_time, self.duration))
        self.end_time = max(self.start_time + 0.01, min(self.end_time, self.duration))

    # ---------- Playback & Export ----------
    def preview(self):
        if not self.audio:
            messagebox.showerror("Error", "No audio loaded.")
            return
        if self.play_obj and self.play_obj.is_playing():
            self.play_obj.stop()

        # Slice directly from cached raw bytes — no pydub overhead
        start_byte = int(self.start_time * self._bytes_per_second)
        end_byte = int(self.end_time * self._bytes_per_second)

        # Align to frame boundary (channels * sample_width)
        frame_size = self._raw_channels * self._raw_sample_width
        start_byte = (start_byte // frame_size) * frame_size
        end_byte = (end_byte // frame_size) * frame_size

        trimmed_raw = self._raw_data[start_byte:end_byte]

        self.play_obj = sa.play_buffer(
            trimmed_raw,
            num_channels=self._raw_channels,
            bytes_per_sample=self._raw_sample_width,
            sample_rate=self._raw_frame_rate,
        )

    def _toggle_playback(self, event=None):
        # Don't trigger spacebar when typing in an entry field
        if event and isinstance(event.widget, (tk.Entry, ttk.Entry)):
            return
        if self.play_obj and self.play_obj.is_playing():
            self.stop_playback()
        else:
            self.preview()

    def stop_playback(self):
        if self.play_obj and self.play_obj.is_playing():
            self.play_obj.stop()

    def export_trimmed(self):
        if not self.audio:
            messagebox.showerror("Error", "No audio loaded.")
            return

        # Build default filename suggestion
        base_name, ext = os.path.splitext(self.audio_path)
        ext = ext.lower()
        if ext not in ['.mp3', '.wav']:
            ext = '.wav'
        default_name = os.path.basename(base_name) + "_trimmed" + ext

        out_path = filedialog.asksaveasfilename(
            initialfile=default_name,
            initialdir=os.path.dirname(self.audio_path),
            defaultextension=ext,
            filetypes=[
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("All files", "*.*")
            ]
        )
        if not out_path:
            return

        start_ms = self.start_time * 1000
        end_ms = self.end_time * 1000
        trimmed = self.audio[start_ms:end_ms]

        # Determine format from chosen extension
        out_ext = os.path.splitext(out_path)[1].lower()
        out_format = out_ext[1:] if out_ext in ['.mp3', '.wav'] else 'wav'

        trimmed.export(out_path, format=out_format)
        messagebox.showinfo("Saved", f"Trimmed file saved:\n{out_path}")

    def update_lines(self):
        self.start_line.set_xdata([self.start_time, self.start_time])
        self.end_line.set_xdata([self.end_time, self.end_time])

        if self.span:
            self.span.remove()
        self.span = self.ax.axvspan(self.start_time, self.end_time,
                                     alpha=0.2, color="steelblue")

        y_bottom = self.ax.get_ylim()[0]
        y_range = self.ax.get_ylim()[1] - y_bottom
        handle_y = y_bottom + y_range * 0.06
        self.start_handle.set_data([self.start_time], [handle_y])
        self.end_handle.set_data([self.end_time], [handle_y])

        y_top = self.ax.get_ylim()[1]
        self.start_text.set_position((self.start_time, y_top))
        self.start_text.set_text(self._format_time(self.start_time))
        self.end_text.set_position((self.end_time, y_top))
        self.end_text.set_text(self._format_time(self.end_time))

        self._update_info()
        self.canvas.draw_idle()


if __name__ == "__main__":
    root = tk.Tk()
    app = AudioTrimmerGUI(root)
    root.mainloop()
