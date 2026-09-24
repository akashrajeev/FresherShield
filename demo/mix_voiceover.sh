#!/usr/bin/env bash
# Lay the voiceover (demo/vo/lineN.wav) under the recorded demo and export MP4.
# Run after: FS_OFFLINE=1 python demo/record_demo.py  (writes demo/out/vo_starts.tsv)
set -euo pipefail
cd "$(dirname "$0")/out"
OFFSET=${OFFSET:-0.34}   # recorder clock vs video clock, measured from the title-card cut
END=$(awk '/\tend$/{print $1}' timeline.tsv)
DUR=$(awk -v e="$END" -v o="$OFFSET" 'BEGIN{printf "%.2f", e-o+0.5}')
inputs=(); filt=""; labels=""; i=0
while read -r n t; do
  i=$((i+1)); inputs+=(-i "../vo/line$n.wav")
  ms=$(awk -v s="$t" -v o="$OFFSET" 'BEGIN{printf "%d",(s-o)*1000}')
  filt+="[$i:a]aresample=48000,adelay=${ms}|${ms}[a$i];"; labels+="[a$i]"
done < vo_starts.tsv
filt+="${labels}amix=inputs=$i:normalize=0,apad,atrim=0:$DUR,loudnorm=I=-16:TP=-1.5[aout]"
ffmpeg -loglevel error -y -i freshershield-demo.webm "${inputs[@]}" -filter_complex "$filt" \
  -map 0:v -map "[aout]" -t "$DUR" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -movflags +faststart freshershield-demo.mp4
echo "demo/out/freshershield-demo.mp4 ($DUR s)"
