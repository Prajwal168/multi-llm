from pathlib import Path
from pypdf import PdfReader


class DocumentLoader:
    """
    Loads supported document types and extracts their text.

    Changes vs. the original version:
      1. A failure loading any single file (corrupt PDF, an
         empty-password-encrypted PDF, a markdown file with bad
         encoding, a permissions error, etc.) no longer crashes the
         whole ingestion run. `load()` prints a warning and returns
         None for that file so callers (Chunker) can skip it and
         keep processing the rest of the documents.
      2. Password-protected PDFs that use an empty password (common
         with PDFs exported as "protected" without a real password)
         are decrypted automatically instead of failing outright.
      3. A single unreadable page inside an otherwise-good PDF is
         skipped with a warning instead of aborting the whole file.
      4. Markdown files that aren't valid UTF-8 are still read, with
         undecodable bytes replaced, instead of raising.
    """

    def load(self, file_path):

        file_path = Path(file_path)

        try:

            if file_path.suffix.lower() == ".md":
                return self._load_markdown(file_path)

            elif file_path.suffix.lower() == ".pdf":
                return self._load_pdf(file_path)

            else:
                raise ValueError(
                    f"Unsupported file type: {file_path.suffix}"
                )

        except ValueError:
            # Unsupported extension is a caller/config mistake, not
            # a bad file — let it surface instead of being masked.
            raise

        except Exception as exc:
            print(f"Warning: failed to load '{file_path}': {exc}")
            return None

    def _load_markdown(self, file_path):

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()

        except UnicodeDecodeError:
            with open(
                file_path, "r", encoding="utf-8", errors="replace"
            ) as file:
                return file.read()

    def _load_pdf(self, file_path):

        reader = PdfReader(file_path)

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                # Leave it to fail naturally below if it's actually
                # password-protected with a real (unknown) password.
                pass

        pages = []

        for page_number, page in enumerate(reader.pages, start=1):

            try:
                text = page.extract_text()

            except Exception as exc:
                print(
                    f"Warning: failed to extract text from page "
                    f"{page_number} of '{file_path}': {exc}"
                )
                continue

            if text:
                pages.append(text)

        return "\n\n".join(pages)


# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------

if __name__ == "__main__":

    loader = DocumentLoader()

    documents_path = Path("documents")

    for file in documents_path.rglob("*"):

        if file.suffix.lower() in [".md", ".pdf"]:

            text = loader.load(file)

            print("=" * 70)
            print("File:", file)
            print("Characters:", len(text))
            print("\nPreview:")
            print(text[:300])