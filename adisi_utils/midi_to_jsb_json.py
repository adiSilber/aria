#!/usr/bin/env python3

import argparse
import json
from ariautils.midi import MidiDict

def quantize_to_resolution(midi_dict, resolution="16th"):
    beats_per_step = {"quarter": 1.0, "8th": 0.5, "16th": 0.25}
    tempo_us_per_beat = midi_dict.tempo_msgs[0]["data"] if midi_dict.tempo_msgs else 500000
    tempo_ms_per_beat = tempo_us_per_beat / 1000.0
    step_duration_ms = tempo_ms_per_beat * beats_per_step[resolution]
    
    if not midi_dict.note_msgs:
        return []
    
    max_end_ms = max(midi_dict.tick_to_ms(msg["data"]["end"]) for msg in midi_dict.note_msgs)
    num_steps = int(max_end_ms / step_duration_ms) + 1
    
    time_steps = []
    for step_idx in range(num_steps):
        step_time_ms = step_idx * step_duration_ms
        active_notes = set()
        for msg in midi_dict.note_msgs:
            note_start_ms = midi_dict.tick_to_ms(msg["data"]["start"])
            note_end_ms = midi_dict.tick_to_ms(msg["data"]["end"])
            note_pitch = msg["data"]["pitch"]
            if (note_start_ms <= step_time_ms < note_end_ms and 21 <= note_pitch <= 108):
                active_notes.add(note_pitch)
        time_steps.append(sorted(list(active_notes), reverse=True))
    return time_steps

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("midi_path", type=str)
    parser.add_argument("output_path", type=str)
    parser.add_argument("--resolution", type=str, choices=["quarter", "8th", "16th"], default="16th")
    parser.add_argument("--key", type=str, default="single")
    args = parser.parse_args()
    
    midi_dict = MidiDict.from_midi(args.midi_path)
    time_steps = quantize_to_resolution(midi_dict, args.resolution)
    output_data = {args.key: [time_steps]}
    
    with open(args.output_path, 'w') as f:
        json.dump(output_data, f)

if __name__ == "__main__":
    main()

