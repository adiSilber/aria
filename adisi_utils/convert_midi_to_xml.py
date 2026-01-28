import os
import subprocess

# 1. Point to your specific AppImage
# Try AppImage first, fallback to AppRun
MSCORE_APPIMAGE = os.path.expanduser("~/bin/musescore3.AppImage")
MSCORE_APPRUN = os.path.expanduser("~/bin/squashfs-root/AppRun")

# Use AppImage if it exists, otherwise use AppRun
if os.path.exists(MSCORE_APPIMAGE):
    MSCORE_PATH = MSCORE_APPIMAGE
elif os.path.exists(MSCORE_APPRUN):
    MSCORE_PATH = MSCORE_APPRUN
else:
    raise FileNotFoundError("MuseScore not found. Check paths.")
def convert_midi_to_xml(input_dir):
    """
    Convert MIDI files to MusicXML using MuseScore.
    
    Args:
        input_dir: Directory containing MIDI files
    """
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.mid', '.midi'))]
    print(f"Found {len(files)} MIDI files. Starting conversion...")

    # 2. Linux Headless Setup for MuseScore
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    
    # Create runtime directory if it doesn't exist
    runtime_dir = "/tmp/runtime-root"
    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
    env["XDG_RUNTIME_DIR"] = runtime_dir
    
    # Additional headless environment variables
    env["DISPLAY"] = ""  # Empty display
    env["QT_X11_NO_MITSHM"] = "1"  # Disable MIT-SHM extension
    
    # Unset problematic variables
    env.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

    for file in files:
        input_path = os.path.join(input_dir, file)
        output_filename = os.path.splitext(file)[0] + ".musicxml"
        output_path = os.path.join(input_dir, output_filename)

        # Command: musescore3.AppImage -o output.xml input.mid
        # Note: MuseScore expects output path BEFORE input path
        cmd = [MSCORE_PATH, "-o", output_path, input_path]
        
        try:
            result = subprocess.run(
                cmd, 
                check=True, 
                env=env, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=60  # 60 second timeout
            )
            print(f"✅ Converted: {file}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to convert: {file} (exit code {e.returncode})")
            if e.stderr:
                print(f"   Error output: {e.stderr[:500]}")
            if e.stdout:
                print(f"   Stdout: {e.stdout[:500]}")
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout converting: {file}")
        except Exception as e:
            print(f"❌ Error converting {file}: {e}")

# Run in current directory
convert_midi_to_xml("debug_stuff")