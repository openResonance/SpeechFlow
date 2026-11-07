#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ptts", "numpy"]
# ///
"""speechflow-start.py – Text offline vorlesen mit Phonon TTS (5 Sprachen).

Aufruf (ohne venv, uv holt sich alles selbst):
    uv run speechflow-start.py           # Text aus der Zwischenablage
    uv run speechflow-start.py "Hallo"   # Text direkt mitgeben
    uv run speechflow-start.py --lang en --voice "" "Hello there."
    uv run speechflow-start.py --no-mpv  # nur WAV archivieren

Der ganze Text wird in EINEM stream() durchlaufen (natürlicher Sprachfluss,
kein Satz-für-Sat-Reset). Die PCM-Frames gehen gleichzeitig an mpv (über
eine FIFO-Pipe, Wiedergabe startet sofort) und an eine Archiv-WAV-Datei.
Einstellungen: speechflow.conf neben diesem Skript.
Basis: https://github.com/gradium-ai/xn-ptts (ptts-Python-Paket)
"""

import argparse
import errno
import os
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONF_FILE = SCRIPT_DIR / "speechflow.conf"

# Einzelsprach-Modelle (gated, CC BY-NC 4.0 – HF-Login nötig)
MODEL_BY_LANG = {
    "de": "hf://gradium/phonon-40m-de",
    "en": "hf://gradium/phonon-40m-en",
    "fr": "hf://gradium/phonon-40m-fr",
    "es": "hf://gradium/phonon-40m-es",
    "pt": "hf://gradium/phonon-40m-pt",
}
# Alternative: ein Modell für alle 5 Sprachen (in speechflow.conf einstellen):
#   MODEL=hf://gradium/phonon-40m-multilingual

DEFAULTS = {
    "LANG": "de",
    "MODEL": "",
    "VOICE": "",
    "QUANT": "q8",
    "ARCHIVE_DIR": "~/text-to-sound-recordings",
}


def load_conf():
    """liest speechflow.conf (KEY=VALUE); fehlt sie, gelten die DEFAULTS."""
    cfg = dict(DEFAULTS)
    if CONF_FILE.exists():
        for line in CONF_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = (p.strip() for p in line.split("=", 1))
            if key in cfg:
                cfg[key] = val
    return cfg


def read_clipboard():
    """liest die Zwischenablage (Wayland oder X11). None = kein Werkzeug."""
    cmds = []
    if os.environ.get("WAYLAND_DISPLAY"):
        cmds.append(["wl-paste", "--no-newline"])
    cmds += [
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
        ["wl-paste", "--no-newline"],
    ]
    for cmd in cmds:
        if not shutil.which(cmd[0]):
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return r.stdout
    return None


def notify(msg):
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "--app-name=SpeechFlow", "SpeechFlow", str(msg)],
            capture_output=True,
        )


def is_gated_error(err):
    """True, wenn Hugging Face den Zugang zum Modell verweigert (gated)."""
    msg = str(err).lower()
    return any(k in msg for k in (
        "gatedrepo", "gated repo", "forbidden", "authorized list",
        "access to model", "401", "restricted",
    ))


def model_page_url(model):
    """hf://owner/name -> https://huggingface.co/owner/name"""
    if model.startswith("hf://"):
        return "https://huggingface.co/" + model[len("hf://"):].split("@")[0]
    return None


def report_gated(model, err):
    """Modellseite im Browser öffnen + freundliche Meldung ausgeben."""
    url = model_page_url(model)
    print("\n🔐🌐📖  Das Modell ist geschützt (gated) – einmalig freischalten:")
    if url:
        print(f"   1. Im Browser öffnet sich: {url}")
        print("   2. Oben unter der Überschrift den Button bestätigen "
              "(\"Agree and access repository\").")
        print("   3. Einloggen:  uvx --from huggingface_hub hf auth login")
        print("   4. Danach dieses Skript einfach erneut starten.\n")
        if shutil.which("xdg-open"):
            try:
                subprocess.Popen(["xdg-open", url],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            except OSError:
                pass
    else:
        print(f"   Modell freischalten: {url or model}\n")
    notify("Log in to Hugging Face and accept the license of your "
           "Phonon model (button at the top of its page), then start "
           "again. Read the README.")


def wav_header(sample_rate, data_size):
    """WAV-Header; data_size groß gewählt, weil die Länge erst am Ende steht."""
    byte_rate = sample_rate * 2
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, byte_rate, 2, 16,
        b"data", data_size,
    )


def parse_args():
    p = argparse.ArgumentParser(
        description="Text offline vorlesen (Phonon TTS, über uv run).")
    p.add_argument("text", nargs="?",
                   help="Vorzulesender Text (Standard: Zwischenablage)")
    p.add_argument("--lang", choices=sorted(MODEL_BY_LANG),
                   help="Sprache (überschreibt LANG aus der conf)")
    p.add_argument("--model", metavar="REPO",
                   help="Modell überschreiben, z.B. "
                        "hf://gradium/phonon-40m-multilingual")
    p.add_argument("--voice", metavar="NAME",
                   help="Stimme, z.B. Nele (leerer String = Modell-Standard)")
    p.add_argument("--no-mpv", action="store_true",
                   help="nur WAV archivieren, nicht abspielen")
    return p.parse_args()


def resolve_text(args):
    if args.text is not None and args.text.strip():
        return args.text
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    cb = read_clipboard()
    if cb and cb.strip():
        return cb
    if cb is None:
        msg = ("Kein Clipboard-Werkzeug gefunden – "
               "xclip (X11) oder wl-clipboard (Wayland) installieren.")
    else:
        msg = "Die Zwischenablage ist leer."
    print(msg, file=sys.stderr)
    notify(msg)
    sys.exit(1)


def synthesize(tts, text, voice, archive, use_mpv):
    """Ein stream() über den ganzen Text -> mpv-FIFO + Archiv-WAV."""
    import numpy as np

    fifo = Path(f"/tmp/phonon-vorlesen-{os.getpid()}.pcm")
    proc = None
    fifo_out = None
    wf = None
    created_fifo = False
    n = 0
    samples = 0
    sr = 24000
    success = False

    try:
        if use_mpv:
            fifo.unlink(missing_ok=True)
            os.mkfifo(fifo)
            created_fifo = True
            proc = subprocess.Popen(
                ["mpv", "--force-window=yes", "--keep-open=yes",
                 "--title=SpeechFlow", str(fifo)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            # O_RDWR: öffnet blockierungsfrei, auch wenn mpv noch startet
            fifo_out = os.fdopen(os.open(fifo, os.O_RDWR), "wb")

        with tts.stream(text, voice=voice) as audio:
            sr = audio.sample_rate
            wf = wave.open(str(archive), "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            if fifo_out:
                fifo_out.write(wav_header(sr, 0x7FFFFFFF))
                fifo_out.flush()
            for pcm in audio:
                a = np.clip(np.asarray(pcm, dtype=np.float32), -1.0, 1.0)
                raw = (a * 32767).astype(np.int16).tobytes()
                wf.writeframes(raw)
                if fifo_out:
                    fifo_out.write(raw)
                n += 1
                samples += len(raw) // 2
                if n % 100 == 0:
                    print(f"\r  ... {n} Frames ({samples // sr} s Audio)",
                          end="", flush=True)
        success = True
        print(f"\r  ... {n} Frames ({samples // sr} s Audio)            ")
    except BrokenPipeError:
        print("\n  mpv wurde geschlossen – Synthese abgebrochen.")
        success = True   # so, als wäre es sauber (Archiv bleibt teilweise gültig)
    except OSError as e:
        if e.errno == errno.EPIPE:
            print("\n  mpv wurde geschlossen – Synthese abgebrochen.")
            success = True
        else:
            raise
    finally:
        if wf is not None:
            wf.close()
        if fifo_out is not None:
            fifo_out.close()
        if created_fifo:
            fifo.unlink(missing_ok=True)
        if proc is not None and not success:
            proc.terminate()

    if success and n:
        print(f"Fertig: {samples / sr:.1f} s Audio → {archive}")
    if use_mpv and success:
        print("mpv-Fenster bleibt offen (schließen mit q). "
              "Neu anhören: Archivdatei abspielen.")


def main():
    args = parse_args()
    cfg = load_conf()
    text = resolve_text(args)

    lang = args.lang or cfg["LANG"]
    model = args.model or cfg["MODEL"] or MODEL_BY_LANG.get(lang)
    if not model:
        print(f"FEHLER: unbekannte Sprache {lang!r} und kein MODEL gesetzt. "
              f"Verfügbar: {', '.join(sorted(MODEL_BY_LANG))}",
              file=sys.stderr)
        sys.exit(1)
    if args.voice is not None:
        voice = args.voice or None      # --voice "" = Modell-Standard
    else:
        voice = cfg["VOICE"] or None
        if voice and args.lang and args.lang != cfg["LANG"]:
            print(f"Hinweis: Stimme {voice!r} stammt aus der conf und ist "
                  f"für Sprache {args.lang!r} evtl. nicht passend. "
                  f"Besser: --voice NAME oder VOICE= leer lassen.",
                  file=sys.stderr)

    archive_dir = Path(cfg["ARCHIVE_DIR"]).expanduser()
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{lang}.wav"

    print(f"Modell:  {model}")
    print(f"Sprache: {lang}   Stimme: {voice or '(Modell-Standard)'}")
    print("Beim ersten Lauf werden Modell und Stimmen geladen (~80 MB).")
    import ptts
    try:
        tts = ptts.TTS(model, lang=lang, quant=cfg["QUANT"])
    except Exception as e:
        if is_gated_error(e):
            report_gated(model, e)
            sys.exit(1)
        raise
    print(f"Archiv:  {archive}")
    synthesize(tts, text, voice, archive, use_mpv=not args.no_mpv)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 – Desktop startet ohne Terminal
        print(f"FEHLER: {e}", file=sys.stderr)
        notify(f"Vorlesen fehlgeschlagen: {e}")
        sys.exit(1)
