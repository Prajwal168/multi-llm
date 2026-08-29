from pathlib import Path
import sys
import re

# Allow the file to be run directly:
# python retrieval/chunker.py
sys.path.append(str(Path(__file__).resolve().parent))

from document_loader import DocumentLoader
from embedder import Embedder


class Chunker:
    """
    Splits documents into hybrid structure-aware and semantic chunks.

    Pipeline:

        PDF
          ↓
        Clean text
          ↓
        Heading-aware sections
          ↓
        Paragraph units
          ↓
        Semantic boundary detection
          ↓
        Chunk-size control
          ↓
        Overlap

    The final chunk structure (chunk_id / domain / source / content)
    remains unchanged from the original implementation.

    Changes vs. the original version:
      1. Overlap is now applied consistently everywhere a chunk boundary
         is created — including inside `_split_large_paragraph`, which
         previously had no overlap at all.
      2. Embeddings for an entire document are computed in a single
         batched `encode()` call instead of one call per section, which
         is significantly faster for documents with many sections.
      3. The overlap-selection logic (walk backward, keep whole units
         until the overlap budget is hit) is factored into one shared
         helper so paragraph-level and sentence-level overlap can't
         drift out of sync.
      4. A few defensive edge cases are handled explicitly (empty
         paragraph lists, sections with zero content paragraphs, etc.)
         so they don't crash — they just fall through to producing no
         chunks for that piece, exactly as before.
      5. Running headers/footers and page numbers left over from PDF
         extraction (e.g. "484 | Chapter 19: Advanced Function Topics",
         a title page repeated on every page) are stripped out before
         chunking, both via known footer shapes and via frequency
         (any short line repeated many times across the document is
         almost certainly boilerplate, not content).
      6. Heading detection now recognizes more than Markdown `#`
         headings. PDF-extracted text essentially never contains a
         literal `#`, so the original heading detector silently never
         fired for PDFs and every PDF fell back to plain paragraph
         splitting. It now also recognizes "Chapter N", numbered
         headings like "18.1 Self Join", and short ALL-CAPS heading
         lines.
      7. Oversized paragraphs that are source code / REPL transcripts
         (detected via `>>>`, `...` continuations, `def`/`class`
         lines, indentation) are now split at line/statement
         boundaries instead of sentence boundaries. Splitting code on
         '.' characters previously tore statements apart at things
         like `L[1:]` or the literal `2.2`.
      8. Back-to-back identical chunks (which can occur when overlap
         logic and small trailing paragraphs interact) are no longer
         emitted twice for the same source file.
    """

    # ----------------------------------------------------------
    # Boilerplate line patterns: obvious footer/page-number shapes
    # left behind by PDF text extraction.
    # ----------------------------------------------------------
    _PAGE_FOOTER_PATTERNS = [
        re.compile(r"^\d{1,4}\s*[\|\-–]\s*chapter\s+\d+.*$", re.IGNORECASE),
        re.compile(r"^chapter\s+\d+.*[\|\-–]\s*\d{1,4}$", re.IGNORECASE),
        re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
        re.compile(r"^\d{1,4}$"),
    ]

    # ----------------------------------------------------------
    # Heading patterns beyond Markdown '#' headings.
    # ----------------------------------------------------------
    _MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+.+")
    _CHAPTER_SECTION_RE = re.compile(
        r"^(chapter|section)\s+\d+([:.\s].{0,80})?$", re.IGNORECASE
    )
    _NUMBERED_HEADING_RE = re.compile(
        r"^\d{1,2}(\.\d{1,2}){1,3}[:.]?\s+[A-Z][^.]{2,80}$"
    )
    _ALL_CAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,:\-'&]{2,69}$")

    # ----------------------------------------------------------
    # Code / REPL transcript line patterns.
    # ----------------------------------------------------------
    _CODE_LINE_RE = re.compile(
        r"^(>>>|\.\.\.|\s{4,}\S|def\s+\w+\s*\(|class\s+\w+\s*[:\(])"
    )

    def __init__(
        self,
        chunk_size=1000,
        overlap=200,
        semantic_threshold=0.55
    ):

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.semantic_threshold = semantic_threshold

        self.loader = DocumentLoader()

        # Use the same embedding model already used
        # by the rest of the RAG pipeline.
        self.embedder = Embedder()

    # ==========================================================
    # DOCUMENT CHUNKING
    # ==========================================================

    def chunk_documents(self, documents_path):

        chunks = []

        documents_path = Path(documents_path)

        if not documents_path.exists():
            print(
                f"Warning: documents path '{documents_path}' does "
                "not exist; no chunks produced."
            )
            return chunks

        chunk_id = 1

        supported_extensions = {
            ".md",
            ".pdf"
        }

        for file in documents_path.rglob("*"):

            if file.suffix.lower() not in supported_extensions:
                continue

            text = self.loader.load(file)

            if not text or not text.strip():
                continue

            # --------------------------------------------------
            # Clean extracted PDF text
            # --------------------------------------------------

            text = self._clean_text(text)

            if not text.strip():
                continue

            domain = file.parent.name

            document_chunks = self._chunk_text(text)

            for content in document_chunks:

                if not content or not content.strip():
                    continue

                normalized_content = content.strip()

                # --------------------------------------------------
                # Guard against back-to-back identical chunks. This
                # can happen when overlap logic and a short trailing
                # paragraph interact, producing the same text twice
                # in a row for the same file.
                # --------------------------------------------------

                if (
                    chunks
                    and chunks[-1]["source"] == str(file)
                    and chunks[-1]["content"].strip() == normalized_content
                ):
                    continue

                chunks.append({

                    "chunk_id": chunk_id,

                    "domain": domain,

                    "source": str(file),

                    "content": content

                })

                chunk_id += 1

        return chunks

    # ==========================================================
    # PDF TEXT CLEANING
    # ==========================================================

    def _clean_text(self, text):

        # Normalize line endings
        text = text.replace(
            "\r\n",
            "\n"
        )

        text = text.replace(
            "\r",
            "\n"
        )

        # --------------------------------------------------
        # Strip running headers/footers and page numbers.
        #
        # This must happen BEFORE the "single line break -> space"
        # step below, because once a footer line is glued onto the
        # preceding sentence it can no longer be identified as its
        # own line.
        # --------------------------------------------------

        text = self._remove_boilerplate_lines(text)

        # --------------------------------------------------
        # Fix hyphenated words caused by PDF line wrapping
        #
        # Example:
        #
        # recur-
        # sion
        #
        # becomes:
        #
        # recursion
        # --------------------------------------------------

        text = re.sub(
            r"(\w)-\n(\w)",
            r"\1\2",
            text
        )

        # --------------------------------------------------
        # Normalize spaces
        # --------------------------------------------------

        text = re.sub(
            r"[ \t]+",
            " ",
            text
        )

        # --------------------------------------------------
        # Replace single PDF line breaks with spaces.
        #
        # Blank lines are preserved because they normally
        # represent paragraph boundaries.
        #
        # This is code-aware: a plain regex collapse here would
        # flatten REPL/code transcripts (one statement per line,
        # single newlines between them) into one continuous line
        # of prose *before* `_is_code_like` / `_split_code_paragraph`
        # ever get a chance to see the line structure they depend
        # on. So instead of an unconditional collapse, newlines
        # adjacent to a code-like line are preserved.
        # --------------------------------------------------

        text = self._collapse_wrapped_lines(text)

        # --------------------------------------------------
        # Normalize excessive blank lines
        # --------------------------------------------------

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        return text.strip()

    def _collapse_wrapped_lines(self, text):

        """
        Collapses single PDF line-wrap breaks into spaces, while
        preserving real newlines around any line that looks like
        code/REPL content (per `_CODE_LINE_RE`).

        Without this, `_clean_text` would merge a whole REPL
        transcript such as:

            >>> def mysum(L):
            ...     if not L:
            ...         return 0

        into a single flattened line of prose, so downstream
        `_is_code_like` (which counts `_CODE_LINE_RE` matches per
        `\\n`-delimited line) would see one "line" that doesn't
        start with `>>>` and never detect it as code — routing it
        into sentence-splitting instead of `_split_code_paragraph`,
        which is how code paragraphs were silently getting cut off
        mid-statement.

        Blank lines (paragraph boundaries) are always preserved.
        """

        lines = text.split("\n")

        result_lines = []

        # `None` means "nothing buffered yet" — distinct from an
        # empty *content* line, which is a real blank line that
        # must be preserved as its own entry, not discarded.
        buffer = None

        for line in lines:

            stripped = line.strip()

            # Blank line: this is a paragraph boundary. Flush
            # whatever's buffered, then emit the blank line itself
            # as its own entry so "\n\n" boundaries survive for
            # downstream paragraph splitting (`_split_into_sections`,
            # `_split_heading_and_paragraphs`, etc.). Previously the
            # blank line was assigned into `buffer` and then
            # silently overwritten on the next loop iteration
            # without ever being appended — collapsing every
            # paragraph boundary in the document into nothing.
            if stripped == "":
                if buffer is not None:
                    result_lines.append(buffer)
                    buffer = None
                result_lines.append(line)
                continue

            if buffer is None:
                buffer = line
                continue

            buffer_stripped = buffer.strip()

            # Either side looks like code/REPL content: keep the
            # newline so line structure survives into
            # `_is_code_like` / `_split_code_paragraph`.
            if (
                self._CODE_LINE_RE.match(buffer_stripped)
                or self._CODE_LINE_RE.match(stripped)
            ):
                result_lines.append(buffer)
                buffer = line
                continue

            # Otherwise this is an ordinary PDF line-wrap: merge
            # with a space, dropping the newline between them.
            buffer = buffer + " " + stripped

        if buffer is not None:
            result_lines.append(buffer)

        return "\n".join(result_lines)

    # ==========================================================
    # BOILERPLATE / HEADER-FOOTER REMOVAL
    # ==========================================================

    def _remove_boilerplate_lines(self, text):

        """
        Removes running headers/footers and page numbers that PDF
        extraction leaves behind as standalone lines.

        Three passes:
          1. Pattern-based: obvious footer shapes such as
             "484 | Chapter 19: Advanced Function Topics" or a bare
             page number sitting alone on its own line.
          2. Exact-frequency-based: any short line that repeats
             verbatim (case-insensitively) several times across the
             document is treated as boilerplate — e.g. a book title
             reprinted on every page — UNLESS it looks like source
             code or a REPL transcript. Code idioms (e.g. a `def`
             line reused across examples/exercises) legitimately
             repeat several times in a technical book and are real
             content, not layout artifacts.
          3. Trailing-page-number-based: running headers where the
             page number is glued directly onto the header text with
             no separator (e.g. "GoalKicker.com - SQL Notes for
             Professionals 55" / "...60" / "...59") don't repeat as
             an *exact* string, since the number differs each time.
             This pass strips a trailing 1-4 digit number before
             comparing, so these are still recognized as the same
             recurring header.
        """

        lines = text.split("\n")

        # ----------------------------------------------------
        # Pass 1: pattern-based footer / page-number removal.
        # ----------------------------------------------------

        pattern_filtered = []

        for line in lines:

            stripped = line.strip()

            if stripped and any(
                pattern.match(stripped)
                for pattern in self._PAGE_FOOTER_PATTERNS
            ):
                continue

            pattern_filtered.append(line)

        lines = pattern_filtered

        # ----------------------------------------------------
        # Build frequency tables for pass 2 (exact match) and
        # pass 3 (trailing-page-number-normalized match), both
        # skipping lines that look like code/REPL content.
        # ----------------------------------------------------

        exact_counts = {}
        prefix_counts = {}

        for line in lines:

            stripped = line.strip()

            if not stripped or len(stripped) > 120:
                continue

            if self._CODE_LINE_RE.match(stripped):
                continue

            exact_key = stripped.lower()
            exact_counts[exact_key] = exact_counts.get(exact_key, 0) + 1

            prefix_key = re.sub(
                r"\s*\d{1,4}\s*$", "", stripped
            ).strip().lower()

            # Only meaningful if stripping the trailing number
            # actually changed something, and what's left still
            # looks like a real title fragment rather than noise.
            if prefix_key and prefix_key != exact_key and len(prefix_key) >= 6:
                prefix_counts[prefix_key] = prefix_counts.get(prefix_key, 0) + 1

        exact_boilerplate = {
            key for key, count in exact_counts.items() if count >= 3
        }

        prefix_boilerplate = {
            key for key, count in prefix_counts.items() if count >= 3
        }

        if not exact_boilerplate and not prefix_boilerplate:
            return "\n".join(lines)

        cleaned = []

        for line in lines:

            stripped = line.strip()

            if not stripped:
                cleaned.append(line)
                continue

            if self._CODE_LINE_RE.match(stripped):
                cleaned.append(line)
                continue

            exact_key = stripped.lower()

            if exact_key in exact_boilerplate:
                continue

            prefix_key = re.sub(
                r"\s*\d{1,4}\s*$", "", stripped
            ).strip().lower()

            if prefix_key in prefix_boilerplate:
                continue

            cleaned.append(line)

        return "\n".join(cleaned)

    # ==========================================================
    # MAIN CHUNKING LOGIC
    # ==========================================================

    def _chunk_text(self, text):

        # --------------------------------------------------
        # Step 1:
        # Preserve document headings.
        # --------------------------------------------------

        sections = self._split_into_sections(
            text
        )

        if not sections:
            return []

        # --------------------------------------------------
        # Step 2:
        # Batch-embed every paragraph in the whole document
        # up front. This replaces the old per-section
        # `encode()` calls with a single call, which is much
        # faster for documents with many sections since most
        # embedding backends have meaningful fixed overhead
        # per call.
        # --------------------------------------------------

        section_paragraphs = []
        all_paragraphs_for_embedding = []

        for section in sections:

            section = section.strip()

            if not section or len(section) <= self.chunk_size:
                # Small/empty sections don't need embeddings —
                # they pass through untouched (or get skipped).
                section_paragraphs.append(None)
                continue

            heading, paragraphs = self._split_heading_and_paragraphs(
                section
            )

            section_paragraphs.append((heading, paragraphs))

            all_paragraphs_for_embedding.extend(paragraphs)

        embeddings_by_text = {}

        if all_paragraphs_for_embedding:

            vectors = self.embedder.model.encode(
                all_paragraphs_for_embedding,
                convert_to_numpy=True,
                normalize_embeddings=True
            )

            # Map each paragraph string to its embedding. If the same
            # paragraph text repeats, later occurrences simply reuse
            # the same vector, which is harmless since we only ever
            # compare adjacent paragraphs within a single section.
            for paragraph, vector in zip(
                all_paragraphs_for_embedding, vectors
            ):
                embeddings_by_text[paragraph] = vector

        # --------------------------------------------------
        # Step 3:
        # Process each logical section.
        # --------------------------------------------------

        chunks = []

        for section, prepared in zip(sections, section_paragraphs):

            section = section.strip()

            if not section:
                continue

            # Small sections remain intact.
            if len(section) <= self.chunk_size:

                chunks.append(section)

                continue

            heading, paragraphs = prepared

            section_chunks = self._semantic_chunk_section(
                heading,
                paragraphs,
                embeddings_by_text
            )

            chunks.extend(
                section_chunks
            )

        return chunks

    # ==========================================================
    # HEADING-AWARE SECTION SPLITTING
    # ==========================================================

    def _split_into_sections(self, text):

        """
        Detect Markdown-style headings.

        The heading remains attached to its section.
        """

        lines = text.split("\n")

        sections = []

        current_section = []

        found_heading = False

        for line in lines:

            stripped = line.strip()

            is_heading = self._is_heading_line(stripped)

            if is_heading:

                found_heading = True

                if current_section:

                    section = "\n".join(
                        current_section
                    ).strip()

                    if section:
                        sections.append(
                            section
                        )

                current_section = [
                    stripped
                ]

            else:

                current_section.append(
                    line
                )

        if current_section:

            section = "\n".join(
                current_section
            ).strip()

            if section:
                sections.append(
                    section
                )

        # --------------------------------------------------
        # If the document has no detectable headings,
        # retain paragraph-based processing.
        # --------------------------------------------------

        if not found_heading:

            return [
                paragraph.strip()
                for paragraph in text.split(
                    "\n\n"
                )
                if paragraph.strip()
            ]

        return sections

    # ==========================================================
    # HEADING DETECTION (shared by section splitting and
    # heading/paragraph splitting so the two can't drift apart)
    # ==========================================================

    def _is_heading_line(self, stripped):

        """
        Recognizes heading-like lines beyond Markdown '#' headings.

        PDF-to-text extraction essentially never produces literal
        '#' characters, so relying on Markdown syntax alone means
        heading detection never fires for PDFs and every PDF falls
        back to plain paragraph splitting. This adds:
          - "Chapter N" / "Section N" lines
          - Numbered headings like "18.1 Self Join"
          - Short ALL-CAPS heading lines (e.g. "JOIN TERMINOLOGY")
        while staying conservative (length caps, requiring the line
        to look like a title rather than a sentence) to avoid
        misfiring on ordinary body text.
        """

        if not stripped:
            return False

        if self._MARKDOWN_HEADING_RE.match(stripped):
            return True

        if len(stripped) <= 90 and self._CHAPTER_SECTION_RE.match(stripped):
            return True

        if len(stripped) <= 90 and self._NUMBERED_HEADING_RE.match(stripped):
            return True

        if (
            len(stripped) <= 70
            and stripped == stripped.upper()
            and sum(char.isalpha() for char in stripped) >= 3
            and self._ALL_CAPS_HEADING_RE.match(stripped)
        ):
            return True

        return False

    # ==========================================================
    # HEADING / PARAGRAPH SPLITTING (used before embedding)
    # ==========================================================

    def _split_heading_and_paragraphs(self, section):

        """
        Splits a section into (heading, paragraphs), where heading
        is "" if the section doesn't start with a detected heading.
        """

        paragraphs = [
            paragraph.strip()
            for paragraph in section.split(
                "\n\n"
            )
            if paragraph.strip()
        ]

        heading = ""

        if paragraphs and self._is_heading_line(paragraphs[0]):

            heading = paragraphs[0]

            paragraphs = paragraphs[1:]

        return heading, paragraphs

    # ==========================================================
    # SEMANTIC CHUNKING
    # ==========================================================

    def _semantic_chunk_section(
        self,
        heading,
        paragraphs,
        embeddings_by_text
    ):

        """
        Creates semantic chunks inside a heading-aware section.

        Adjacent paragraphs are compared using precomputed
        embeddings (see `_chunk_text`).

        If semantic similarity drops below the threshold,
        a new semantic boundary is created.

        Chunk-size limits are still enforced.
        """

        if not paragraphs:

            return [heading] if heading else []

        if len(paragraphs) == 1 and not heading:

            return self._split_large_paragraph(
                paragraphs[0]
            )

        embeddings = [
            embeddings_by_text[paragraph]
            for paragraph in paragraphs
        ]

        chunks = []

        current_parts = []

        current_length = 0

        # --------------------------------------------------
        # Add heading to the first semantic chunk.
        # --------------------------------------------------

        if heading:

            current_parts.append(
                heading
            )

            current_length = (
                len(heading) + 2
            )

        # --------------------------------------------------
        # Process paragraphs.
        # --------------------------------------------------

        for index, paragraph in enumerate(
            paragraphs
        ):

            paragraph_length = len(
                paragraph
            )

            semantic_boundary = False

            # --------------------------------------------------
            # Compare current paragraph with previous paragraph.
            # --------------------------------------------------

            if index > 0:

                similarity = float(
                    embeddings[index - 1]
                    @
                    embeddings[index]
                )

                if (
                    similarity
                    < self.semantic_threshold
                ):

                    semantic_boundary = True

            # --------------------------------------------------
            # Size boundary.
            # --------------------------------------------------

            size_boundary = (
                current_parts
                and
                current_length
                + paragraph_length
                + 2
                > self.chunk_size
            )

            # --------------------------------------------------
            # Create a new chunk when either:
            #
            # 1. semantic meaning changes
            # 2. chunk becomes too large
            # --------------------------------------------------

            if (
                current_parts
                and
                (
                    semantic_boundary
                    or
                    size_boundary
                )
            ):

                chunks.append(
                    "\n\n".join(
                        current_parts
                    )
                )

                # ----------------------------------------------
                # Preserve overlap (whole paragraphs, walking
                # backward from the end of the finished chunk).
                # ----------------------------------------------

                current_parts, current_length = self._take_overlap(
                    current_parts
                )

            # --------------------------------------------------
            # Paragraph larger than chunk size.
            # --------------------------------------------------

            if paragraph_length > self.chunk_size:

                if current_parts:

                    chunks.append(
                        "\n\n".join(
                            current_parts
                        )
                    )

                    current_parts = []

                    current_length = 0

                large_chunks = (
                    self._split_large_paragraph(
                        paragraph
                    )
                )

                chunks.extend(
                    large_chunks
                )

                continue

            current_parts.append(
                paragraph
            )

            current_length += (
                paragraph_length + 2
            )

        # --------------------------------------------------
        # Final chunk.
        # --------------------------------------------------

        if current_parts:

            chunks.append(
                "\n\n".join(
                    current_parts
                )
            )

        return chunks

    # ==========================================================
    # SHARED OVERLAP HELPER
    # ==========================================================

    def _take_overlap(self, parts):

        """
        Given the list of units (paragraphs or sentences) that made
        up a just-finished chunk, walk backward from the end and
        keep whole units until the overlap budget (self.overlap
        characters) is reached. Returns (kept_parts, kept_length),
        used to seed the next chunk.

        This is the single source of truth for overlap selection,
        used by both paragraph-level chunking and sentence-level
        chunking of oversized paragraphs — so the two paths can't
        silently drift out of sync.
        """

        overlap_parts = []
        overlap_length = 0

        for part in reversed(parts):

            part_length = len(part)

            if (
                overlap_length
                + part_length
                + 2
                > self.overlap
            ):
                break

            overlap_parts.insert(0, part)

            overlap_length += part_length + 2

        return overlap_parts, overlap_length

    # ==========================================================
    # LARGE PARAGRAPH SPLITTING
    # ==========================================================

    def _split_large_paragraph(
        self,
        text
    ):

        """
        Splits very large paragraphs at sentence boundaries.

        Unlike the original implementation, overlap is now applied
        between consecutive chunks here too — using the same
        `_take_overlap` helper as the paragraph-level chunker —
        so an oversized paragraph doesn't lose retrieval context
        at its internal chunk boundaries.

        Source code / REPL transcripts are routed to
        `_split_code_paragraph` instead, since sentence-splitting on
        '.' characters tears code apart at things like `L[1:]` or the
        literal `2.2` inside a list.
        """

        if self._is_code_like(text):
            return self._split_code_paragraph(text)

        sentences = (
            self._split_sentences(text)
        )

        if not sentences:
            return []

        chunks = []

        current = []

        current_length = 0

        for sentence in sentences:

            sentence_length = len(
                sentence
            )

            if (
                current
                and
                current_length
                + sentence_length
                + 1
                > self.chunk_size
            ):

                chunks.append(
                    " ".join(current)
                )

                current, current_length = self._take_overlap(
                    current
                )

            current.append(
                sentence
            )

            current_length += (
                sentence_length + 1
            )

        if current:

            chunks.append(
                " ".join(current)
            )

        return chunks

    # ==========================================================
    # CODE / REPL TRANSCRIPT DETECTION AND SPLITTING
    # ==========================================================

    def _is_code_like(self, text):

        """
        Heuristic check for whether a paragraph is source code or a
        REPL transcript, so it can be split at line/statement
        boundaries instead of sentence boundaries.
        """

        lines = [line for line in text.split("\n") if line.strip()]

        if not lines:
            return False

        code_like_lines = sum(
            1
            for line in lines
            if self._CODE_LINE_RE.match(line)
        )

        return (code_like_lines / len(lines)) >= 0.25

    def _split_code_paragraph(self, text):

        """
        Splits an oversized code/REPL-style paragraph at line
        boundaries instead of sentence boundaries.

        Each '>>>' prompt line absorbs any immediately following
        '...' continuation lines into one atomic unit, so a
        multi-line statement is never torn apart mid-way. Overlap
        between chunks uses the same `_take_overlap` helper as
        every other split path.
        """

        lines = [line for line in text.split("\n") if line.strip()]

        if not lines:
            return []

        units = []
        current_unit = []

        for line in lines:

            stripped = line.strip()

            if stripped.startswith(">>>") and current_unit:

                units.append("\n".join(current_unit))

                current_unit = [line]

            else:

                current_unit.append(line)

        if current_unit:
            units.append("\n".join(current_unit))

        chunks = []

        current = []

        current_length = 0

        for unit in units:

            unit_length = len(unit)

            if (
                current
                and current_length + unit_length + 1 > self.chunk_size
            ):

                chunks.append(
                    "\n".join(current)
                )

                current, current_length = self._take_overlap(current)

            current.append(unit)

            current_length += unit_length + 1

        if current:

            chunks.append(
                "\n".join(current)
            )

        return chunks

    # ==========================================================
    # SENTENCE SPLITTING
    # ==========================================================

    def _split_sentences(
        self,
        text
    ):

        sentences = re.split(
            r"(?<=[.!?])\s+",
            text
        )

        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]


# ==========================================================
# STANDALONE TESTING
# ==========================================================

if __name__ == "__main__":

    chunker = Chunker(
        chunk_size=1000,
        overlap=200,
        semantic_threshold=0.55
    )

    chunks = chunker.chunk_documents(
        "documents"
    )

    print(
        f"\nTotal Chunks: {len(chunks)}\n"
    )

    for chunk in chunks[:10]:

        print(
            f"Chunk ID : {chunk['chunk_id']}"
        )

        print(
            f"Domain   : {chunk['domain']}"
        )

        print(
            f"Source   : {chunk['source']}"
        )

        print(
            f"Characters: {len(chunk['content'])}"
        )

        print("\nContent Preview:")

        print(
            chunk["content"][:500]
        )

        print("-" * 80)