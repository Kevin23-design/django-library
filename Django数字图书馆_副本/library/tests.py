import os
import random

import django
from datetime import datetime, timedelta
from django.utils import timezone
# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_management.settings')
django.setup()

from django.contrib.auth.models import User
from library.models import Reader, Book, Borrowing

# 配置参数
NUM_READERS = 20  # 想生成的读者数量
NUM_BOOKS = 30  # 想生成的图书数量
MAX_BORROWING_PER_READER = 5  # 每个读者最大借阅数

# 中文姓名列表
CHINESE_NAMES = [
    '张三', '李四', '王五', '赵六', '钱七',
    '孙八', '周九', '吴十', '郑十一', '王十二',
    '刘明', '陈华', '杨光', '黄强', '吴芳',
    '林小', '徐大', '胡伟', '朱莉', '高杰'
]



def generate_phone_number():
    """生成不重复的手机号"""
    while True:
        phone = '1' + ''.join([str(random.randint(0, 9)) for _ in range(10)])
        if not Reader.objects.filter(phone=phone).exists():
            return phone


def create_users_and_readers():
    """创建不存在的用户和读者"""
    existing_count = User.objects.count()
    if existing_count >= NUM_READERS:
        print(f"已有 {existing_count} 个用户，跳过创建")
        return

    print("正在创建用户和读者...")
    created = 0
    for name in random.sample(CHINESE_NAMES, min(len(CHINESE_NAMES), NUM_READERS)):
        if User.objects.filter(first_name=name).exists():
            continue

        username = f'user{random.randint(1000, 9999)}'
        while User.objects.filter(username=username).exists():
            username = f'user{random.randint(1000, 9999)}'

        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='123456',
            first_name=name
        )

        Reader.objects.create(
            user=user,
            name=name,
            phone=generate_phone_number(),
            max_borrowing=random.randint(3, 10),
            balance=round(random.uniform(0, 100), 2),
            status=0
        )
        created += 1
    print(f"成功创建 {created} 个新用户和读者")



def create_borrowing_records():
    """为已有用户和图书创建借阅记录"""
    readers = list(Reader.objects.all())
    books = list(Book.objects.filter(is_active=True, available_copies__gt=0))

    if not readers or not books:
        print("缺少读者或可借图书，无法创建借阅记录")
        return

    print("正在创建借阅记录...")
    created = 0
    for reader in random.sample(readers, min(len(readers), NUM_READERS)):
        # 每个读者借1-5本书
        for _ in range(random.randint(1, MAX_BORROWING_PER_READER)):
            if reader.max_borrowing <= 0:
                break

            book = random.choice(books)
            days_ago = random.randint(1, 60)
            date_issued = timezone.now() - timedelta(days=days_ago)
            date_due = date_issued + timedelta(days=30)

            # 50%几率已归还
            if random.choice([True, False]):
                date_returned = date_issued + timedelta(days=random.randint(1, 40))
                is_return = True
                fine = max(0, (date_returned - date_due).days) * 0.1
            else:
                date_returned = None
                is_return = False
                fine = 0.0

            Borrowing.objects.create(
                reader=reader,
                ISBN=book,
                date_issued=date_issued,
                date_due_to_returned=date_due,
                date_returned=date_returned,
                amount_of_fine=fine,
                is_return=is_return
            )

            if not is_return:
                book.available_copies -= 1
                book.save()
                reader.max_borrowing -= 1
                reader.save()

            created += 1
    print(f"成功创建 {created} 条借阅记录")


def main():
    print("=== 开始生成测试数据 ===")
    create_users_and_readers()
    create_borrowing_records()
    print("=== 测试数据生成完成 ===")


if __name__ == '__main__':
    main()