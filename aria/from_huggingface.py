# i think this file is not really helping - saving it here just in case needed.

from transformers import AutoModelForCausalLM
from transformers import AutoTokenizer
import torch

PROMPT_MIDI_LOAD_PATH = "/home/adisi/repos/py/aria/example-prompts/smooth_jazz.mid"
# CONTINUATION_MIDI_SAVE_PATH = "/home/adisi÷/repos/py/aria/example-prompts/classical.mid" #"/home/adisi/repos/py/aria/aria/output_1.midi"
CONTINUATION_MIDI_SAVE_PATH = "/home/adisi/repos/py/aria/aria/smooth_jazz_output.midi" #"/home/adisi/repos/py/aria/aria/output_1.midi"

print("hi1")


# Determine device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

model = AutoModelForCausalLM.from_pretrained(
    "loubb/aria-medium-base",
    trust_remote_code=True,
    # device = "cuda",
    torch_dtype=torch.float16,  # Fixed: should be torch_dtype, not dtype
    device_map="auto" if device == "cuda" else None,  # Only use device_map on GPU
    low_cpu_mem_usage=True,  # Reduce memory usage during loading
)

print("hi2")

# If not using device_map, manually move to device
# if device == "cpu":
#     model = model.to(device)
# print(f"Model loaded on device: {device}")

tokenizer = AutoTokenizer.from_pretrained(
    "loubb/aria-medium-base",
    trust_remote_code=True,
)


print("hi3")

prompt = tokenizer.encode_from_file(
    PROMPT_MIDI_LOAD_PATH, return_tensors="pt"
)

# def look_on_the_tokens(prompt):
#     print(prompt.input_ids.shape)
#     print(prompt.input_ids)
#     print(prompt.input_ids.tolist())
#     print(prompt.input_ids.tolist()[0])
#     print(prompt.input_ids.tolist()[0][0])
#     print(prompt.input_ids.tolist()[0][0][0])
#     print(prompt.input_ids.tolist()[0][0][0][0])
#     print(prompt.input_ids.tolist()[0][0][0][0][0])

# look_on_the_tokens(prompt)

# Move prompt input_ids to same device as model
if hasattr(prompt, 'input_ids'):
    prompt.input_ids = prompt.input_ids.to(device)
elif isinstance(prompt, dict) and 'input_ids' in prompt:
    prompt['input_ids'] = prompt['input_ids'].to(device)

print("hi4")
prompt_length = prompt.input_ids.shape[-1]
print(f"Prompt length: {prompt_length} tokens")

continuation = model.generate(
    prompt.input_ids[..., :512],
    max_length=prompt_length + 2048,  # Generate up to 2048 new tokens
    do_sample=True,  
    temperature=0.97,  
    top_p=0.95,
    use_cache=True,
)

print("hi5")
print(f"Continuation length: {continuation.shape[-1]} tokens")

# Verify prompt is preserved in continuation
prompt_tokens = prompt.input_ids[0].tolist()
continuation_prompt = continuation[0][:prompt_length].tolist()
if prompt_tokens == continuation_prompt:
    print("✓ Prompt tokens preserved correctly")
    # Decode the full continuation (includes prompt + new tokens)
    full_midi_dict = tokenizer.decode(continuation[0].tolist())
else:
    print("⚠ Warning: Prompt tokens differ! Decoding only new tokens")
    # Decode only new tokens - you'll need to combine with original MIDI manually
    new_tokens = continuation[0][prompt_length:].tolist()
    full_midi_dict = tokenizer.decode(new_tokens)
    print("Note: This saves only the continuation. Combine with original MIDI if needed.")

print("hi6")
full_midi_dict.to_midi().save(CONTINUATION_MIDI_SAVE_PATH)
print("hi7")