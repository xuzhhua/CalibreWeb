"""
查找Calibre数据库中的重复书籍
"""
import sqlite3
import os
from dotenv import load_dotenv
from collections import Counter

def find_calibre_duplicates():
    """查找Calibre中的重复书籍"""
    load_dotenv()
    calibre_path = os.getenv('CALIBRE_LIBRARY_PATH')
    calibre_db = os.path.join(calibre_path, 'metadata.db')
    
    if not os.path.exists(calibre_db):
        print(f"❌ Calibre数据库不存在: {calibre_db}")
        return
    
    print("=" * 80)
    print("Calibre数据库重复书籍检查")
    print("=" * 80)
    
    conn = sqlite3.connect(calibre_db)
    cursor = conn.cursor()
    
    # 获取所有书籍
    cursor.execute("""
        SELECT b.id, b.title, 
               (SELECT a.name FROM authors a 
                JOIN books_authors_link bal ON a.id = bal.author 
                WHERE bal.book = b.id LIMIT 1) as author,
               b.path
        FROM books b
        ORDER BY b.title, author
    """)
    
    books = cursor.fetchall()
    print(f"Calibre总书籍数: {len(books)}")
    
    # 统计重复
    key_to_books = {}
    for book_id, title, author, path in books:
        key = (title, author or '')
        if key not in key_to_books:
            key_to_books[key] = []
        key_to_books[key].append({
            'id': book_id,
            'title': title,
            'author': author or '未知作者',
            'path': path
        })
    
    # 找出重复的
    duplicates = {k: v for k, v in key_to_books.items() if len(v) > 1}
    
    print(f"唯一键数: {len(key_to_books)}")
    print(f"重复组数: {len(duplicates)}")
    
    if duplicates:
        total_duplicate_books = sum(len(v) for v in duplicates.values())
        extra_books = sum(len(v) - 1 for v in duplicates.values())
        print(f"重复书籍总数: {total_duplicate_books}")
        print(f"多余条目数: {extra_books}")
        
        print("\n重复的书籍详情:")
        print("-" * 80)
        
        for i, ((title, author), book_list) in enumerate(duplicates.items(), 1):
            print(f"\n{i}. {title}")
            print(f"   作者: {author}")
            print(f"   重复次数: {len(book_list)}")
            for book in book_list:
                print(f"     - ID={book['id']}, Path={book['path']}")
    else:
        print("\n✅ 没有发现重复的书籍")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == '__main__':
    find_calibre_duplicates()
