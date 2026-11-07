from pathlib import Path

from app.services.parsers import extract_text

# 测试素材放在 tests/fixtures/ 下
FILE = Path(__file__).parent / "fixtures" / "员工手册.pdf"


def test_extract_pdf_text():
    assert FILE.exists(), f"缺少测试素材：{FILE}"
    text = extract_text(FILE.name, FILE.read_bytes())
    assert text.strip()
    assert "�" not in text


def main():
    if not FILE.exists():
        print("找不到文件:", FILE.resolve())
        return

    raw = FILE.read_bytes()
    text = extract_text(FILE.name, raw)

    print("文件:", FILE.name)
    print("原始字节:", len(raw))
    print("抽出字符:", len(text))
    print("乱码字符:", sum(1 for ch in text if ch == "�"))
    print("空行占比: %.0f%%" % (100 * text.count("\n\n") / max(1, len(text)) * 2))
    print("=" * 40)
    print("【开头 200 字】")
    print(text[:200])
    print("=" * 40)
    print("【结尾 150 字】")
    print(text[-150:])


if __name__ == "__main__":
    main()
