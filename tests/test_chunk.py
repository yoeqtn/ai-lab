from app.services.chunking import split_text

SAMPLE = """# 售后政策

## 一、退货
本店支持 7 天无理由退货。自签收之日起 7 个自然日内，商品未使用、吊牌完整、包装完好，可申请无理由退货，来回运费由买家承担。
生鲜食品、定制商品、贴身衣物、已拆封的软件类商品不支持 7 天无理由退货。

## 二、退款
退款将在商家确认收货后 1-3 个工作日内原路退回，具体到账时间以银行或支付平台为准。
如遇节假日，到账时间可能顺延 1-2 个工作日。

## 三、质量问题的售后
商品出现质量问题（破损、缺件、功能故障），运费由商家承担，买家可在订单页上传照片申请售后。
商家需在 48 小时内响应，逾期未响应平台将自动介入。

## 四、发票
发票需在订单完成后 30 天内申请，支持电子发票，抬头可为个人或公司。
"""


def test_split_text_within_size():
    chunks = split_text(SAMPLE, size=200, overlap=40)
    assert chunks
    assert all(c.strip() for c in chunks)
    # 硬切长段落时每块最多 size 个字
    assert all(len(c) <= 200 for c in chunks)


def test_split_text_empty_input():
    assert split_text("   \n\n  ") == []


def main():
    chunks = split_text(SAMPLE, size=200, overlap=40)
    print("原文长度:", len(SAMPLE), " 切出块数:", len(chunks))
    for i, c in enumerate(chunks):
        print(f"--- 第 {i} 块（{len(c)} 字）---")
        print(c.replace("\n", " "))


if __name__ == "__main__":
    main()
