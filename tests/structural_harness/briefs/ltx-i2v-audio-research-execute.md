# Add custom voice input to the LTX image-to-video workflow

Start from the ready LTX image-to-video workflow `video/ltx2_3_i2v`.

I want the generated character to speak from an audio clip I provide. Please add
a voice/audio input path and wire it into the LTX/RuneXX custom-audio or lipsync
style flow so the implementation uses the relevant workflow lessons instead of
guessing a generic audio node.

Research should find the LTX/RuneXX custom-audio template source as Python, then
the implementation should actually use that research context to modify the
workflow. The result needs a structural audio input or audio-related node in the
compiled workflow evidence.
