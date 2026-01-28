import os
import random
import glob
import argparse
import copy
from ariautils.midi import MidiDict
from aria.run import generate

# Config
BASE_DIR = "chorale_continuations"
TRAIN_DIR = "jsb_chorales_midi/train_16th"
CHECKPOINT = "config/models/aria-medium-base/model-gen.safetensors"
NUM_CHORALES = 50

os.makedirs(f"{BASE_DIR}/inputs", exist_ok=True)
os.makedirs(f"{BASE_DIR}/outputs", exist_ok=True)

files = sorted(glob.glob(f"{TRAIN_DIR}/*.mid"))[:NUM_CHORALES]
print(f"Processing {len(files)} chorales...")

for idx, file in enumerate(files):
    print(f"Processing {file} which is the {idx}th file...")
    midi_dict = MidiDict.from_midi(file)
    if not midi_dict.note_msgs:
        continue
    
    max_time = max(midi_dict.tick_to_ms(msg["data"]["end"]) for msg in midi_dict.note_msgs)
    cut1 = random.uniform(0.2, 0.4) * max_time
    cut2 = random.uniform(0.6, 0.8) * max_time
    cuts = sorted([cut1, cut2])
    
    for seg_idx, (start_ms, end_ms) in enumerate([(0, cuts[0]), (0, cuts[1])]):
        seg_midi = copy.deepcopy(midi_dict)
        seg_midi.note_msgs = [
            msg for msg in midi_dict.note_msgs
            if start_ms <= midi_dict.tick_to_ms(msg["data"]["start"]) < end_ms
        ]
        
        if not seg_midi.note_msgs:
            continue
            
        name = f"chorale_{idx:04d}_seg_{seg_idx}"
        input_path = f"{BASE_DIR}/inputs/{name}.mid"
        seg_midi.to_midi().save(input_path)
        
        args = argparse.Namespace(
            backend="torch_cuda",
            checkpoint_path=CHECKPOINT,
            prompt_midi_path=input_path,
            prompt_duration=999999,
            variations=1,
            temp=0.8,
            min_p=0.035,
            length=1024,
            save_dir=f"{BASE_DIR}/outputs/{name}_cont.mid",
            verbose=False,
            print_tokens=False,
            end=False,
            top_p=None,
            compile=False
        )
        
        try:
            generate(args)
            print(f"✓ {name}")
        except Exception as e:
            print(f"✗ {name}: {e}")