import edge_tts, asyncio

VOICE = "fa-IR-DilaraNeural"
TEXT = "در حال حاضر فروش محصولات خانگی در افتِ ماهیانه است"

async def synth(text, outfile, rate="+0%", pitch="+0Hz"):
    c = edge_tts.Communicate(text, voice=VOICE, rate=rate, pitch=pitch)
    await c.save(outfile)
    print(f"Saved {outfile}")

async def main():
    await synth(TEXT, "neutral.mp3")
    await synth(TEXT, "warm.mp3",   rate="-8%",  pitch="-10Hz")
    await synth(TEXT, "bright.mp3", rate="+8%",  pitch="+12Hz")

asyncio.run(main())