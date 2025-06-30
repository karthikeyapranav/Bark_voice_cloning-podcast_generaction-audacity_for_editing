import win32file
import time
import os

# Named pipe endpoints provided by Audacity’s mod-script-pipe
TO_PIPE = r'\\.\pipe\ToSrvPipe'
FR_PIPE = r'\\.\pipe\FromSrvPipe'

def send(cmd: str):
    """
    Send a command to Audacity via the ToSrvPipe.
    Retries up to 5 times, then raises with the last error.
    """
    last_exc = None
    for _ in range(5):
        try:
            h = win32file.CreateFile(
                TO_PIPE,
                win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            win32file.WriteFile(h, (cmd + "\n").encode("utf-8"))
            h.close()
            print(f"[>] {cmd}")
            return
        except Exception as exc:
            last_exc = exc
            time.sleep(0.2)
    # After 5 failed attempts, raise with the last captured exception
    raise RuntimeError(f"❌ Unable to write to {TO_PIPE}: {last_exc}")

def recv(timeout=5):
    """
    Read a single-line response from Audacity’s FromSrvPipe.
    Times out after `timeout` seconds.
    """
    buffer = b""
    start = time.time()
    while time.time() - start < timeout:
        try:
            h = win32file.CreateFile(
                FR_PIPE,
                win32file.GENERIC_READ,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            part = win32file.ReadFile(h, 4096)[1]
            h.close()
            buffer += part
            if b"\n" in part:
                msg = buffer.decode(errors="ignore").strip()
                print(f"[<] {msg}")
                return msg
        except Exception:
            time.sleep(0.1)
    print("[!] recv timed out.")
    return ""

def ensure_pipes():
    """
    Wait until Audacity’s named pipes are visible.
    Raises if they don’t appear in ~6 seconds.
    """
    print("[🔍] Waiting for Audacity pipes…")
    for _ in range(20):
        if os.path.exists(TO_PIPE) and os.path.exists(FR_PIPE):
            print("✅ Pipes are live.")
            return
        time.sleep(0.3)
    raise RuntimeError(
        "❌ Cannot find pipes. Make sure:\n"
        "  1) Audacity is running\n"
        "  2) mod-script-pipe is enabled\n"
        "  3) You restarted Audacity after enabling it"
    )

def main():
    ensure_pipes()

    inp = os.path.abspath("D:/audacity_poadcast/natural_conversation.wav").replace("\\", "/")
    out = os.path.abspath("natural_conversation_final_outputt.wav").replace("\\", "/")
    print(f"[📁] Input : {inp}")
    print(f"[📁] Output: {out}")
    print(f"[🧪] Exists?: {os.path.exists(inp)}")
    if not os.path.exists(inp):
        raise FileNotFoundError(f"Input file not found: {inp}")

    pipeline = [
    f'Import2: Filename="{inp}"',
    'SelectAll:',

    'NoiseReduction: Action=GetProfile',
    'NoiseReduction: Action=Reduce NoiseLevel=9 Sensitivity=6 FrequencySmoothing=3 AttackTime=0.03 ReleaseTime=0.2',

    'FilterCurve: Filter="Low roll-off for speech"',
    'FilterCurve: Filter="Bass Boost"',
    
    'TruncateSilence: Threshold=-40dB Duration=0.5 Action=Truncate Silence=0.3',

    'Compressor: Threshold=-20 NoiseFloor=-40 Ratio=3:1 AttackTime=0.1 ReleaseTime=1 Normalize=True',
    'Limiter: LimitType=SoftLimit InputGain=0 Limit=-3 Hold=10',

    'LoudnessNormalization: TargetLUFS=-16',  # Needs plugin

    'Normalize: PeakLevel=-3',

    f'Export2: Filename="{out}"'
]

    print("\n[🔁] Executing audio pipeline…\n")
    for cmd in pipeline:
        send(cmd)
        recv()
        time.sleep(0.2)

    # Verify that Audacity actually loaded the track 
    print("\n[🔍] Verifying import…")
    send("GetInfo: Type=Tracks")
    tracks = recv()
    if '"name"' in tracks.lower():
        print("✅ Track loaded successfully.")
    else:
        print("❌ No track detected. Import may have failed.")

    print(f"\n[🎉] Done! Check your output at:\n{out}")

if __name__ == "__main__":
    main()
