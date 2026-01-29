"""
Analyze experiment continuations: for each chorale's cut points, identify what
chord the model generated immediately after the prompt ends (for both original
and minorized variants across all seeds).

Copies each chorale's _chords.txt into the experiment directory and appends
a continuation analysis block.
"""

import argparse
import os
import re
import shutil
import mido
from music21 import pitch, chord, roman, key as m21key


# ---------------------------------------------------------------------------
# MIDI helpers (same logic as adisi_main._get_sounding_notes_per_16th)
# ---------------------------------------------------------------------------

def _get_sounding_notes_per_16th(midi_path):
    """Return (list_of_sorted_midi_note_lists, total_16ths) from a MIDI file."""
    mid = mido.MidiFile(midi_path)
    ticks_per_16th = mid.ticks_per_beat / 4.0

    events = []
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                events.append(('on', abs_time, msg.note))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                events.append(('off', abs_time, msg.note))
    events.sort(key=lambda x: (x[1], 0 if x[0] == 'off' else 1))

    last_tick = max(t for _, t, _ in events) if events else 0
    total_16ths = int(round(last_tick / ticks_per_16th))

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


def _get_prompt_length_seconds(midi_path):
    """Return the total duration of a MIDI file in seconds."""
    return mido.MidiFile(midi_path).length


def _get_tempo(midi_path):
    """Return the first set_tempo value (microseconds per beat), default 500000."""
    mid = mido.MidiFile(midi_path)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return msg.tempo
    return 500000  # default 120 BPM


# ---------------------------------------------------------------------------
# Chord identification
# ---------------------------------------------------------------------------

def _identify_chord(midi_notes, parsed_key):
    """
    Given a list of MIDI note numbers and a music21 Key, return
    (chord_name, roman_numeral) or (None, None) if no notes.
    """
    if not midi_notes or len(midi_notes) < 2:
        return None, None
    pitches_list = [pitch.Pitch(midi=m) for m in midi_notes]
    c = chord.Chord(pitches_list)
    rn = roman.romanNumeralFromChord(c, parsed_key)
    return c.pitchedCommonName, rn.figure


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_key_from_chords_txt(chords_path):
    """Parse 'Key: B- major' line from a _chords.txt file into a music21 Key."""
    with open(chords_path, 'r') as f:
        for line in f:
            if line.startswith('Key:'):
                # e.g. "Key: B- major"
                parts = line[4:].strip().split()
                tonic_name = parts[0]  # e.g. "B-"
                mode = parts[1] if len(parts) > 1 else "major"
                return m21key.Key(tonic_name, mode)
    return None


def _parse_strong_cadences(chords_path):
    """Parse 'Strong Cadences: [56, 184]' line from a _chords.txt file."""
    with open(chords_path, 'r') as f:
        content = f.read()
    match = re.search(r"Strong Cadences.*\[(.*?)\]", content)
    if match:
        nums = match.group(1)
        if nums.strip():
            return [int(n.strip()) for n in nums.split(',') if n.strip().isdigit()]
    return []


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _find_input_midi(data_dir, chorale_name, tick_label):
    """Find the original (pre-cut) input MIDI for a given chorale + tick."""
    # e.g. trying_to_get_the_chords_from_the_midi/chorale_0000_cuts_output/chorale_0000_cut_tick_56.mid
    cuts_dir = os.path.join(data_dir, f"{chorale_name}_cuts_output")
    filename = f"{chorale_name}_{tick_label}.mid"
    path = os.path.join(cuts_dir, filename)
    if os.path.exists(path):
        return path
    return None


def analyze_continuation(continuation_path, prompt_length_sec, parsed_key):
    """
    Load a continuation MIDI, find the notes at the first 16th after the
    prompt ends, and return (chord_name, roman_numeral, prompt_end_ms).
    """
    # Get tempo from continuation to compute 16th note duration in seconds
    tempo_us = _get_tempo(continuation_path)
    sec_per_16th = (tempo_us / 1e6) / 4.0  # each 16th = quarter / 4

    # Get all notes per 16th in the continuation
    notes_per_16th, total_16ths = _get_sounding_notes_per_16th(continuation_path)

    # Find the first 16th index whose time >= prompt_length_sec
    prompt_16th_index = None
    for i in range(total_16ths):
        time_sec = i * sec_per_16th
        if time_sec >= prompt_length_sec - 0.001:  # small tolerance
            prompt_16th_index = i
            break

    if prompt_16th_index is None or prompt_16th_index >= total_16ths:
        return None, None, int(prompt_length_sec * 1000)

    midi_notes = notes_per_16th[prompt_16th_index]
    chord_name, rn_figure = _identify_chord(midi_notes, parsed_key)
    return chord_name, rn_figure, int(prompt_length_sec * 1000)


def analyze_chorale(experiment_dir, data_dir, chorale_name, seeds):
    """Analyze all continuations for one chorale and return the analysis text."""
    chords_src = os.path.join(data_dir, f"{chorale_name}_chords.txt")
    if not os.path.exists(chords_src):
        print(f"  Skipping {chorale_name}: no _chords.txt found")
        return None

    # Parse key and cadences
    parsed_key = _parse_key_from_chords_txt(chords_src)
    if parsed_key is None:
        print(f"  Skipping {chorale_name}: could not parse key")
        return None

    strong_cadences = _parse_strong_cadences(chords_src)

    # Copy chords file into experiment chorale dir
    chorale_exp_dir = os.path.join(experiment_dir, chorale_name)
    if not os.path.isdir(chorale_exp_dir):
        print(f"  Skipping {chorale_name}: no experiment directory")
        return None

    chords_dst = os.path.join(chorale_exp_dir, f"{chorale_name}_chords.txt")
    shutil.copy2(chords_src, chords_dst)

    # Find cut point directories in the experiment
    cut_dirs = sorted([
        d for d in os.listdir(chorale_exp_dir)
        if os.path.isdir(os.path.join(chorale_exp_dir, d)) and d.startswith("cut_tick_")
    ])

    if not cut_dirs:
        print(f"  Skipping {chorale_name}: no cut_tick directories")
        return None

    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("CONTINUATION ANALYSIS")
    lines.append("=" * 60)

    for cut_dir_name in cut_dirs:
        # e.g. "cut_tick_56"
        tick_num_match = re.search(r"cut_tick_(\d+)", cut_dir_name)
        if not tick_num_match:
            continue
        tick_num = int(tick_num_match.group(1))
        cadence_type = "Strong Cadence" if tick_num in strong_cadences else "Cadence"

        # Find the input MIDI to get prompt duration
        input_midi = _find_input_midi(data_dir, chorale_name, cut_dir_name)
        if input_midi is None:
            lines.append(f"\n--- {cut_dir_name} ({cadence_type}) ---")
            lines.append("  Could not find input MIDI")
            continue

        prompt_sec = _get_prompt_length_seconds(input_midi)
        prompt_ms = int(prompt_sec * 1000)

        lines.append(f"\n--- {cut_dir_name} ({cadence_type}) ---")
        lines.append(f"Original prompt ends at: {prompt_ms}ms")
        lines.append("")

        # Analyze each continuation file
        cut_path = os.path.join(chorale_exp_dir, cut_dir_name)
        variant_order = ["original", "minorized"]
        for variant in variant_order:
            for seed in seeds:
                cont_filename = f"{variant}_seed{seed}.mid"
                cont_path = os.path.join(cut_path, cont_filename)
                if not os.path.exists(cont_path):
                    lines.append(f"  {variant}_seed{seed}:  [file not found]")
                    continue

                chord_name, rn_figure, _ = analyze_continuation(
                    cont_path, prompt_sec, parsed_key
                )

                if chord_name and rn_figure:
                    lines.append(
                        f"  {variant}_seed{seed}:  {chord_name:<30} | {rn_figure}"
                    )
                else:
                    lines.append(f"  {variant}_seed{seed}:  [no notes found]")

    # Append analysis to the copied chords file
    analysis_text = "\n".join(lines) + "\n"
    with open(chords_dst, 'a') as f:
        f.write(analysis_text)

    return chords_dst


def main():
    parser = argparse.ArgumentParser(
        description="Analyze experiment continuations and append chord info to _chords.txt"
    )
    parser.add_argument(
        "--experiment_dir", required=True,
        help="Path to the experiment directory (e.g. experiments/20260129_...)"
    )
    parser.add_argument(
        "--data_dir", required=True,
        help="Path to the data source directory with _chords.txt files"
    )
    args = parser.parse_args()

    experiment_dir = args.experiment_dir
    data_dir = args.data_dir

    # Read seeds from experiment_info.json if available
    import json
    info_path = os.path.join(experiment_dir, "experiment_info.json")
    seeds = [42, 43, 44]  # default
    if os.path.exists(info_path):
        with open(info_path, 'r') as f:
            info = json.load(f)
            seeds = info.get("seeds", seeds)

    # Find all chorale directories in the experiment
    chorale_dirs = sorted([
        d for d in os.listdir(experiment_dir)
        if os.path.isdir(os.path.join(experiment_dir, d)) and d.startswith("chorale_")
    ])

    print(f"Found {len(chorale_dirs)} chorale directories")
    print(f"Seeds: {seeds}")
    print()

    processed = 0
    for chorale_name in chorale_dirs:
        print(f"Analyzing {chorale_name}...")
        result = analyze_chorale(experiment_dir, data_dir, chorale_name, seeds)
        if result:
            print(f"  -> Wrote: {result}")
            processed += 1

    print(f"\nDone. Processed {processed}/{len(chorale_dirs)} chorales.")


if __name__ == "__main__":
    main()
