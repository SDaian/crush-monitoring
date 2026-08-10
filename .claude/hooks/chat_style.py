#!/usr/bin/env python3
"""Stop hook: hold the chat replies to the style CLAUDE.md asks for.

CLAUDE.md asks for ASD-STE100 Simplified Technical English in the chat, plus
Zinsser's four principles — clarity, simplicity, brevity, humanity. A promise
to follow a style decays inside one long session. This hook measures the reply
instead, and blocks the turn with the specific faults so the model rewrites it.

What it measures, and what it deliberately does not:

  long sentences     over 25 words (STE allows 20 for an instruction, 25 for
                     a description)
  passive voice      "the file is read by the parser"
  compound tenses    "has been", "would have damaged"
  clutter            Zinsser's chapter on it: "very", "basically", "in order
                     to", "the fact that"
  long paragraphs    over 6 sentences

  clarity, humanity  NOT measured. No regex judges those. The block message
                     names them so they stay in view.

Code blocks, tables, links and paths are stripped first: a command line is not
prose and must not count against a word limit.

It blocks once. `stop_hook_active` guards the second pass, so a stubborn reply
costs one retry, never a loop. Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import sys

MAX_WORDS = 25          # STE: 20 for an instruction, 25 for a description
HARD_WORDS = 32         # one sentence this long is enough to send it back
MAX_SENTENCES = 6       # STE: one topic per paragraph, six sentences maximum
MIN_WORDS_TO_JUDGE = 40  # a short reply has no room for a style problem
MIN_FAULTS = 2          # below this, the reply passes: no nitpicking
TAIL_BYTES = 2_000_000  # transcripts reach tens of MB; read only the end

PASSIVE = re.compile(
    r"\b(is|are|was|were|be|been|being|gets|get|got)\s+"
    r"(\w+ed|done|made|shown|seen|taken|given|written|built|kept|held|sent|"
    r"set|put|found|left|lost|drawn|known|meant|told|caught)\b", re.I)
COMPOUND = re.compile(
    r"\b(have|has|had)\s+(been|\w+ed|\w+en)\b"
    r"|\b(will|would|could|should|might|must)\s+have\b", re.I)
CLUTTER = (
    "very", "really", "quite", "somewhat", "actually", "basically",
    "essentially", "in order to", "at this point in time", "the fact that",
    "it should be noted", "needless to say", "for all intents and purposes",
    "a bit of a", "kind of a", "sort of a",
)


def strip_non_prose(text: str) -> str:
    """Remove what is not prose: a command line is not a sentence."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)   # fenced code
    text = re.sub(r"`[^`]*`", " ", text)                 # inline code
    text = "\n".join(l for l in text.splitlines()
                     if not l.lstrip().startswith("|"))  # table rows
    text = re.sub(r"https?://\S+", "link", text)         # URLs
    text = re.sub(r"[\w./-]+/[\w./-]+", "path", text)    # file paths
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)  # headings
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)  # bullet markers
    text = re.sub(r"\*\*?([^*]+)\*\*?", r"\1", text)       # bold / italic
    return text


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if len(p.split()) > 1]


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def faults(text: str) -> list[str]:
    """Every measurable fault, as one display line each."""
    prose = strip_non_prose(text)
    found: list[str] = []

    for sentence in sentences(prose):
        words = len(sentence.split())
        if words > MAX_WORDS:
            found.append(f"{words}-word sentence: \"{sentence[:90]}…\"")

    for pattern, label in ((PASSIVE, "passive voice"),
                           (COMPOUND, "compound tense")):
        for match in pattern.finditer(prose):
            found.append(f"{label}: \"{match.group(0)}\"")

    low = prose.lower()
    for word in CLUTTER:
        if re.search(rf"\b{re.escape(word)}\b", low):
            found.append(f"clutter: \"{word}\"")

    for para in paragraphs(prose):
        count = len(sentences(para))
        if count > MAX_SENTENCES:
            found.append(f"{count}-sentence paragraph (limit {MAX_SENTENCES})")

    return found


def last_reply(path: str) -> str:
    """The text of the most recent assistant message in the transcript."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > TAIL_BYTES:
                handle.seek(size - TAIL_BYTES)
                handle.readline()  # drop the partial line
            lines = handle.read().decode("utf-8", "ignore").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") != "assistant":
            continue
        content = row.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        text = "".join(b.get("text", "") for b in content
                       if isinstance(b, dict) and b.get("type") == "text")
        if text.strip():
            return text
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    # One retry, never a loop: the second pass always lets the turn end.
    if payload.get("stop_hook_active"):
        return 0

    reply = last_reply(payload.get("transcript_path", ""))
    if len(strip_non_prose(reply).split()) < MIN_WORDS_TO_JUDGE:
        return 0

    found = faults(reply)
    hard = any(f.split("-")[0].isdigit() and int(f.split("-")[0]) >= HARD_WORDS
               for f in found)
    if len(found) < MIN_FAULTS and not hard:
        return 0

    shown = found[:8]
    more = len(found) - len(shown)
    print(json.dumps({
        "decision": "block",
        "reason": (
            "The reply misses the chat style CLAUDE.md asks for: ASD-STE100 "
            "Simplified Technical English, and Zinsser's clarity, simplicity, "
            "brevity and humanity.\n\nMeasured faults:\n"
            + "\n".join(f"  - {f}" for f in shown)
            + (f"\n  - …and {more} more" if more > 0 else "")
            + "\n\nRewrite the reply and send it again. Cut each sentence to "
              "25 words or fewer. Use the active voice. Use simple tenses. "
              "Delete the clutter words. Keep a paragraph to six sentences.\n"
              "Two things no check can measure: write with clarity, and write "
              "like a person. Do not strip the warmth to satisfy a counter.\n"
              "Code blocks, tables and paths do not count — only prose."),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
