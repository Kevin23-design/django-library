from django.urls import path, re_path
from django.contrib.staticfiles import views as static_views
from django.conf.urls.static import static
from django.conf import settings

import library.views as views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('register/', views.user_register, name='user_register'),
    path('register/verify/', views.register_verify, name='register_verify'),
    path('set_password/', views.set_password, name='set_password'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),  # 新增
    path('reset-password/verify/', views.reset_password_verify, name='reset_password_verify'),  # 新增
    path('api/get-remaining-time/', views.get_remaining_time, name='get_remaining_time'),  # 获取剩余时间接口
    re_path(r'^static/(?P<path>.*)$', static_views.serve, name='static'),  # 需要正则表达式，所以用 re_path
    path('book/detail/', views.book_detail, name='book_detail'),
    path('book/action/', views.reader_operation, name='reader_operation'),
    path('search/', views.book_search, name='book_search'),
    path('profile/', views.profile, name='profile'),
    path('statistics/', views.statistics, name='statistics'),
    path('api/reader-borrowing/<int:reader_id>/', views.reader_borrowing_details, name='reader_borrowing_details'),  # 新增
    path('search_reader/', views.search_reader, name='search_reader'),  # 新增读者搜索API
    path('about/', views.about, name='about'),
    path('api/chat/', views.chat_api, name='chat_api'),
    
    # Admin管理路由
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-books/', views.admin_books, name='admin_books'),
    path('admin-books/add/', views.admin_book_add, name='admin_book_add'),
    path('admin-books/edit/<int:book_id>/', views.admin_book_edit, name='admin_book_edit'),
    path('admin-books/delete/<int:book_id>/', views.admin_book_delete, name='admin_book_delete'),
    path('admin-borrowings/', views.admin_borrowings, name='admin_borrowings'),
    path('admin-readers/', views.admin_readers, name='admin_readers'),
    path('api/reader-borrowings/<int:reader_id>/', views.get_reader_borrowings, name='get_reader_borrowings'),

    path('api/check_task/', views.check_task, name='check_task'),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, view=static_views.serve)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)