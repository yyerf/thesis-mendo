"""STT + Multilingual Symptom Spotting (POC)

✅ BEST APPROACH FOR MIXED LANGUAGES (Taglish / Bislish / Conyo)

Instead of guessing the language, we do:
  "What symptoms can I detect from this sentence, regardless of language?"

Pipeline:
1) Speech -> Text (Whisper / Google SpeechRecognition)
2) Text -> Symptom spotting (simple language-agnostic rules)

Example:
  "Grabe I’m coughing since yesterday tapos masakit ulo ko"
Output:
  transcription: grabe i'm coughing since yesterday tapos masakit ulo ko
  symptoms: cough, headache

This is intentionally simple so you can test quickly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from mendo_core.symptom_models import RuleRegexModel, available_models, get_model, normalize_text


# -----------------------------
# Symptom spotting (rules)
# -----------------------------

@dataclass
class SymptomHit:
    symptom: str
    matches: List[str]


def spot_symptoms(text: str, model_id: str = "rules") -> List[SymptomHit]:
    """Return detected symptoms using the selected model.

    Note: for now, only regex-based models expose match details.
    """
    model = get_model(model_id)
    if isinstance(model, RuleRegexModel):
        return model.spot(text)
    # Fallback shape for non-regex models (kept for future expansion)
    return [SymptomHit(symptom=s, matches=[]) for s in sorted(model.predict(text))]


# -----------------------------
# Speech-to-text (optional)
# -----------------------------

def transcribe_audio(audio_path: str, backend: str = "auto") -> str:
    """Transcribe audio to text.

    backends:
      - auto: try whisper, fallback to speech_recognition
      - whisper: requires `pip install openai-whisper` + ffmpeg
      - google: requires `pip install SpeechRecognition pydub` + ffmpeg; uses Google Web Speech API
    """

    if backend not in {"auto", "whisper", "google"}:
        raise ValueError("backend must be one of: auto, whisper, google")

    if backend in {"auto", "whisper"}:
        try:
            import whisper  # type: ignore

            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return (result.get("text") or "").strip()
        except Exception:
            if backend == "whisper":
                raise

    # fallback: speech_recognition + (optional) pydub conversion
    try:
        import speech_recognition as sr  # type: ignore
    except ImportError as e:
        raise RuntimeError("SpeechRecognition not installed. Try whisper or install SpeechRecognition.") from e

    recognizer = sr.Recognizer()

    # SpeechRecognition works best with WAV; convert if needed
    wav_path = audio_path
    cleanup_wav = False

    ext = os.path.splitext(audio_path)[1].lower()
    if ext not in {".wav", ".aiff", ".aif", ".flac"}:
        try:
            from pydub import AudioSegment  # type: ignore

            wav_path = "_temp_stt.wav"
            sound = AudioSegment.from_file(audio_path)
            sound.export(wav_path, format="wav")
            cleanup_wav = True
        except ImportError as e:
            raise RuntimeError("pydub not installed for conversion. Provide a WAV file or install pydub + ffmpeg.") from e

    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data)
    finally:
        if cleanup_wav and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass


# -----------------------------
# CLI
# -----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="STT + Taglish symptom spotting (POC)")
    parser.add_argument("--audio", type=str, help="Path to audio file (wav/mp3/webm/etc)")
    parser.add_argument("--text", type=str, help="Skip STT and analyze this text")
    parser.add_argument("--backend", type=str, default="auto", help="auto | whisper | google")
    parser.add_argument(
        "--model",
        type=str,
        default="rules",
        help=f"Symptom model id (available: {', '.join(available_models())})",
    )
    parser.add_argument("--json", action="store_true", help="Print output as JSON")

    args = parser.parse_args()

    if not args.audio and not args.text:
        parser.error("Provide --audio or --text")

    if args.text:
        transcript = args.text
    else:
        transcript = transcribe_audio(args.audio, backend=args.backend)

    hits = spot_symptoms(transcript, model_id=args.model)

    output = {
        "transcript": transcript,
        "normalized": normalize_text(transcript),
        "model": args.model,
        "symptoms": [h.symptom for h in hits],
        "details": [{"symptom": h.symptom, "matches": h.matches} for h in hits],
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("TRANSCRIPT:")
        print(transcript)
        print("\nDETECTED SYMPTOMS:")
        if output["symptoms"]:
            for s in output["symptoms"]:
                print(f"- {s}")
        else:
            print("(none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
