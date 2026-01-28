#!/usr/bin/env python3
from typing import List, Tuple

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def _is_major_chord(chord_base: str) -> bool:
    """Check if chord is major (not minor, dim, aug, sus)."""
    # Remove root note to check chord quality
    if len(chord_base) <= 1:
        return True  # Just root note = major triad
    if chord_base[1] == '#':
        quality_start = 2
    else:
        quality_start = 1
    
    if quality_start >= len(chord_base):
        return True
    
    quality = chord_base[quality_start:]
    # Major if: starts with "maj7", "7", or just extensions (not "m", "dim", "aug", "sus")
    if quality.startswith('m') and not quality.startswith('maj'):
        return False  # minor
    if quality.startswith('dim') or quality.startswith('aug'):
        return False
    if quality.startswith('sus'):
        return False
    return True  # major triad, 7, maj7, or extensions

def get_5_to_1_places(text_file_path: str, output_path: str):
    """Find V-I cadences (5th to 1st) in chord progression file."""
    result = []
    prev_16th = prev_root = prev_chord_base = None
    
    with open(text_file_path, 'r') as f:
        for line in f:
            if ':' not in line:
                continue
            parts = line.strip().split(':', 1)
            if len(parts) != 2:
                continue

            try:
                curr_16th = int(parts[0].strip())
                chord = parts[1].strip()
            except ValueError:
                continue
            
            if chord == 'rest':
                continue
            
            # Extract root note and bass note (e.g., "Cm7/G" -> root="C", bass="G")
            chord_parts = chord.split('/')
            chord_base = chord_parts[0]
            if chord_base[0] not in 'ABCDEFG':
                continue
            
            curr_root = chord_base[0]
            if len(chord_base) > 1 and chord_base[1] == '#':
                curr_root += '#'
            
            if curr_root not in NOTES:
                continue
            
            # Extract bass note (if slash chord exists, otherwise bass = root)
            if len(chord_parts) > 1:
                bass_str = chord_parts[1].strip()
                bass_note = bass_str[0]
                if len(bass_str) > 1 and bass_str[1] == '#':
                    bass_note += '#'
                if bass_note not in NOTES:
                    continue
            else:
                bass_note = curr_root
            
            # Check if previous chord is perfect 5th above current (V-I cadence)
            # AND previous chord is major (V must be major)
            # AND bass of I chord is the root (1st degree)
            # AND I chord starts on 3rd quarter (16th notes 9-12 of bar)
            if prev_root and (NOTES.index(prev_root) - NOTES.index(curr_root)) % 12 == 7:
                # Check if current 16th is in 3rd quarter (positions 9-12 within bar)
                position_in_bar = (curr_16th - 1) % 16
                is_third_quarter = 8 <= position_in_bar <= 11
                if _is_major_chord(prev_chord_base) and bass_note == curr_root and is_third_quarter:
                    result.append((prev_16th, curr_16th))
            
            prev_16th, prev_root, prev_chord_base = curr_16th, curr_root, chord_base
    
    with open(output_path, 'w') as f:
        for v, i in result:
            f.write(f"{v} -> {i}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Find V-I cadences in chord progression file")
    parser.add_argument("input_path", help="Path to text file created by get_chords_per_16th")
    parser.add_argument("output_path", help="Path to output text file with V-I cadence locations")
    args = parser.parse_args()
    
    places = get_5_to_1_places(args.input_path, args.output_path)
    
