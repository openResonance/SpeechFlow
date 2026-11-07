# SpeechFlow

**Text to Speech: Offline. Lightweight. Private.**
**Text vorlesen: Offline. Leichtgewichtig. Privat.**

Text markieren, in die Zwischenablage kopieren, einen Klick (oder einen
Befehl) – und [Phonon TTS](https://github.com/gradium-ai/xn-ptts) liest ihn
in einem Fenster vor, das man pausieren und steuern kann. Während des
Hörens entsteht parallel eine WAV-Archivdatei – jede Aufnahme bleibt
jederzeit nachhörbar.

- **Startet sofort** – der ganze Text läuft in einem einzigen
  Streaming-Durchlauf, die Wiedergabe beginnt mit dem ersten Audio-Frame
  (kein Warten auf eine fertige Datei).
- **Komplett offline** nach dem ersten Lauf (Paket- und Modell-Cache).
- **Eine einzige Python-Datei** – kein `venv`, kein `pip install`, keine
  Abhängigkeiten zum Pflegen. [uv](https://docs.astral.sh/uv/) führt sie
  aus und holt sich alles selbst, genau wie `uvx`.
- **5 Sprachen** – Deutsch, Englisch, Französisch, Spanisch, Portugiesisch
  (Einzelmodelle oder ein multilinguales Modell).
- **Archiv inklusive** – jeder Lauf hinterlegt eine WAV mit Zeitstempel in
  `~/text-to-sound-recordings/`.

## ⚠️ Erster Start: Modell-Lizenz akzeptieren (30 Sekunden)

Die Phonon-40m-Modelle sind **geschützt (gated)** – der allererste Lauf
stoppt und öffnet die Modellseite im Browser. **Oben auf der Seite, direkt
unter der Überschrift, den Button im Textfluss bestätigen** („Agree and
access repository"). Dann einmalig einloggen:

```bash
uvx --from huggingface_hub hf auth login
```

Danach das Skript einfach erneut starten – das war die einzige
Einrichtung. (Jedes Modell hat eine **eigene** Lizenz – die Freigabe von
`phonon-40m-de` gilt **nicht** für `phonon-40m-en`. Für jede gewünschte
Sprache einmal den Button auf der jeweiligen Modellseite bestätigen.)

*Kein Konto?* Das reine Englisch-Modell `gradium/phonon-31m-en` ist
**Apache 2.0 und ungated** – kein Login nötig (siehe `--model` unten).

**Noch nie ein Terminal benutzt?** `START-HERE.txt` in diesem Ordner
öffnen – da steht alles Schritt für Schritt. Oder `start.sh` doppelklicken.

## Voraussetzungen

| Was | Warum |
|---|---|
| [`uv`](https://docs.astral.sh/uv/) | führt das Skript aus und holt sich `ptts` + `numpy` |
| `mpv` | Wiedergabe-Fenster |
| `xclip` (X11) oder `wl-clipboard` (Wayland) | Zwischenablage auslesen |
| Hugging-Face-Konto | die 40m-Modelle sind *gated* (CC BY-NC 4.0) |

### Abhängigkeiten installieren

**Arch Linux / Manjaro / EndeavourOS**

```bash
sudo pacman -S uv mpv xclip
```

**Fedora**

```bash
sudo dnf install uv mpv xclip
```

**Ubuntu / Debian** (kein `uv`-Paket im Archiv – offizieller Installer)

```bash
sudo apt install mpv xclip
curl -LsSf https://astral.sh/uv/install.sh | sh
# Shell neu starten, dann: uv --version
```

**openSUSE**

```bash
sudo zypper install mpv xclip
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Andere Distributionen:** `mpv` und ein Clipboard-Werkzeug über den
eigenen Paketmanager, dann `uv` über den
[Standalone-Installer](https://docs.astral.sh/uv/getting-started/installation/).

> Wayland statt X11? Statt `xclip` `wl-clipboard` installieren
> (das Skript probiert automatisch beide).

## Starten

```bash
# Text markieren, kopieren (Strg+C), dann:
uv run speechflow-start.py
```

Beim **ersten Lauf** werden Pakete (~100 MB) und das Modell (~80 MB, q8)
geladen – danach läuft alles offline. Die fertige WAV-Datei landet in
`~/text-to-sound-recordings/`, z. B. `2026-11-07_00-09-11_de.wav`.

Oder die Helfer nutzen: `./start.sh` (Terminal) · `START-HERE.txt`
(Schritt-für-Schritt) · Desktop-Eintrag unten (ein Klick).

## Alle Sprachen

```bash
uv run speechflow-start.py --lang en        # Englisch
uv run speechflow-start.py --lang fr        # Französisch
uv run speechflow-start.py --lang es        # Spanisch
uv run speechflow-start.py --lang pt        # Portugiesisch
uv run speechflow-start.py --lang de        # Deutsch (Standard)
```

Je Sprache lädt `speechflow-start.py` das passende Modell
(`hf://gradium/phonon-40m-<lang>`). Alternativ **ein Modell für alle
fünf Sprachen** – in `speechflow.conf` einstellen:

```ini
MODEL=hf://gradium/phonon-40m-multilingual
```

Weitere Sprachen (Arabisch, Hindi, Japanisch …) stehen in der
[Modell-Übersicht von gradium](https://github.com/gradium-ai/xn-ptts#model-setup) –
per `--model hf://…` aufrufbar.

## Stimmen

```bash
uvx ptts --list-voices
```

Standard ist die zum Modell passende Standardstimme. Abweichende Stimme in
`speechflow.conf` eintragen, z. B.:

```ini
VOICE=Harper
```

oder pro Aufruf: `uv run speechflow-start.py --voice Harper "Hallo dort."`
**Die Stimme muss zur Sprache passen** – deutsche Stimmen lesen
französischen Text nicht sauber.

## Weitere Optionen

```bash
uv run speechflow-start.py "Direkt mit Text starten"   # statt Zwischenablage
uv run speechflow-start.py --no-mpv                     # nur archivieren, nicht abspielen
uv run speechflow-start.py --model hf://gradium/phonon-31m-en --lang en
```

Tastaturkürzel in mpv funktionieren normal (Pause mit Leertaste,
Schließen mit `q`). Die Archivdatei bleibt nach dem Schließen erhalten –
jederzeit neu abspielbar:

```bash
mpv ~/text-to-sound-recordings/2026-11-07_00-09-11_de.wav
```

## Konfiguration (`speechflow.conf`)

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `LANG` | `de` | Sprache (auch Normalisierung von Zahlen/Daten) |
| `MODEL` | leer | leer = Standardmodell der Sprache, z. B. `hf://gradium/phonon-40m-multilingual` |
| `VOICE` | leer | leer = passende Standardstimme des Modells |
| `QUANT` | `q8` | `q8` (klein/schnell) oder `f32` (genauer) |
| `ARCHIVE_DIR` | `~/text-to-sound-recordings` | Ordner für die WAV-Archivdateien |

## Desktop-Eintrag (optional)

Ein Klick statt Terminal – `speechflow.desktop` kopieren und den `Exec=`-Pfad
zur `speechflow-start.py` anpassen:

```bash
cp speechflow.desktop ~/.local/share/applications/
# Exec= in der kopierten Datei anpassen, dann:
update-desktop-database ~/.local/share/applications/
```

Text markieren → kopieren → Klick auf das Icon → Vorlesen startet.

## Architektur & Alternativen (Transparenz)

```
Zwischenablage → EIN tts.stream() über den ganzen Text
                    ├── PCM-Frames → FIFO → mpv (Start sofort)
                    └── PCM-Frames → WAV-Datei (Archiv, parallel)
```

Bewusste Entscheidungen:

- *Frame-Streaming statt Satz-Chunks:* Der ganze Text läuft in einem
  Durchlauf – dieselbe Methode wie die offizielle `ptts`-CLI. Satz-für-Satz
  setzt den Prosodie-Kontext pro Satz zurück und klingt abgeschnitten.
- *Keine künstlichen Satzpausen:* Die Engine setzt natürliche Lücken.
- *Keine Wartezeit:* Weil gestreamt wird, beginnt die Wiedergabe sofort –
  im Gegensatz zu einem reinen `uvx ptts "…" -o datei.wav`, das erst die
  ganze Datei schreibt (~2× Echtzeit, d. h. bei einem 5-Minuten-Text
  ~2,5 Minuten Wartezeit).
- *Reine CLI-Variante:* Für einfache Einmal-Aufnahmen ohne Skript geht
  `uvx ptts` auch – die [ptts-CLI](https://github.com/gradium-ai/xn-ptts#cli)
  kennt aber keine Streaming-Ausgabe.
- *Browser-/WASM-Variante:* [phonon-tts (npm)](https://www.npmjs.com/package/phonon-tts)
  ist noch leichter (0 Dependencies, Millisekunden-Start), braucht aber
  eine HTML-Seite und kann *gated* Modelle ohne lokalen Auslieferungsservice
  nicht laden. Dieses Skript ist bewusst die Desktop-Variante mit
  mpv-Fenster und Clipboard-Ablauf.

## Lizenz

Der Code in diesem Repository ist **MIT OR Apache-2.0**, nach Wahl
(see [LICENSE](LICENSE)).

**Modellgewichte und Stimmen werden separat verteilt und haben eigene
Bedingungen.** Phonon 31m steht unter Apache 2.0, Phonon 40m und
Phonon 40m multilingual unter CC BY-NC 4.0 (nur nicht-kommerziell).
Vor jeder Weiterverteilung die jeweilige Modellseite auf Hugging Face
prüfen. Details: [gradium-ai/xn-ptts](https://github.com/gradium-ai/xn-ptts#license).

---

**English:** [README.md](README.md)
