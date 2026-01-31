"""
测试差异分析逻辑修复

验证作者为None时的key匹配问题
"""

# 模拟旧逻辑（有问题的）
def old_logic():
    # 本地书籍
    local_books = [
        {'title': '测试书1', 'author': None},
        {'title': '测试书2', 'author': '作者A'},
    ]
    
    local_dict = {}
    for book in local_books:
        key = (book['title'], book['author'])  # 问题：None
        local_dict[key] = book
    
    # Calibre书籍
    calibre_books = [
        {'title': '测试书1', 'author': None},  # 应该匹配
        {'title': '测试书3', 'author': '作者B'},  # 不应该匹配
    ]
    
    only_in_calibre = []
    for book in calibre_books:
        key = (book['title'], book['author'])  # 问题：None
        if key not in local_dict:
            only_in_calibre.append(book)
    
    return only_in_calibre


# 模拟新逻辑（修复后的）
def new_logic():
    # 本地书籍
    local_books = [
        {'title': '测试书1', 'author': None},
        {'title': '测试书2', 'author': '作者A'},
    ]
    
    local_dict = {}
    for book in local_books:
        key = (book['title'], book['author'] or '')  # 修复：None -> ''
        local_dict[key] = book
    
    # Calibre书籍
    calibre_books = [
        {'title': '测试书1', 'author': None},  # 应该匹配
        {'title': '测试书3', 'author': '作者B'},  # 不应该匹配
    ]
    
    only_in_calibre = []
    for book in calibre_books:
        key = (book['title'], book['author'] or '')  # 修复：None -> ''
        if key not in local_dict:
            only_in_calibre.append(book)
    
    return only_in_calibre


if __name__ == '__main__':
    print("=" * 60)
    print("测试差异分析逻辑修复")
    print("=" * 60)
    
    print("\n旧逻辑结果（有问题）：")
    old_result = old_logic()
    print(f"待导入书籍数量: {len(old_result)}")
    for book in old_result:
        print(f"  - {book['title']} by {book['author']}")
    
    print("\n新逻辑结果（修复后）：")
    new_result = new_logic()
    print(f"待导入书籍数量: {len(new_result)}")
    for book in new_result:
        print(f"  - {book['title']} by {book['author']}")
    
    print("\n" + "=" * 60)
    print("结论：")
    if len(old_result) == 1 and old_result[0]['title'] == '测试书1':
        print("❌ 旧逻辑：测试书1被错误识别为待导入（实际已存在）")
    if len(new_result) == 1 and new_result[0]['title'] == '测试书3':
        print("✅ 新逻辑：正确识别，只有测试书3需要导入")
    print("=" * 60)
