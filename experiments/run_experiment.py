#!/usr/bin/env python3
"""
Experiment framework for running aria continuations on paired original/minorized
cut files and organizing results per-experiment.

Usage:
    python experiments/run_experiment.py \
        --name minorized_cadences \
        --data_dir trying_to_get_the_chords_from_the_midi
"""

import argparse
import json
import os
import sys
import datetime
import random

import numpy as np
import torch

# ── Configurable parameters ──────────────────────────────────────────────────
SEEDS = [42, 43, 44]
CONTINUATION_SECONDS = 2.5
TEMP = 0.8
MIN_P = 0.035
BACKEND = "torch_cuda"
CHECKPOINT = "config/models/aria-medium-base/model-gen.safetensors"
PROMPT_DURATION = 999999  # use entire input as prompt
MIN_GEN_LENGTH = 50
MAX_GEN_LENGTH = 500
# ─────────────────────────────────────────────────────────────────────────────


def _set_seed(seed: int):
    """Set all random seeds for reproducibility."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def compute_generation_length(midi_path: str) -> int:
    """Compute token generation length targeting CONTINUATION_SECONDS of audio.

    1. Load and tokenize the MIDI file
    2. Get the MIDI duration in seconds
    3. tokens_per_second = len(tokens) / duration
    4. generation_length = tokens_per_second * CONTINUATION_SECONDS
    """
    from ariautils.midi import MidiDict
    from ariautils.tokenizer import AbsTokenizer

    midi_dict = MidiDict.from_midi(midi_path)
    tokenizer = AbsTokenizer()
    tokens = tokenizer.tokenize(midi_dict, add_dim_tok=False, add_eos_tok=False)

    # Get duration from note messages
    if not midi_dict.note_msgs:
        return MIN_GEN_LENGTH

    max_end_ms = max(
        midi_dict.tick_to_ms(msg["data"]["end"]) for msg in midi_dict.note_msgs
    )
    duration_seconds = max_end_ms / 1000.0

    if duration_seconds <= 0:
        return MIN_GEN_LENGTH

    tokens_per_second = len(tokens) / duration_seconds
    gen_length = int(tokens_per_second * CONTINUATION_SECONDS)
    gen_length = max(MIN_GEN_LENGTH, min(MAX_GEN_LENGTH, gen_length))

    print(f"  Tokens: {len(tokens)}, Duration: {duration_seconds:.2f}s, "
          f"Tok/s: {tokens_per_second:.1f}, Gen length: {gen_length}")

    return gen_length


def run_generate(midi_path: str, output_path: str, seed: int, gen_length: int):
    """Run aria generate for a single file with a specific seed."""
    _set_seed(seed)

    # Import here so model loading happens after seed is set
    from aria.run import generate

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    args = argparse.Namespace(
        backend=BACKEND,
        checkpoint_path=CHECKPOINT,
        prompt_midi_path=midi_path,
        prompt_duration=PROMPT_DURATION,
        variations=1,
        temp=TEMP,
        min_p=MIN_P,
        top_p=None,
        length=gen_length,
        save_dir=output_path,
        verbose=False,
        print_tokens=False,
        end=False,
        compile=False,
    )

    generate(args)


def find_paired_files(chorale_dir: str):
    """Find original cut files and their minorized pairs in a chorale directory.

    Returns list of (tick_label, original_path, minorized_path) tuples.
    """
    pairs = []

    # Find original cut files
    midi_files = sorted(
        f for f in os.listdir(chorale_dir)
        if f.endswith(".mid") and os.path.isfile(os.path.join(chorale_dir, f))
    )

    minorized_dir = os.path.join(chorale_dir, "minorized")

    for midi_file in midi_files:
        # Extract tick label, e.g. "cut_tick_56" from "chorale_0000_cut_tick_56.mid"
        base = midi_file.replace(".mid", "")
        # Find the "cut_tick_NNN" part
        idx = base.find("cut_tick_")
        if idx == -1:
            continue
        tick_label = base[idx:]  # e.g. "cut_tick_56"

        original_path = os.path.join(chorale_dir, midi_file)

        # Look for the minorized counterpart
        minor_name = base + "_minor.mid"
        minor_path = os.path.join(minorized_dir, minor_name)

        if os.path.isfile(minor_path):
            pairs.append((tick_label, original_path, minor_path))
        else:
            # Still include the original even without a minor pair
            pairs.append((tick_label, original_path, None))

    return pairs


def main():
    parser = argparse.ArgumentParser(
        description="Run aria continuation experiment on paired original/minorized files"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Experiment name (used in directory name)",
    )
    parser.add_argument(
        "--data_dir",
        required=True,
        help="Data source directory containing chorale subdirectories",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        print(f"Error: Data directory '{data_dir}' does not exist")
        sys.exit(1)

    # Create timestamped experiment directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_dir = os.path.join("experiments", f"{timestamp}_{args.name}")
    os.makedirs(experiment_dir, exist_ok=True)

    # Save experiment info
    experiment_info = {
        "name": args.name,
        "timestamp": timestamp,
        "data_dir": os.path.abspath(data_dir),
        "seeds": SEEDS,
        "continuation_seconds": CONTINUATION_SECONDS,
        "temp": TEMP,
        "min_p": MIN_P,
        "backend": BACKEND,
        "checkpoint": CHECKPOINT,
        "prompt_duration": PROMPT_DURATION,
        "min_gen_length": MIN_GEN_LENGTH,
        "max_gen_length": MAX_GEN_LENGTH,
    }
    info_path = os.path.join(experiment_dir, "experiment_info.json")
    with open(info_path, "w") as f:
        json.dump(experiment_info, f, indent=2)
    print(f"Experiment directory: {experiment_dir}")
    print(f"Saved experiment info to {info_path}")

    # Find all chorale directories
    chorale_dirs = sorted(
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
    )

    if not chorale_dirs:
        print(f"No chorale directories found in {data_dir}")
        sys.exit(1)

    print(f"Found {len(chorale_dirs)} chorale directories")
    print(f"Seeds: {SEEDS}")
    print(f"Target continuation: {CONTINUATION_SECONDS}s")
    print()

    total_generated = 0
    total_errors = 0

    for chorale_dir_name in chorale_dirs:
        chorale_dir_path = os.path.join(data_dir, chorale_dir_name)
        pairs = find_paired_files(chorale_dir_path)

        if not pairs:
            print(f"Skipping {chorale_dir_name}: no cut files found")
            continue

        # Extract chorale name (e.g. "chorale_0000" from "chorale_0000_cuts_output")
        chorale_name = chorale_dir_name.replace("_cuts_output", "")
        chorale_out_dir = os.path.join(experiment_dir, chorale_name)

        print(f"Processing {chorale_name} ({len(pairs)} cut points)...")

        for tick_label, original_path, minor_path in pairs:
            tick_out_dir = os.path.join(chorale_out_dir, tick_label)
            os.makedirs(tick_out_dir, exist_ok=True)

            # Compute generation length from the original file
            print(f"  {tick_label}:")
            gen_length = compute_generation_length(original_path)

            # Generate for each seed
            for seed in SEEDS:
                # Original
                out_file = os.path.join(tick_out_dir, f"original_seed{seed}.mid")
                print(f"    Generating original seed={seed} -> {out_file}")
                try:
                    run_generate(original_path, out_file, seed, gen_length)
                    total_generated += 1
                except Exception as e:
                    print(f"    ERROR: {e}")
                    total_errors += 1

                # Minorized
                if minor_path is not None:
                    out_file = os.path.join(tick_out_dir, f"minorized_seed{seed}.mid")
                    print(f"    Generating minorized seed={seed} -> {out_file}")
                    try:
                        run_generate(minor_path, out_file, seed, gen_length)
                        total_generated += 1
                    except Exception as e:
                        print(f"    ERROR: {e}")
                        total_errors += 1

        print()

    print("=" * 60)
    print(f"Experiment complete: {experiment_dir}")
    print(f"  Generated: {total_generated} files")
    if total_errors:
        print(f"  Errors: {total_errors}")


if __name__ == "__main__":
    main()
