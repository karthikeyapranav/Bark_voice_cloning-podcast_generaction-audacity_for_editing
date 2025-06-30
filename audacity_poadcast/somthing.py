import win32file
try:
    h = win32file.CreateFile(
        r'\\.\pipe\ToSrvPipe',
        win32file.GENERIC_WRITE,
        0, None,
        win32file.OPEN_EXISTING,
        0, None
    )
    win32file.WriteFile(h, b"GetInfo: Type=Commands\n")
    print("✅ Pipe test successful!")
    h.close()
except Exception as e:
    print(f"❌ Pipe test failed: {str(e)}")

    