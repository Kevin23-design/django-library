#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
处理逾期图书的管理命令
定期检查所有逾期图书并自动扣费
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from library.models import Borrowing

class Command(BaseCommand):
    help = '处理逾期图书并自动扣费'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要处理的逾期图书，不实际执行扣费操作',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # 获取所有未归还且逾期的图书
        today = timezone.now().date()
        overdue_borrowings = Borrowing.objects.filter(
            is_return=False,
            date_due_to_returned__lt=today,
            is_overdue_charged=False
        )
        
        if not overdue_borrowings.exists():
            self.stdout.write(
                self.style.SUCCESS('✅ 没有需要处理的逾期图书')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'📋 发现 {overdue_borrowings.count()} 本逾期图书需要处理')
        )
        
        processed_count = 0
        total_charged = 0.0
        
        for borrowing in overdue_borrowings:
            book_price = borrowing.ISBN.get_price()
            overdue_days = (today - borrowing.date_due_to_returned).days
            
            self.stdout.write(
                f'📚 《{borrowing.ISBN.title[:40]}...》'
            )
            self.stdout.write(
                f'   借阅者: {borrowing.reader.name}'
            )
            self.stdout.write(
                f'   应还日期: {borrowing.date_due_to_returned}'
            )
            self.stdout.write(
                f'   逾期天数: {overdue_days} 天'
            )
            self.stdout.write(
                f'   图书价格: ¥{book_price:.2f}'
            )
            self.stdout.write(
                f'   当前余额: ¥{borrowing.reader.balance:.2f}'
            )
            
            if not dry_run:
                if borrowing.process_overdue_charge():
                    processed_count += 1
                    total_charged += book_price
                    new_balance = borrowing.reader.balance
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'   ✅ 已扣费 ¥{book_price:.2f}，新余额: ¥{new_balance:.2f}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('   ❌ 扣费失败')
                    )
            else:
                expected_balance = borrowing.reader.balance - book_price
                self.stdout.write(
                    self.style.WARNING(
                        f'   🔄 模拟扣费 ¥{book_price:.2f}，预期余额: ¥{expected_balance:.2f}'
                    )
                )
            
            self.stdout.write('   ' + '-' * 50)
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n📊 处理完成！'
                    f'\n   处理图书数量: {processed_count} 本'
                    f'\n   总扣费金额: ¥{total_charged:.2f}'
                )
            )
        else:
            total_would_charge = sum(b.ISBN.get_price() for b in overdue_borrowings)
            self.stdout.write(
                self.style.WARNING(
                    f'\n📊 模拟处理完成！'
                    f'\n   待处理图书数量: {overdue_borrowings.count()} 本'
                    f'\n   预计总扣费金额: ¥{total_would_charge:.2f}'
                    f'\n   使用 --dry-run=False 执行实际扣费操作'
                )
            )
