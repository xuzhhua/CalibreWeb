#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在Calibre数据库中查找匹配的书籍"""

import sqlite3
import os
import re
from app import app, db, Book

def clean_title(title):
    """清理书名，去除特殊字符和网址"""
    # 去除网址
    title = re.sub(r'\[www\.\w+\.com\]', '', title)
    # 去除常见的特殊后缀
    title = re.sub(r'[-_\s]+第[一二三四五六七八九十\d]+[卷册部集].*$', '', title)
    title = re.sub(r'[-_\s]+\d+.*$', '', title)
    # 去除括号内容
    title = re.sub(r'\s*[（(].*?[）)]', '', title)
    return title.strip()

def find_matches_in_calibre():
    """查找这4本书在Calibre中的可能匹配"""
    with app.app_context():
        # 获取缺少calibre_id的书籍
        missing_books = [
            105040, 105041, 105042, 105043
        ]
        
        # 获取Calibre数据库路径
        library_path = app.config.get('CALIBRE_LIBRARY_PATH')
        if not library_path or not os.path.exists(library_path):
            print("错误: Calibre库路径未配置或不存在")
            return
        
        calibre_db = os.path.join(library_path, 'metadata.db')
        if not os.path.exists(calibre_db):
            print(f"错误: Calibre数据库文件不存在: {calibre_db}")
            return
        
        conn = sqlite3.connect(calibre_db)
        cursor = conn.cursor()
        
        for book_id in missing_books:
            book = db.session.get(Book, book_id)
            if not book:
                continue
            
            print(f"\n{'='*100}")
            print(f"本地书籍 ID: {book.id}")
            print(f"书名: {book.title}")
            print(f"作者: {book.author or '未知'}")
            print(f"{'='*100}")
            
            # 方法1: 精确匹配
            cursor.execute("""
                SELECT b.id, b.title, a.name FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                WHERE b.title = ?
                LIMIT 5
            """, (book.title,))
            results = cursor.fetchall()
            
            if results:
                print("\n✓ 精确匹配:")
                for r in results:
                    print(f"  - Calibre ID: {r[0]}, 书名: {r[1]}, 作者: {r[2]}")
            else:
                print("\n✗ 精确匹配: 未找到")
            
            # 方法2: 清理后的书名匹配
            clean = clean_title(book.title)
            if clean != book.title:
                cursor.execute("""
                    SELECT b.id, b.title, a.name FROM books b
                    LEFT JOIN books_authors_link bal ON b.id = bal.book
                    LEFT JOIN authors a ON bal.author = a.id
                    WHERE b.title LIKE ?
                    LIMIT 5
                """, (f"{clean}%",))
                results = cursor.fetchall()
                
                if results:
                    print(f"\n✓ 清理后匹配 (清理后书名: {clean}):")
                    for r in results:
                        print(f"  - Calibre ID: {r[0]}, 书名: {r[1]}, 作者: {r[2]}")
                else:
                    print(f"\n✗ 清理后匹配 (清理后书名: {clean}): 未找到")
            
            # 方法3: 部分书名匹配（前10个字符）
            title_part = book.title[:10] if len(book.title) >= 10 else book.title
            cursor.execute("""
                SELECT b.id, b.title, a.name FROM books b
                LEFT JOIN books_authors_link bal ON b.id = bal.book
                LEFT JOIN authors a ON bal.author = a.id
                WHERE b.title LIKE ?
                LIMIT 5
            """, (f"%{title_part}%",))
            results = cursor.fetchall()
            
            if results:
                print(f"\n✓ 部分匹配 (搜索: {title_part}):")
                for r in results:
                    print(f"  - Calibre ID: {r[0]}, 书名: {r[1]}, 作者: {r[2]}")
            else:
                print(f"\n✗ 部分匹配: 未找到")
        
        conn.close()
        print(f"\n{'='*100}")
        print("查询完成！")

if __name__ == '__main__':
    find_matches_in_calibre()
