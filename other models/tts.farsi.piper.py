import wave
from piper import PiperVoice

voice = PiperVoice.load("fa_IR-gyro-medium.onnx", config_path="fa_IR-gyro-medium.onnx.json")

text = "در حال حاضر فروش محصولات خانگی در افتِ ماهیانه است"

with wave.open("output.wav", "wb") as wav_file:
    voice.synthesize_wav(text, wav_file)

print("Saved output.wav")