from bark import generate_audio, preload_models
from scipy.io.wavfile import write as write_wav
from pydub import AudioSegment, silence
import numpy as np
import os
import time
import random
import logging
from typing import List, Dict, Tuple, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Bark
logger.info("Preloading Bark models...")
preload_models()
logger.info("Bark models preloaded.")

# --- Configuration ---
VOICES = {
    "sandip": "voice_clone_of_sandip.npz",
    "yash": "voice_clone_of_yash.npz"
}

# Generation parameters
TEXT_TEMP = 0.65
WAVEFORM_TEMP = 0.65

# Extended conversation for 5 minutes
BASE_SCRIPT = [
    {"speaker": "sandip", "text": "Hey Yash, I was reviewing our podcast analytics from last month"},
    {"speaker": "yash", "text": "Yeah, what were the numbers looking like?"},
    {"speaker": "sandip", "text": "We got about 15% more listens compared to the previous month"},
    {"speaker": "yash", "text": "That's really encouraging growth actually"},
    {"speaker": "sandip", "text": "Right? And the engagement metrics were particularly strong"},
    {"speaker": "yash", "text": "Which episodes performed the best?"},
    {"speaker": "sandip", "text": "The one about AI tools and the interview with the startup founder"},
    {"speaker": "yash", "text": "Makes sense, those were really in-depth discussions"},
    {"speaker": "sandip", "text": "Exactly, listeners seem to prefer our longer format content"},
    {"speaker": "yash", "text": "We should plan more of those then"},
    {"speaker": "sandip", "text": "Definitely, I was thinking we could do a series"},
    {"speaker": "yash", "text": "That's a great idea, maybe three parts?"},
    {"speaker": "sandip", "text": "Yeah, we could cover different aspects each week"},
    {"speaker": "yash", "text": "Should we start planning the topics?"},
    {"speaker": "sandip", "text": "Let's schedule a brainstorming session for tomorrow"},
    {"speaker": "yash", "text": "Perfect, I'll bring some research to the meeting"}
]

# Natural response fillers
FILLERS = [
    {"text": "hmm", "duration_range": (0.3, 0.6), "speaker": "any", "type": "acknowledgment"},
    {"text": "yeah", "duration_range": (0.4, 0.7), "speaker": "any", "type": "acknowledgment"},
    {"text": "right", "duration_range": (0.4, 0.6), "speaker": "any", "type": "acknowledgment"},
    {"text": "yes", "duration_range": (0.4, 0.6), "speaker": "any", "type": "acknowledgment"},
    {"text": "aha", "duration_range": (0.3, 0.5), "speaker": "any", "type": "acknowledgment"},
    {"text": "mm-hmm", "duration_range": (0.4, 0.7), "speaker": "any", "type": "acknowledgment"},
    {"text": "got it", "duration_range": (0.5, 0.8), "speaker": "any", "type": "acknowledgment"},
    {"text": "I see", "duration_range": (0.6, 0.9), "speaker": "any", "type": "acknowledgment"},
    {"text": "that's true", "duration_range": (0.8, 1.0), "speaker": "any", "type": "agreement"},
    {"text": "exactly", "duration_range": (0.6, 0.9), "speaker": "any", "type": "agreement"}
]

# Conversation parameters
ACKNOWLEDGMENT_PROBABILITY = 0.8  # Very high for natural flow
MIN_SILENCE_FOR_FILLER = 300  # ms
PAUSE_BETWEEN_LINES = 500  # ms
FILLER_VOLUME_REDUCTION = -8  # dB

# --- Audio Generation Functions ---

def generate_audio_clip(text: str, speaker: str, duration: Optional[float] = None) -> np.ndarray:
    """Generate audio clip with error handling."""
    try:
        audio = generate_audio(
            text,
            history_prompt=VOICES[speaker],
            text_temp=TEXT_TEMP,
            waveform_temp=WAVEFORM_TEMP
        )
        if duration:
            samples = int(duration * 24000)
            audio = audio[:samples]
        return audio
    except Exception as e:
        logger.error(f"Failed to generate '{text}' by {speaker}: {str(e)}")
        raise

def ensure_filler_clips() -> Dict[Tuple[str, str], Tuple[str, str, float]]:
    """Generate all needed filler clips."""
    logger.info("\nGenerating filler clips...")
    os.makedirs("fillers", exist_ok=True)
    filler_clips = {}
    
    for filler in FILLERS:
        speakers = list(VOICES.keys()) if filler["speaker"] == "any" else [filler["speaker"]]
        
        for speaker in speakers:
            try:
                duration = random.uniform(*filler["duration_range"])
                key = (filler["text"], speaker)
                
                # Skip if already exists
                if key in filler_clips:
                    continue
                
                logger.info(f"Creating {duration:.2f}s '{filler['text']}' by {speaker}")
                audio = generate_audio_clip(filler["text"], speaker, duration)
                
                filename = f"fillers/{speaker}{filler['text'].replace(' ','')}.wav"
                write_wav(filename, 24000, audio)
                
                filler_clips[key] = (filename, filler["type"], duration)
                
            except Exception as e:
                logger.error(f"Failed to create filler: {str(e)}")
                continue
                
    return filler_clips

def find_conversation_pauses(audio: AudioSegment) -> List[Tuple[int, int]]:
    """Find natural pause points in speech."""
    return silence.detect_silence(
        audio,
        min_silence_len=MIN_SILENCE_FOR_FILLER,
        silence_thresh=-40,
        seek_step=50
    )

def add_listener_responses(main_audio: AudioSegment, main_speaker: str, filler_clips: dict) -> AudioSegment:
    """Add natural listener responses during pauses."""
    other_speaker = "yash" if main_speaker == "sandip" else "sandip"
    pauses = find_conversation_pauses(main_audio)
    
    if not pauses or random.random() > ACKNOWLEDGMENT_PROBABILITY:
        return main_audio
    
    # Filter suitable pauses (middle 80% of audio)
    suitable_pauses = [
        p for p in pauses 
        if p[0] > len(main_audio)*0.1 and p[1] < len(main_audio)*0.9
        and (p[1] - p[0]) > MIN_SILENCE_FOR_FILLER
    ]
    
    if not suitable_pauses:
        return main_audio
    
    # Select a random pause (weighted toward longer pauses)
    pause = random.choices(
        suitable_pauses,
        weights=[(p[1]-p[0])**1.5 for p in suitable_pauses]
    )[0]
    
    # Get available fillers from the listener
    available_fillers = [
        (path, dur) 
        for (text, spkr), (path, typ, dur) in filler_clips.items()
        if spkr == other_speaker and typ == "acknowledgment"
    ]
    
    if not available_fillers:
        return main_audio
    
    filler_path, filler_duration = random.choice(available_fillers)
    filler_ms = int(filler_duration * 1000)
    
    # Ensure the filler fits with buffer space
    if (pause[1] - pause[0]) < filler_ms + 200:
        return main_audio
    
    try:
        # Load and adjust filler volume
        filler = AudioSegment.from_wav(filler_path) + FILLER_VOLUME_REDUCTION
        
        # Insert at natural point in pause
        insert_pos = pause[0] + (pause[1] - pause[0] - filler_ms) // 2
        
        # Combine audio
        return main_audio[:insert_pos] + filler + main_audio[insert_pos:]
        
    except Exception as e:
        logger.error(f"Failed to insert filler: {str(e)}")
        return main_audio

def generate_conversation(filler_clips: dict) -> AudioSegment:
    """Generate the full conversation with natural responses."""
    logger.info("\nBuilding conversation...")
    conversation = AudioSegment.silent(duration=0)
    
    for line in BASE_SCRIPT:
        try:
            logger.info(f"Processing: {line['speaker']} - '{line['text']}'")
            
            # Generate main line
            audio_array = generate_audio_clip(line["text"], line["speaker"])
            
            # Convert to AudioSegment
            temp_wav = "temp_line.wav"
            write_wav(temp_wav, 24000, audio_array)
            line_audio = AudioSegment.from_wav(temp_wav)
            os.remove(temp_wav)
            
            # Add listener responses
            enhanced_audio = add_listener_responses(line_audio, line["speaker"], filler_clips)
            conversation += enhanced_audio
            
            # Add pause between lines
            if line != BASE_SCRIPT[-1]:
                pause = PAUSE_BETWEEN_LINES + random.randint(-100, 200)
                conversation += AudioSegment.silent(duration=pause)
                
        except Exception as e:
            logger.error(f"Failed to process line: {str(e)}")
            continue
            
    return conversation

# --- Main Execution ---

if __name__ == "__main__":
    start_time = time.time()
    
    try:
        # First ensure all fillers exist
        fillers = ensure_filler_clips()
        
        # Generate the conversation
        podcast = generate_conversation(fillers)
        
        # Normalize and export
        podcast = podcast.normalize()
        output_path = "natural_conversation.wav"
        podcast.export(output_path, format="wav", bitrate="192k")
        
        logger.info(f"\n✅ Successfully created: {output_path}")
        logger.info(f"Total runtime: {time.time()-start_time:.1f} seconds")
        
    except Exception as e:
        logger.error(f"\n❌ Failed to create podcast: {str(e)}")
        raise