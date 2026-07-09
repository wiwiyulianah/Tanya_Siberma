from pathlib import Path
import json
import re
import os  # Ditambahkan untuk membaca API Key dari environment variabel

import faiss
import requests
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path("indexes")

# OLLAMA_URL dan OLLAMA_MODEL dihapus, diganti dengan konfigurasi Groq
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-8b-8192" # Model Llama 3 8B (Super cepat dan gratis)

embedder = SentenceTransformer("all-MiniLM-L6-v2")


PRODI_BIAYA = {
    "Administrasi Publik": {
        "fakultas": "FISIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.750.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["administrasi publik", "admin publik"],
    },
    "Ilmu Komunikasi": {
        "fakultas": "FISIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.500.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["ilmu komunikasi", "komunikasi"],
    },
    "Pendidikan Bahasa dan Sastra Indonesia": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan bahasa dan sastra indonesia", "pbsi", "bahasa indonesia"],
    },
    "Pendidikan Jasmani": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan jasmani", "penjas", "pjkr"],
    },
    "Pendidikan Bahasa Inggris": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan bahasa inggris", "bahasa inggris"],
    },
    "Pendidikan Guru SD": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan guru sd", "pgsd", "guru sd", "pendidikan guru sekolah dasar"],
    },
    "Pendidikan Matematika": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.500.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan matematika", "matematika"],
    },
    "Pendidikan Biologi": {
        "fakultas": "FKIP",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.500.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan biologi", "biologi"],
    },
    "Manajemen": {
        "fakultas": "FEB",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.750.000",
        "karyawan": "Rp4.000.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["manajemen"],
    },
    "Akuntansi": {
        "fakultas": "FEB",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.500.000",
        "karyawan": "Rp3.750.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["akuntansi"],
    },
    "Agribisnis": {
        "fakultas": "FAPERTA",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "Rp3.250.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["agribisnis"],
    },
    "Agroteknologi": {
        "fakultas": "FAPERTA",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "Rp3.250.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["agroteknologi", "agro teknologi"],
    },
    "Peternakan": {
        "fakultas": "FAPERTA",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.750.000",
        "karyawan": "Rp3.250.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["peternakan"],
    },
    "Pendidikan Agama Islam": {
        "fakultas": "FAI",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.250.000",
        "karyawan": "Rp2.500.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["pendidikan agama islam", "pai"],
    },
    "Pendidikan Islam Anak Usia Dini": {
        "fakultas": "FAI",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["pendidikan islam anak usia dini", "piaud"],
    },
    "Ekonomi Syariah": {
        "fakultas": "FAI",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp2.000.000",
        "karyawan": "-",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "-",
        "aliases": ["ekonomi syariah", "eksyar"],
    },
    "Informatika": {
        "fakultas": "FT",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp4.000.000",
        "karyawan": "Rp5.000.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["informatika", "teknik informatika"],
    },
    "Teknik Sipil": {
        "fakultas": "FT",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp4.000.000",
        "karyawan": "Rp5.000.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["teknik sipil", "sipil"],
    },
    "Teknik Mesin": {
        "fakultas": "FT",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.500.000",
        "karyawan": "Rp4.500.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["teknik mesin", "mesin"],
    },
    "Teknik Industri": {
        "fakultas": "FT",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.250.000",
        "karyawan": "Rp4.500.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["teknik industri", "industri"],
    },
    "Ilmu Hukum": {
        "fakultas": "FH",
        "pendaftaran": "Rp250.000",
        "registrasi": "Rp600.000",
        "prospek": "Rp500.000",
        "reguler": "Rp3.000.000",
        "karyawan": "Rp3.250.000",
        "bangunan": "Rp3.000.000",
        "sks_reguler": "Rp75.000",
        "sks_karyawan": "Rp100.000",
        "aliases": ["ilmu hukum", "hukum"],
    },
}

STOPWORDS = {
    "apa", "apakah", "yang", "di", "ke", "dari", "dan", "atau", "itu", "ini",
    "saya", "aku", "kamu", "mau", "ingin", "tentang", "untuk", "pada", "dengan",
    "bagaimana", "berapa", "dimana", "di mana", "kah", "nya", "unma",
    "universitas", "majalengka", "pmb"
}

SYNONYMS = {
    "biaya": ["uang kuliah", "ukt", "pembayaran", "tagihan", "semester", "daftar ulang"],
    "kuliah": ["perkuliahan", "mahasiswa", "kampus"],
    "daftar": ["pendaftaran", "registrasi", "pmb", "mendaftar", "jalur masuk"],
    "syarat": ["persyaratan", "berkas", "dokumen", "ketentuan"],
    "fakultas": ["program studi", "prodi", "jurusan", "daftar fakultas"],
    "prodi": ["program studi", "jurusan", "fakultas"],
    "jurusan": ["program studi", "prodi", "fakultas"],
    "beasiswa": ["bantuan biaya", "kip", "kip kuliah", "pembiayaan"],
    "kip": ["kip kuliah", "beasiswa kip", "bantuan pendidikan"],
    "lokasi": ["alamat", "tempat", "kampus", "letak"],
    "kontak": ["nomor", "whatsapp", "admin", "hubungi", "email"],
    "jadwal": ["tanggal", "waktu", "gelombang", "periode"],
    "asrama": ["kos", "tempat tinggal", "hunian", "kontrakan"],
}

def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9A-ZÀ-ÿ\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def expand_question(question: str) -> str:
    q = normalize_text(question)
    additions = []
    for key, values in SYNONYMS.items():
        if key in q:
            additions.extend(values)
    if additions:
        q = q + " " + " ".join(additions)
    return q

def tokenize(text: str):
    text = normalize_text(text)
    tokens = text.split()
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def keyword_overlap_score(question: str, document_text: str) -> float:
    q_tokens = set(tokenize(expand_question(question)))
    d_tokens = set(tokenize(document_text))
    if not q_tokens or not d_tokens:
        return 0.0
    overlap = q_tokens.intersection(d_tokens)
    return len(overlap) / max(len(q_tokens), 1)

def load_index():
    index_path = INDEX_DIR / "faiss.index"
    chunks_path = INDEX_DIR / "chunks.json"
    if not index_path.exists() or not chunks_path.exists():
        raise FileNotFoundError("Index belum dibuat. Jalankan: python build_index.py")
    index = faiss.read_index(str(index_path))
    with open(chunks_path, "r", encoding="utf-8") as file:
        chunks = json.load(file)
    return index, chunks

def detect_biaya_prodi_question(question: str):
    q = normalize_text(question)
    biaya_words = [
        "biaya", "uang kuliah", "ukt", "bayar", "pembayaran",
        "semester", "registrasi", "pendaftaran", "prospek",
        "bangunan", "sks", "karyawan", "reguler"
    ]
    if not any(word in q for word in biaya_words):
        return None
    matched = []
    for prodi, data in PRODI_BIAYA.items():
        for alias in data["aliases"]:
            alias_norm = normalize_text(alias)
            if alias_norm in q:
                matched.append((len(alias_norm), prodi))
    if not matched:
        return None
    matched.sort(reverse=True)
    return matched[0][1]

def format_biaya_prodi_answer(prodi: str):
    data = PRODI_BIAYA[prodi]
    return f"""Biaya kuliah Program Studi {prodi} Universitas Majalengka Tahun Akademik 2025/2026 adalah sebagai berikut:

| Komponen Biaya | Nominal |
|---|---:|
| Fakultas | {data["fakultas"]} |
| Pendaftaran | {data["pendaftaran"]} |
| Registrasi | {data["registrasi"]} |
| Prospek | {data["prospek"]} |
| Uang Kuliah/Semester Reguler | {data["reguler"]} |
| Uang Kuliah/Semester Karyawan | {data["karyawan"]} |
| Uang Bangunan | {data["bangunan"]} |
| Biaya SKS Reguler | {data["sks_reguler"]} |
| Biaya SKS Karyawan | {data["sks_karyawan"]} |

Catatan:
Rincian biaya dapat berubah sewaktu-waktu sesuai kebijakan Universitas Majalengka. Calon mahasiswa disarankan melakukan pengecekan ulang melalui portal PMB atau layanan informasi resmi Universitas Majalengka.
"""

def find_biaya_prodi_from_chunks(prodi: str):
    try:
        _, chunks = load_index()
    except Exception:
        return ""
    target_1 = f"biaya kuliah {prodi.lower()} unma"
    target_2 = f"biaya kuliah {prodi.lower()}"
    for chunk in chunks:
        topic = normalize_text(chunk.get("topic", ""))
        answer = chunk.get("answer", "").strip()
        if not answer:
            continue
        if normalize_text(target_1) in topic or normalize_text(target_2) in topic:
            return answer
    return ""

def answer_specific_biaya_question(question: str):
    prodi = detect_biaya_prodi_question(question)
    if not prodi:
        return None
    answer_from_file = find_biaya_prodi_from_chunks(prodi)
    if answer_from_file:
        return clean_answer(answer_from_file)
    return format_biaya_prodi_answer(prodi)

def retrieve_context(question: str, top_k: int = 8):
    index, chunks = load_index()
    expanded_question = expand_question(question)
    query_embedding = embedder.encode(
        [expanded_question],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype("float32")
    scores, indices = index.search(query_embedding, top_k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if 0 <= idx < len(chunks):
            item = chunks[idx].copy()
            search_text = "\n".join([
                str(item.get("topic", "")),
                str(item.get("search_text", "")),
                str(item.get("content", "")),
                str(item.get("answer", "")),
                " ".join(item.get("questions", [])) if isinstance(item.get("questions", []), list) else str(item.get("questions", "")),
            ])
            keyword_score = keyword_overlap_score(question, search_text)
            semantic_score = float(score)
            final_score = (semantic_score * 0.60) + (keyword_score * 0.40)
            item["semantic_score"] = semantic_score
            item["keyword_score"] = keyword_score
            item["score"] = final_score
            results.append(item)
    results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
    return results

# FUNGSI DIUBAH: Tetap bernama check_ollama_status agar app.py tidak error, 
# tapi mengecek API key Groq
def check_ollama_status():
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return False
        headers = {"Authorization": f"Bearer {api_key}"}
        # Cek ketersediaan model di Groq
        response = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# FUNGSI DIUBAH: Memanggil Groq API menggantikan localhost Ollama
def ask_llm(prompt: str):
    api_key = os.environ.get("GROQ_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 600,
        "top_p": 0.1
    }
    
    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

FALLBACK_MESSAGE = (
    "Maaf, informasi tersebut belum tersedia pada dokumen PMB yang saya miliki. "
    "Silakan ajukan pertanyaan lain seputar PMB Universitas Majalengka."
)

def professional_fallback():
    return FALLBACK_MESSAGE

def clean_answer(answer: str) -> str:
    answer = str(answer)
    answer = answer.replace("\r\n", "\n").replace("\r", "\n")
    answer = re.sub(
        r"^\s*Jawaban\s*:\s*",
        "",
        answer,
        flags=re.IGNORECASE
    ).strip()
    answer = re.sub(r"[ \t]+", " ", answer)
    answer = re.sub(
        r"(?<!\n)\s+([1-9]|[1-9][0-9])[\.\)]?\s+(?=[A-ZÀ-Ü])",
        r"\n\1. ",
        answer
    )
    answer = re.sub(
        r":\s*\n([1-9]|[1-9][0-9])\.",
        r":\n\n\1.",
        answer
    )
    answer = re.sub(
        r"(?<!\n)\s+[•]\s+",
        "\n• ",
        answer
    )
    answer = re.sub(r"\n{3,}", "\n\n", answer)
    return answer.strip()

def answer_looks_unavailable(answer: str) -> bool:
    text = normalize_text(answer)
    unavailable_patterns = [
        "belum tersedia", "tidak tersedia", "tidak ditemukan",
        "tidak ada informasi", "tidak terdapat", "saya tidak tahu",
        "saya tidak memiliki", "tidak disebutkan", "tidak dapat ditemukan",
        "tidak ada dalam konteks", "tidak ada di konteks",
        "tidak ada pada data", "tidak tercantum",
    ]
    return any(pattern in text for pattern in unavailable_patterns)

IMPORTANT_STOPWORDS = STOPWORDS.union({
    "siapa", "apa", "apakah", "berapa", "bagaimana", "dimana", "mana",
    "tolong", "mohon", "jelaskan", "sebutkan", "informasi",
    "saja", "aja", "dong", "kak", "min", "bang",
    "mahasiswa", "baru", "calon", "kampus", "kuliah",
    "unma", "universitas", "majalengka", "pmb",
    "cara", "daftar", "mendaftar", "pendaftaran", "alur",
    "prosedur", "tahapan", "langkah",
    "syarat", "persyaratan", "ketentuan",
    "dokumen", "berkas", "upload", "unggah",
    "jenis", "macam", "kategori", "skema",
    "pengertian", "maksud", "definisi",
})

def important_tokens(question: str):
    q = normalize_text(question)
    q = q.replace("rekognisi pembelajaran lampau", "rpl")
    q = q.replace("r p l", "rpl")
    q = q.replace("ka prodi", "kaprodi")
    q = q.replace("kap rodi", "kaprodi")
    q = q.replace("ketua prodi", "kaprodi")
    q = q.replace("ketua program studi", "kaprodi")
    tokens = []
    for token in q.split():
        if token in IMPORTANT_STOPWORDS:
            continue
        if len(token) <= 2:
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))

def full_context_text(ctx):
    questions = ctx.get("questions", "")
    if isinstance(questions, list):
        questions_text = " ".join(questions)
    else:
        questions_text = str(questions)
    return normalize_text(
        str(ctx.get("topic", "")) + "\n" +
        str(ctx.get("search_text", "")) + "\n" +
        str(ctx.get("content", "")) + "\n" +
        str(ctx.get("answer", "")) + "\n" +
        questions_text
    )

def detect_intent(question: str):
    q = normalize_text(question)
    if any(x in q for x in ["apa itu", "pengertian", "maksud", "definisi"]):
        return "definisi"
    if any(x in q for x in ["cara", "daftar", "pendaftaran", "alur", "prosedur", "tahapan", "langkah"]):
        return "alur"
    if any(x in q for x in ["syarat", "persyaratan", "ketentuan"]):
        return "syarat"
    if any(x in q for x in ["dokumen", "berkas", "upload", "unggah", "ijazah", "transkrip", "sertifikat"]):
        return "dokumen"
    if any(x in q for x in ["jenis", "macam", "kategori", "skema"]):
        return "jenis"
    return "umum"

def intent_score(question: str, ctx: dict):
    intent = detect_intent(question)
    topic = normalize_text(str(ctx.get("topic", "")))
    text = full_context_text(ctx)
    score = 0.0
    if intent == "definisi":
        if any(x in topic for x in ["informasi umum", "apa itu", "pengertian", "definisi", "profil"]):
            score += 1.0
        if any(x in topic for x in ["dokumen", "syarat", "alur", "pendaftaran"]):
            score -= 0.5
    elif intent == "alur":
        if any(x in topic for x in ["alur", "cara daftar", "pendaftaran", "prosedur", "tahapan"]):
            score += 1.0
        if any(x in topic for x in ["syarat", "dokumen", "informasi umum"]):
            score -= 0.3
    elif intent == "syarat":
        if any(x in topic for x in ["syarat", "persyaratan", "ketentuan"]):
            score += 1.0
        if any(x in topic for x in ["alur", "cara daftar", "informasi umum"]):
            score -= 0.3
    elif intent == "dokumen":
        if any(x in topic for x in ["dokumen", "berkas", "persyaratan"]):
            score += 1.0
    elif intent == "jenis":
        if any(x in topic for x in ["jenis", "macam", "kategori", "skema"]):
            score += 1.0
    return score

def rerank_contexts(question: str, contexts):
    tokens = important_tokens(question)
    ranked = []
    for ctx in contexts:
        text = full_context_text(ctx)
        semantic_score = float(ctx.get("semantic_score", 0))
        keyword_score = float(ctx.get("keyword_score", 0))
        base_score = float(ctx.get("score", 0))
        matched = [token for token in tokens if token in text]
        coverage = len(matched) / max(len(tokens), 1) if tokens else 0
        ctx["_matched_tokens"] = matched
        ctx["_rank_score"] = (
            base_score +
            keyword_score * 0.5 +
            semantic_score * 0.2 +
            coverage * 1.2 +
            intent_score(question, ctx)
        )
        ranked.append(ctx)
    ranked.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
    return ranked

def is_relevant_context(question: str, ctx: dict) -> bool:
    tokens = important_tokens(question)
    text = full_context_text(ctx)
    answer = str(ctx.get("answer", "")).strip()
    content = str(ctx.get("content", "")).strip()
    if not answer and not content:
        return False
    if answer_looks_unavailable(answer):
        return False
    if tokens:
        matched = [token for token in tokens if token in text]
        if not matched:
            return False
        coverage = len(matched) / max(len(tokens), 1)
        if coverage < 1.0:
            return False
    return True

def build_context_prompt(contexts):
    result = []
    for i, ctx in enumerate(contexts[:4], start=1):
        questions = ctx.get("questions", [])
        if isinstance(questions, list):
            questions_text = ", ".join(questions)
        else:
            questions_text = str(questions)
        result.append(
            f"""
Sumber {i}
Topik: {ctx.get("topic", "-")}
Pertanyaan terkait: {questions_text}
Jawaban resmi:
{ctx.get("answer", "")}
""".strip()
        )
    return "\n\n---\n\n".join(result)

def answer_question(question: str):
    specific_biaya_answer = answer_specific_biaya_question(question)
    if specific_biaya_answer:
        return specific_biaya_answer, []

    contexts = retrieve_context(question, top_k=25)
    if not contexts:
        return professional_fallback(), []

    contexts = rerank_contexts(question, contexts)
    relevant_contexts = [
        ctx for ctx in contexts
        if is_relevant_context(question, ctx)
    ]

    if not relevant_contexts:
        return professional_fallback(), []

    best_context = relevant_contexts[0]
    direct_answer = clean_answer(best_context.get("answer", ""))

    if direct_answer and not answer_looks_unavailable(direct_answer):
        return direct_answer, relevant_contexts[:3]

    context_text = build_context_prompt(relevant_contexts)

    prompt = f"""
Kamu adalah Tanya Siberma, chatbot informasi Universitas Majalengka.

Aturan wajib:
1. Jawab hanya berdasarkan KONTEKS DOKUMEN.
2. Jangan membuat jawaban di luar dokumen.
3. Jangan mengambil jawaban dari topik lain.
4. Jika jawaban tidak ada pada konteks, jawab persis:
"{FALLBACK_MESSAGE}"
5. Jika pengguna bertanya tentang satu topik tertentu, jawab hanya topik tersebut.
6. Jika pengguna bertanya satu program studi, jangan tampilkan semua program studi.
7. Jawaban harus jelas, singkat, sopan, dan profesional.

KONTEKS DOKUMEN:
{context_text}

PERTANYAAN USER:
{question}

JAWABAN:
"""
    try:
        # FUNGSI DIUBAH: Pemanggilan fungsi diganti dari ask_ollama ke ask_llm
        answer = clean_answer(ask_llm(prompt))

        if not answer:
            return professional_fallback(), []

        if answer_looks_unavailable(answer):
            return professional_fallback(), []

        return answer, relevant_contexts[:3]

    except Exception:
        return professional_fallback(), []