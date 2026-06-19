# src/swiss_tts/main.py
import os
import re
import warnings
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
    def __init__(self, model_name: str = config.MODEL_NAME):
        """
        Initialize the Swiss TTS engine with the specified model.
        
        Downloads the model for speech synthesis and prepares speaker embeddings if required.
        
        Parameters:
            model_name (str): Name of the ESPnet model to download and configure.
        """
        print(f"Initializing ESPnet Speech Engine using model: {model_name}...")
        self.downloader = ModelDownloader()
        self.model_config = self.downloader.download_and_unpack(model_name)
        
        self.text2speech = Text2Speech(
            train_config=self.model_config["train_config"],
            model_file=self.model_config["model_file"],
            device="cpu"
        )
        self.sample_rate = self.text2speech.tts.fs
        
        # Provision speaker embeddings dynamically if the model demands them
        self.kwargs = {}
        if self.text2speech.use_spembs:
            if hasattr(self.text2speech.tts, "spk_embed_dim"):
                self.kwargs["spembs"] = torch.zeros(self.text2speech.tts.spk_embed_dim)
            elif "spembs" in self.model_config:
                self.kwargs["spembs"] = self.model_config["spembs"]

    def generate_dialect_speech(
        self, 
        text: str, 
        dialect_name: str, 
        silence_duration: float = config.DEFAULT_SILENCE_DURATION,
        output_dir: str = "audio_output"
    ) -> str:
        """
        Generate and save speech audio for text in a specified dialect.
        
        Splits the input text into sentences, synthesizes speech for each sentence,
        inserts silence padding between sentences, and saves the concatenated audio as a WAV file.
        
        Returns:
            Path to the generated WAV file.
        """
        # Split input parameter text into clean sentence arrays
        sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if s.strip()]
        all_audio_chunks = []
        
        print(f"\nProcessing {dialect_name.upper()} text sequence ({len(sentences)} sentences)...")
        for i, sentence in enumerate(sentences, 1):
            with torch.no_grad():
                outputs = self.text2speech(sentence, **self.kwargs)
                all_audio_chunks.append(outputs["wav"].numpy())
                
                # Dynamic pause duration padding between speech tokens
                silence = np.zeros(int(self.sample_rate * silence_duration))
                all_audio_chunks.append(silence)
                
        # Concatenate audio chunks
        final_audio = np.concatenate(all_audio_chunks)
        os.makedirs(output_dir, exist_ok=True)
        
        output_filename = os.path.join(output_dir, f"{dialect_name}_speech.wav")
        sf.write(output_filename, final_audio, self.sample_rate)
        print(f"✓ Saved audio output asset to: {output_filename}")
        return output_filename

def run():
    """
    Generate speech audio files for Swiss dialects using custom text and configuration fallback texts.
    
    Initializes a TTS engine and generates audio outputs for a custom Zurich dialect sample, then batch-processes multiple dialects from the default fallback text configuration.
    """
    engine = SwissTTSEngine()
    
    # Example 1: Running with dynamic text custom passed via local params
    custom_zuri_text = "Sali! Das isch en ganz neue, dynaamische Text im Züri Dialäkt."
    engine.generate_dialect_speech(
        text=custom_zuri_text, 
        dialect_name="zurich_custom", 
        silence_duration=0.3
    )
    
    # Example 2: Looping through default settings mapped via the updated config layer
    print("\n--- Running Fallback Config Batch Processing ---")
    for dialect, fallback_text in config.DEFAULT_FALLBACK_TEXTS.items():
        engine.generate_dialect_speech(text=fallback_text, dialect_name=dialect)

if __name__ == "__main__":
    run()
