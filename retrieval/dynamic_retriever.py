import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


# Allow the file to be run directly:
# python retrieval/dynamic_retriever.py
sys.path.append(
    str(Path(__file__).resolve().parent)
)

from chunker import Chunker


class DynamicRetriever:
    """
    Retrieves relevant context from the live web.

    Dynamic retrieval pipeline:

        Task Query
            ↓
        Web Search
            ↓
        URLs + Titles
            ↓
        Fetch Web Pages
            ↓
        Extract Main Content
            ↓
        Reuse Chunker
            ↓
        Filter Bad Chunks
            ↓
        Embed Query + Chunks
            ↓
        Cosine Similarity
            ↓
        Top-K Relevant Chunks

    The returned task structure matches StaticRetriever.

    Dynamic retrieved_context format:

        {
            "content": "...",
            "domain": "...",
            "source": "...",
            "score": 0.84
        }

    DuckDuckGo is the default search backend.

    A different search backend can later be supplied through
    search_fn without changing the rest of the retrieval pipeline.
    """

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(
        self,
        top_k=5,
        num_search_results=8,
        chunk_size=1000,
        overlap=200,
        semantic_threshold=0.55,
        request_timeout=10,
        request_delay=0.3,
        search_fn=None
    ):

        self.top_k = top_k

        self.num_search_results = (
            num_search_results
        )

        self.request_timeout = (
            request_timeout
        )

        self.request_delay = (
            request_delay
        )

        # --------------------------------------------------
        # Reuse the EXISTING Chunker.
        #
        # This means web content goes through the same
        # cleaning, heading-aware splitting, semantic
        # chunking, size control and overlap logic as
        # the local documents.
        # --------------------------------------------------

        self.chunker = Chunker(
            chunk_size=chunk_size,
            overlap=overlap,
            semantic_threshold=semantic_threshold
        )

        # --------------------------------------------------
        # Reuse the SAME embedding model that Chunker uses.
        # --------------------------------------------------

        self.embedder = (
            self.chunker.embedder
        )

        # --------------------------------------------------
        # Search backend.
        #
        # Default:
        #     DuckDuckGo
        #
        # Later:
        #     Google / Bing / Tavily / etc.
        # --------------------------------------------------

        self._search_fn = (
            search_fn
            or self._search_duckduckgo
        )

        # --------------------------------------------------
        # HTTP headers.
        # --------------------------------------------------

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }

    # ==========================================================
    # MAIN RETRIEVAL FUNCTION
    # ==========================================================

    def retrieve(
        self,
        routed_plan
    ):

        """
        Process the routed plan.

        Dynamic tasks are retrieved from the web.

        Static tasks are passed through unchanged.

        The overall structure remains the same as the
        StaticRetriever output.
        """

        retrieval_results = []

        for task in routed_plan:

            # --------------------------------------------------
            # Only dynamically retrieve dynamic tasks.
            # --------------------------------------------------

            if task.get(
                "retrieval_source"
            ) != "dynamic":

                retrieval_results.append(
                    task
                )

                continue

            # --------------------------------------------------
            # Copy original task.
            # --------------------------------------------------

            retrieved_task = task.copy()

            # --------------------------------------------------
            # Get query.
            # --------------------------------------------------

            query = task.get(
                "query",
                ""
            )

            query = self._normalize_query(
                query
            )

            # --------------------------------------------------
            # Missing query.
            # --------------------------------------------------

            if not query:

                retrieved_task[
                    "retrieved_context"
                ] = []

                retrieval_results.append(
                    retrieved_task
                )

                continue

            # --------------------------------------------------
            # Perform dynamic retrieval.
            # --------------------------------------------------

            retrieved_context = (
                self._retrieve_query(
                    query,
                    task.get(
                        "knowledge_type",
                        ""
                    )
                )
            )

            # --------------------------------------------------
            # Attach context.
            # --------------------------------------------------

            retrieved_task[
                "retrieved_context"
            ] = retrieved_context

            retrieval_results.append(
                retrieved_task
            )

        return retrieval_results

    # ==========================================================
    # QUERY NORMALIZATION
    # ==========================================================

    def _normalize_query(
        self,
        query
    ):

        """
        Normalize the query in the same spirit as
        StaticRetriever.
        """

        if not query:
            return ""

        return " ".join(
            str(query).split()
        )

    # ==========================================================
    # QUERY-LEVEL RETRIEVAL
    # ==========================================================

    def _retrieve_query(
        self,
        query,
        knowledge_type=""
    ):

        """
        Performs dynamic retrieval for one query.
        """

        # --------------------------------------------------
        # Search web.
        # --------------------------------------------------

        try:

            search_results = (
                self._search_fn(
                    query,
                    self.num_search_results
                )
            )

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"Search backend failed: {error}"
            )

            return []

        if not search_results:
            return []

        # --------------------------------------------------
        # All chunks from all pages.
        # --------------------------------------------------

        all_chunks = []

        # --------------------------------------------------
        # Process every search result.
        # --------------------------------------------------

        for url, title in search_results:

            # --------------------------------------------------
            # Fetch page.
            # --------------------------------------------------

            html = self._fetch_page(
                url
            )

            if not html:
                continue

            # --------------------------------------------------
            # Extract actual page content.
            # --------------------------------------------------

            self._current_url = url

            text = self._extract_main_text(
                html
            )

            if not text:
                continue

            # --------------------------------------------------
            # Reuse Chunker's cleaning.
            # --------------------------------------------------

            cleaned = (
                self.chunker._clean_text(
                    text
                )
            )

            if not cleaned:
                continue

            # --------------------------------------------------
            # Reuse Chunker's existing chunking logic.
            # --------------------------------------------------

            page_chunks = (
                self.chunker._chunk_text(
                    cleaned
                )
            )

            # --------------------------------------------------
            # Filter bad chunks.
            # --------------------------------------------------

            kept_count = 0

            for content in page_chunks:

                content = content.strip()

                if not content:
                    continue

                if self._is_bad_chunk(
                    content
                ):
                    continue

                kept_count += 1

                all_chunks.append({
                    "content": content,
                    "source": url,
                    "domain": knowledge_type
                })

            print(
                "[DynamicRetriever] "
                f"{url} -> {len(page_chunks)} raw chunks, "
                f"{kept_count} kept"
            )

            # --------------------------------------------------
            # Avoid hitting websites too quickly.
            # --------------------------------------------------

            if self.request_delay:

                time.sleep(
                    self.request_delay
                )

        # --------------------------------------------------
        # Nothing usable retrieved.
        # --------------------------------------------------

        if not all_chunks:
            return []

        # --------------------------------------------------
        # Rank chunks.
        # --------------------------------------------------

        ranked_chunks = (
            self._rank_chunks(
                query,
                all_chunks
            )
        )

        # --------------------------------------------------
        # Return top-k.
        # --------------------------------------------------

        return ranked_chunks[
            :self.top_k
        ]

    # ==========================================================
    # BAD CHUNK FILTER
    # ==========================================================

    def _is_bad_chunk(
        self,
        content
    ):

        """
        Reject chunks that are not useful RAG context.

        Examples rejected:

            # Photosynthesis

            # Dark Matter

            1 2 3 4 5

            References

        The existing Chunker is NOT modified.

        Filtering happens only for dynamically retrieved
        web content.
        """

        normalized = " ".join(
            content.split()
        ).strip()

        if not normalized:
            return True

        # --------------------------------------------------
        # Reject extremely short chunks.
        #
        # Raised from 80 -> 120: short chunks are rarely
        # substantive explanatory text.
        # --------------------------------------------------

        if len(normalized) < 120:
            return True

        # --------------------------------------------------
        # Heading-only chunks.
        #
        # Example:
        #
        #     # Photosynthesis
        #
        # No actual explanatory content.
        # --------------------------------------------------

        if (
            normalized.startswith("#")
            and "\n" not in content
        ):

            heading_text = (
                normalized.lstrip("#").strip()
            )

            if len(heading_text) < 100:
                return True

        lowered = normalized.lower()

        # --------------------------------------------------
        # Citation / bibliography chunks.
        #
        # Example:
        #
        #     "1 2 3 4 5 Bertone, G.; Hooper, D... arXiv:
        #      hep-ph/0404175 doi:10.1016/..."
        #
        # These slip past exact-phrase noise matching because
        # they're rarely JUST the word "references" - they're
        # full citation text mixed with real-looking words.
        # --------------------------------------------------

        if self._is_citation_chunk(lowered):
            return True

        # --------------------------------------------------
        # Common web noise.
        # --------------------------------------------------

        noise_phrases = [
            "cookie policy",
            "privacy policy",
            "terms of use",
            "sign up",
            "log in",
            "subscribe",
            "advertisement",
            "all rights reserved",
            "share this article",
            "related articles",
            "references",
            "bibliography"
        ]

        for phrase in noise_phrases:

            if lowered == phrase:
                return True

        # --------------------------------------------------
        # Reject chunks that are mostly just numbers.
        # Example:
        #
        #     1 2 3 4 5
        # --------------------------------------------------

        words = normalized.split()

        if words:

            numeric_words = sum(
                word.isdigit()
                for word in words
            )

            if (
                len(words) >= 3
                and numeric_words / len(words)
                > 0.70
            ):
                return True

            # --------------------------------------------------
            # Reject punctuation-dense chunks.
            #
            # Citation lists tend to be very punctuation-heavy
            # even when they aren't purely numeric.
            # --------------------------------------------------

            punct_chars = sum(
                1
                for character in normalized
                if character in ".,;:()[]"
            )

            if (
                punct_chars / max(len(normalized), 1)
                > 0.12
            ):
                return True

        return False

    # ==========================================================
    # CITATION CHUNK DETECTION
    # ==========================================================

    def _is_citation_chunk(
        self,
        normalized_lower
    ):

        """
        Detects bibliography/citation-style chunks that slip
        past simple phrase matching.

        Example:

            "1 2 3 4 5 Bertone, G.; Hooper, D.; Silk, J. (2005).
             arXiv: hep-ph/0404175 doi:10.1016/j.physrep..."
        """

        citation_markers = [
            "doi:",
            "arxiv",
            "isbn",
            "bibcode",
            "s2cid",
            "retrieved",
            "issn",
            "archived from the original",
            "pp.",
            "vol."
        ]

        marker_hits = sum(
            marker in normalized_lower
            for marker in citation_markers
        )

        if marker_hits >= 2:
            return True

        # --------------------------------------------------
        # Dense runs of bracketed numbers: [1][2][3]
        # --------------------------------------------------

        if re.search(
            r'(\[\d+\]\s*){3,}',
            normalized_lower
        ):
            return True

        return False

    # ==========================================================
    # DUCKDUCKGO SEARCH
    # ==========================================================

    def _search_duckduckgo(
        self,
        query,
        num_results
    ):

        """
        Default web search backend.

        Uses DuckDuckGo's HTML endpoint.

        No API key is required.

        Returns:

            [
                (url, title),
                ...
            ]
        """

        try:

            response = requests.post(
                "https://html.duckduckgo.com/html/",
                data={
                    "q": query
                },
                headers=self.headers,
                timeout=self.request_timeout
            )

            response.raise_for_status()

        except requests.RequestException as error:

            print(
                "[DynamicRetriever] "
                f"DuckDuckGo search failed: {error}"
            )

            return []

        try:

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            results = []

            seen_urls = set()

            # --------------------------------------------------
            # Extract search result links.
            # --------------------------------------------------

            for link in soup.select(
                "a.result__a"
            ):

                href = link.get(
                    "href"
                )

                title = link.get_text(
                    strip=True
                )

                if not href:
                    continue

                if not title:
                    continue

                if href in seen_urls:
                    continue

                seen_urls.add(
                    href
                )

                results.append(
                    (
                        href,
                        title
                    )
                )

                if (
                    len(results)
                    >= num_results
                ):
                    break

            return results

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"DuckDuckGo parsing failed: {error}"
            )

            return []

    # ==========================================================
    # PAGE FETCHING
    # ==========================================================

    def _fetch_page(
        self,
        url
    ):

        """
        Fetch a web page.

        Only HTML pages are processed.
        """

        try:

            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.request_timeout
            )

            response.raise_for_status()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
            )

            if (
                "html"
                not in content_type.lower()
            ):
                return None

            return response.text

        except requests.RequestException as error:

            print(
                "[DynamicRetriever] "
                f"Page fetch failed for {url}: {error}"
            )

            return None

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"Unexpected fetch error for {url}: {error}"
            )

            return None

    # ==========================================================
    # HTML CONTENT EXTRACTION
    # ==========================================================

    def _extract_main_text(
        self,
        html
    ):

        """
        Extract useful textual content from a web page.

        Removes:

            script
            style
            nav
            header
            footer
            aside
            form
            noscript
            svg
            iframe

        Prefers:

            main
            article
            body

        HTML headings are converted to Markdown so that the
        existing Chunker can recognize them.
        """

        try:

            soup = BeautifulSoup(
                html,
                "html.parser"
            )

            # --------------------------------------------------
            # Remove obvious non-content elements.
            # --------------------------------------------------

            for tag in soup([
                "script",
                "style",
                "nav",
                "header",
                "footer",
                "aside",
                "form",
                "noscript",
                "svg",
                "iframe"
            ]):

                tag.decompose()

            # --------------------------------------------------
            # Kill known citation/reference containers before
            # any text is pulled out.
            #
            # Mainly targets Wikipedia-style pages, but the
            # selectors are harmless on other sites too.
            # --------------------------------------------------

            for tag in soup.select(
                "ol.references, div.reflist, .citation, "
                "sup.reference, #References, .refbegin, "
                ".mw-references-wrap, .navbox, "
                "table.vertical-navbox"
            ):

                tag.decompose()

            # --------------------------------------------------
            # Prefer the actual article/main content.
            # --------------------------------------------------

            content_root = (
                soup.find("main")
                or soup.find("article")
                or soup.body
                or soup
            )

            if not content_root:
                return ""

            # --------------------------------------------------
            # HTML heading → Markdown heading.
            # --------------------------------------------------

            heading_tags = {
                "h1": "#",
                "h2": "##",
                "h3": "###",
                "h4": "####",
                "h5": "#####",
                "h6": "######"
            }

            blocks = []

            # --------------------------------------------------
            # Extract only meaningful structural elements.
            #
            # Wikipedia's <li> elements are mostly nav / TOC /
            # leftover reference fragments rather than article
            # prose, so they're excluded there. Other sites
            # keep <li> since it can hold real content.
            # --------------------------------------------------

            is_wikipedia = (
                "wikipedia.org"
                in getattr(
                    self,
                    "_current_url",
                    ""
                )
            )

            tag_targets = (
                list(heading_tags.keys())
                + ["p"]
            )

            if not is_wikipedia:
                tag_targets.append("li")

            for element in content_root.find_all(
                tag_targets
            ):

                text = element.get_text(
                    " ",
                    strip=True
                )

                if not text:
                    continue

                # --------------------------------------------------
                # Ignore tiny list items that are probably
                # navigation or page controls.
                # --------------------------------------------------

                if (
                    element.name == "li"
                    and len(text) < 30
                ):
                    continue

                # --------------------------------------------------
                # Preserve heading structure.
                # --------------------------------------------------

                if (
                    element.name
                    in heading_tags
                ):

                    blocks.append(
                        f"{heading_tags[element.name]} "
                        f"{text}"
                    )

                else:

                    blocks.append(
                        text
                    )

            # --------------------------------------------------
            # Fallback.
            # --------------------------------------------------

            if not blocks:

                return content_root.get_text(
                    "\n\n",
                    strip=True
                )

            # --------------------------------------------------
            # Join blocks so Chunker can recognize paragraph
            # and heading boundaries.
            # --------------------------------------------------

            return "\n\n".join(
                blocks
            )

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"Content extraction failed: {error}"
            )

            return ""

    # ==========================================================
    # EMBEDDING + RANKING
    # ==========================================================

    def _rank_chunks(
        self,
        query,
        chunks
    ):

        """
        Embed the query and every web chunk.

        Embeddings are normalized.

        Therefore:

            query_vector @ chunk_vector

        is cosine similarity.
        """

        texts = [
            chunk["content"]
            for chunk in chunks
        ]

        try:

            vectors = (
                self.embedder.model.encode(
                    [query] + texts,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
            )

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"Embedding failed: {error}"
            )

            return []

        query_vector = vectors[0]

        chunk_vectors = vectors[1:]

        # --------------------------------------------------
        # Calculate similarity.
        # --------------------------------------------------

        for chunk, vector in zip(
            chunks,
            chunk_vectors
        ):

            chunk["score"] = float(
                query_vector @ vector
            )

        # --------------------------------------------------
        # Highest similarity first.
        # --------------------------------------------------

        return sorted(
            chunks,
            key=lambda chunk: chunk["score"],
            reverse=True
        )


# ==========================================================
# Standalone Testing
# ==========================================================

if __name__ == "__main__":

    retriever = DynamicRetriever(
        top_k=3
    )

    routed_plan = [

        {
            "task_id": 1,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 2,
            "task": "Describe photosynthesis.",
            "knowledge_type": "biology",
            "query": "Photosynthesis",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 3,
            "task": "Explain recursion.",
            "knowledge_type": "programming",
            "query": "Python recursion",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

         {
        "task_id": 5,
        "task": "Analyze the time and space complexity.",
        "knowledge_type": "programming",
        "query": "Analyze the time and space complexity.",
        "priority": "low",
        "planner": "planner_llm",
        "retrieval_source": "dynamic",
        
    }
    ]

    retrieval_results = retriever.retrieve(
        routed_plan
    )

    print(
        json.dumps(
            retrieval_results,
            indent=4,
            ensure_ascii=False
        )
    )