from base64 import b64encode
from pathlib import Path

_audio = Path(__file__).with_name("audio") / "parry_andrias.mp3"
DATA_URI = "data:audio/mpeg;base64," + b64encode(_audio.read_bytes()).decode("ascii")
