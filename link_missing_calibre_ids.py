#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""手动关联缺少的calibre_id"""

from app import app, db, Book

def link_calibre_ids():
    """为这4本书关联calibre_id"""
    # 映射关系：本地ID -> Calibre ID
    mappings = {
        105040: 25325,   # 《砍刀术练习法·一路》尹玉章[www.neikuw.com]
        105041: 25332,   # 中国名臣全传 （上册）
        105042: 25333,   # 中国集团公司资金管理 理论、实践与案例 1...
        105043: 130569,  # 败北女角太多了！-第一卷-迷糊轻小说
    }
    
    with app.app_context():
        success_count = 0
        
        for local_id, calibre_id in mappings.items():
            book = db.session.get(Book, local_id)
            if book:
                old_calibre_id = book.calibre_id
                book.calibre_id = calibre_id
                db.session.commit()
                
                print(f"✓ 已关联: ID {local_id} ({book.title}) -> calibre_id: {calibre_id}")
                success_count += 1
            else:
                print(f"✗ 未找到本地书籍 ID: {local_id}")
        
        print(f"\n{'='*80}")
        print(f"完成！成功关联 {success_count}/{len(mappings)} 本书")
        print(f"{'='*80}")
        
        # 验证结果
        print("\n验证结果:")
        remaining = Book.query.filter(Book.calibre_id.is_(None)).count()
        print(f"剩余未关联calibre_id的书籍数量: {remaining}")

if __name__ == '__main__':
    link_calibre_ids()
