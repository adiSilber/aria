#!/usr/bin/env python3

import argparse
import json
import mido

def jsb_json_to_midi(json_path, output_path, resolution="16th", tempo=120):
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    sequences = []
    for key in ['train', 'test', 'valid', 'single']:
        if key in data:
            sequences.extend(data[key])
            break
    
    if not sequences:
        raise ValueError("No sequences found in JSON")
    
    beats_per_step = {"quarter": 1.0, "8th": 0.5, "16th": 0.25}
    tempo_us_per_beat = int(60000000 / tempo)
    step_duration_ticks = int(480 * beats_per_step[resolution])
    
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    track.append(mido.MetaMessage('set_tempo', tempo=tempo_us_per_beat, time=0))
    
    for sequence in sequences:
        active_notes = set()
        current_time = 0
        
        for time_step in sequence:
            time_step_set = set(note for note in time_step if 21 <= note <= 108)
            
            notes_off = active_notes - time_step_set
            notes_on = time_step_set - active_notes
            
            for note in sorted(notes_off):
                track.append(mido.Message('note_off', note=note, velocity=0, time=current_time))
                current_time = 0
            
            for note in sorted(notes_on):
                track.append(mido.Message('note_on', note=note, velocity=64, time=current_time))
                current_time = 0
            
            active_notes = time_step_set
            current_time = step_duration_ticks
        
        for note in sorted(active_notes):
            track.append(mido.Message('note_off', note=note, velocity=0, time=current_time))
            current_time = 0
    
    mid.save(output_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", type=str)
    parser.add_argument("output_path", type=str)
    parser.add_argument("--resolution", type=str, choices=["quarter", "8th", "16th"], default="16th")
    parser.add_argument("--tempo", type=int, default=120)
    args = parser.parse_args()
    
    jsb_json_to_midi(args.json_path, args.output_path, args.resolution, args.tempo)

if __name__ == "__main__":
    main()

