"""Measure real transcription latency and word error rate on one sample.

Run from Dev/Backend with OPENAI_API_KEY set:
python -m scripts.benchmark_stt --audio recording.webm --reference "spoken words"
Without --audio, a synthetic TTS recording of the reference is used as a smoke test.
"""

import argparse
import re
from pathlib import Path
from time import perf_counter

from app.adapters.speech.client import OpenAISpeechToText, OpenAITextToSpeech
from app.config import settings


def word_error_rate(reference: str, transcript: str) -> float:
    expected = re.findall(r"\w+", reference.lower())
    actual = re.findall(r"\w+", transcript.lower())
    if not expected:
        raise ValueError("Reference text must contain words")
    distances = list(range(len(actual) + 1))
    for row, word in enumerate(expected, start=1):
        next_distances = [row]
        for column, candidate in enumerate(actual, start=1):
            next_distances.append(
                min(
                    distances[column] + 1,
                    next_distances[column - 1] + 1,
                    distances[column - 1] + (word != candidate),
                )
            )
        distances = next_distances
    return distances[-1] / len(expected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path)
    parser.add_argument(
        "--reference", default="Please book an appointment with Dr. Chen next Tuesday"
    )
    parser.add_argument("--language", choices=("en", "es"), default="en")
    parser.add_argument("--model", default=settings.openai_stt_model)
    args = parser.parse_args()
    if not settings.openai_api_key:
        parser.error("OPENAI_API_KEY is required")
    if args.audio:
        audio = args.audio.read_bytes()
        filename = args.audio.name
    else:
        audio = OpenAITextToSpeech(
            settings.openai_api_key, settings.openai_tts_model, settings.openai_tts_voice
        ).synthesize(args.reference)
        filename = "synthetic.mp3"
    recognizer = OpenAISpeechToText(settings.openai_api_key, args.model)
    start = perf_counter()
    transcript = recognizer.transcribe(audio, filename, language=args.language)
    seconds = perf_counter() - start
    print(f"Transcript: {transcript}")
    print(f"Transcription latency: {seconds:.3f} s")
    print(f"Word error rate: {word_error_rate(args.reference, transcript):.1%}")


if __name__ == "__main__":
    main()
