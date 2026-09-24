#!/usr/bin/env bash
# Lay the voiceover (demo/vo/lineN.wav) under the recorded demo and export MP4.
# Run after: python demo/record_demo.py  (writes demo/out/vo_starts.tsv and timeline.tsv)
# CUTS="a-b c-d" (recorder clock, seconds) drops dead waiting time, e.g. while a live scan
# runs; voiceover lines after each cut move up by the time removed.
set -euo pipefail
cd "$(dirname "$0")/out"
OFFSET=${OFFSET:-0.34}   # recorder clock vs video clock, measured from the title-card cut
CUTS=${CUTS:-}
END=$(awk '/\tend$/{print $1}' timeline.tsv)
removed_before() {  # seconds of cut footage before recorder time $1 (partial cuts count partly)
  awk -v s="$1" -v cuts="$CUTS" -v o="$OFFSET" 'BEGIN{v=s-o; n=split(cuts,c," "); r=0; for(i=1;i<=n;i++){split(c[i],p,"-"); a=p[1]-o; if (a<0) a=0; e=(v<p[2]-o?v:p[2]-o); if (e>a) r+=e-a} printf "%.3f", r}'
}
DUR=$(awk -v e="$END" -v o="$OFFSET" -v r="$(removed_before "$END")" 'BEGIN{printf "%.2f", e-o-r+0.5}')
vsel="null"
if [ -n "$CUTS" ]; then
  expr=$(awk -v cuts="$CUTS" -v o="$OFFSET" 'BEGIN{n=split(cuts,c," "); for(i=1;i<=n;i++){split(c[i],p,"-"); printf "%sbetween(t,%.3f,%.3f)", (i>1?"+":""), p[1]-o, p[2]-o}}')
  vsel="fps=30,select='not($expr)',setpts=N/30/TB"
fi
inputs=(); filt="[0:v]${vsel}[vout];"; labels=""; i=0
while read -r n t; do
  i=$((i+1)); inputs+=(-i "../vo/line$n.wav")
  ms=$(awk -v s="$t" -v o="$OFFSET" -v r="$(removed_before "$t")" 'BEGIN{d=(s-o-r)*1000; printf "%d",(d<0?0:d)}')
  filt+="[$i:a]aresample=48000,adelay=${ms}|${ms}[a$i];"; labels+="[a$i]"
done < vo_starts.tsv
filt+="${labels}amix=inputs=$i:normalize=0,apad,atrim=0:$DUR,loudnorm=I=-16:TP=-1.5[aout]"
ffmpeg -loglevel error -y -i freshershield-demo.webm "${inputs[@]}" -filter_complex "$filt" \
  -map "[vout]" -map "[aout]" -t "$DUR" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -movflags +faststart freshershield-demo.mp4
echo "demo/out/freshershield-demo.mp4 ($DUR s)"
