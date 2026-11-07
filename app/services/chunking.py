import re


def split_text(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    """把长文本切成若干块。
    size    : 每块目标字数（中文按字符算）
    overlap : 相邻块重叠字数，防止一句话被切断
    """
    # 1. 统一换行符 + 去掉 Windows 记事本可能带的 BOM
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff").strip()
    if not text:
        return []

    # 2. 先按空行切段（Markdown 的段落分隔）
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    step = max(1, size - overlap)
    chunks: list[str] = []
    buf = ""

    for p in paras:
        if len(p) > size:
            # 3a. 单段就超长，先把缓存的冲出去，再硬切这一段
            if buf:
                chunks.append(buf)
                buf = ""
            for start in range(0, len(p), step):
                piece = p[start:start + size]
                if piece:
                    chunks.append(piece)
                if start + size >= len(p):
                    break
        elif len(buf) + len(p) + 1 <= size:
            # 3b. 还装得下，拼到当前块
            buf = f"{buf}\n{p}" if buf else p
        else:
            # 3c. 装不下了，当前块收口，另起一块
            chunks.append(buf)
            buf = p

    if buf:
        chunks.append(buf)

    return chunks