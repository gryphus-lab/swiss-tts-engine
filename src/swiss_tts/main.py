# src/swiss_tts/main.py
import os
import re
import numpy as np
import soundfile as sf
import torch
from espnet_model_zoo.downloader import ModelDownloader
from espnet2.bin.tts_inference import Text2Speech
from swiss_tts import config

import warnings

# Suppress Python syntax/deprecation warnings from third-party libraries
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Suppress internal PyTorch or framework logs if desired
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class SwissTTSEngine:
    def __init__(self):
        print("Initializing ESPnet Swiss German Speech Engine via uv/mise...")
        self.downloader = ModelDownloader()
        self.model_config = self.downloader.download_and_unpack(config.MODEL_NAME)

        self.text2speech = Text2Speech(
            train_config=self.model_config["train_config"],
            model_file=self.model_config["model_file"],
            device="cpu",
        )
        self.sample_rate = self.text2speech.tts.fs

        self.kwargs = {}
        if self.text2speech.use_spembs:
            if hasattr(self.text2speech.tts, "spk_embed_dim"):
                self.kwargs["spembs"] = torch.zeros(self.text2speech.tts.spk_embed_dim)
            elif "spembs" in self.model_config:
                self.kwargs["spembs"] = self.model_config["spembs"]

    def generate_dialect_speech(self, text: str, dialect_name: str):
        sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if s.strip()]
        all_audio_chunks = []

        print(f"\nProcessing {dialect_name.upper()} text...")
        for i, sentence in enumerate(sentences, 1):
            with torch.no_grad():
                outputs = self.text2speech(sentence, **self.kwargs)
                all_audio_chunks.append(outputs["wav"].numpy())

                silence = np.zeros(
                    int(self.sample_rate * config.DEFAULT_SILENCE_DURATION)
                )
                all_audio_chunks.append(silence)

        final_audio = np.concatenate(all_audio_chunks)
        os.makedirs("audio_output", exist_ok=True)
        output_filename = f"audio_output/{dialect_name}_speech.wav"
        sf.write(output_filename, final_audio, self.sample_rate)
        print(f"✓ Saved: {output_filename}")


def run():
    engine = SwissTTSEngine()
    for dialect, dialect_text in config.DEFAULT_TEXTS.items():
        engine.generate_dialect_speech(dialect_text, dialect)


if __name__ == "__main__":
    run()
