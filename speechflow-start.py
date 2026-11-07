#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ptts", "numpy"]
# ///
"""speechflow-start.py – Text offline vorlesen mit Phonon TTS (5 Sprachen).

Aufruf (ohne venv, uv holt sich alles selbst):
    uv run speechflow-start.py           # Text aus der Zwischenablage
    uv run speechflow-start.py "Hallo"   # Text direkt mitgeben
    uv run speechflow-start.py --no-mpv  # nur WAV archivieren

Sprache, Modell und Stimme kommen aus speechflow.conf – die Sprache
leitet das Skript automatisch aus dem Modellnamen ab (z.B. ...-de -> de).
Genau EIN Modell und höchstens EINE Stimme aktivieren (Raute entfernen).

Der ganze Text wird in EINEM stream() durchlaufen (natürlicher Sprachfluss,
kein Satz-für-Sat-Reset). Die PCM-Frames gehen gleichzeitig an mpv (über
eine FIFO-Pipe, Wiedergabe startet sofort) und an eine Archiv-WAV-Datei.
Basis: https://github.com/gradium-ai/xn-ptts (ptts-Python-Paket)
"""

import argparse
import errno
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CONF_FILE = SCRIPT_DIR / "speechflow.conf"
LOG_FILE = SCRIPT_DIR / "speechflow-last-run.log"
LOG_MAX_BYTES = 64 * 1024        # harte Grenze: 64 KB
LOG_KEEP_LINES = 200             # beim Kürzen übrig lassen


def log(msg):
    """Diagnose-Log: zeigt, wo der Lauf gestartet/abgebrochen ist.

    Die Datei ist auf LOG_MAX_BYTES begrenzt – beim Überschreiten werden
    die ältesten Zeilen verworfen, es wächst nie unbegrenzt.
    """
    try:
        if (LOG_FILE.exists()
                and LOG_FILE.stat().st_size > LOG_MAX_BYTES):
            old = LOG_FILE.read_text(encoding="utf-8",
                                     errors="replace").splitlines()
            LOG_FILE.write_text("\n".join(old[-LOG_KEEP_LINES:]) + "\n",
                                encoding="utf-8")
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H-%M-%S')} {msg}\n")
    except OSError:
        pass


# Sehr früh: beweist, dass das Skript überhaupt gestartet wurde.
log(f"Skript geladen (argv={sys.argv[1:]!r})")
# Zeilenweise Pufferung – Ausgabe erscheint sofort, auch in Pipes/Desktop.
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

DEFAULTS = {
    "MODEL": "",
    "VOICE": "",
    "QUANT": "q8",
    "ARCHIVE_DIR": "~/text-to-sound-recordings",
}


def load_conf():
    """liest speechflow.conf (KEY=VALUE); fehlt sie, gelten die DEFAULTS.

    MODEL und VOICE dürfen mehrfach aktiv vorkommen – alle aktiven
    Einträge werden gesammelt (cfg["MODELS"]/cfg["VOICES"]).
    """
    cfg = dict(DEFAULTS)
    cfg["MODELS"] = []
    cfg["VOICES"] = []
    if CONF_FILE.exists():
        for line in CONF_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = (p.strip() for p in line.split("=", 1))
            if not val:
                continue
            if key == "MODEL":
                cfg["MODELS"].append(val)
                cfg["MODEL"] = val
            elif key == "VOICE":
                cfg["VOICES"].append(val)
                cfg["VOICE"] = val
            elif key in cfg:
                cfg[key] = val
    return cfg


def last_active(values, plural, key):
    """Bei mehreren aktiven Einträgen warnen und den letzten verwenden."""
    if len(values) <= 1:
        return values[0] if values else ""
    log(f"Warnung: {len(values)} {plural} aktiv -> weiter mit {values[-1]!r}")
    print(f"\n⚠️  Achtung: {len(values)} {plural} aktiv in speechflow.conf:")
    for v in values:
        print(f"      - {v}")
    print(f"   → Not-Fallback: es läuft weiter mit dem letzten: {values[-1]}")
    print("   Entferne die Raute (#) vor allen anderen Zeilen, damit genau "
          f"EINE {key}-Zeile aktiv ist.\n")
    notify(f"Mehrere {plural} aktiv ({', '.join(values)}) – "
           f"weiter mit: {values[-1]}. In speechflow.conf nur EINE "
           f"{key}-Zeile aktiv lassen.")
    return values[-1]


def lang_from_model(model):
    """Modellname -> Sprachcode, z.B. hf://gradium/phonon-40m-de -> 'de'."""
    name = model.rstrip("/").split("/")[-1].split("@")[0]
    m = re.search(r"-([a-z]{2})$", name)
    return m.group(1) if m else None


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
    log(f"notify: {msg}")
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
    log(f"gated erkannt: {model} url={url} "
        f"xdg-open={'ja' if shutil.which('xdg-open') else 'FEHLT'}")
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
    p.add_argument("--model", metavar="REPO",
                   help="Modell überschreiben, z.B. "
                        "hf://gradium/phonon-40m-en")
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
        print(f"✅ Fertig: {samples / sr:.1f} s Audio → {archive}")
    if use_mpv and success:
        print("🔊 mpv-Fenster bleibt offen (schließen mit q). "
              "Neu anhören: Archivdatei abspielen.")


def main():
    args = parse_args()
    cfg = load_conf()
    log("Text wird ermittelt …")
    text = resolve_text(args)
    log(f"Text: {len(text)} Zeichen")

    model = args.model or last_active(cfg["MODELS"], "Modelle", "MODEL")
    if not model:
        print("FEHLER: kein MODEL in speechflow.conf aktiv "
              "(Raute vor EINER MODEL-Zeile entfernen).",
              file=sys.stderr)
        sys.exit(1)
    lang = lang_from_model(model)
    if not lang:
        print(f"FEHLER: Sprache aus Modellname {model!r} nicht ableitbar "
              "(z.B. ...-de, ...-en).", file=sys.stderr)
        sys.exit(1)
    if args.voice is not None:
        voice = args.voice or None      # --voice "" = Modell-Standard
    else:
        voice = last_active(cfg["VOICES"], "Stimmen", "VOICE") or None

    archive_dir = Path(cfg["ARCHIVE_DIR"]).expanduser()
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{lang}.wav"

    print("🎬 SpeechFlow – los geht's!")
    print(f"Modell:  {model}")
    print(f"Sprache: {lang}   Stimme: {voice or '(Modell-Standard)'}")
    print("⬇️  Beim ersten Lauf werden Modell und Stimmen geladen (~80 MB).")
    import ptts
    log("ptts.TTS wird erstellt …")
    try:
        tts = ptts.TTS(model, lang=lang, quant=cfg["QUANT"])
    except Exception as e:
        log(f"ptts.TTS Fehler: {type(e).__name__}: {e}")
        if is_gated_error(e):
            report_gated(model, e)
            sys.exit(1)
        raise
    log("ptts.TTS bereit – Synthese startet")
    print(f"Archiv:  {archive}")
    synthesize(tts, text, voice, archive, use_mpv=not args.no_mpv)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Abgebrochen (KeyboardInterrupt)")
        print("\nAbgebrochen.")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001 – Desktop startet ohne Terminal
        log(f"FEHLER (global): {type(e).__name__}: {e}")
        print(f"FEHLER: {e}", file=sys.stderr)
        notify(f"Vorlesen fehlgeschlagen: {e}")
        sys.exit(1)
