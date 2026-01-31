"""
查找缺失的书籍
精确定位Calibre中有但本地数据库没有的书籍
"""
from app import app, db, Book
import sqlite3
import os
from dotenv import load_dotenv

def find_missing_books():
    """查找缺失的书籍"""
    with app.app_context():
        load_dotenv()
        calibre_path = os.getenv('CALIBRE_LIBRARY_PATH')
        calibre_db = os.path.join(calibre_path, 'metadata.db')
        
        if not os.path.exists(calibre_db):
            print(f"❌ Calibre数据库不存在: {calibre_db}")
            return
        
        print("=" * 80)
        print("查找缺失的书籍")
        print("=" * 80)
        
        # 构建本地书籍索引
        print("\n正在构建本地书籍索引...")
        local_books = Book.query.all()
        local_keys = set()
        local_dict = {}
        
        for book in local_books:
            key = (book.title, book.author or '')
            local_keys.add(key)
            local_dict[key] = book
        
        print(f"本地书籍总数: {len(local_books)}")
        print(f"本地唯一键数: {len(local_keys)}")
        
        # 扫描Calibre数据库
        print("\n正在扫描Calibre数据库...")
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM books")
        calibre_total = cursor.fetchone()[0]
        print(f"Calibre书籍总数: {calibre_total}")
        
        # 获取所有Calibre书籍
        cursor.execute("""
            SELECT b.id, b.title, 
                   (SELECT a.name FROM authors a 
                    JOIN books_authors_link bal ON a.id = bal.author 
                    WHERE bal.book = b.id LIMIT 1) as author,
                   b.path
            FROM books b
        """)
        
        missing_books = []
        calibre_keys = set()
        checked_count = 0
        
        for calibre_id, title, author, path in cursor.fetchall():
            checked_count += 1
            key = (title, author or '')
            calibre_keys.add(key)
            
            if key not in local_keys:
                missing_books.append({
                    'calibre_id': calibre_id,
                    'title': title,
                    'author': author or '未知作者',
                    'path': path
                })
            
            if checked_count % 10000 == 0:
                print(f"  已检查: {checked_count}/{calibre_total}")
        
        conn.close()
        
        print(f"\n检查完成: 共检查 {checked_count} 本书")
        print(f"Calibre唯一键数: {len(calibre_keys)}")
        
        # 显示结果
        print("\n" + "=" * 80)
        print(f"【结果】缺失的书籍数量: {len(missing_books)}")
        print("=" * 80)
        
        if missing_books:
            print("\n缺失的书籍列表:")
            print("-" * 80)
            for i, book in enumerate(missing_books, 1):
                print(f"{i}. [ID:{book['calibre_id']}] {book['title']}")
                print(f"   作者: {book['author']}")
                print(f"   路径: {book['path']}")
                print()
        else:
            print("\n✅ 未发现缺失的书籍！")
            print("\n可能的原因:")
            print("  1. Calibre和本地的书籍数量统计方式不同")
            print("  2. 存在重复的书籍记录")
            print("  3. 数据库索引问题")
        
        # 检查重复
        print("\n【额外检查】重复的书籍")
        print("-" * 80)
        duplicate_count = len(local_books) - len(local_keys)
        if duplicate_count > 0:
            print(f"⚠️  本地有 {duplicate_count} 条重复记录")
            
            # 找出重复的书
            from collections import Counter
            key_counts = Counter()
            for book in local_books:
                key = (book.title, book.author or '')
                key_counts[key] += 1
            
            duplicates = [(key, count) for key, count in key_counts.items() if count > 1]
            if duplicates:
                print(f"\n重复的书籍（前10个）:")
                for (title, author), count in duplicates[:10]:
                    print(f"  - {title} by {author}: {count} 次")
        else:
            print("✅ 无重复记录")
        
        # 检查孤立书籍
        print("\n【额外检查】孤立的书籍（本地有但Calibre没有）")
        print("-" * 80)
        orphaned_books = []
        for key in local_keys:
            if key not in calibre_keys:
                orphaned_books.append(local_dict[key])
        
        if orphaned_books:
            print(f"⚠️  发现 {len(orphaned_books)} 本孤立书籍")
            print("\n孤立书籍列表（前10本）:")
            for book in orphaned_books[:10]:
                print(f"  - [ID:{book.id}] {book.title} by {book.author or '未知'}")
        else:
            print("✅ 无孤立书籍")
        
        print("\n" + "=" * 80)

if __name__ == '__main__':
    find_missing_books()
