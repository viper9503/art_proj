import pygame
import random
import os
import sounddevice as sd
import numpy as np
import wave
import time
from threading import Thread, Lock
import pyaudio
import webrtcvad

# Function to record audio for a specified duration
def record_audio(filename, sample_rate=16000, chunk_duration_ms=30):
    vad = webrtcvad.Vad(1)  # Set aggressiveness from 0 to 3
    format = pyaudio.paInt16
    channels = 1
    chunk_size = int(sample_rate * chunk_duration_ms / 1000)

    audio = pyaudio.PyAudio()
    stream = audio.open(format=format, channels=channels, rate=sample_rate, input=True, frames_per_buffer=chunk_size)

    print("Listening for speech...")
    frames = []
    recording = False
    silence_counter = 0

    while True:
        frame = stream.read(chunk_size)
        is_speech = vad.is_speech(frame, sample_rate)

        if recording:
            frames.append(frame)
            if len(frames) >= int(10 * 1000 / chunk_duration_ms):  # 10 seconds of audio
                # Save the recording
                wf = wave.open(filename, 'wb')
                wf.setnchannels(channels)
                wf.setsampwidth(audio.get_sample_size(format))
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(frames))
                wf.close()

                print(f"Recording saved: {filename}")
                return  # Stop after saving one 10-second clip

        if is_speech:
            recording = True
            silence_counter = 0
        elif recording:
            # Increment silence counter if no speech detected
            silence_counter += 1
            if silence_counter > int(3 * 1000 / chunk_duration_ms):  # 3 seconds of silence
                recording = False
                frames.clear()

    stream.stop_stream()
    stream.close()
    audio.terminate()

# Function to play a random 3-5 second interval from an available file on a given channel with random volume
def play_random_interval_on_channel(channel, current_files, playback_lock):
    with playback_lock:
        # Filter out files that are currently being played on any channel
        available_files = [file for file in audio_files if file not in current_files.values()]
        if not available_files:
            return

    file_path = random.choice(available_files)
    sound = pygame.mixer.Sound(os.path.join(audio_files_dir, file_path))
    sound_length = sound.get_length()

    # Set start time to a random point within the audio clip's length
    start_time = random.uniform(0, max(sound_length - 5, 0))  # Ensure there's enough time for a 3-5 second clip
    duration = random.uniform(3, 5)  # Duration between 3 and 5 seconds
    volume = random.uniform(0.7, 1.0)  # Random volume adjustment between 70% and 100%

    # Adjust duration if it exceeds the available duration
    if start_time + duration > sound_length:
        duration = sound_length - start_time

    sound.set_volume(volume)  # Set the adjusted volume

    # Ensure that the end time does not exceed the audio clip's length
    end_time = min(start_time + duration, sound_length)

    # Play the specified interval
    sound.play()

    # Delay to allow playing only the specified interval
    pygame.time.delay(int(start_time * 1000))

    # Stop the playback after the interval duration
    pygame.time.delay(int((end_time - start_time) * 1000))
    sound.stop()

    with playback_lock:
        # Update the current file being played on this channel
        current_files[channel] = file_path

    return file_path  # Return the file being played

# Function to play tracks and record once simultaneously
def play_and_record(channel, recording_lock, current_files, playback_lock):
    while True:
        file = play_random_interval_on_channel(channel, current_files, playback_lock)
        if file:
            current_files[channel] = file

            # Try to acquire the lock to ensure only one thread records at a time
            if recording_lock.acquire(blocking=False):
                try:
                    new_file_name = os.path.join(audio_files_dir, f"recording_{int(time.time())}.wav")
                    record_audio(new_file_name)
                    audio_files.append(new_file_name)  # Add new recording to the playlist
                finally:
                    recording_lock.release()

# Initialize pygame and the mixer
pygame.mixer.init()

# Directory containing the audio files
audio_files_dir = "/home/pi/Desktop/art_proj/mp3clips"

# List all files in the directory
audio_files = os.listdir(audio_files_dir)

# Initialize three channels
channels = [pygame.mixer.Channel(i) for i in range(4)]

# Create a lock to control recording access
recording_lock = Lock()

# Create a new lock for playback
playback_lock = Lock()

# Dictionary to track which file is playing on each channel
current_files = {}

# Start threads as daemon threads to play tracks and record on each channel
threads = [Thread(target=play_and_record, args=(channel, recording_lock, current_files, playback_lock), daemon=True) for channel in channels]
for thread in threads:
    thread.start()

try:
    while True:
        pygame.time.Clock().tick(10)
except KeyboardInterrupt:
    print("Stopping...")
    pygame.quit()
