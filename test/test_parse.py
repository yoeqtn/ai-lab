from pathlib import Path

from parsers import extract_text

# 改成你要测的文件名（放在项目根目录）
FILE = "员工手册.pdf"


def main():
    path = Path(FILE)
    if not path.exists():
        print("找不到文件:", path.resolve())
        return

    raw = path.read_bytes()
    text = extract_text(path.name, raw)

    print("文件:", path.name)
    print("原始字节:", len(raw))
    print("抽出字符:", len(text))
    print("乱码字符:", sum(1 for ch in text if ch == "\ufffd"))
    print("空行占比: %.0f%%" % (100 * text.count("\n\n") / max(1, len(text)) * 2))
    print("=" * 40)
    print("【开头 200 字】")
    print(text[:200])
    print("=" * 40)
    print("【结尾 150 字】")
    print(text[-150:])


if __name__ == "__main__":
    main()