import io
from collections import Counter
from pathlib import Path
from pypdf import PdfReader
from docx import Document as DocxDocument

TEXT_SUFFIX = {".txt", ".md"}
ALLOWED_SUFFIX = TEXT_SUFFIX | {".pdf", ".docx"}
MAX_PAGES = 100

def _decode(raw: bytes) -> str:
    """纯文本解码：优先 UTF-8，失败降级 GBK"""
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码，请另存为 UTF-8")


def _strip_repeated_lines(pages: list[str], ratio: float = 0.6) -> str:
    """去掉每页都出现的页眉、页脚、水印"""
    if len(pages) < 3:
        return "\n\n".join(pages)

    counter = Counter()
    for page in pages:
        # 用 set 去重，同一页里重复的行只算一次
        for line in {l.strip() for l in page.split("\n") if l.strip()}:
            counter[line] += 1

    threshold = len(pages) * ratio
    repeated = {
        line for line, n in counter.items()
        if n >= threshold and len(line) < 60
    }
    if not repeated:
        return "\n\n".join(pages)

    cleaned = []
    for page in pages:
        kept = [l for l in page.split("\n")
                if l.strip() and l.strip() not in repeated]
        if kept:
            cleaned.append("\n".join(kept))
    return "\n\n".join(cleaned)


def _from_pdf(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    if len(reader.pages) > MAX_PAGES:
        raise ValueError(f"PDF 超过 {MAX_PAGES} 页，请拆分后再传")

    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)

    if not pages:
        raise ValueError("这份 PDF 抽不出文字，可能是扫描件（整页是图片），需要 OCR")

    return _strip_repeated_lines(pages)


def _from_docx(raw: bytes) -> str:
    doc = DocxDocument(io.BytesIO(raw))

    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    # 表格单独处理：python-docx 不会把表格混在 paragraphs 里
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    if not parts:
        raise ValueError("这份 Word 没有可用文字")

    return "\n\n".join(parts)


def extract_text(filename: str, raw: bytes) -> str:
    """统一入口：按后缀分发到具体解析器"""
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIX:
        return _decode(raw)
    if suffix == ".pdf":
        return _from_pdf(raw)
    if suffix == ".docx":
        return _from_docx(raw)
    raise ValueError(f"不支持的文件类型：{suffix or '未知'}")