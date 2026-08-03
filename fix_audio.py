with open('tts_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Replace the part where audio_data is passed to TRT QA and STT QA
old_trt_part = 'types.Part.from_bytes(data=audio_data, mime_type="audio/wav")'
new_trt_part = 'types.Part.from_bytes(data=valid_wav_bytes, mime_type="audio/wav")'
content = content.replace(old_trt_part, new_trt_part)

old_stt_call = 'is_valid, stt_msg = self.qa_checker.check_audio_stt(audio_data, text)'
new_stt_call = 'is_valid, stt_msg = self.qa_checker.check_audio_stt(valid_wav_bytes, text)'
content = content.replace(old_stt_call, new_stt_call)

# Insert the valid_wav_bytes creation right after "if not is_retake and len(audio_data) > 0:"
insert_pattern = r'if not is_retake and len\(audio_data\) > 0:\s*print\("  -> Üretildi. Oto-Denetmen dinleyip hata kontrolü yapýyor..."\)'
replacement = """if not is_retake and len(audio_data) > 0:
                    print("  -> Üretildi. Oto-Denetmen dinleyip hata kontrolü yapýyor...")
                    import io
                    from pydub import AudioSegment
                    temp_seg = AudioSegment(data=audio_data, sample_width=2, frame_rate=24000, channels=1)
                    wav_io = io.BytesIO()
                    temp_seg.export(wav_io, format="wav")
                    valid_wav_bytes = wav_io.getvalue()"""

content = re.sub(insert_pattern, replacement, content)

with open('tts_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed QA audio bytes issue.')
