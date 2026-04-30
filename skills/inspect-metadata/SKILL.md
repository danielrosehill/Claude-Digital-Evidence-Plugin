---
name: inspect-metadata
description: Use when extracting and analyzing metadata (EXIF, MediaInfo) from files.
model: haiku
---

# Inspect Metadata

Extract metadata from files using ExifTool and MediaInfo, merge results, and report notable fields.

## When to use

- Analyzing file provenance (camera, device, software)
- Identifying GPS location data, timestamps, and modification history
- Flagging temporal inconsistencies (e.g., modify-time predates create-time)
- Documenting encoding, codec, and technical properties for evidence context
- Detecting redacted or stripped metadata

## Inputs to gather

- File path (required)
- `--out <metadata-path>` (optional; write JSON to custom location; defaults to `<file>.metadata.json`)

## Procedure

1. Run `exiftool -j <file>` to extract EXIF data as JSON.
2. Run `mediainfo --Output=JSON <file>` to extract media metadata as JSON.
3. Merge both outputs into a single JSON object with keys `exif` and `mediainfo`.
4. Write merged JSON to `<file>.metadata.json` (or `--out` path if given).
5. Parse and summarize notable fields for user:
   - GPS coordinates, altitude (if present)
   - Capture timestamp (DateTimeOriginal, FileCreateTime)
   - Camera/device model and serial number
   - Software fingerprint (editor, encoder, app name)
   - Duration, frame rate, codec, bitrate (media files)
   - Any modification-time anomalies (e.g., modify-time before creation-time)
6. Report summary to user with key findings and any flagged inconsistencies.

## Output / side effects

- `<file>.metadata.json` — merged exiftool + mediainfo output (not modified)
- User sees a formatted summary of notable fields and any anomalies.

## Safety / constraints

- This is a read-only operation on the original file.
- Large media files may take 10–30 seconds to scan; inform user.
- Some tools may report different timestamps for the same event (e.g., system metadata vs. internal file timestamps); mention this in output.
- Metadata may contain personal information (GPS, device serial); remind user to handle appropriately if sharing.
