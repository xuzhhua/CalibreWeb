"""
诊断书籍数据库问题
检查Book表结构、数据完整性和差异分析逻辑
"""
from app import app, db, Book
from sqlalchemy import inspect, text
import sqlite3
import os

def diagnose_book_database():
    """诊断书籍数据库"""
    with app.app_context():
        print("=" * 80)
        print("书籍数据库诊断工具")
        print("=" * 80)
        
        # 1. 检查Book表结构
        print("\n【1】检查Book表结构")
        print("-" * 80)
        inspector = inspect(db.engine)
        columns = inspector.get_columns('book')
        print(f"Book表列数: {len(columns)}")
        for col in columns:
            nullable = "可空" if col['nullable'] else "不可空"
            default = f", 默认={col['default']}" if col.get('default') else ""
            print(f"  - {col['name']:20s} : {str(col['type']):15s} ({nullable}{default})")
        
        # 2. 检查数据统计
        print("\n【2】本地数据库统计")
        print("-" * 80)
        total_books = Book.query.count()
        print(f"总书籍数: {total_books}")
        
        if total_books > 0:
            # 统计作者为NULL的书籍
            books_with_null_author = Book.query.filter(Book.author == None).count()
            books_with_empty_author = Book.query.filter(Book.author == '').count()
            books_with_author = Book.query.filter(Book.author != None, Book.author != '').count()
            
            print(f"  - 作者为NULL: {books_with_null_author} 本")
            print(f"  - 作者为空字符串: {books_with_empty_author} 本")
            print(f"  - 有作者信息: {books_with_author} 本")
            
            # 统计完整性
            books_with_cover = Book.query.filter(Book.cover_image != None, Book.cover_image != '').count()
            books_with_file = Book.query.filter(Book.file_path != None, Book.file_path != '').count()
            books_with_desc = Book.query.filter(Book.description != None, Book.description != '').count()
            books_with_tags = Book.query.filter(Book.tags != None, Book.tags != '').count()
            
            print(f"  - 有封面: {books_with_cover} 本 ({books_with_cover/total_books*100:.1f}%)")
            print(f"  - 有文件: {books_with_file} 本 ({books_with_file/total_books*100:.1f}%)")
            print(f"  - 有简介: {books_with_desc} 本 ({books_with_desc/total_books*100:.1f}%)")
            print(f"  - 有标签: {books_with_tags} 本 ({books_with_tags/total_books*100:.1f}%)")
            
            # 示例数据
            print("\n前5本书示例:")
            sample_books = Book.query.limit(5).all()
            for i, book in enumerate(sample_books, 1):
                author_info = f"'{book.author}'" if book.author else "NULL"
                print(f"  {i}. [{book.id}] {book.title} by {author_info}")
        
        # 3. 检查Calibre数据库
        print("\n【3】Calibre数据库统计")
        print("-" * 80)
        
        # 获取Calibre数据库路径
        from dotenv import load_dotenv
        load_dotenv()
        calibre_path = os.getenv('CALIBRE_LIBRARY_PATH')
        
        if not calibre_path or not os.path.exists(calibre_path):
            print(f"❌ Calibre路径不存在: {calibre_path}")
            return
        
        calibre_db = os.path.join(calibre_path, 'metadata.db')
        if not os.path.exists(calibre_db):
            print(f"❌ Calibre数据库不存在: {calibre_db}")
            return
        
        print(f"Calibre数据库: {calibre_db}")
        
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        # 统计总数
        cursor.execute("SELECT COUNT(*) FROM books")
        calibre_total = cursor.fetchone()[0]
        print(f"Calibre总书籍数: {calibre_total}")
        
        # 统计作者情况
        cursor.execute("""
            SELECT COUNT(*) FROM books b
            WHERE NOT EXISTS (
                SELECT 1 FROM books_authors_link bal 
                WHERE bal.book = b.id
            )
        """)
        calibre_no_author = cursor.fetchone()[0]
        print(f"  - 无作者记录: {calibre_no_author} 本")
        
        # 示例数据
        print("\nCalibre前5本书示例:")
        cursor.execute("""
            SELECT b.id, b.title, 
                   (SELECT a.name FROM authors a 
                    JOIN books_authors_link bal ON a.id = bal.author 
                    WHERE bal.book = b.id LIMIT 1) as author
            FROM books b
            LIMIT 5
        """)
        for i, (book_id, title, author) in enumerate(cursor.fetchall(), 1):
            author_info = f"'{author}'" if author else "NULL"
            print(f"  {i}. [{book_id}] {title} by {author_info}")
        
        # 4. 差异分析模拟
        print("\n【4】差异分析逻辑测试")
        print("-" * 80)
        
        # 构建本地key集合
        local_books = Book.query.all()
        local_keys_old = set()
        local_keys_new = set()
        
        for book in local_books:
            key_old = (book.title, book.author)
            key_new = (book.title, book.author or '')
            local_keys_old.add(key_old)
            local_keys_new.add(key_new)
        
        # 获取Calibre书籍
        cursor.execute("""
            SELECT b.id, b.title, 
                   (SELECT a.name FROM authors a 
                    JOIN books_authors_link bal ON a.id = bal.author 
                    WHERE bal.book = b.id LIMIT 1) as author
            FROM books b
            LIMIT 100
        """)
        
        calibre_books = cursor.fetchall()
        not_in_local_old = []
        not_in_local_new = []
        
        for book_id, title, author in calibre_books:
            key_old = (title, author)
            key_new = (title, author or '')
            
            if key_old not in local_keys_old:
                not_in_local_old.append((book_id, title, author))
            
            if key_new not in local_keys_new:
                not_in_local_new.append((book_id, title, author))
        
        print(f"使用旧逻辑 (key包含None): {len(not_in_local_old)} 本待导入")
        print(f"使用新逻辑 (key转换''): {len(not_in_local_new)} 本待导入")
        
        if not_in_local_old != not_in_local_new:
            print("\n⚠️  检测到逻辑差异！")
            diff_count = abs(len(not_in_local_old) - len(not_in_local_new))
            print(f"差异数量: {diff_count} 本")
            
            # 显示差异示例
            if len(not_in_local_new) > len(not_in_local_old):
                print("\n新逻辑多识别的书籍（前5本）:")
                extra = [x for x in not_in_local_new if x not in not_in_local_old][:5]
                for book_id, title, author in extra:
                    author_info = f"'{author}'" if author else "NULL"
                    print(f"  - [{book_id}] {title} by {author_info}")
        else:
            print("✅ 两种逻辑结果一致")
        
        conn.close()
        
        # 5. 检查是否需要数据清理
        print("\n【5】数据完整性建议")
        print("-" * 80)
        
        issues = []
        if books_with_null_author > 0:
            issues.append(f"发现 {books_with_null_author} 本书的作者为NULL")
        
        if total_books < calibre_total:
            missing = calibre_total - total_books
            issues.append(f"本地少了 {missing} 本书")
        
        if total_books > calibre_total:
            extra = total_books - calibre_total
            issues.append(f"本地多了 {extra} 本书（可能是孤立数据）")
        
        if issues:
            print("⚠️  发现以下问题:")
            for issue in issues:
                print(f"  - {issue}")
            print("\n建议:")
            print("  1. 运行 migrate_books.py 清理数据")
            print("  2. 重新运行差异分析")
        else:
            print("✅ 数据完整性良好")
        
        print("\n" + "=" * 80)

if __name__ == '__main__':
    diagnose_book_database()
