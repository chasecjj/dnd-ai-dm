# Sound Assets

Place audio sprite sheets here:
- `dice-sprites.webm` + `dice-sprites.mp3` — Dice roll and land sounds
- `ceremony-sprites.webm` + `ceremony-sprites.mp3` — Ceremony sounds

Sources:
- SONNISS GDC bundle (free, royalty-free): https://gdc.sonniss.com/
- Freesound.org (CC0 license)

Encode: WAV -> WebM (primary) + MP3 (Safari fallback)
Tool: ffmpeg -i input.wav -c:a libopus output.webm
