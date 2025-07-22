#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import re
import time
import uuid
from cmath import phase

import jieba
import requests
from django.core.cache import cache
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django import forms
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

import json

from django.views.decorators.csrf import csrf_exempt

from library.models import Book, Reader, User, Borrowing
from library.forms import SearchForm, LoginForm, RegisterForm, ResetPasswordForm
from library.email_utils import (
    generate_verification_code, 
    send_reset_password_email, 
    store_verification_code, 
    verify_code, 
    is_code_valid, 
    get_code_remaining_time,
    send_registration_email,
    store_registration_verification_code,
    verify_registration_code,
    is_registration_code_valid,
    get_registration_code_remaining_time
)


def index(request):
    context = {
        'searchForm': SearchForm(),
    }
    return render(request, 'library/index.html', context)


def user_login(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('/')

    state = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = auth.authenticate(username=username, password=password)

        if user:
            if user.is_active:
                auth.login(request, user)
                # 检查是否为admin用户
                if username == 'admin':
                    return HttpResponseRedirect('/admin-dashboard/')
                else:
                    return HttpResponseRedirect('/')
            else:
                return HttpResponse(u'Your account is disabled.')
        else:
            state = 'not_exist_or_password_error'

    context = {
        'loginForm': LoginForm(),
        'state': state,
    }

    return render(request, 'library/login.html', context)


def user_register(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('/')

    registerForm = RegisterForm()

    state = None
    if request.method == 'POST':
        registerForm = RegisterForm(request.POST, request.FILES)
        password = request.POST.get('password', '')
        repeat_password = request.POST.get('re_password', '')
        email = request.POST.get('email', '').strip()
        
        if password == '' or repeat_password == '':
            state = 'empty'
        elif password != repeat_password:
            state = 'repeat_error'
        elif not email:
            state = 'empty_email'
        else:
            username = request.POST.get('username', '')
            name = request.POST.get('name', '')
            
            # 处理用户名/手机号
            if isinstance(username, int):
                phone = int(username)
            else:
                phone = None
                
            if User.objects.filter(username=username):
                state = 'user_exist'
            else:
                # 生成验证码并发送邮件
                verification_code = generate_verification_code()
                success, message = send_registration_email(email, verification_code)
                
                if success:
                    # 存储验证码
                    store_registration_verification_code(email, verification_code)
                    
                    # 将注册信息存储到session中
                    request.session['register_data'] = {
                        'username': username,
                        'name': name,
                        'email': email,
                        'password': password,
                        'phone': phone
                    }
                    
                    # 处理头像
                    if 'photo' in request.FILES:
                        # 将头像文件保存到临时位置
                        import os
                        import uuid
                        from django.conf import settings
                        
                        photo = request.FILES['photo']
                        temp_filename = f"temp_{uuid.uuid4()}_{photo.name}"
                        temp_path = os.path.join(settings.MEDIA_ROOT, 'temp', temp_filename)
                        
                        # 确保temp目录存在
                        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                        
                        with open(temp_path, 'wb+') as destination:
                            for chunk in photo.chunks():
                                destination.write(chunk)
                        
                        request.session['register_data']['photo_path'] = temp_path
                    
                    # 跳转到验证页面
                    return HttpResponseRedirect(f'/register/verify?email={email}')
                else:
                    state = 'email_send_failed'

    context = {
        'state': state,
        'registerForm': registerForm,
    }

    return render(request, 'library/register.html', context)


def register_verify(request):
    """注册邮箱验证"""
    email = request.GET.get('email', '')
    state = None
    
    if not email:
        return HttpResponseRedirect('/register/')
    
    # 检查验证码是否还有效
    if not is_registration_code_valid(email):
        state = 'code_expired'
    
    # 获取剩余时间
    remaining_time = get_registration_code_remaining_time(email)
    
    if request.method == 'POST':
        verification_code = request.POST.get('verification_code', '').strip()
        
        if not verification_code:
            state = 'empty_code'
        else:
            # 验证验证码
            if verify_registration_code(email, verification_code):
                # 从session中获取注册数据
                register_data = request.session.get('register_data')
                if not register_data or register_data.get('email') != email:
                    state = 'session_expired'
                else:
                    try:
                        # 再次检查用户名是否已存在（防止在验证过程中被其他人注册）
                        if User.objects.filter(username=register_data['username']).exists():
                            state = 'username_taken_during_verification'
                        else:
                            # 创建用户
                            new_user = User.objects.create(
                                username=register_data['username'], 
                                email=register_data['email']
                            )
                            new_user.set_password(register_data['password'])
                            new_user.save()
                            
                            # 创建读者信息
                            new_reader = Reader.objects.create(
                                user=new_user, 
                                name=register_data['name'], 
                                phone=register_data.get('phone')
                            )
                            
                            # 处理头像
                            if 'photo_path' in register_data:
                                import os
                                import shutil
                                from django.conf import settings
                                
                                temp_path = register_data['photo_path']
                                if os.path.exists(temp_path):
                                    try:
                                        # 移动文件到正确位置
                                        filename = os.path.basename(temp_path).replace('temp_', '').split('_', 1)[-1]
                                        final_dir = os.path.join(settings.MEDIA_ROOT, 'reader_photos')
                                        os.makedirs(final_dir, exist_ok=True)
                                        final_path = os.path.join(final_dir, filename)
                                        shutil.move(temp_path, final_path)
                                        
                                        # 更新读者头像路径
                                        new_reader.photo = f'reader_photos/{filename}'
                                    except Exception as e:
                                        print(f"头像处理失败: {e}")
                                        # 头像处理失败不影响注册
                            
                            new_reader.save()
                            
                            # 清理session数据
                            del request.session['register_data']
                            
                            # 自动登录
                            auth.login(request, new_user)
                            
                            state = 'success'
                        
                    except Exception as e:
                        state = 'registration_failed'
                        print(f"注册失败: {e}")
            else:
                state = 'invalid_code'
    
    context = {
        'state': state,
        'email': email,
        'remaining_time': remaining_time,
    }
    return render(request, 'library/register_verify.html', context)


@login_required
@login_required
def set_password(request):
    user = request.user
    state = None
    
    if request.method == 'POST':
        method = request.POST.get('method', 'password')
        
        if method == 'password':
            # 使用原密码修改
            old_password = request.POST.get('old_password', '')
            new_password = request.POST.get('new_password', '')
            repeat_password = request.POST.get('repeat_password', '')

            if user.check_password(old_password):
                if not new_password:
                    state = 'empty'
                elif new_password != repeat_password:
                    state = 'repeat_error'
                else:
                    user.set_password(new_password)
                    user.save()
                    state = 'success'
            else:
                state = 'password_error'
                
        elif method == 'email':
            # 通过邮箱重置
            if user.email:
                # 生成验证码
                verification_code = generate_verification_code()
                
                # 发送邮件
                success, message = send_reset_password_email(user.email, verification_code)
                
                if success:
                    # 存储验证码
                    store_verification_code(user.email, verification_code)
                    # 跳转到验证码输入页面，但这次是用户已登录状态
                    return HttpResponseRedirect(f'/reset-password/verify?email={user.email}&from=settings')
                else:
                    state = 'email_failed'
            else:
                state = 'user_no_email'

    context = {
        'state': state,
        'resetPasswordForm': ResetPasswordForm(),
    }

    return render(request, 'library/set_password.html', context)


@login_required
def user_logout(request):
    auth.logout(request)
    return HttpResponseRedirect('/')


def profile(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/login')

    id = request.user.id
    try:
        reader = Reader.objects.get(user_id=id)
    except Reader.DoesNotExist:
        return HttpResponse('no this id reader')

    state = None
    
    # 处理余额充值和退款
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        if action == 'recharge':
            amount_str = request.POST.get('amount', '').strip()
            try:
                amount = float(amount_str)
                if amount > 0 and amount <= 1000:  # 限制充值金额
                    reader.balance += amount
                    reader.save()
                    state = 'recharge_success'
                elif amount <= 0:
                    state = 'invalid_amount'
                else:
                    state = 'amount_too_large'
            except (ValueError, TypeError):
                state = 'invalid_amount'
                
        elif action == 'refund':
            # 使用新的退款检查方法
            if not reader.can_refund():
                if reader.balance <= 0:
                    state = 'refund_no_balance'
                else:
                    state = 'refund_has_borrowings'
            else:
                # 记录退款金额（可用于日志记录）
                refund_amount = reader.balance
                reader.balance = 0.0
                reader.save()
                state = 'refund_success'
                
        elif action == 'refresh_overdue':
            # 刷新处理逾期扣费
            from django.utils import timezone
            overdue_borrowings = Borrowing.objects.filter(
                reader=reader,
                is_return=False,
                date_due_to_returned__lt=timezone.now().date(),
                is_overdue_charged=False
            )
            
            processed_count = 0
            total_charged = 0.0
            
            for borrowing in overdue_borrowings:
                if borrowing.process_overdue_charge():
                    processed_count += 1
                    total_charged += borrowing.overdue_amount
            
            if processed_count > 0:
                state = 'overdue_processed'
                # 可以在session中存储处理结果用于显示
                request.session['overdue_processed_count'] = processed_count
                request.session['overdue_charged_amount'] = total_charged
            else:
                state = 'no_overdue_found'
                
        elif action == 'toggle_borrowing_visibility':
            # 切换借阅信息可见性
            reader.borrowing_visible = not reader.borrowing_visible
            reader.save()
            state = 'privacy_updated'
            
        elif action == 'delete_account':
            # 删除账号处理
            # 检查是否有未归还的图书
            active_borrowings = Borrowing.objects.filter(reader=reader, is_return=False)
            
            if active_borrowings.exists():
                state = 'delete_failed_has_borrowings'
            else:
                # 执行账号删除
                # 1. 删除Reader记录
                user_to_delete = reader.user
                reader.delete()
                
                # 2. 删除User记录
                user_to_delete.delete()
                
                # 3. 登出并重定向到首页
                auth.logout(request)
                return HttpResponseRedirect('/?state=account_deleted')

    borrowing = Borrowing.objects.filter(reader=reader, is_return=False)
    
    context = {
        'state': state,
        'reader': reader,
        'borrowing': borrowing,
        'today': datetime.date.today(),  # 添加今天日期用于逾期判断
        'max_borrowing_by_balance': reader.get_max_borrowing_by_balance(),
        'max_renewals_by_balance': reader.get_max_renewals_by_balance(),
        'remaining_borrow_count': reader.remaining_borrow_count(),
    }
    return render(request, 'library/profile.html', context)


def reader_operation(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/login')

    action = request.GET.get('action', None)

    if action == 'return_book':
        id = request.GET.get('id', None)
        if not id:
            return HttpResponse('no id')
        b = Borrowing.objects.get(pk=id)
        
        # 归还前先退回逾期扣费（如果有的话）
        refund_applied = b.refund_overdue_charge()
        
        b.date_returned = datetime.date.today()
        if b.date_returned > b.date_due_to_returned:
            # 如果没有逾期扣费，则按原逻辑计算罚金
            if not b.is_overdue_charged:
                b.amount_of_fine = (b.date_returned - b.date_due_to_returned).total_seconds() / 24 / 3600 * 0.1
        b.is_return = True
        b.save()

        r = Reader.objects.get(user=request.user)
        r.max_borrowing += 1
        r.save()

        bk = Book.objects.get(pk=b.ISBN_id)
        bk.available_copies += 1
        bk.save()

        return HttpResponseRedirect('/profile?state=return_success')

    elif action == 'renew_book':
        id = request.GET.get('id', None)
        if not id:
            return HttpResponse('no id')
        
        b = Borrowing.objects.get(pk=id)
        reader = Reader.objects.get(user=request.user)
        
        # 定义续借费用
        RENEW_FEE = 3.0
        
        # 检查余额是否足够支付续借费用
        if reader.balance < RENEW_FEE:
            return HttpResponseRedirect('/profile?state=renew_insufficient_balance')
        
        # 检查续借次数限制
        max_renewals = reader.get_max_renewals_by_balance()
        
        if b.renewal_count >= max_renewals:
            return HttpResponseRedirect('/profile?state=renew_limit_exceeded')
        
        # 检查是否已经续借过太多次（额外安全检查）
        if (b.date_due_to_returned - b.date_issued) >= datetime.timedelta(days=90):
            return HttpResponseRedirect('/profile?state=renew_period_exceeded')
        
        # 执行续借：扣除费用并延长还书日期
        reader.balance -= RENEW_FEE
        reader.save()
        
        b.date_due_to_returned += datetime.timedelta(days=30)
        b.renewal_count += 1
        b.save()

        return HttpResponseRedirect('/profile?state=renew_success')

    return HttpResponseRedirect('/profile')


def book_search(request):
    search_by = request.GET.get('search_by', '书名')
    books = []
    current_path = request.get_full_path()

    keyword = request.GET.get('keyword', u'_书目列表')

    if keyword == u'_书目列表':
        books = Book.objects.all()
    else:
        if search_by == u'书名':
            keyword = request.GET.get('keyword', None)
            books = Book.objects.filter(title__contains=keyword).order_by('-created_at')[0:50]
        elif search_by == u'ISBN':
            keyword = request.GET.get('keyword', None)
            books = Book.objects.filter(isbn__contains=keyword).order_by('-created_at')[0:50]
        elif search_by == u'作者':
            keyword = request.GET.get('keyword', None)
            books = Book.objects.filter(authors__contains=keyword).order_by('-created_at')[0:50]

    paginator = Paginator(books, 5)
    page = request.GET.get('page', 1)

    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)

    # ugly solution for &page=2&page=3&page=4
    if '&page' in current_path:
        current_path = current_path.split('&page')[0]

    context = {
        'books': books,
        'search_by': search_by,
        'keyword': keyword,
        'current_path': current_path,
        'searchForm': SearchForm(),
    }
    return render(request, 'library/search.html', context)


def book_detail(request):
    ISBN = request.GET.get('isbn', None)
    print(ISBN)
    if not ISBN:
        return HttpResponse('there is no such an ISBN')
    try:
        book = Book.objects.get(pk=ISBN)
    except Book.DoesNotExist:
        return HttpResponse('there is no such an ISBN')

    action = request.GET.get('action', None)
    state = None

    if action == 'borrow':

        if not request.user.is_authenticated:
            state = 'no_user'
        else:
            reader = Reader.objects.get(user_id=request.user.id)
            
            # 检查余额是否为负数
            if reader.balance < 0:
                state = 'negative_balance'
            # 检查是否还能借更多书（包含余额和数量检查）
            elif reader.can_borrow_more():
                reader.max_borrowing -= 1
                reader.save()

                bk = Book.objects.get(pk=ISBN)
                bk.available_copies -= 1
                bk.save()

                issued = datetime.date.today()
                due_to_returned = issued + datetime.timedelta(30)

                b = Borrowing.objects.create(
                    reader=reader,
                    ISBN=bk,
                    date_issued=issued,
                    date_due_to_returned=due_to_returned)

                b.save()
                state = 'success'
                return HttpResponseRedirect('/profile?state=borrow_success')
            else:
                state = 'upper_limit'

    # 计算前七天的借阅数据
    from django.db.models import Count
    from django.utils import timezone
    import json
    
    today = timezone.now().date()
    # 生成前7天的日期列表
    dates = []
    borrowing_counts = []
    
    for i in range(6, -1, -1):  # 从6天前到今天
        date = today - datetime.timedelta(days=i)
        dates.append(date.strftime('%m-%d'))
        
        # 统计该日期的借阅数量
        count = Borrowing.objects.filter(
            ISBN=book,
            date_issued=date
        ).count()
        
        borrowing_counts.append(count)
    
    # 转换为JSON格式供前端图表使用
    borrowing_chart_dates = json.dumps(dates, ensure_ascii=False)
    borrowing_chart_data = json.dumps(borrowing_counts)
    
    # 处理主题标签，将字符串分割为列表
    subjects_list = []
    if book.subjects:
        # 尝试多种分隔符进行分割
        subjects_str = book.subjects.strip()
        if ';' in subjects_str:
            subjects_list = [s.strip() for s in subjects_str.split(';') if s.strip()]
        elif '；' in subjects_str:
            subjects_list = [s.strip() for s in subjects_str.split('；') if s.strip()]
        elif ',' in subjects_str:
            subjects_list = [s.strip() for s in subjects_str.split(',') if s.strip()]
        elif '，' in subjects_str:
            subjects_list = [s.strip() for s in subjects_str.split('，') if s.strip()]
        elif ' ' in subjects_str:
            subjects_list = [s.strip() for s in subjects_str.split(' ') if s.strip()]
        else:
            subjects_list = [subjects_str]

    context = {
        'state': state,
        'book': book,
        'borrowing_chart_dates': borrowing_chart_dates,
        'borrowing_chart_data': borrowing_chart_data,
        'subjects_list': subjects_list,
    }
    return render(request, 'library/book_detail.html', context)


def statistics(request):
    borrowing = Borrowing.objects.all()
    readerInfo = {}
    readerIdInfo = {}  # 新增：存储读者ID映射
    
    for r in borrowing:
        # 只统计设置为公开借阅信息的读者
        if r.reader.borrowing_visible:
            reader_name = r.reader.name
            reader_id = r.reader.id
            if reader_name not in readerInfo:
                readerInfo[reader_name] = 1
                readerIdInfo[reader_name] = reader_id  # 记录读者名对应的ID
            else:
                readerInfo[reader_name] += 1

    bookInfo = {}
    bookIdInfo = {}  # 新增：存储图书ID映射
    for r in borrowing:
        book_title = r.ISBN.title
        book_id = r.ISBN.id
        if book_title not in bookInfo:
            bookInfo[book_title] = 1
            bookIdInfo[book_title] = book_id  # 记录书名对应的ID
        else:
            bookInfo[book_title] += 1

    readerData = list(sorted(readerInfo, key=readerInfo.__getitem__, reverse=True))[0:10]
    bookData = list(sorted(bookInfo, key=bookInfo.__getitem__, reverse=True))[0:5]

    readerAmountData = [readerInfo[x] for x in readerData]
    bookAmountData = [bookInfo[x] for x in bookData]
    
    # 新增：为读者和图书数据添加ID信息
    readerDataWithIds = [{'name': name, 'id': readerIdInfo[name], 'count': readerInfo[name]} for name in readerData]
    bookDataWithIds = [{'title': title, 'id': bookIdInfo[title], 'count': bookInfo[title]} for title in bookData]

    context = {
        'readerData': readerData,
        'readerAmountData': readerAmountData,
        'readerDataWithIds': readerDataWithIds,  # 新增：包含ID的读者数据
        'bookData': bookData,
        'bookAmountData': bookAmountData,
        'bookDataWithIds': bookDataWithIds,  # 新增：包含ID的图书数据
    }
    return render(request, 'library/statistics.html', context)


def about(request):
    return render(request, 'library/about.html', {})

# 千帆API配置
QIANFAN_API_URL = "https://qianfan.baidubce.com/v2/chat/completions"
MODEL_NAME = "ernie-3.5-8k"  # 可根据需要改为ernie-4.0-8k等模型
access_token = 'bce-v3/----'
# 任务状态缓存时间(秒)
TASK_TIMEOUT = 300

@csrf_exempt
def chat_api(request):
    if request.method == 'POST':
        user_message = request.POST.get('message', '').strip()

        if not user_message:
            return JsonResponse({'status': 'error', 'message': '请输入查询内容'})

        # 生成唯一任务ID
        task_id = str(uuid.uuid4())

        # 将任务存入缓存(初始状态)
        cache.set(f'chat_task_{task_id}', {
            'status': 'pending',
            'message': user_message,
            'created_at': time.time()
        }, TASK_TIMEOUT)

        # 立即开始处理任务(实际项目中建议使用Celery异步任务)
        process_task(task_id, user_message)

        return JsonResponse({
            'status': 'success',
            'task_id': task_id
        })

    return JsonResponse({'status': 'error', 'message': '无效请求方法'}, status=400)
from django.core.cache import cache

def process_task(task_id, user_message):
    """实际处理任务的方法"""
    try:

        # 构造请求数据
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": f"""
                    你是一个专业的图书馆智能助手，请根据用户需求推荐书籍并提取关键词。

                    用户需求: {user_message}

                    请按以下格式回复:
                    1. 首先用自然友好的语言回答用户
                    2. 然后分析提取3个最相关的图书检索关键词，格式为[关键词1,关键词2,关键词3]
                    3. 如果是内容咨询问题，请先简要解答再推荐相关书籍
                    """
                }
            ],
            "temperature": 0.6
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        # 调用千帆API
        response = requests.post(
            QIANFAN_API_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=100
        )

        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")

        response_data = response.json()
        role = response_data['choices'][0]['message']['role']
        message = response_data['choices'][0]['message']['content']
        reply_content = message

        # 解析回复内容
        reply = reply_content.split('[')[0].strip()
        keywords = extract_keywords(reply_content)

        # 查询推荐图书
        recommended_books = search_books_by_keywords(keywords)
        print(keywords,'keywords')
        print(recommended_books,'recommended_books')
        print(reply,'reply')

        # 更新任务状态为完成
        cache.set(f'chat_task_{task_id}', {
            'status': 'completed',
            'result': {
                'reply': reply,
                'recommendations': recommended_books,
                'keywords': keywords
            },
            'completed_at': time.time()
        }, TASK_TIMEOUT)

    except requests.Timeout:
        cache.set(f'chat_task_{task_id}', {
            'status': 'failed',
            'error': '请求超时，请稍后再试'
        }, TASK_TIMEOUT)

    except Exception as e:
        cache.set(f'chat_task_{task_id}', {
            'status': 'failed',
            'error': f'智能服务暂时不可用: {str(e)}'
        }, TASK_TIMEOUT)


@csrf_exempt
def check_task(request):
    """检查任务状态的API"""
    if request.method == 'GET':
        task_id = request.GET.get('task_id')
        if not task_id:
            return JsonResponse({'status': 'error', 'message': '缺少task_id'})

        task_data = cache.get(f'chat_task_{task_id}')
        if not task_data:
            return JsonResponse({'status': 'error', 'message': '任务不存在或已过期'})

        response_data = {
            'status': 'success',
            'task_status': task_data.get('status')
        }

        if task_data['status'] == 'completed':
            response_data['result'] = task_data.get('result')
        elif task_data['status'] == 'failed':
            response_data['error'] = task_data.get('error')

        return JsonResponse(response_data)

    return JsonResponse({'status': 'error', 'message': '无效请求方法'}, status=400)


def extract_keywords(text):
    """从API回复中提取关键词"""
    # 尝试从格式化的回复中提取 [关键词1,关键词2,关键词3]
    keyword_match = re.search(r'\[([^\]]+)\]', text)
    if keyword_match:
        return [kw.strip() for kw in keyword_match.group(1).split(',')[:3]]

    # 降级方案：使用jieba分词提取
    text = re.sub(r'[^\w\s]', '', text)
    words = jieba.lcut_for_search(text)
    stopwords = ['的', '了', '和', '是', '我', '你', '他', '这', '那', '在']
    keywords = [word for word in words if word not in stopwords and len(word) > 1]
    return list(set(keywords))[:3]  # 去重后取前3


def search_books_by_keywords(keywords):
    """根据关键词搜索图书"""
    from django.db.models import Q

    if not keywords:
        return []

    # 构建查询条件
    query = Q()
    for kw in keywords:
        query |= Q(title__icontains=kw) | Q(authors__icontains=kw) | Q(subjects__icontains=kw)

    # 随机获取3本符合条件的图书
    books = Book.objects.filter(query).distinct().order_by('?')[:3]

    # 格式化结果
    return [{
        'id': book.id,
        'title': book.title,
        'authors': book.authors or "未知作者",
        'image': book.image.url if book.image else None,
        'description': getattr(book, 'description', '')[:100] + '...' if getattr(book, 'description', '') else ''
    } for book in books]


def forgot_password(request):
    """忘记密码 - 第一步：输入邮箱"""
    state = None
    error_message = None
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            state = 'empty_email'
        else:
            # 检查邮箱是否存在
            users_with_email = User.objects.filter(email=email)
            
            if not users_with_email.exists():
                state = 'email_not_found'
            elif users_with_email.count() > 1:
                # 同一邮箱有多个用户，提示用户通过其他方式重置密码
                state = 'multiple_accounts'
            else:
                # 只有一个用户，正常处理
                # 生成验证码
                verification_code = generate_verification_code()
                
                # 发送邮件
                success, message = send_reset_password_email(email, verification_code)
                
                if success:
                    # 存储验证码
                    store_verification_code(email, verification_code)
                    # 跳转到验证码输入页面
                    return HttpResponseRedirect(f'/reset-password/verify?email={email}')
                else:
                    state = 'send_failed'
                    error_message = message  # 保存详细错误信息
    
    context = {
        'state': state,
        'error_message': error_message,
    }
    return render(request, 'library/forgot_password.html', context)

def reset_password_verify(request):
    """忘记密码 - 第二步：验证验证码"""
    email = request.GET.get('email', '')
    from_settings = request.GET.get('from', '') == 'settings'  # 判断是否来自设置页面
    state = None
    
    if not email:
        redirect_url = '/set_password/' if from_settings else '/forgot-password'
        return HttpResponseRedirect(redirect_url)
    
    # 检查验证码是否还有效
    if not is_code_valid(email):
        state = 'code_expired'
    
    # 获取剩余时间
    remaining_time = get_code_remaining_time(email)
    
    if request.method == 'POST':
        verification_code = request.POST.get('verification_code', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not verification_code:
            state = 'empty_code'
        elif not new_password or not confirm_password:
            state = 'empty_password'
        elif new_password != confirm_password:
            state = 'password_mismatch'
        else:
            # 验证验证码
            if verify_code(email, verification_code):
                try:
                    # 处理同一邮箱多个用户的情况
                    users_with_email = User.objects.filter(email=email)
                    
                    if not users_with_email.exists():
                        state = 'user_not_found'
                    elif users_with_email.count() == 1:
                        # 只有一个用户，直接重置密码
                        user = users_with_email.first()
                        user.set_password(new_password)
                        user.save()
                        
                        # 如果是来自设置页面，保持登录状态
                        if from_settings and request.user.is_authenticated and request.user.email == email:
                            # 更新session以避免登录失效
                            from django.contrib.auth import update_session_auth_hash
                            update_session_auth_hash(request, user)
                        
                        state = 'success'
                    else:
                        # 多个用户使用同一邮箱，需要用户选择
                        if from_settings and request.user.is_authenticated:
                            # 如果是从设置页面来的，重置当前登录用户的密码
                            current_user = request.user
                            if current_user.email == email:
                                current_user.set_password(new_password)
                                current_user.save()
                                
                                # 更新session以避免登录失效
                                from django.contrib.auth import update_session_auth_hash
                                update_session_auth_hash(request, current_user)
                                
                                state = 'success'
                            else:
                                state = 'email_mismatch'
                        else:
                            # 从忘记密码页面来的，需要额外信息来确定用户
                            state = 'multiple_users_found'
                            
                except Exception as e:
                    state = 'reset_failed'
                    print(f"密码重置失败: {e}")
            else:
                state = 'invalid_code'
    
    context = {
        'state': state,
        'email': email,
        'remaining_time': remaining_time,
        'from_settings': from_settings,
    }
    return render(request, 'library/reset_password_verify.html', context)

@csrf_exempt
def get_remaining_time(request):
    """获取验证码剩余时间的AJAX接口"""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        if email:
            remaining_time = get_code_remaining_time(email)
            return JsonResponse({
                'success': True,
                'remaining_time': remaining_time,
                'is_valid': remaining_time > 0
            })
    
    return JsonResponse({
        'success': False,
        'remaining_time': 0,
        'is_valid': False
    })

def reader_borrowing_details(request, reader_id):
    """显示特定读者的借阅详情（仅当读者设置为公开时）"""
    try:
        reader = Reader.objects.get(id=reader_id)
        
        # 检查读者是否设置为公开借阅信息
        if not reader.borrowing_visible:
            return JsonResponse({
                'success': False, 
                'message': '该用户的借阅信息不公开'
            })
        
        # 获取该读者的所有借阅记录
        borrowings = Borrowing.objects.filter(reader=reader).order_by('-date_issued')
        
        borrowing_list = []
        for borrowing in borrowings:
            borrowing_list.append({
                'book_title': borrowing.ISBN.title,
                'book_id': borrowing.ISBN.id,
                'date_issued': borrowing.date_issued.strftime('%Y-%m-%d'),
                'date_due': borrowing.date_due_to_returned.strftime('%Y-%m-%d'),
                'date_returned': borrowing.date_returned.strftime('%Y-%m-%d') if borrowing.date_returned else None,
                'is_returned': borrowing.is_return,
                'renewal_count': borrowing.renewal_count
            })
        
        return JsonResponse({
            'success': True,
            'reader_name': reader.name,
            'borrowing_count': borrowings.count(),
            'borrowings': borrowing_list
        })
        
    except Reader.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': '用户不存在'
        })

# Admin管理系统视图
@login_required
def admin_dashboard(request):
    """Admin管理仪表板"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    # 获取统计数据
    total_books = Book.objects.count()
    total_readers = Reader.objects.count()
    total_borrowings = Borrowing.objects.filter(is_return=False).count()
    overdue_borrowings = Borrowing.objects.filter(
        is_return=False,
        date_due_to_returned__lt=datetime.date.today()
    ).count()
    
    # 获取最近的借阅记录
    recent_borrowings = Borrowing.objects.select_related('reader', 'ISBN').order_by('-date_issued')[:10]
    
    context = {
        'total_books': total_books,
        'total_readers': total_readers,
        'total_borrowings': total_borrowings,
        'overdue_borrowings': overdue_borrowings,
        'recent_borrowings': recent_borrowings,
        'today': datetime.date.today(),
    }
    return render(request, 'library/admin_dashboard.html', context)

@login_required
def admin_books(request):
    """图书管理"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    # 搜索功能
    search_query = request.GET.get('search', '')
    books = Book.objects.all()
    
    if search_query:
        books = books.filter(
            Q(title__icontains=search_query) |
            Q(authors__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    # 分页
    paginator = Paginator(books, 20)
    page = request.GET.get('page')
    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)
    
    context = {
        'books': books,
        'search_query': search_query,
    }
    return render(request, 'library/admin_books.html', context)

@login_required
def admin_book_add(request):
    """添加图书"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        authors = request.POST.get('authors', '').strip()
        isbn = request.POST.get('isbn', '').strip()
        publisher_info = request.POST.get('publisher_info', '').strip()
        total_copies = request.POST.get('total_copies', '1')
        available_copies = request.POST.get('available_copies', '1')
        location = request.POST.get('location', '').strip()
        notes = request.POST.get('notes', '').strip()
        
        try:
            total_copies = int(total_copies)
            available_copies = int(available_copies)
            
            book = Book.objects.create(
                title=title,
                authors=authors,
                isbn=isbn,
                publisher_info=publisher_info,
                total_copies=total_copies,
                available_copies=available_copies,
                location=location,
                notes=notes,
                is_active=True
            )
            
            # 处理图书封面
            if 'image' in request.FILES:
                book.image = request.FILES['image']
                book.save()
            
            return HttpResponseRedirect('/admin-books/?success=add')
        except ValueError:
            return render(request, 'library/admin_book_form.html', {
                'error': '请输入有效的数字',
                'form_data': request.POST
            })
    
    return render(request, 'library/admin_book_form.html', {'action': 'add'})

@login_required
def admin_book_edit(request, book_id):
    """编辑图书"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return HttpResponse('图书不存在')
    
    if request.method == 'POST':
        book.title = request.POST.get('title', '').strip()
        book.authors = request.POST.get('authors', '').strip()
        book.isbn = request.POST.get('isbn', '').strip()
        book.publisher_info = request.POST.get('publisher_info', '').strip()
        book.location = request.POST.get('location', '').strip()
        book.notes = request.POST.get('notes', '').strip()
        
        try:
            book.total_copies = int(request.POST.get('total_copies', '1'))
            book.available_copies = int(request.POST.get('available_copies', '1'))
            
            # 处理图书封面
            if 'image' in request.FILES:
                book.image = request.FILES['image']
            
            book.save()
            return HttpResponseRedirect('/admin-books/?success=edit')
        except ValueError:
            return render(request, 'library/admin_book_form.html', {
                'error': '请输入有效的数字',
                'book': book,
                'action': 'edit'
            })
    
    return render(request, 'library/admin_book_form.html', {
        'book': book,
        'action': 'edit'
    })

@login_required
def admin_book_delete(request, book_id):
    """删除图书"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    try:
        book = Book.objects.get(id=book_id)
        # 检查是否有借阅记录
        if Borrowing.objects.filter(ISBN=book, is_return=False).exists():
            return HttpResponseRedirect('/admin-books/?error=has_borrowings')
        
        book.delete()
        return HttpResponseRedirect('/admin-books/?success=delete')
    except Book.DoesNotExist:
        return HttpResponse('图书不存在')

@login_required
def admin_borrowings(request):
    """借阅管理"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    # 获取筛选参数
    status = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    borrowings = Borrowing.objects.select_related('reader', 'ISBN').all()
    
    # 状态筛选
    if status == 'active':
        borrowings = borrowings.filter(is_return=False)
    elif status == 'returned':
        borrowings = borrowings.filter(is_return=True)
    elif status == 'overdue':
        borrowings = borrowings.filter(
            is_return=False,
            date_due_to_returned__lt=datetime.date.today()
        )
    
    # 搜索功能
    if search_query:
        borrowings = borrowings.filter(
            Q(reader__name__icontains=search_query) |
            Q(ISBN__title__icontains=search_query) |
            Q(ISBN__authors__icontains=search_query)
        )
    
    # 排序
    borrowings = borrowings.order_by('-date_issued')
    
    # 分页
    paginator = Paginator(borrowings, 20)
    page = request.GET.get('page')
    try:
        borrowings = paginator.page(page)
    except PageNotAnInteger:
        borrowings = paginator.page(1)
    except EmptyPage:
        borrowings = paginator.page(paginator.num_pages)
    
    context = {
        'borrowings': borrowings,
        'status': status,
        'search_query': search_query,
        'today': datetime.date.today(),
    }
    return render(request, 'library/admin_borrowings.html', context)

@login_required  
def admin_readers(request):
    """读者管理"""
    if request.user.username != 'admin':
        return HttpResponseForbidden('只有管理员可以访问此页面')
    
    search_query = request.GET.get('search', '')
    readers = Reader.objects.select_related('user').all()
    
    if search_query:
        readers = readers.filter(
            Q(name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # 为每个读者添加借阅统计信息
    for reader in readers:
        reader.total_borrowings = reader.borrowing_set.count()
        reader.active_borrowings = reader.borrowing_set.filter(is_return=False).count()
    
    # 分页
    paginator = Paginator(readers, 20)
    page = request.GET.get('page')
    try:
        readers_page = paginator.page(page)
    except PageNotAnInteger:
        readers_page = paginator.page(1)
    except EmptyPage:
        readers_page = paginator.page(paginator.num_pages)
    
    # 为分页后的读者对象也添加统计信息
    for reader in readers_page:
        reader.total_borrowings = reader.borrowing_set.count()
        reader.active_borrowings = reader.borrowing_set.filter(is_return=False).count()
    
    context = {
        'readers': readers_page,
        'search_query': search_query,
    }
    return render(request, 'library/admin_readers.html', context)

@login_required
def get_reader_borrowings(request, reader_id):
    """获取指定读者的借阅记录（AJAX接口）"""
    if not request.user.username == 'admin':
        return JsonResponse({'error': '权限不足'}, status=403)
    
    try:
        reader = Reader.objects.get(id=reader_id)
        
        # 获取当前借阅（未归还）
        current_borrowings = Borrowing.objects.filter(
            reader=reader,
            is_return=False
        ).select_related('ISBN').order_by('-date_issued')
        
        # 获取历史借阅（已归还）
        history_borrowings = Borrowing.objects.filter(
            reader=reader,
            is_return=True
        ).select_related('ISBN').order_by('-date_returned')
        
        today = datetime.date.today()
        
        # 构建当前借阅数据
        current_data = []
        for borrowing in current_borrowings:
            status = "正常"
            if borrowing.date_due_to_returned < today:
                status = "逾期"
            
            current_data.append({
                'title': borrowing.ISBN.title,
                'authors': borrowing.ISBN.authors,
                'dateIssued': borrowing.date_issued.strftime('%Y-%m-%d'),
                'dateDue': borrowing.date_due_to_returned.strftime('%Y-%m-%d'),
                'renewalCount': borrowing.renewal_count,
                'isOverdueCharged': borrowing.is_overdue_charged,
                'overdueAmount': float(borrowing.overdue_amount) if borrowing.overdue_amount else 0,
                'status': status
            })
        
        # 构建历史借阅数据
        history_data = []
        for borrowing in history_borrowings:
            history_data.append({
                'title': borrowing.ISBN.title,
                'authors': borrowing.ISBN.authors,
                'dateIssued': borrowing.date_issued.strftime('%Y-%m-%d'),
                'dateReturned': borrowing.date_returned.strftime('%Y-%m-%d') if borrowing.date_returned else '',
                'renewalCount': borrowing.renewal_count,
                'wasOverdueCharged': borrowing.is_overdue_charged,
                'overdueAmount': float(borrowing.overdue_amount) if borrowing.overdue_amount else 0,
                'status': "已归还"
            })
        
        return JsonResponse({
            'success': True,
            'readerName': reader.name,
            'current': current_data,
            'history': history_data
        })
        
    except Reader.DoesNotExist:
        return JsonResponse({'error': '读者不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def search_reader(request):
    """搜索读者API"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            reader_name = data.get('reader_name', '').strip()
            
            if not reader_name:
                return JsonResponse({'success': False, 'message': '请输入读者姓名'})
            
            # 模糊搜索读者，只返回borrowing_visible=True的读者
            readers = Reader.objects.filter(
                name__icontains=reader_name,
                borrowing_visible=True
            ).prefetch_related('borrowing_set')
            
            # 构建返回数据
            results = []
            for reader in readers:
                # 计算借阅总数
                borrow_count = reader.borrowing_set.count()
                results.append({
                    'id': reader.id,
                    'name': reader.name,
                    'borrow_count': borrow_count
                })
            
            # 按借阅数量排序
            results.sort(key=lambda x: x['borrow_count'], reverse=True)
            
            return JsonResponse({
                'success': True,
                'readers': results[:10]  # 最多返回10个结果
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': '请求数据格式错误'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'搜索失败：{str(e)}'})
    
    return JsonResponse({'success': False, 'message': '仅支持POST请求'})