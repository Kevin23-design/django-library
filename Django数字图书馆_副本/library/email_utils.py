#!/usr/bin/env python
# -*- coding: utf-8 -*-

import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from django.core.cache import cache

# 邮箱配置
SMTP_SERVER = 'smtp.qq.com'
SMTP_PORT = 587
EMAIL_HOST_USER = '3534704571@qq.com'
EMAIL_HOST_PASSWORD = 'ztznnfmcetnocjgg'  # QQ邮箱授权码

def generate_verification_code():
    """生成4位随机验证码"""
    return ''.join(random.choices(string.digits, k=4))

def send_registration_email(email, verification_code):
    """发送注册验证码邮件"""
    try:
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = email
        msg['Subject'] = Header('古韵书斋 - 注册验证码', 'utf-8').encode()
        
        # HTML邮件内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Microsoft YaHei', Arial, sans-serif;
                    background: linear-gradient(135deg, #fdfcf8 0%, #f9f6f0 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border: 3px solid #d4af37;
                    border-radius: 20px;
                    padding: 30px;
                    box-shadow: 0 10px 30px rgba(212, 175, 55, 0.3);
                }}
                .header {{
                    text-align: center;
                    color: #8b4513;
                    font-size: 24px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                .code-box {{
                    background: linear-gradient(135deg, #d4af37 0%, #b8860b 100%);
                    color: #654321;
                    padding: 20px;
                    border-radius: 15px;
                    text-align: center;
                    margin: 20px 0;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    border: 2px solid #8b4513;
                }}
                .content {{
                    color: #654321;
                    line-height: 1.6;
                    font-size: 16px;
                }}
                .warning {{
                    background: rgba(255, 193, 7, 0.1);
                    border: 1px solid #d4af37;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #8b4513;
                }}
                .footer {{
                    text-align: center;
                    color: #999;
                    font-size: 12px;
                    margin-top: 30px;
                    border-top: 1px solid #d4af37;
                    padding-top: 15px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    ◆ 古韵书斋 - 注册验证 ◆
                </div>
                
                <div class="content">
                    <p>尊敬的读者：</p>
                    <p>欢迎注册古韵书斋！请使用以下验证码完成邮箱验证：</p>
                </div>
                
                <div class="code-box">
                    {verification_code}
                </div>
                
                <div class="warning">
                    <strong>📋 重要提醒：</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>验证码有效期为3分钟，请及时使用</li>
                        <li>请勿将验证码告知他人，保护账户安全</li>
                        <li>如非本人操作，请忽略此邮件</li>
                    </ul>
                </div>
                
                <div class="content">
                    <p>完成验证后，您就可以开始您的古韵书斋之旅了！</p>
                    <p>祝您学习愉快！</p>
                    <p style="text-align: right; margin-top: 20px;">
                        <strong>古韵书斋管理团队</strong><br>
                        <small>{EMAIL_HOST_USER}</small>
                    </p>
                </div>
                
                <div class="footer">
                    此邮件由系统自动发送，请勿直接回复<br>
                    © 2025 古韵书斋 - 承千年文韵，启智慧之门
                </div>
            </div>
        </body>
        </html>
        """
        
        # 纯文本内容（备用）
        text_content = f"""
        古韵书斋 - 注册验证码
        
        尊敬的读者：
        
        欢迎注册古韵书斋！您的验证码为：{verification_code}
        
        验证码有效期为3分钟，请及时使用。
        如非本人操作，请忽略此邮件。
        
        古韵书斋管理团队
        """
        
        # 添加HTML和文本内容
        html_part = MIMEText(html_content, 'html', 'utf-8')
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # 启用TLS加密
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(EMAIL_HOST_USER, [email], text)
        server.quit()
        
        return True, "邮件发送成功"
        
    except smtplib.SMTPAuthenticationError as e:
        return False, f"SMTP认证失败: {str(e)}"
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"收件人被拒绝: {str(e)}"
    except smtplib.SMTPSenderRefused as e:
        return False, f"发件人被拒绝: {str(e)}"
    except smtplib.SMTPDataError as e:
        return False, f"SMTP数据错误: {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"SMTP连接错误: {str(e)}"
    except smtplib.SMTPServerDisconnected as e:
        return False, f"SMTP服务器断开连接: {str(e)}"
    except Exception as e:
        return False, f"邮件发送失败: {str(e)}"

def send_reset_password_email(email, verification_code):
    """发送密码重置验证码邮件"""
    try:
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_HOST_USER
        msg['To'] = email
        msg['Subject'] = Header('古韵书斋 - 密码重置验证码', 'utf-8').encode()
        
        # HTML邮件内容
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Microsoft YaHei', Arial, sans-serif;
                    background: linear-gradient(135deg, #fdfcf8 0%, #f9f6f0 100%);
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border: 3px solid #d4af37;
                    border-radius: 20px;
                    padding: 30px;
                    box-shadow: 0 10px 30px rgba(212, 175, 55, 0.3);
                }}
                .header {{
                    text-align: center;
                    color: #8b4513;
                    font-size: 24px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                .code-box {{
                    background: linear-gradient(135deg, #d4af37 0%, #b8860b 100%);
                    color: #654321;
                    padding: 20px;
                    border-radius: 15px;
                    text-align: center;
                    margin: 20px 0;
                    font-size: 32px;
                    font-weight: bold;
                    letter-spacing: 8px;
                    border: 2px solid #8b4513;
                }}
                .content {{
                    color: #654321;
                    line-height: 1.6;
                    font-size: 16px;
                }}
                .warning {{
                    background: rgba(255, 193, 7, 0.1);
                    border: 1px solid #d4af37;
                    border-radius: 8px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #8b4513;
                }}
                .footer {{
                    text-align: center;
                    color: #999;
                    font-size: 12px;
                    margin-top: 30px;
                    border-top: 1px solid #d4af37;
                    padding-top: 15px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    ◆ 古韵书斋 - 密码重置 ◆
                </div>
                
                <div class="content">
                    <p>尊敬的读者：</p>
                    <p>您正在申请重置古韵书斋的登录密码，请使用以下验证码完成密码重置：</p>
                </div>
                
                <div class="code-box">
                    {verification_code}
                </div>
                
                <div class="warning">
                    <strong>📋 重要提醒：</strong>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>验证码有效期为3分钟，请及时使用</li>
                        <li>请勿将验证码告知他人，保护账户安全</li>
                        <li>如非本人操作，请忽略此邮件</li>
                    </ul>
                </div>
                
                <div class="content">
                    <p>如有疑问，请联系书斋管理员。</p>
                    <p>祝您学习愉快！</p>
                    <p style="text-align: right; margin-top: 20px;">
                        <strong>古韵书斋管理团队</strong><br>
                        <small>{EMAIL_HOST_USER}</small>
                    </p>
                </div>
                
                <div class="footer">
                    此邮件由系统自动发送，请勿直接回复<br>
                    © 2025 古韵书斋 - 承千年文韵，启智慧之门
                </div>
            </div>
        </body>
        </html>
        """
        
        # 纯文本内容（备用）
        text_content = f"""
        古韵书斋 - 密码重置验证码
        
        尊敬的读者：
        
        您正在申请重置古韵书斋的登录密码，验证码为：{verification_code}
        
        验证码有效期为3分钟，请及时使用。
        如非本人操作，请忽略此邮件。
        
        古韵书斋管理团队
        """
        
        # 添加HTML和文本内容
        html_part = MIMEText(html_content, 'html', 'utf-8')
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # 启用TLS加密
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(EMAIL_HOST_USER, [email], text)
        server.quit()
        
        return True, "邮件发送成功"
        
    except smtplib.SMTPAuthenticationError as e:
        return False, f"SMTP认证失败: {str(e)}"
    except smtplib.SMTPRecipientsRefused as e:
        return False, f"收件人被拒绝: {str(e)}"
    except smtplib.SMTPSenderRefused as e:
        return False, f"发件人被拒绝: {str(e)}"
    except smtplib.SMTPDataError as e:
        return False, f"SMTP数据错误: {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"SMTP连接错误: {str(e)}"
    except smtplib.SMTPServerDisconnected as e:
        return False, f"SMTP服务器断开连接: {str(e)}"
    except Exception as e:
        return False, f"邮件发送失败: {str(e)}"

def store_registration_verification_code(email, code):
    """将注册验证码存储到缓存中，有效期3分钟"""
    import time
    cache_key = f'registration_code_{email}'
    time_key = f'registration_time_{email}'
    
    current_time = time.time()
    cache.set(cache_key, code, 180)  # 180秒 = 3分钟
    cache.set(time_key, current_time, 180)  # 同时存储创建时间

def verify_registration_code(email, code):
    """验证注册验证码是否正确"""
    cache_key = f'registration_code_{email}'
    time_key = f'registration_time_{email}'
    stored_code = cache.get(cache_key)
    
    if stored_code and stored_code == code:
        # 验证成功后删除验证码和时间记录
        cache.delete(cache_key)
        cache.delete(time_key)
        return True
    return False

def is_registration_code_valid(email):
    """检查注册验证码是否仍然有效"""
    cache_key = f'registration_code_{email}'
    return cache.get(cache_key) is not None

def get_registration_code_remaining_time(email):
    """获取注册验证码剩余有效时间（秒）"""
    cache_key = f'registration_code_{email}'
    time_key = f'registration_time_{email}'
    
    import time
    current_time = time.time()
    create_time = cache.get(time_key)
    
    if create_time is None:
        return 0
    
    elapsed_time = current_time - create_time
    remaining_time = 180 - elapsed_time  # 3分钟 = 180秒
    
    return max(0, int(remaining_time))

def store_verification_code(email, code):
    """将验证码存储到缓存中，有效期3分钟"""
    import time
    cache_key = f'reset_password_code_{email}'
    time_key = f'reset_password_time_{email}'
    
    current_time = time.time()
    cache.set(cache_key, code, 180)  # 180秒 = 3分钟
    cache.set(time_key, current_time, 180)  # 同时存储创建时间
    
    # 存储创建时间
    time_key = f'reset_password_time_{email}'
    import time
    current_time = time.time()
    cache.set(time_key, current_time, 180)

def verify_code(email, code):
    """验证验证码是否正确"""
    cache_key = f'reset_password_code_{email}'
    time_key = f'reset_password_time_{email}'
    stored_code = cache.get(cache_key)
    
    if stored_code and stored_code == code:
        # 验证成功后删除验证码和时间记录
        cache.delete(cache_key)
        cache.delete(time_key)
        return True
    return False

def is_code_valid(email):
    """检查验证码是否仍然有效"""
    cache_key = f'reset_password_code_{email}'
    return cache.get(cache_key) is not None

def get_code_remaining_time(email):
    """获取验证码剩余有效时间（秒）"""
    cache_key = f'reset_password_code_{email}'
    # Django cache没有直接获取TTL的方法，我们需要用一个辅助key来记录创建时间
    time_key = f'reset_password_time_{email}'
    
    import time
    current_time = time.time()
    create_time = cache.get(time_key)
    
    if create_time is None:
        return 0
    
    elapsed_time = current_time - create_time
    remaining_time = 180 - elapsed_time  # 3分钟 = 180秒
    
    return max(0, int(remaining_time))
