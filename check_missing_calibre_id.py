#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查本地数据库中缺少calibre_id的图书"""

from app import app, db, Book

def check_missing_calibre_id():
    """检查并列出所有calibre_id为None的图书"""
    with app.app_context():
        books_without_calibre_id = Book.query.filter(Book.calibre_id.is_(None)).all()
        total = len(books_without_calibre_id)
        
        print(f"找到 {total} 本书的calibre_id为None\n")
        
        if total > 0:
            print("详细列表:")
            print("-" * 100)
            print(f"{'序号':<6} {'本地ID':<10} {'书名':<50} {'作者':<20}")
            print("-" * 100)
            
            for i, book in enumerate(books_without_calibre_id, 1):
                title = book.title[:47] + "..." if len(book.title) > 50 else book.title
                author = (book.author[:17] + "..." if book.author and len(book.author) > 20 
                         else book.author or "未知")
                print(f"{i:<6} {book.id:<10} {title:<50} {author:<20}")
            
            print("-" * 100)
            print(f"\n总计: {total} 本书缺少calibre_id")
        else:
            print("✓ 所有书籍都已关联calibre_id！")

if __name__ == '__main__':
    check_missing_calibre_id()
