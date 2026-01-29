from music21 import converter, roman, stream, pitch, interval, note, chord
import sys  
import os
import re
import copy
from typing import List
import subprocess
import shutil
import tempfile
import mido
# import partitura



def _get_sounding_notes_per_16th(midi_path):
    """
    Use mido to accurately determine which MIDI notes are sounding at each
    16th-note position. Returns a list of sorted MIDI note lists, one per 16th.
    This bypasses music21's unreliable single-track polyphonic MIDI parsing.
    """
    mid = mido.MidiFile(midi_path)
    ticks_per_16th = mid.ticks_per_beat / 4.0

    # Collect all note on/off events with absolute tick times
    events = []
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                events.append(('on', abs_time, msg.note))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                events.append(('off', abs_time, msg.note))
    # Process note-offs before note-ons at the same tick
    events.sort(key=lambda x: (x[1], 0 if x[0] == 'off' else 1))

    # Find the last event tick to determine total duration
    last_tick = max(t for _, t, _ in events) if events else 0
    total_16ths = int(round(last_tick / ticks_per_16th))

    # Build active notes at each 16th position
    result = []
    for tick_16th in range(total_16ths):
        target_tick = int(tick_16th * ticks_per_16th)
        active = set()
        for typ, t, n in events:
            if t > target_tick:
                break
            if typ == 'on':
                active.add(n)
            elif typ == 'off':
                active.discard(n)
        result.append(sorted(active))

    return result, total_16ths


def save_harmonic_analysis(input_path, output_filename):
    """
    Analyze harmonic structure from MIDI or MusicXML files.

    Args:
        input_path: Path to MIDI (.mid) or MusicXML (.musicxml, .xml, .mxl) file
        output_filename: Path to output text file with harmonic analysis
    """
    # 1. Load and Analyze
    try:
        # Check file extension for logging
        file_ext = os.path.splitext(input_path)[1].lower()
        if file_ext in ['.mid', '.midi']:
            file_type = "MIDI"
        elif file_ext in ['.musicxml', '.xml', '.mxl']:
            file_type = "MusicXML"
        else:
            file_type = "unknown"
            print(f"Warning: Unknown file extension {file_ext}, attempting to parse anyway...")

        print(f"Loading {file_type} file: {input_path}")

        # Use music21 only for key detection
        score = converter.parse(input_path)
        key = score.analyze('key')

        # if key is minor i want to return false and not procces the file
        if key.mode.lower() == "minor":
            print(f"Skipping {input_path}: Key is minor.")
            return False

        # 2. Use mido for accurate note extraction (bypasses music21 MIDI parsing bugs)
        if file_type == "MIDI":
            sounding_notes, total_16ths = _get_sounding_notes_per_16th(input_path)
        else:
            # For MusicXML, music21 parsing works correctly, so use the old approach
            chords_stream = score.chordify().flatten().getElementsByClass('Chord')
            total_16ths = int(round(score.duration.quarterLength * 4))
            sounding_notes = None

        # 3. Validate: check that every position has at least 3 notes
        if sounding_notes is not None:
            for tick_idx, notes in enumerate(sounding_notes):
                if len(notes) < 3:
                    print(f"Skipping {input_path}: Found chord with less than 3 notes ({len(notes)} notes) at 16th={tick_idx}")
                    return False
        else:
            for element in chords_stream:
                if len(element.pitches) < 3:
                    print(f"Skipping {input_path}: Found chord with less than 3 notes ({len(element.pitches)} notes)")
                    return False

        print(f"Processing {total_16ths} time steps...")

        with open(output_filename, 'w') as f:
            # Header
            f.write(f"File: {input_path}\n")
            f.write(f"Type: {file_type}\n")
            f.write(f"Key: {key.tonic.name} {key.mode}\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Tick':<6} | {'Chord Name':<30} | {'Function'}\n")
            f.write("-" * 60 + "\n")

            # 4. Iterate through every single 16th note tick
            for tick in range(total_16ths):
                chord_name = "Rest"
                func = "-"

                if sounding_notes is not None:
                    # MIDI path: build chord from mido's accurate note data
                    midi_notes = sounding_notes[tick]
                    if midi_notes:
                        pitches_list = [pitch.Pitch(midi=m) for m in midi_notes]
                        c = chord.Chord(pitches_list)
                        rn = roman.romanNumeralFromChord(c, key)
                        chord_name = c.pitchedCommonName
                        func = rn.figure
                else:
                    # MusicXML path: use music21's chordify (works fine for XML)
                    current_offset = tick / 4.0
                    element = chords_stream.getElementAtOrBefore(current_offset)
                    if element:
                        chord_end = element.offset + element.duration.quarterLength
                        if chord_end > current_offset + 0.001:
                            rn = roman.romanNumeralFromChord(element, key)
                            chord_name = element.pitchedCommonName
                            func = rn.figure

                # if chord_name is Rest, delete the whole file f and return
                if chord_name == 'Rest':
                    print(f"Skipping {input_path}: Found rest in the chord.")
                    os.remove(output_filename)
                    return
                # 5. Write line to file
                f.write(f"{tick:<6} | {chord_name:<30} | {func}\n")

        print(f"Done! Saved analysis to '{output_filename}'")

    except Exception as e:
        print(f"An error occurred: {e}")

# --- Run the function above ---
save_harmonic_analysis(
    # 'chorale_0001.musicxml',
    'jsb_chorales_midi/train_16th/chorale_0001.mid',
    'sixteenth_chords.txt'
)


from typing import List, Dict

# --- 1. PARSING THE FILE ---
def parse_harmonic_output(file_content: str) -> List[Dict]:
    """
    Reads the text output (Tick | Chord | Function) and returns a raw timeline.
    """
    timeline = []
    lines = file_content.strip().split('\n')
    
    for line in lines:
        parts = line.split('|')
        # We look for lines with 3 parts: "Tick | Name | Function"
        if len(parts) >= 3:
            tick_str = parts[0].strip()
            if tick_str.isdigit(): # Skip headers, only read data
                timeline.append({
                    'tick': int(tick_str),
                    'function': parts[2].strip()
                })
    return timeline


# --- 2. COMPRESSION (GET CHORD EVENTS) ---
def get_chord_events(timeline: List[Dict]) -> List[Dict]:
    """
    Compresses a list of 16th-note ticks into a list of 'Chord Events'.
    Example: [I, I, I, I, V, V] -> [{'func': 'I', 'dur': 4}, {'func': 'V', 'dur': 2}]
    """
    events = []
    if not timeline:
        return events

    # Initialize
    current_func = timeline[0]['function']
    start_tick = timeline[0]['tick']

    for i, tick_data in enumerate(timeline):
        func = tick_data['function']
        tick = tick_data['tick']
        
        # If chord changes, save the previous event
        if func != current_func:
            duration = tick - start_tick
            events.append({
                'function': current_func,
                'start_tick': start_tick,
                'duration': duration
            })
            # Reset
            current_func = func
            start_tick = tick

    # Don't forget the final chord event
    final_tick = timeline[-1]['tick']
    events.append({
        'function': current_func,
        'start_tick': start_tick,
        'duration': final_tick - start_tick + 1
    })
    
    return events


# --- 3. ANALYSIS (FIND CADENCES) ---
def is_perfect_cadence(prev: Dict, curr: Dict) -> bool:
    """
    Determines if a pair of events is a 'Strict' Perfect Cadence.
    """
    prev_func = prev['function']
    curr_func = curr['function']
    
    # --- A. Harmonic Check (Strict V -> I) ---
    # Dominant: Must start with 'V'. Exclude 'vi', 'vii', 'IV'
    # Logic: Starts with V, and if there is a 2nd letter, it cannot be 'I' or 'i'
    is_dominant = prev_func.startswith('V') and (len(prev_func) == 1 or prev_func[1] not in ['I', 'i'])
    
    # Tonic: Must start with 'I' or 'i'. Exclude 'II', 'III', 'IV', 'ii', 'vi'
    # Logic: Starts with I/i, and if there is a 2nd letter, it cannot be 'I', 'i', 'V', 'v'
    is_tonic = (curr_func.startswith('I') or curr_func.startswith('i')) and \
               (len(curr_func) == 1 or curr_func[1] not in ['I', 'i', 'V', 'v'])

    if not (is_dominant and is_tonic):
        return False

    # --- B. Rhythmic Check ---
    # Must land on a beat (Tick divisible by 4)
    if curr['start_tick'] % 4 != 0:
        return False

    # --- C. Duration Check ---
    # Preceding V chord must last at least an 8th note (2 ticks)
    if prev['duration'] < 2:
        return False

    return True

def find_cadences(text_data: str) -> List[int]:
    # Pipeline: Parse -> Compress -> Analyze
    timeline = parse_harmonic_output(text_data)
    chord_events = get_chord_events(timeline)
    
    strong_cadences = []   # For phrase endings (long resolution)
    regular_cadences = []  # For internal cadences (short resolution)
    
    # Compare every event with the one before it
    for prev_event, curr_event in zip(chord_events, chord_events[1:]):
        if is_perfect_cadence(prev_event, curr_event):
            if curr_event['duration'] >= 8:  # 8 ticks = Half Note (Long)
                strong_cadences.append(curr_event['start_tick'])
            elif curr_event['duration'] >= 2: # Ignore tiny blips
                regular_cadences.append(curr_event['start_tick'])
            
    return strong_cadences, regular_cadences

# --- USAGE EXAMPLE ---

def save_cadences_to_input_file(input_file):
    # read the input file and save the cadences to the input file as a new line
    with open(input_file, 'r') as f:
        input_file_content = f.read()
        strong_cadences, regular_cadences = find_cadences(input_file_content)
    with open(input_file, 'w') as f:
        f.write(input_file_content)
        f.write(f"Strong Cadences: {strong_cadences}\n")
        f.write(f"Regular Cadences: {regular_cadences}\n")

def run_process_on_all_midi_files_in_directory(input_directory, output_directory):
    ordered_files = sorted(os.listdir(input_directory))
    for file in ordered_files:
        if file.endswith('.musicxml'):
            input_file = os.path.join(input_directory, file)
            chords_file_path = os.path.join(output_directory, f"{file.split('.')[0]}_chords.txt")
            save_harmonic_analysis(input_file, chords_file_path)
            if os.path.exists(chords_file_path):
                save_cadences_to_input_file(chords_file_path)



# adisi first I made this running:
# run_processs_on_all_midi_files_in_directory('jsb_chorales_xml/train_16th', 'trying_to_get_the_chords_from_the_midi')




# --- 1. PARSE TEXT (Same logic, just helper) ---
def extract_cut_points(analysis_text_path: str) -> List[int]:
    cadence_ticks = []
    try:
        with open(analysis_text_path, 'r') as f:
            content = f.read()
            # Match list format: [56, 184]
            match = re.search(r"Strong Cadences.*\[(.*?)\]", content)
            if match:
                nums = match.group(1)
                if nums.strip():
                    cadence_ticks = [int(n.strip()) for n in nums.split(',') if n.strip().isdigit()]
    except Exception as e:
        print(f"Error parsing text: {e}")
    return cadence_ticks



def cut_midi_at_16th(input_path: str, output_path: str, cut_16th_index: int):
    try:
        mid = mido.MidiFile(input_path)
    except Exception as e:
        print(f"Failed to load {input_path}: {e}")
        return

    # Calculate exact Cut Tick
    ticks_per_16th = mid.ticks_per_beat / 4.0
    cut_threshold_ticks = int(cut_16th_index * ticks_per_16th)

    new_mid = mido.MidiFile()
    new_mid.ticks_per_beat = mid.ticks_per_beat

    for track in mid.tracks:
        new_track = mido.MidiTrack()
        current_time = 0
        active_notes = {} 

        for msg in track:
            # Calculate absolute time of this message
            current_time += msg.time
            
            # --- THE FIX: STRICT BOUNDARY LOGIC ---
            
            # Case 1: Message is completely BEFORE the cut
            if current_time < cut_threshold_ticks:
                new_track.append(msg)
                
                # Track active notes
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[(msg.channel, msg.note)] = msg.velocity
                elif (msg.type == 'note_on' and msg.velocity == 0) or msg.type == 'note_off':
                    key = (msg.channel, msg.note)
                    if key in active_notes: del active_notes[key]

            # Case 2: Message is EXACTLY ON the cut boundary
            elif current_time == cut_threshold_ticks:
                
                # REJECT 'Note On' (This is the start of the '1' chord -> Delete it!)
                if msg.type == 'note_on' and msg.velocity > 0:
                    continue 
                
                # KEEP 'Note Off' (This is the '5' chord finishing naturally -> Keep it!)
                # Also keep MetaMessages (Tempo, Key Sig) if they happen here
                else:
                    new_track.append(msg)
                    # Update tracker to remove from active list since it closed naturally
                    if (msg.type == 'note_on' and msg.velocity == 0) or msg.type == 'note_off':
                        key = (msg.channel, msg.note)
                        if key in active_notes: del active_notes[key]

            # Case 3: Message is AFTER the cut -> STOP
            else:
                # We crossed the line.
                # Force-close any notes that are still ringing (the '5' chord)
                remaining_delta = int(cut_threshold_ticks - (current_time - msg.time))
                
                first = True
                for (channel, note), velocity in active_notes.items():
                    delta = remaining_delta if first else 0
                    # Create a Note Off to cleanly silence the "5"
                    new_track.append(mido.Message('note_off', note=note, velocity=0, channel=channel, time=delta))
                    first = False
                
                break # Stop processing this track
        
        # Finalize Track
        new_track.append(mido.MetaMessage('end_of_track', time=0))
        new_mid.tracks.append(new_track)

    new_mid.save(output_path)





# --- 3. MAIN DRIVER ---
def process_cadence_cuts_raw(midi_path: str, analysis_text_path: str, output_dir: str):
    cadence_ticks = extract_cut_points(analysis_text_path)
    if not cadence_ticks:
        print("No cuts found.")
        return

    print(f"Processing {len(cadence_ticks)} cuts with Mido...")
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(midi_path))[0]

    for tick in cadence_ticks:
        output_filename = f"{base_name}_cut_tick_{tick}.mid"
        output_path = os.path.join(output_dir, output_filename)
        
        cut_midi_at_16th(midi_path, output_path, tick)
        print(f"Saved: {output_filename}")



def run_process_cadence_cuts_raw_on_all_midi_files_in_directory(input_directory, analysis_texts_directory, output_directory):
    ordered_files = sorted(os.listdir(input_directory))
    for file in ordered_files:
        if file.endswith('.mid'):
            input_file = os.path.join(input_directory, file)
            chords_file_path = os.path.join(analysis_texts_directory, f"{file.split('.')[0]}_chords.txt")
            if os.path.exists(chords_file_path):
                process_cadence_cuts_raw(input_file, chords_file_path, os.path.join(output_directory, f"{file.split('.')[0]}_cuts_output"))
                print(f"Processed: {file}")
            else:
                print(f"Skipping {file}: Chords file not found")


# adisi second I made this running:
# run_process_cadence_cuts_raw_on_all_midi_files_in_directory('jsb_chorales_midi/train_16th', 'trying_to_get_the_chords_from_the_midi', 'trying_to_get_the_chords_from_the_midi')



def make_dominant_minor(midi_path: str, output_path: str):
    """
    Lowers the Major 3rd of the final V chord to a Minor 3rd.
    Preserves the original VELOCITY of the notes/chords.
    """
    try:
        score = converter.parse(midi_path)
    except Exception as e:
        print(f"Failed to load {midi_path}: {e}")
        return

    # 1. IDENTIFY THE TARGET PITCH
    chord_stream = score.chordify().flat.getElementsByClass('Chord')
    if not chord_stream:
        print("Error: No chords found.")
        return

    last_chord = chord_stream[-1]
    root = last_chord.root()
    
    target_pitch_name = None
    for p in last_chord.pitches:
        inter = interval.Interval(noteStart=root, noteEnd=p)
        if inter.simpleName == 'M3':
            target_pitch_name = p.name
            break
            
    if not target_pitch_name:
        print(f"No Major 3rd found in {os.path.basename(midi_path)}.")
        return

    print(f"Processing {os.path.basename(midi_path)} (Target: {target_pitch_name})...")
    final_chord_onset = last_chord.offset
    
    # 2. MODIFY SCORE WITH VELOCITY PRESERVATION
    for part in score.parts:
        for element in part.flat.notes:
            
            # Check overlap logic
            element_end = element.offset + element.duration.quarterLength
            if element_end > final_chord_onset:
                
                # --- CAPTURE ORIGINAL VELOCITY ---
                # If velocity is missing (None), default to generic 64 to be safe, 
                # but usually it's an int.
                original_velocity = element.volume.velocity
                if original_velocity is None:
                    original_velocity = 64
                
                # --- CASE A: Single Note ---
                if element.isNote:
                    if element.name == target_pitch_name:
                        element.transpose(-1, inPlace=True)
                        
                        # FORCE RESTORE VELOCITY
                        element.volume.velocity = original_velocity
                        print(f"  -> Modified Note {target_pitch_name} (Vel: {original_velocity})")

                # --- CASE B: Chord ---
                elif element.isChord:
                    new_pitches = []
                    changed = False
                    
                    for p in element.pitches:
                        if p.name == target_pitch_name:
                            new_p = p.transpose(-1)
                            new_pitches.append(new_p)
                            changed = True
                        else:
                            new_pitches.append(p)
                    
                    if changed:
                        element.pitches = tuple(new_pitches)
                        
                        # FORCE RESTORE VELOCITY
                        # (Reassigning pitches often resets volume in music21)
                        element.volume.velocity = original_velocity
                        print(f"  -> Modified Chord (Vel: {original_velocity})")

    score.write('midi', fp=output_path)
    print(f"Saved: {output_path}\n")


# --- HELPER TO RUN ON A FOLDER ---
def process_all_cuts(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if filename.endswith(".mid"):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_minor.mid")
            
            make_dominant_minor(input_path, output_path)


def run_process_all_cuts_on_all_midi_files_in_directory(input_directory):

    all_directories_in_input_directory = sorted([d for d in os.listdir(input_directory) 
           if os.path.isdir(os.path.join(input_directory, d))])
    for directory in all_directories_in_input_directory:
        process_all_cuts(os.path.join(input_directory, directory), os.path.join(input_directory, directory, 'minorized'))
        print(f"Processed: {directory} with all its cuts")

# adisi third I made this running:
# run_process_all_cuts_on_all_midi_files_in_directory('trying_to_get_the_chords_from_the_midi')