# Speaker Identity Workflow

The archive now separates three different tasks:

1. **Diarization**: separate a recording into speaker clusters.
2. **Speaker identification**: compare each cluster with a reviewed Chris Bache
   reference set.
3. **Transcript acceptance**: human review confirms labels before publication.

The tools do not assume that `SPEAKER_00` means Chris across files. Diarization
labels are local to a recording.

## Build The Chris Reference Manifest

The reference manifest is built from existing timecoded diarist files where the
speaker label already identifies Chris Bache. By default it only uses sources
with two or fewer speaker labels, because those are less ambiguous than panels
or audience-heavy sessions.

```bash
make speaker-reference
```

Output:

```text
data/speakers/chris_bache.reference_manifest.json
```

This file contains public source metadata, slug, speaker label, time ranges, and
short text excerpts. It does not contain audio clips or embeddings.

## Extract Local Reference Clips

After source audio exists locally at the paths named in `index.json`, extract
review clips:

```bash
make speaker-reference-clips
```

Output stays ignored under:

```text
build/speaker-reference-clips/chris_bache/
```

If source audio is missing, the clips manifest records `missing_audio`. That is
expected on machines that have not downloaded media.

## Identify Speakers In A New Diarized File

First diarize normally:

```bash
make diarize DIAR_PYTHON=.venv-diarize/bin/python SLUG=<slug> AUDIO=<path-to-audio.mp3>
```

Then compare detected speaker clusters against the Chris reference clips:

```bash
make speaker-identify SLUG=<slug> AUDIO=<path-to-audio.mp3>
```

Output:

```text
reports/diarization/<slug>.speaker_identity.json
```

This report suggests the cluster most similar to the Chris reference bank, but
it is not an archival label by itself. A reviewer should listen to the suggested
segments, confirm the mapping, and only then normalize transcript labels.

## Dependencies

Reference manifest generation is lightweight and offline. Clip extraction needs
`ffmpeg`. Speaker identification needs local ML dependencies:

```bash
python3 -m venv .venv-speakers
. .venv-speakers/bin/activate
pip install speechbrain torch torchaudio
make speaker-identify SPEAKER_PYTHON=.venv-speakers/bin/python SLUG=<slug> AUDIO=<path-to-audio.mp3>
```

Generated clips and embeddings are biometric-like working artifacts. Keep them
local unless the archive owner explicitly approves committing or publishing
them.
