#!/bin/bash

# Set seeds for reproducibility
export PYTHONHASHSEED=42
export CUBLAS_WORKSPACE_CONFIG=:4096:8  # For CUDA determinism


# Base command parameters
BACKEND="torch_cuda"
CHECKPOINT="config/models/aria-medium-base/model-gen.safetensors"
VARIATIONS=1
TEMP=0.8
MIN_P=0.035
LENGTH=1024
PROMPT_DURATION=999999
SEED=42  # Add this
INPUT_DIRECTORY="trying_to_get_the_chords_from_the_midi"
# Files to process (excluding the ones already processed)
FILES=(
    # "manualy_created_midi/choral_0000_orig_30bits.mid"
    "manualy_created_midi/choral_0000_tweaked_30bits.mid"
    
    # "manualy_created_midi/choral_0000_orig_46bits.mid"
    # "manualy_created_midi/choral_0000_tweaked_46bits.mid"
    

    # "/home/adisi/repos/py/aria/example-prompts/classical.mid"
    
    # "manualy_created_midi/choral_0001_orig_21bits.mid"
    # "manualy_created_midi/choral_0001_orig_9bits.mid"
    # "manualy_created_midi/choral_0001_tweaked_21bits.mid"
    # "manualy_created_midi/choral_0001_tweaked_9bits.mid"
)


per_chorale_directories = sorted([d for d in os.listdir(INPUT_DIRECTORY) 
                            if os.path.isdir(os.path.join(INPUT_DIRECTORY, d))])
for chorale_directory in per_chorale_directories:
    midi_files_in_chorale_directory = sorted([f for f in os.listdir(os.path.join(input_directory, chorale_directory)) 
                                                if f.endswith('.mid')])
    for midi_file in midi_files_in_chorale_directory:
        input_file = os.path.join(INPUT_DIRECTORY, chorale_directory, midi_file)
        output_file = os.path.join(INPUT_DIRECTORY, chorale_directory, midi_file.replace('.mid', '_with_continuation.mid'))
        aria generate \
            --backend "$BACKEND" \
            --checkpoint_path "$CHECKPOINT" \
            --prompt_midi_path "$input_file" \
            --variations "$VARIATIONS" \
            --temp "$TEMP" \
            --min_p "$MIN_P" \
            --save_dir "$output_file" \
            --prompt_duration "$PROMPT_DURATION" \
        
        echo "Continuation generated for $input_file"
        echo "Output: $output_file"
        echo "---"
    done
    minorized_directory = os.path.join(INPUT_DIRECTORY, chorale_directory, 'minorized')
    minorized_files = sorted([f for f in os.listdir(minorized_directory) 
                              if f.endswith('.mid')])
    for minorized_file in minorized_files:
        input_file = os.path.join(minorized_directory, minorized_file)
        output_file = os.path.join(minorized_directory, minorized_file.replace('.mid', '_with_continuation.mid'))
        aria generate \
            --backend "$BACKEND" \
            --checkpoint_path "$CHECKPOINT" \
            --prompt_midi_path "$input_file" \
            --variations "$VARIATIONS" \
            --temp "$TEMP" \
            --min_p "$MIN_P" \
            --save_dir "$output_file" \
            --prompt_duration "$PROMPT_DURATION" \
        
        echo "Continuation generated for $input_file"
        echo "Output: $output_file"
        echo "---"
    done
done

# # Process each file
# for file in "${FILES[@]}"; do
#     # Extract base name without extension
#     basename=$(basename "$file" .mid)
#     output_file="outputs/${basename}_with_continuation.mid"
    
#     echo "Processing: $file"
#     echo "Output: $output_file"
#     echo "---"
    
#     aria generate \
#         --backend "$BACKEND" \
#         --checkpoint_path "$CHECKPOINT" \
#         --prompt_midi_path "$file" \
#         --variations "$VARIATIONS" \
#         --temp "$TEMP" \
#         --min_p "$MIN_P" \
#         --save_dir "$output_file" \
#         --prompt_duration "$PROMPT_DURATION" \
#         # --length "$LENGTH" \
    
#     echo ""
# done

echo "All files processed!"