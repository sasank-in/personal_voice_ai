import json
import sys
from pathlib import Path

POC_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = POC_DIR / "output"
VOICE_STATE = POC_DIR / "voice_state.json"

sys.path.insert(0, str(POC_DIR.parent))

OUTPUT_DIR.mkdir(exist_ok=True)


def load_voice_id() -> str | None:
    if VOICE_STATE.exists():
        return json.loads(VOICE_STATE.read_text())["voice_id"]
    return None


def save_voice_id(voice_id: str) -> None:
    VOICE_STATE.write_text(json.dumps({"voice_id": voice_id}))
