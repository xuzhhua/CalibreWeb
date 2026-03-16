"""
数据库迁移脚本 - 更新现有用户审核状态
将所有现有用户设置为已审核状态
"""
from app import app, db, User
from sqlalchemy import inspect, text

def migrate_users():
    """更新现有用户"""
    with app.app_context():
        try:
            # 检查 is_approved 列是否存在
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'is_approved' not in columns:
                print("检测到数据库缺少 is_approved 列，正在添加...")
                # 添加 is_approved 列，默认值为 True（保持现有用户可用）
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE user ADD COLUMN is_approved BOOLEAN DEFAULT 1'))
                    conn.commit()
                print("✓ 成功添加 is_approved 列")
            else:
                print("✓ is_approved 列已存在")
            
            # 更新所有用户为已审核状态
            users = User.query.all()
            updated_count = 0
            
            for user in users:
                if not user.is_approved:
                    user.is_approved = True
                    updated_count += 1
            
            db.session.commit()
            print(f"✓ 成功更新 {updated_count} 个用户的审核状态")
            print(f"总用户数: {len(users)}")
            
            # 显示所有用户状态
            print("\n当前用户列表:")
            print("-" * 60)
            for user in users:
                status = "管理员" if user.is_admin else ("已审核" if user.is_approved else "待审核")
                print(f"  {user.username:20s} | {user.email:25s} | {status}")
            
        except Exception as e:
            print(f"✗ 迁移失败: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    print("开始数据库迁移...")
    print("=" * 60)
    migrate_users()
    print("=" * 60)
    print("迁移完成！")
