#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User

import uuid, os


def custom_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = '{}.{}'.format(uuid.uuid4().hex[:10], ext)
    return filename


class Reader(models.Model):
    class Meta:
        verbose_name = '读者'
        verbose_name_plural = '读者'

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='读者')
    name = models.CharField(max_length=16, unique=True, verbose_name='姓名')
    phone = models.IntegerField(unique=True, verbose_name='电话',blank=True,null=True)
    max_borrowing = models.IntegerField(default=5, verbose_name='可借数量')
    balance = models.FloatField(default=0.0, verbose_name='余额')
    photo = models.ImageField(blank=True, upload_to=custom_path, verbose_name='头像')
    borrowing_visible = models.BooleanField(default=False, verbose_name='借阅信息是否公开')  # 新增隐私设置字段

    STATUS_CHOICES = (
        (0, 'normal'),
        (-1, 'overdue')
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=0,
    )

    def __str__(self):
        return self.name
    
    def get_max_borrowing_by_balance(self):
        """根据余额计算最大借书数量：基础5本 + 每10元增加1本"""
        base_limit = 5
        bonus_books = int(self.balance // 10)
        return base_limit + bonus_books
    
    def get_max_renewals_by_balance(self):
        """根据余额计算续借次数：余额超过50元可续借2次，否则1次"""
        return 2 if self.balance >= 50 else 1
    
    def can_borrow_more(self):
        """检查是否还能借更多书（余额为负数时不能借书）"""
        if self.balance < 0:
            return False
        current_borrowings = self.borrowing_set.filter(is_return=False).count()
        max_allowed = self.get_max_borrowing_by_balance()
        return current_borrowings < max_allowed
    
    def remaining_borrow_count(self):
        """获取剩余可借数量（余额为负数时返回0）"""
        if self.balance < 0:
            return 0
        current_borrowings = self.borrowing_set.filter(is_return=False).count()
        max_allowed = self.get_max_borrowing_by_balance()
        return max(0, max_allowed - current_borrowings)
    
    def can_refund(self):
        """检查是否可以退款（余额为负数或有未归还图书时不能退款）"""
        if self.balance <= 0:
            return False
        current_borrowings = self.borrowing_set.filter(is_return=False).count()
        return current_borrowings == 0


from django.db import models

class Book(models.Model):
    title = models.CharField("题名/责任者", max_length=500)
    image = models.ImageField("封面", blank=True, null=True)
    publisher_info = models.CharField("出版发行项", max_length=500, blank=True, null=True)
    isbn = models.CharField("ISBN及定价", max_length=200, blank=True, null=True)
    physical_description = models.CharField("载体形态项", max_length=500, blank=True, null=True)
    other_titles = models.CharField("其它题名", max_length=500, blank=True, null=True)
    series = models.CharField("丛编项", max_length=500, blank=True, null=True)
    authors = models.CharField("个人责任者", max_length=500, blank=True, null=True)
    subjects = models.CharField("学科主题", max_length=500, blank=True, null=True)
    classification = models.CharField("中图法分类号", max_length=100, blank=True, null=True)
    notes = models.TextField("内容附注", blank=True, null=True)
    # 馆藏信息
    location = models.CharField(
        '馆藏位置',
        blank=True, null=True
    )
    total_copies = models.PositiveIntegerField("馆藏数量", default=100)
    available_copies = models.PositiveIntegerField("可借数量", default=100)

    # 系统信息
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    is_active = models.BooleanField("是否可借", default=True)

    def __str__(self):
        return self.title
    
    def get_price(self):
        """从ISBN字段中提取价格"""
        if not self.isbn:
            return 0.0
        
        import re
        # 匹配CNY后面的数字部分
        price_match = re.search(r'CNY(\d+(?:\.\d+)?)', self.isbn)
        if price_match:
            try:
                return float(price_match.group(1))
            except ValueError:
                return 0.0
        return 0.0

    class Meta:
        verbose_name = "图书"
        verbose_name_plural = "图书"


class Borrowing(models.Model):
    class Meta:
        verbose_name = '借阅'
        verbose_name_plural = '借阅'

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, verbose_name='读者')
    ISBN = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name='ISBN')
    date_issued = models.DateField(verbose_name='借出时间')
    date_due_to_returned = models.DateField(verbose_name='应还时间')
    date_returned = models.DateField(null=True, verbose_name='还书时间')
    amount_of_fine = models.FloatField(default=0.0, verbose_name='欠款')
    renewal_count = models.IntegerField(default=0, verbose_name='续借次数')  # 新增续借次数字段
    is_return = models.BooleanField(default=False, verbose_name='是否归还')
    is_overdue_charged = models.BooleanField(default=False, verbose_name='是否已逾期扣费')  # 新增逾期扣费标记
    overdue_amount = models.FloatField(default=0.0, verbose_name='逾期扣费金额')  # 新增逾期扣费金额

    def __str__(self):
        return '{} 借了 {}'.format(self.reader, self.ISBN)
    
    def is_overdue(self):
        """检查是否逾期"""
        from django.utils import timezone
        if self.is_return:
            return False
        return timezone.now().date() > self.date_due_to_returned
    
    def process_overdue_charge(self):
        """处理逾期扣费"""
        if self.is_overdue_charged or self.is_return:
            return False
        
        if self.is_overdue():
            book_price = self.ISBN.get_price()
            if book_price > 0:
                # 从读者余额中扣除书本价格
                self.reader.balance -= book_price
                self.overdue_amount = book_price
                self.is_overdue_charged = True
                self.amount_of_fine = book_price
                
                # 保存更改
                self.reader.save()
                self.save()
                return True
        return False
    
    def refund_overdue_charge(self):
        """归还时退回逾期扣费"""
        if self.is_overdue_charged and self.overdue_amount > 0:
            # 将扣除的金额返回给读者
            self.reader.balance += self.overdue_amount
            self.amount_of_fine = 0.0
            
            # 保存更改
            self.reader.save()
            self.save()
            return True
        return False
