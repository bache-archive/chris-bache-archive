# INPUT TRANSCRIPT (verbatim)
{raw_transcript_text}

# CONTEXT
Work: Christopher M. Bache — public talk, interview, or panel.
Audience: general readers and scholars.
Desired style: calm, precise, spiritually reflective, faithful to Bache’s voice.
Each speaker must be tagged as **Name:** (e.g., **Chris Bache:** …). Do not invent names.

# SPEAKER NORMALIZATION RULES
- Detect all speakers from the verbatim text; preserve real names exactly when present.
- If a speaker is unidentified (e.g., “Audience Member,” “Interviewer”), use a neutral generic:
  **Host:**, **Interviewer:**, **Moderator:**, **Panelist:**, **Audience:** (do not number unless the source does).
- Always use **Chris Bache:** in dialogue; use “Christopher M. Bache” only in metadata, never in tags.
- Keep tag format EXACTLY as: `**Name:** ` (bold name, colon, one space).
- Do not merge different speakers into one. Do not split one speaker into multiple.
- If the source switches among multiple interviewers, retain their distinct labels if names are provided; otherwise keep **Interviewer:** consistently.
- If a name appears later (e.g., “I’m Sarah”), retroactively standardize earlier turns of that same voice to **Sarah:**.

# GLOSSARY (optional; JSON object)
{glossary_json_or_empty_object}
