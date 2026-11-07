# SpeechFlow

**Text to Speech: Offline. Lightweight. Private.**

Copy any text to the clipboard, click one button (or run one command), and
[Phonon TTS](https://github.com/gradium-ai/xn-ptts) reads it aloud in a
window you can pause, seek, and control. While you listen, a WAV archive
file is written to disk — every recording stays available for later.

- **Starts instantly** — the whole text is synthesized in a single streaming
  pass; playback begins with the first audio frame (no waiting for a
  finished file).
- **Fully offline** after the first run — packages and model come from
  local caches.
- **One single Python file** — no `venv`, no `pip install`, no dependency
  tree to maintain. [uv](https://docs.astral.sh/uv/) runs it and fetches
  what it needs, exactly like `uvx`.
- **5 languages** — German, English, French, Spanish, Portuguese
  (one model per language; the language comes from the model name).
- **Archive included** — every run leaves a timestamped WAV in
  `~/text-to-sound-recordings/`.

## ⚠️ First run: accept the model license (30 seconds)

The Phonon 40m models are **gated** — the very first run stops and opens
the model page in your browser. **Look at the top of that page, right under
the title: confirm the button in the text flow** ("Agree and access
repository"). Then log in once:

```bash
uvx --from huggingface_hub hf auth login
```

Run the script again and it works. That's the only one-time setup.
(Each model has its own license — accepting `phonon-40m-de` does **not**
unlock `phonon-40m-en`. Accept each language you want to use.)

*No account?* The English-only model `gradium/phonon-31m-en` is
**Apache 2.0 and ungated** — no login needed (see `--model` below).

**Never used a terminal?** Open `START-HERE.txt` in this folder — it walks
you through it, or double-click `start.sh`.

## Requirements

| What | Why |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | runs the script and fetches `ptts` + `numpy` |
| `mpv` | playback window |
| `xclip` (X11) or `wl-clipboard` (Wayland) | reads the clipboard |
| A Hugging Face account | the 40m models are *gated* (CC BY-NC 4.0) |

### Install the dependencies

**Arch Linux / Manjaro / EndeavourOS**

```bash
sudo pacman -S uv mpv xclip
```

**Fedora**

```bash
sudo dnf install uv mpv xclip
```

**Ubuntu / Debian** (no `uv` package in the archive — use the official installer)

```bash
sudo apt install mpv xclip
curl -LsSf https://astral.sh/uv/install.sh | sh
# restart the shell, then: uv --version
```

**openSUSE**

```bash
sudo zypper install mpv xclip
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Any other distribution:** install `mpv` and a clipboard tool with your
package manager, then `uv` via the
[standalone installer](https://docs.astral.sh/uv/getting-started/installation/).

> Wayland instead of X11? Install `wl-clipboard` instead of `xclip`
> (the script tries both automatically).

## Run it

```bash
# select text, copy it (Ctrl+C), then:
uv run speechflow-start.py
```

On the **first run** ~80 MB are downloaded once (packages + model, q8) —
after that everything runs offline. The finished WAV lands in
`~/text-to-sound-recordings/`, e.g. `2026-11-07_00-09-11_de.wav`.

Or use the helpers: `./start.sh` (terminal) · `START-HERE.txt` (guided) ·
desktop entry below (one click).

## Languages

The language is **derived from the model name** — no language setting
needed. Uncomment exactly one model in `speechflow.conf`:

```ini
MODEL=hf://gradium/phonon-40m-de    # German
#MODEL=hf://gradium/phonon-40m-en   # English
#MODEL=hf://gradium/phonon-40m-fr   # French
#MODEL=hf://gradium/phonon-40m-es   # Spanish
#MODEL=hf://gradium/phonon-40m-pt   # Portuguese
```

`phonon-40m-en` → `en`, `phonon-40m-fr` → `fr`, and so on — the archive
filename uses the same code (`…_en.wav`).

> **One model = one language.** A single model covers exactly one
> language (the model that would handle all five at once did not work
> reliably and is therefore not offered). Switch languages by
> uncommenting a different `MODEL=` line — each model you activate for
> the first time needs its own license acceptance (see above).

Other languages (Arabic, Hindi, Japanese, …) are listed in gradium's
[model overview](https://github.com/gradium-ai/xn-ptts#model-setup) —
pass any of them via `--model hf://…`.

## Voices

```bash
uvx ptts --list-voices
```

By default each model uses its own voice, matched to the language. Set a
different voice in `speechflow.conf`, e.g.:

```ini
VOICE=Harper
```

or per run: `uv run speechflow-start.py --voice Harper "Hello there."`
**Pick a voice that matches the language** — German voices read French
text poorly.

> **Exactly one `VOICE=` line active at most** (or none = model default).
> If several are uncommented, SpeechFlow warns you and keeps going with
> the **last active** line.

## More options

```bash
uv run speechflow-start.py "Start with text directly"   # instead of clipboard
uv run speechflow-start.py --no-mpv                     # only archive, no playback
uv run speechflow-start.py --model hf://gradium/phonon-31m-en   # ungated English model
```

mpv keyboard shortcuts work as usual (pause with Space, quit with `q`).
The archive file survives closing the window — replay it any time:

```bash
mpv ~/text-to-sound-recordings/2026-11-07_00-09-11_de.wav
```

## Configuration (`speechflow.conf`)

The config is hashtag-style: **uncomment (remove `#`) exactly one
`MODEL=` line and at most one `VOICE=` line.** Everything else stays
commented. If several `MODEL=` or `VOICE=` lines are active, SpeechFlow
prints a warning and continues with the **last active** entry.

| Key | Default | Meaning |
|---|---|---|
| `MODEL` | `hf://gradium/phonon-40m-de` | the model — also determines the language |
| `VOICE` | empty | empty = model's default voice for the language |
| `QUANT` | `q8` | `q8` (small/fast) or `f32` (more precise) |
| `ARCHIVE_DIR` | `~/text-to-sound-recordings` | folder for the WAV archive files |

## Desktop entry (optional)

One click instead of a terminal — copy `speechflow.desktop` and adjust the
`Exec=` path to where your `speechflow-start.py` lives:

```bash
cp speechflow.desktop ~/.local/share/applications/
# edit Exec= in the copied file, then:
update-desktop-database ~/.local/share/applications/
```

Select text → copy → click the icon → listening starts.

## How it works

```
Clipboard → ONE tts.stream() over the whole text
               ├── PCM frames → FIFO → mpv (starts immediately)
               └── PCM frames → WAV file (archive, written in parallel)
```

Design decisions, for transparency:

- **Single-pass streaming, not per-sentence chunks.** The whole text runs
  in one `stream()` call — the same approach as the official `ptts` CLI.
  Synthesizing sentence by sentence resets the prosody context for every
  sentence and makes the delivery sound clipped.
- **No artificial sentence pauses.** The engine inserts natural gaps.
- **No waiting.** Because audio streams, playback starts at once — unlike
  a plain `uvx ptts "…" -o out.wav`, which renders the whole file first
  (~2× realtime, i.e. ~2.5 minutes of waiting for a 5-minute text).
- **Plain-CLI alternative:** for simple one-off recordings without any
  script, `uvx ptts` works too — but the
  [ptts CLI](https://github.com/gradium-ai/xn-ptts#cli) has no streaming
  output.
- **Browser variant:** [phonon-tts (npm)](https://www.npmjs.com/package/phonon-tts)
  is even lighter (0 dependencies, millisecond startup) but needs an HTML
  page and cannot load *gated* models without a local delivery service.
  This project is deliberately the desktop variant with an mpv window and
  clipboard workflow.

## License

The code in this repository is **MIT OR Apache-2.0**, at your option
(see [NOTICE](NOTICE)).

**Model weights and voices are distributed separately and have their own
terms.** Phonon 31m is under Apache 2.0, and the Phonon 40m models are
under CC BY-NC 4.0 (non-commercial use only). Check each
model's page on Hugging Face before redistribution. Details:
[gradium-ai/xn-ptts](https://github.com/gradium-ai/xn-ptts#license).

---

**Deutsch:** [README.de.md](README.de.md)
