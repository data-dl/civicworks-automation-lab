"""Spoken narration with a built-in Windows voice (no network, no account): text in, WAV file out."""

from __future__ import annotations

import asyncio
import wave
from pathlib import Path

VOICE = "Microsoft Mark"


async def _speak(text: str, rate: float) -> bytes:
    from winrt.windows.media.speechsynthesis import SpeechSynthesizer
    from winrt.windows.storage.streams import DataReader

    synth = SpeechSynthesizer()
    for v in SpeechSynthesizer.all_voices:
        if v.display_name == VOICE:
            synth.voice = v
    synth.options.speaking_rate = rate
    synth.options.audio_pitch = 1.0
    stream = await synth.synthesize_text_to_stream_async(text)
    reader = DataReader(stream.get_input_stream_at(0))
    await reader.load_async(stream.size)
    buf = bytearray(stream.size)
    reader.read_bytes(buf)
    return bytes(buf)


def speak(text: str, out: Path, rate: float = 0.96) -> float:
    """Write a WAV of `text`; return its length in seconds."""
    data = asyncio.run(_speak(text, rate))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    with wave.open(str(out)) as w:
        return w.getnframes() / w.getframerate()


if __name__ == "__main__":
    import sys

    print(speak(" ".join(sys.argv[2:]), Path(sys.argv[1])))
