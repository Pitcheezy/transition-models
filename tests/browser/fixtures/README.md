# Synthetic observation playback fixtures

These original fixtures contain only FFmpeg-generated colors and geometry. They
contain no broadcast, athlete, private observations, model outputs or human labels.
The invented package in `observation-playback.test.cjs` tests browser behavior only.

Generated with FFmpeg 8.0 using:

```sh
ffmpeg -f lavfi -i 'testsrc2=s=160x96:r=15:d=8' -an -c:v libx264 -preset veryslow -crf 35 -pix_fmt yuv420p -movflags +faststart observation-colors-8s.mp4
ffmpeg -f lavfi -i 'color=c=red:s=64x48' -frames:v 1 -update 1 observation-red.jpg
ffmpeg -f lavfi -i 'color=c=blue:s=64x48' -frames:v 1 -update 1 observation-blue.jpg
```

The MP4 is 8 seconds, 160×96, 15 fps, H.264 with no audio; JPEGs are 64×48.
Fixtures are committed so normal tests require no FFmpeg installation. Tests use
the real immutable Range server and copy the current production UI into an isolated
temporary package. They do not read or modify the running private review package.

The 15 fps fixture has a 66.7 ms frame period. Browser seek assertions allow one
fixture frame plus 25 ms for decoding/clock settlement, not for publication or
pre-pitch eligibility. Scientific comparisons keep their exact DTO thresholds.
