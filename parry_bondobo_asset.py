from base64 import b64encode
from pathlib import Path

_audio = Path(__file__).with_name("audio") / "parry_bondobo.webm"
DATA_URI = "data:audio/webm;base64," + b64encode(_audio.read_bytes()).decode("ascii")
