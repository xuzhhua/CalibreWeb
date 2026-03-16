#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为Book表添加calibre_id字段
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Book
import sqlite3

def migrate_add_calibre_id():
    """为Book表添加calibre_id字段"""
    with app.app_context():
        try:
            # 检查字段是否已存在
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('book')]
            
            if 'calibre_id' in columns:
                print("✓ calibre_id字段已存在，无需迁移")
                return True
            
            print("正在添加calibre_id字段...")
            
            # 添加新字段
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE book ADD COLUMN calibre_id INTEGER'))
                conn.execute(db.text('CREATE INDEX ix_book_calibre_id ON book (calibre_id)'))
                conn.commit()
            
            print("✓ 成功添加calibre_id字段和索引")
            
            # 尝试从Calibre数据库匹配并填充calibre_id
            fill_calibre_ids()
            
            return True
            
        except Exception as e:
            print(f"✗ 迁移失败: {e}")
            return False


def fill_calibre_ids():
    """尝试为现有书籍填充calibre_id"""
    calibre_library_path = app.config.get('CALIBRE_LIBRARY_PATH')
    if not calibre_library_path or not os.path.exists(calibre_library_path):
        print("未配置Calibre书库路径，跳过calibre_id填充")
        return
    
    calibre_db = os.path.join(calibre_library_path, 'metadata.db')
    if not os.path.exists(calibre_db):
        print("未找到Calibre数据库，跳过calibre_id填充")
        return
    
    try:
        print("正在从Calibre数据库匹配书籍...")
        
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        books = Book.query.filter(Book.calibre_id == None).all()
        matched_count = 0
        
        for book in books:
            # 尝试匹配书名和作者
            cursor.execute("""
                SELECT b.id FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                WHERE b.title = ? AND (a.name = ? OR (a.name IS NULL AND ? IS NULL))
                LIMIT 1
            """, (book.title, book.author, book.author))
            
            result = cursor.fetchone()
            if result:
                book.calibre_id = result[0]
                matched_count += 1
        
        db.session.commit()
        conn.close()
        
        print(f"✓ 成功匹配 {matched_count}/{len(books)} 本书籍的calibre_id")
        
    except Exception as e:
        print(f"填充calibre_id时出错: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("数据库迁移：添加calibre_id字段")
    print("=" * 50)
    
    success = migrate_add_calibre_id()
    
    if success:
        print("\n迁移完成！")
    else:
        print("\n迁移失败，请检查错误信息")
        sys.exit(1)
