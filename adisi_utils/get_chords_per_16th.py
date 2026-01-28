#!/usr/bin/env python3
from typing import List, Optional, Set
from ariautils.midi import MidiDict

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def _get_intervals(root_pc: int) -> dict:
    return {
        'm2': (root_pc + 1) % 12, 'M2': (root_pc + 2) % 12, 'm3': (root_pc + 3) % 12,
        'M3': (root_pc + 4) % 12, 'p4': (root_pc + 5) % 12, 'd5': (root_pc + 6) % 12,
        'p5': (root_pc + 7) % 12, 'a5': (root_pc + 8) % 12, 'd7': (root_pc + 9) % 12,
        'm7': (root_pc + 10) % 12, 'M7': (root_pc + 11) % 12
    }

def _check_sus_chord(root_pc: int, pc: Set[int], iv: dict) -> Optional[str]:
    if iv['M2'] in pc and iv['p5'] in pc:
        return f"{NOTES[root_pc]}sus2{'7' if iv['m7'] in pc else ''}"
    if iv['p4'] in pc and iv['p5'] in pc:
        return f"{NOTES[root_pc]}sus4{'7' if iv['m7'] in pc else ''}"
    return None

def _get_tensions(root_pc: int, pc: Set[int], iv: dict, has_3rd: bool) -> List[str]:
    tensions = []
    if iv['m2'] in pc:
        tensions.append("b9")
    if iv['d5'] in pc and has_3rd and iv['p5'] in pc:
        tensions.append("#11")
    if iv['a5'] in pc and (iv['m7'] in pc or iv['M7'] in pc):
        tensions.append("b13")
    return tensions

def _check_major_chord(root_pc: int, pc: Set[int], iv: dict, tensions: List[str]) -> Optional[str]:
    if iv['M3'] in pc and iv['p5'] in pc:
        base = f"{NOTES[root_pc]}{'maj7' if iv['M7'] in pc else '7' if iv['m7'] in pc else ''}"
        return base + "".join(tensions) if tensions else base
    return None

def _check_minor_chord(root_pc: int, pc: Set[int], iv: dict, tensions: List[str]) -> Optional[str]:
    if iv['m3'] in pc and iv['p5'] in pc:
        base = f"{NOTES[root_pc]}m{'7' if iv['m7'] in pc else ''}"
        return base + "".join(tensions) if tensions else base
    return None

def _check_dim_chord(root_pc: int, pc: Set[int], iv: dict, tensions: List[str]) -> Optional[str]:
    if iv['m3'] in pc and iv['d5'] in pc:
        if iv['d7'] in pc:
            return f"{NOTES[root_pc]}dim7"
        if iv['m7'] in pc:
            return f"{NOTES[root_pc]}m7b5"
        return f"{NOTES[root_pc]}dim"
    return None

def _check_aug_chord(root_pc: int, pc: Set[int], iv: dict, tensions: List[str]) -> Optional[str]:
    if iv['M3'] in pc and iv['a5'] in pc:
        return f"{NOTES[root_pc]}aug"
    return None

def _find_chord_type(root_pc: int, pc: Set[int]) -> Optional[str]:
    iv = _get_intervals(root_pc)
    has_3rd = iv['m3'] in pc or iv['M3'] in pc
    
    if not has_3rd and (sus := _check_sus_chord(root_pc, pc, iv)):
        return sus
    
    tensions = _get_tensions(root_pc, pc, iv, has_3rd)
    
    for check in [_check_major_chord, _check_minor_chord, _check_dim_chord, _check_aug_chord]:
        if chord := check(root_pc, pc, iv, tensions):
            return chord
    
    return None

def _notes_to_chord(notes: Set[int]) -> Optional[str]:
    if not notes or len(notes) > 4:
        return None
    pc = {n % 12 for n in notes}
    bass_pc = min(notes) % 12
    
    for r in sorted(pc):
        if chord := _find_chord_type(r, pc):
            return f"{chord}/{NOTES[bass_pc]}" if bass_pc != r else chord
    print(NOTES[bass_pc])
    return NOTES[bass_pc]

def _extract_chords(midi_path: str, tempo: Optional[float] = None) -> List[str]:
    md = MidiDict.from_midi(midi_path)
    if not md.note_msgs:
        return []
    if tempo is None:
        tempo = 60000000.0 / md.tempo_msgs[0]["data"] if md.tempo_msgs else 120.0
    step_ms = (60000.0 / tempo) * 0.25
    max_ms = max(md.tick_to_ms(msg["data"]["end"]) for msg in md.note_msgs)
    chords = []
    for i in range(int(max_ms / step_ms) + 1):
        t = i * step_ms
        notes = {msg["data"]["pitch"] for msg in md.note_msgs
                 if md.tick_to_ms(msg["data"]["start"]) <= t < md.tick_to_ms(msg["data"]["end"]) 
                 and 21 <= msg["data"]["pitch"] <= 108}
        if i < 10:
            print(sorted(notes))
        chords.append(_notes_to_chord(notes))
    return chords

def get_chords_per_16th(midi_path: str, output_path: str, tempo: Optional[float] = None) -> List[str]:
    chords = _extract_chords(midi_path, tempo)
    with open(output_path, 'w') as f:
        for i, c in enumerate(chords):
            f.write(f"{i+1}: {c or 'rest'}\n")
    return chords

def get_chords_per_16th_by_bar(midi_path: str, output_path: str, tempo: Optional[float] = None) -> List[List[str]]:
    chords = _extract_chords(midi_path, tempo)
    bars = [chords[i:i+16] for i in range(0, len(chords), 16)]
    with open(output_path, 'w') as f:
        for i, bar in enumerate(bars):
            f.write(f"Bar {i+1}:\n")
            for j, c in enumerate(bar):
                f.write(f"  16th {j+1}: {c or 'rest'}\n")
    return bars

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("midi_path")
    p.add_argument("output_path")
    p.add_argument("--by-bar", action="store_true")
    p.add_argument("--tempo", type=float, default=None)
    args = p.parse_args()
    if args.by_bar:
        get_chords_per_16th_by_bar(args.midi_path, args.output_path, args.tempo)
    else:
        get_chords_per_16th(args.midi_path, args.output_path, args.tempo)