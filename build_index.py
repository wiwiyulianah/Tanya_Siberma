from pathlib import Path
import json
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader


DATA_DIR = Path("data")
INDEX_DIR = Path("indexes")
INDEX_DIR.mkdir(exist_ok=True)

EMBED_MODEL = "all-MiniLM-L6-v2"


def read_text_file(path: Path) -> str:
    ext = path.suffix.lower()

    if ext in [".txt", ".md"]:
        return path.read_text(encoding="utf-8", errors="ignore")

    if ext == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text() or ""
                pages.append(text)
            except Exception:
                pass

        return "\n".join(pages)

    return ""


def repair_pdf_numbered_list(text: str) -> str:
    """
    Memperbaiki hasil ekstraksi PDF yang membuat list 1, 2, 3 menjadi satu paragraf.
    Contoh:
    'berikut: 1 Pendaftar ... 2 Status ...'
    menjadi:
    'berikut:\n1. Pendaftar ...\n2. Status ...'
    """


    text = re.sub(
        r"(?<!\n)\s+([1-9]|[1-9][0-9])[\.\)]?\s+(?=[A-ZÀ-Ü])",
        r"\n\1. ",
        text
    )


    text = re.sub(
        r":\s*\n([1-9]|[1-9][0-9])\.",
        r":\n\n\1.",
        text
    )

    return text


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Bersihkan teks tambahan dari PDF
    text = re.sub(r"FAQ RPL Universitas Majalengka.*?Halaman\s*\d+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Halaman\s*\d+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"PDF uji coba chatbot", "", text, flags=re.IGNORECASE)

    text = re.sub(r"[ \t]+", " ", text)

    text = repair_pdf_numbered_list(text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_markdown_topics(text: str):
    """
    Mendukung format:
    ## Topik: ...
    # Topik: ...
    Topik: ...

    Jadi file .md, .txt, dan .pdf hasil ekstraksi tetap bisa dibaca per topik.
    """

    text = clean_text(text)

    if not text:
        return []

    pattern = r"(?=^\s*(?:#{1,6}\s*)?Topik\s*:)"
    parts = re.split(pattern, text, flags=re.MULTILINE | re.IGNORECASE)

    sections = []

    for part in parts:
        part = part.strip()

        if not part:
            continue

        if re.match(r"^\s*(?:#{1,6}\s*)?Topik\s*:", part, flags=re.IGNORECASE):
            sections.append(part)

    return sections


def extract_topic(section: str) -> str:
    match = re.search(
        r"^\s*(?:#{1,6}\s*)?Topik\s*:\s*(.+)$",
        section,
        flags=re.MULTILINE | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return "Informasi PMB"


def extract_questions(section: str):
    questions = []

    match = re.search(
        r"Pertanyaan yang mungkin ditanyakan\s*:\s*(.*?)(?=\n\s*Jawaban\s*:|\Z)",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        raw_questions = match.group(1).strip()

        for line in raw_questions.splitlines():
            line = line.strip()
            line = re.sub(r"^[-*•]\s*", "", line).strip()

            if line:
                questions.append(line)

    return questions


def extract_answer(section: str) -> str:
    match = re.search(
        r"Jawaban\s*:\s*(.*)",
        section,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        answer = match.group(1).strip()

        answer = re.split(r"\n\s*---\s*$", answer, flags=re.MULTILINE)[0].strip()

        answer = re.split(
            r"\n\s*(?:#{1,6}\s*)?Topik\s*:",
            answer,
            flags=re.IGNORECASE
        )[0].strip()

        return answer

    return section.strip()


def extract_keywords(section: str) -> str:
    body = re.sub(
        r"^\s*(?:#{1,6}\s*)?Topik\s*:\s*.+$",
        "",
        section,
        flags=re.MULTILINE | re.IGNORECASE
    ).strip()

    before_questions = re.split(
        r"Pertanyaan yang mungkin ditanyakan\s*:",
        body,
        flags=re.IGNORECASE,
    )[0].strip()

    before_questions = before_questions.replace("Jawaban:", "").strip()

    return before_questions


def split_long_text(text: str, chunk_size: int = 1200, overlap: int = 150):
    text = clean_text(text)

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def create_documents_from_structured_text(path: Path, text: str):
    sections = split_markdown_topics(text)
    documents = []

    if sections:
        for section in sections:
            topic = extract_topic(section)
            questions = extract_questions(section)
            answer = extract_answer(section)
            keywords = extract_keywords(section)

            search_text = "\n".join(
                [
                    f"Topik: {topic}",
                    f"Kata kunci: {keywords}",
                    "Pertanyaan:",
                    "\n".join(questions),
                    "Jawaban:",
                    answer,
                ]
            )

            documents.append(
                {
                    "source": str(path).replace("\\", "/"),
                    "filename": path.name,
                    "topic": topic,
                    "questions": questions,
                    "answer": answer,
                    "content": section,
                    "search_text": search_text,
                    "type": "faq_topic",
                }
            )

        return documents

    return []


def create_documents_from_plain_file(path: Path, text: str):
    chunks = split_long_text(text)
    documents = []

    for i, chunk in enumerate(chunks, start=1):
        documents.append(
            {
                "source": str(path).replace("\\", "/"),
                "filename": path.name,
                "topic": f"Bagian {i}",
                "questions": [],
                "answer": chunk,
                "content": chunk,
                "search_text": chunk,
                "type": "text_chunk",
            }
        )

    return documents


def collect_all_documents():
    allowed_ext = [".txt", ".md", ".pdf"]
    documents = []

    for path in DATA_DIR.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in allowed_ext:
            continue

        text = read_text_file(path)

        if not text.strip():
            continue

        text = clean_text(text)

        docs = create_documents_from_structured_text(path, text)

        if not docs:
            docs = create_documents_from_plain_file(path, text)

        documents.extend(docs)

    return documents


def build_index():
    documents = collect_all_documents()

    if not documents:
        raise ValueError(
            "Tidak ada dokumen yang terbaca. Pastikan file .md, .txt, atau .pdf berada di folder data."
        )

    model = SentenceTransformer(EMBED_MODEL)

    texts = [doc["search_text"] for doc in documents]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(INDEX_DIR / "faiss.index"))

    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as file:
        json.dump(documents, file, ensure_ascii=False, indent=2)

    return len(documents)


if __name__ == "__main__":
    total = build_index()
    print("✅ Index RAG berhasil dibuat ulang.")
    print(f"✅ Total topik/bagian dokumen terbaca: {total}")
    print("✅ File index tersimpan di folder indexes.")