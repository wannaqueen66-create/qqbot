"""
消息转发功能测试脚本
用于验证文本分段逻辑的正确性
"""
import sys
sys.path.insert(0, 'd:/AAA所有应用/资源/qqbot')

from src.utils.message_forwarder import split_text_into_paragraphs, create_forward_nodes


def test_split_text():
    """测试文本分段功能"""
    
    print("=" * 60)
    print("测试 1: 双换行符分段")
    print("=" * 60)
    
    text1 = """这是第一段内容。

这是第二段内容，包含一些详细的说明。

这是第三段内容。"""
    
    result1 = split_text_into_paragraphs(text1)
    print(f"输入文本:\n{text1}\n")
    print(f"分段结果: {len(result1)} 个段落")
    for i, para in enumerate(result1, 1):
        print(f"  段落 {i}: {para[:50]}...")
    
    print("\n" + "=" * 60)
    print("测试 2: 单换行符分段")
    print("=" * 60)
    
    text2 = """第一行内容
第二行内容
第三行内容
第四行内容"""
    
    result2 = split_text_into_paragraphs(text2)
    print(f"输入文本:\n{text2}\n")
    print(f"分段结果: {len(result2)} 个段落")
    for i, para in enumerate(result2, 1):
        print(f"  段落 {i}: {para[:50]}...")
    
    print("\n" + "=" * 60)
    print("测试 3: 超长文本强制分段")
    print("=" * 60)
    
    text3 = "这是一段非常长的文本，" * 100  # 生成一个很长的文本
    
    result3 = split_text_into_paragraphs(text3, max_paragraph_length=200)
    print(f"输入文本长度: {len(text3)} 字符")
    print(f"分段结果: {len(result3)} 个段落")
    for i, para in enumerate(result3, 1):
        print(f"  段落 {i} 长度: {len(para)} 字符")
    
    print("\n" + "=" * 60)
    print("测试 4: 混合格式文本")
    print("=" * 60)
    
    text4 = """大家好，我是 AI 助手！

今天我要为大家介绍一些关于 Python 编程的知识：

1. Python 是一种高级编程语言
2. Python 语法简洁优雅
3. Python 适用于多种领域

具体来说：
- Web 开发
- 数据分析
- 人工智能
- 自动化脚本

如果你想学习 Python，建议从基础语法开始，逐步深入到高级特性。

祝你学习愉快！"""
    
    result4 = split_text_into_paragraphs(text4)
    print(f"输入文本:\n{text4}\n")
    print(f"分段结果: {len(result4)} 个段落")
    for i, para in enumerate(result4, 1):
        print(f"\n段落 {i}:")
        print(f"  {para}")


def test_create_nodes():
    """测试节点创建功能"""
    
    print("\n" + "=" * 60)
    print("测试 5: 创建转发节点")
    print("=" * 60)
    
    paragraphs = [
        "这是第一段内容",
        "这是第二段内容",
        "这是第三段内容"
    ]
    
    nodes = create_forward_nodes(paragraphs, "123456789", "AI 助手")
    
    print(f"段落数量: {len(paragraphs)}")
    print(f"节点数量: {len(nodes)}\n")
    
    for i, node in enumerate(nodes, 1):
        print(f"节点 {i}:")
        print(f"  类型: {node['type']}")
        print(f"  昵称: {node['data']['name']}")
        print(f"  QQ号: {node['data']['uin']}")
        print(f"  内容: {node['data']['content']}")
        print()


if __name__ == "__main__":
    print("开始测试消息转发功能...\n")
    
    try:
        test_split_text()
        test_create_nodes()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
