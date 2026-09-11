import json
import os
import re
import sys
import time
import concurrent.futures
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

    If DuckDuckGo fails outright, returns a non-200 status
    (e.g. 202 under rate limiting / bot detection), or returns
    200 with no parsable result links (soft block / captcha
    page), the search automatically falls back to Tavily
    (search_depth="basic") for that query. Requires
    TAVILY_API_KEY to be set in the environment for the
    fallback to actually work; otherwise it just logs and
    returns no results for that query.

    A different primary search backend can later be supplied
    through search_fn without changing the rest of the
    retrieval pipeline. Note: search_fn, if supplied, replaces
    DuckDuckGo entirely - the DuckDuckGo -> Tavily fallback
    chain described above only applies to the default backend.
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
        search_fn=None,
        max_workers=3
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
        # Max number of dynamic tasks processed concurrently
        # in a single retrieve() call. Bounded to avoid
        # hammering the search backend / target websites and
        # to keep concurrent embedder.encode() calls sane.
        # --------------------------------------------------

        self.max_workers = max_workers

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
        #     DuckDuckGo (with Tavily as an automatic
        #     fallback - see _search_duckduckgo)
        #
        # Later:
        #     Google / Bing / etc, via search_fn.
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

        # --------------------------------------------------
        # Tavily fallback config.
        #
        # Only used when DuckDuckGo fails, returns a non-200
        # status (e.g. 202), or returns 200 with no parsable
        # results. Deliberately "basic" search_depth, not
        # "advanced" - this is a cheap fallback, not a
        # primary backend.
        # --------------------------------------------------

        self.tavily_api_key = (
            os.environ.get("TAVILY_API_KEY")
        )

        self.tavily_search_depth = "basic"

        if not self.tavily_api_key:

            print(
                "[DynamicRetriever] "
                "Warning: TAVILY_API_KEY not set. "
                "If DuckDuckGo starts returning 202/blocked "
                "responses, searches will fail with no "
                "fallback available."
            )

    # ==========================================================
    # MAIN RETRIEVAL FUNCTION
    # ==========================================================

    def retrieve(
        self,
        routed_plan
    ):

        """
        Process the routed plan.

        Dynamic tasks are retrieved from the web, concurrently
        (up to self.max_workers at a time).

        Static tasks are passed through unchanged.

        The overall structure remains the same as the
        StaticRetriever output, and result order matches the
        order of routed_plan regardless of thread completion
        order.
        """

        retrieval_results = [None] * len(routed_plan)

        dynamic_indices = []
        dynamic_tasks = []

        # --------------------------------------------------
        # Split out dynamic tasks. Everything else passes
        # through unchanged, in place.
        # --------------------------------------------------

        for index, task in enumerate(routed_plan):

            if task.get("retrieval_source") != "dynamic":

                retrieval_results[index] = task

                continue

            dynamic_indices.append(index)
            dynamic_tasks.append(task)

        # --------------------------------------------------
        # Nothing dynamic to do.
        # --------------------------------------------------

        if not dynamic_tasks:
            return retrieval_results

        # --------------------------------------------------
        # Run dynamic tasks concurrently. Each task gets its
        # own web search + fetch + chunk + embed cycle, run
        # on a worker thread. A failure in one task doesn't
        # abort the others.
        # --------------------------------------------------

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as pool:

            future_to_index = {
                pool.submit(
                    self._retrieve_single_task,
                    task
                ): index
                for index, task in zip(
                    dynamic_indices,
                    dynamic_tasks
                )
            }

            for future in concurrent.futures.as_completed(
                future_to_index
            ):

                index = future_to_index[future]

                try:

                    retrieval_results[index] = (
                        future.result()
                    )

                except Exception as error:

                    print(
                        "[DynamicRetriever] "
                        f"Task failed: {error}"
                    )

                    fallback_task = (
                        routed_plan[index].copy()
                    )

                    fallback_task[
                        "retrieved_context"
                    ] = []

                    retrieval_results[index] = (
                        fallback_task
                    )

        return retrieval_results

    # ==========================================================
    # SINGLE-TASK RETRIEVAL (used by the thread pool in retrieve)
    # ==========================================================

    def _retrieve_single_task(
        self,
        task
    ):

        """
        Runs the full dynamic retrieval pipeline for one task.
        Safe to call from a worker thread: no shared mutable
        instance state is written here (see _extract_main_text,
        which takes url as an argument rather than reading
        self._current_url).
        """

        retrieved_task = task.copy()

        query = self._normalize_query(
            task.get("query", "")
        )

        if not query:

            retrieved_task["retrieved_context"] = []

            return retrieved_task

        retrieved_task["retrieved_context"] = (
            self._retrieve_query(
                query,
                task.get("knowledge_type", "")
            )
        )

        return retrieved_task

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
        # Stop fetching further pages once we have comfortably
        # more good candidates than top_k, instead of always
        # working through every one of num_search_results URLs.
        # Ranking still picks the best top_k from whatever was
        # collected — this just avoids fetching/chunking/
        # embedding pages that were never going to be needed.
        # Restored after being dropped in the concurrency
        # refactor; still needed per-task even though tasks
        # themselves now run in parallel, since each task can
        # still be handed up to num_search_results=8 URLs.
        # --------------------------------------------------

        early_stop_target = self.top_k * 3

        # --------------------------------------------------
        # Process every search result.
        # --------------------------------------------------

        for url, title in search_results:

            if len(all_chunks) >= early_stop_target:

                print(
                    "[DynamicRetriever] "
                    f"Collected {len(all_chunks)} candidate "
                    f"chunks (>= {early_stop_target}); "
                    "skipping remaining search results."
                )

                break

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

            text = self._extract_main_text(
                html,
                url
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
            # A single page can yield 100+ raw chunks (e.g. a
            # long guide). Only a handful could ever end up in
            # the final top_k, so cap how many chunks from ONE
            # page get filtered/kept — avoids one long page
            # crowding out chunks from other, possibly more
            # relevant, sources. Restored after being dropped
            # in the concurrency refactor.
            # --------------------------------------------------

            max_chunks_per_page = self.top_k * 4

            page_chunks = page_chunks[:max_chunks_per_page]

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
    # DUCKDUCKGO SEARCH (primary backend)
    # ==========================================================

    def _search_duckduckgo(
        self,
        query,
        num_results
    ):

        """
        Default web search backend.

        Uses DuckDuckGo's HTML endpoint. No API key required.

        Falls back to Tavily (see _search_tavily) when:

            - the request itself raises (timeout, connection
              error, etc.)
            - the response status is anything other than 200
              (e.g. 202, which raise_for_status() does NOT
              treat as an error, so it's checked explicitly)
            - the response is 200 but no parsable result links
              are found (soft block / captcha / layout change)

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

            # --------------------------------------------------
            # 202 (and any other non-200) means DuckDuckGo did
            # NOT give us a normal result page - typically rate
            # limiting or bot detection. raise_for_status() only
            # catches 4xx/5xx, so this is checked separately.
            # --------------------------------------------------

            if response.status_code != 200:

                print(
                    "[DynamicRetriever] "
                    f"DuckDuckGo returned status "
                    f"{response.status_code} for query "
                    f"'{query}'; falling back to Tavily."
                )

                return self._search_tavily(
                    query,
                    num_results
                )

        except requests.RequestException as error:

            print(
                "[DynamicRetriever] "
                f"DuckDuckGo search failed: {error}; "
                "falling back to Tavily."
            )

            return self._search_tavily(
                query,
                num_results
            )

        try:

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            results = []

            seen_urls = set()

            # --------------------------------------------------
            # Domains/URL patterns that are ad redirects or
            # tracking links rather than real content pages.
            # Fetching these wastes a full fetch+chunk+embed
            # cycle for near-zero usable content.
            # --------------------------------------------------

            AD_REDIRECT_MARKERS = (
                "duckduckgo.com/y.js",
                "bing.com/aclick",
                "/aclk?",
                "googleadservices.com",
                "doubleclick.net",
            )

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

                if any(
                    marker in href
                    for marker in AD_REDIRECT_MARKERS
                ):
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

            # --------------------------------------------------
            # 200 OK but nothing usable parsed out (DuckDuckGo
            # sometimes serves a soft-block/captcha page with a
            # 200 status). Treat this the same as a hard failure
            # and fall back rather than returning empty-handed.
            # --------------------------------------------------

            if not results:

                print(
                    "[DynamicRetriever] "
                    f"DuckDuckGo returned no parsable results "
                    f"for query '{query}'; falling back to "
                    "Tavily."
                )

                return self._search_tavily(
                    query,
                    num_results
                )

            return results

        except Exception as error:

            print(
                "[DynamicRetriever] "
                f"DuckDuckGo parsing failed: {error}; "
                "falling back to Tavily."
            )

            return self._search_tavily(
                query,
                num_results
            )

    # ==========================================================
    # TAVILY SEARCH (fallback backend)
    # ==========================================================

    def _search_tavily(
        self,
        query,
        num_results
    ):

        """
        Fallback search backend.

        Only reached when DuckDuckGo fails, returns a non-200
        status (e.g. 202), or returns 200 with no parsable
        results.

        Deliberately uses search_depth="basic", NOT "advanced" -
        this is meant to be a cheap fallback, not a primary
        backend, and "advanced" costs more Tavily credits per
        call for reranking we don't need here.

        Requires TAVILY_API_KEY in the environment. If it's not
        set, logs and returns [] rather than raising, so the
        rest of the pipeline degrades gracefully (that task
        just gets no retrieved_context, per _retrieve_query).

        Returns the same shape as _search_duckduckgo:

            [
                (url, title),
                ...
            ]
        """

        if not self.tavily_api_key:

            print(
                "[DynamicRetriever] "
                "Tavily fallback unavailable: "
                "TAVILY_API_KEY not set."
            )

            return []

        try:

            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": self.tavily_search_depth,
                    "max_results": num_results,
                    "include_answer": False,
                    "include_raw_content": False
                },
                timeout=self.request_timeout
            )

            response.raise_for_status()

            data = response.json()

        except requests.RequestException as error:

            print(
                "[DynamicRetriever] "
                f"Tavily search failed: {error}"
            )

            return []

        except ValueError as error:

            print(
                "[DynamicRetriever] "
                f"Tavily response parsing failed: {error}"
            )

            return []

        results = []

        for item in data.get("results", []):

            url = item.get("url")

            title = (
                item.get("title")
                or url
            )

            if not url:
                continue

            results.append(
                (
                    url,
                    title
                )
            )

            if len(results) >= num_results:
                break

        print(
            "[DynamicRetriever] "
            f"Tavily fallback returned {len(results)} "
            f"results for query '{query}'."
        )

        return results

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
        html,
        url=""
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
                "wikipedia.org" in url
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