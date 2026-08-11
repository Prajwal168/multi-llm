from pathlib import Path
from pypdf import PdfReader


class DocumentLoader:
    """
    Loads supported document types and extracts their text.
    """

    def load(self, file_path):

        file_path = Path(file_path)

        if file_path.suffix.lower() == ".md":
            return self._load_markdown(file_path)

        elif file_path.suffix.lower() == ".pdf":
            return self._load_pdf(file_path)

        else:
            raise ValueError(
                f"Unsupported file type: {file_path.suffix}"
            )

    def _load_markdown(self, file_path):

        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def _load_pdf(self, file_path):

        reader = PdfReader(file_path)

        pages = []

        for page in reader.pages:
            text = page.extract_text()

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