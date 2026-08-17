"""PyInstaller entry point for the bundled Vosk worker."""

from mmd_mouth.recognition.worker import main


if __name__ == "__main__":
    raise SystemExit(main())
