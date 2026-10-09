# ScarliPleer
## ✨ Features

### 🎧 Playback
- MP3, WAV, OGG support
- Play / Pause / Next / Previous
- Shuffle & Repeat
- Volume control + mute

### 📚 Library
- Drag & drop files or whole folders
- Fuzzy search (finds even with typos)
- Sort by title / artist / length / date
- Favorites list
- Play counts & statistics
- Duplicate detection

### 🎨 Interface
- Purple accent (6 presets + custom color picker)
- Smooth color transitions
- Custom hover effects
- Tooltips everywhere
- Fullscreen cover view (double-click the cover)
- Compact mode (`Ctrl+F`)

### 📝 Tags & Metadata
- Read ID3 tags (title, artist, album, cover)
- Built-in tag editor
- Drag & drop cover replacement
- Cover cache for fast scrolling

### 🖥️ System integration
- System tray with menu (Show / Play / Next / Prev / Quit)
- Minimize to tray on close
- Taskbar progress (Windows)
- Auto-start with Windows (optional)
- Sleep timer (15 / 30 / 60 / 120 min)

### ⌨️ Hotkeys

| Key | Action |
|-----|--------|
| `Space` | Play / Pause |
| `←` / `→` | Seek ±5s |
| `↑` / `↓` | Volume ±5 |
| `S` | Shuffle |
| `R` | Repeat |
| `M` | Mute |
| `Ctrl+O` | Add files |
| `Ctrl+L` | Clear playlist |
| `Ctrl+F` | Compact mode |
| `Ctrl+S` | Statistics |
| `F11` | Fullscreen |
| `Esc` | Clear search |

---

## 📥 Installation

### Option 1 — Download the `.exe` (recommended)

1. Go to [**Releases**](https://github.com/ScarlLV/ScarliPleer)
2. Download `ScarliPleer.exe`
3. Run it
4. Windows may show a warning → click **More info** → **Run anyway**
5. Enjoy 🎵

### Option 2 — Run from source

```bash
git clone https://github.com/YOUR_USERNAME/scarliplayer.git
cd scarliplayer
pip install -r requirements.txt
python player.py
