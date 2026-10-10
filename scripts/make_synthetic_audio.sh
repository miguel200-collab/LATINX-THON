#!/bin/zsh
# Makes SYNTHETIC Spanish test clips from the fixture transcripts using the macOS voice "Paulina" (es_MX).
# These are for testing the pipeline only. The real demo clip should be a human voice reading fixtures/transcripts/A.txt.
# Uses only macOS built-ins (say, afconvert). No ffmpeg needed.
set -e
cd "$(dirname "$0")/.."
mkdir -p fixtures/audio
for id in A A_long B C; do
  say -v Paulina -r 170 -o "fixtures/audio/${id}_synthetic.aiff" -f "fixtures/transcripts/${id}.txt"
  afconvert -f WAVE -d LEI16@16000 -c 1 "fixtures/audio/${id}_synthetic.aiff" "fixtures/audio/${id}_synthetic.wav"
  rm "fixtures/audio/${id}_synthetic.aiff"
  # Guard: inside a restricted sandbox, `say` silently writes an empty file.
  bytes=$(afinfo "fixtures/audio/${id}_synthetic.wav" | awk '/audio bytes/ {print $3}')
  if [ -z "$bytes" ] || [ "$bytes" -le 0 ]; then
    echo "ERROR: say produced no audio for ${id} (speech service blocked? run outside a sandbox)" >&2
    exit 1
  fi
  echo "made fixtures/audio/${id}_synthetic.wav (${bytes} bytes of audio)"
done
