#!/usr/bin/env python3
import os
import sys
import subprocess
import torch
import random
import numpy as np

# Set seeds for reproducibility
SEED = 42
os.environ['PYTHONHASHSEED'] = str(SEED)
os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'  # For CUDA determinism

torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
random.seed(SEED)
np.random.seed(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False


# Base command parameters
BACKEND = "torch_cuda"
CHECKPOINT = "config/models/aria-medium-base/model-gen.safetensors"
VARIATIONS = 1
TEMP = 0.8
MIN_P = 0.035
LENGTH = 1024
PROMPT_DURATION = 999999
INPUT_DIRECTORY = "trying_to_get_the_chords_from_the_midi"
LENGTH = 100


def run_aria_generate(input_file: str, output_file: str):
    """Run aria generate command for a single file."""
    cmd = [
        "aria", "generate",
        "--backend", BACKEND,
        "--checkpoint_path", CHECKPOINT,
        "--prompt_midi_path", input_file,
        "--variations", str(VARIATIONS),
        "--temp", str(TEMP),
        "--min_p", str(MIN_P),
        "--save_dir", output_file,
        "--prompt_duration", str(PROMPT_DURATION),
        "--length", str(LENGTH),
    ]
    
    print(f"Processing: {input_file}")
    print(f"Output: {output_file}")
    print("---")
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode == 0:
        print(f"Continuation generated for {input_file}")
        print(f"Output: {output_file}")
        print("---")
    else:
        print(f"Error processing {input_file}")
        print("---")
    
    return result.returncode == 0


def main():
    # Get all subdirectories in INPUT_DIRECTORY
    if not os.path.exists(INPUT_DIRECTORY):
        print(f"Error: Directory {INPUT_DIRECTORY} does not exist")
        return
    
    per_chorale_directories = sorted([
        d for d in os.listdir(INPUT_DIRECTORY)
        if os.path.isdir(os.path.join(INPUT_DIRECTORY, d))
    ])
    
    for chorale_directory in per_chorale_directories:
        chorale_dir_path = os.path.join(INPUT_DIRECTORY, chorale_directory)
        
        # Process MIDI files in the chorale directory
        midi_files = sorted([
            f for f in os.listdir(chorale_dir_path)
            if f.endswith('.mid') and os.path.isfile(os.path.join(chorale_dir_path, f))
        ])
        
        for midi_file in midi_files:
            input_file = os.path.join(chorale_dir_path, midi_file)
            output_file = os.path.join(chorale_dir_path, midi_file.replace('.mid', '_with_continuation.mid'))
            run_aria_generate(input_file, output_file)
        
        # Process minorized directory if it exists
        minorized_directory = os.path.join(chorale_dir_path, 'minorized')
        if os.path.isdir(minorized_directory):
            minorized_files = sorted([
                f for f in os.listdir(minorized_directory)
                if f.endswith('.mid') and os.path.isfile(os.path.join(minorized_directory, f))
            ])
            
            for minorized_file in minorized_files:
                input_file = os.path.join(minorized_directory, minorized_file)
                output_file = os.path.join(minorized_directory, minorized_file.replace('.mid', '_with_continuation.mid'))
                run_aria_generate(input_file, output_file)
    
    print("All files processed!")


if __name__ == "__main__":
    main()

