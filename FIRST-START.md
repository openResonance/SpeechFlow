# Welcome to SpeechFlow!

SpeechFlow is already prepared with an English model and the **Juniper** voice as its beginner-friendly default. The installer opens `speechflow.conf` so you can review or change this selection before your first start.

## 1. Connect to Hugging Face

The installer starts this login for you:

```bash
uvx --from huggingface_hub hf auth login
```

Follow the instructions in the terminal. If you do not have a Hugging Face account yet, create one for free at [huggingface.co](https://huggingface.co).

If you cancel the login, you can run the command above later.

## 2. Check your language and voice

Open `speechflow.conf` in your SpeechFlow folder. For the recommended default, these must be the only active model and voice entries:

```ini
MODEL=hf://gradium/phonon-40m-en
VOICE=Juniper
```

An active entry has no `#` in front of it. Make sure only one `MODEL=` and one `VOICE=` line are active, then save the file.

## 3. Accept the model license

Copy some text and launch **SpeechFlow** from your Linux application menu.

On the first start, the Hugging Face page for your selected model may open. Sign in, review the license and accept its terms. Then launch SpeechFlow again.

## 4. Let SpeechFlow download the model

SpeechFlow downloads the selected model automatically. A model is approximately 80 MB, although the exact size can vary. Additional Python packages may also be downloaded on the first start.

The download happens only once for each model. After that, the model remains available on your computer.

## 5. Add another language later

Choose the matching model and voice in `speechflow.conf`. Keep only one model and one voice active. A new model may require you to accept another license on Hugging Face and will be downloaded once.

## 6. Use SpeechFlow

Copy text to your clipboard and launch **SpeechFlow** from the application menu. After a few seconds, an mpv window opens and reads the text aloud. Speech generation can use your CPU heavily; that is normal.

Recordings are saved in:

```text
~/text-to-sound-recordings
```

That is it — enjoy listening!
