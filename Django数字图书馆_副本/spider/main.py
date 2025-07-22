import string
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
import os
import django
from django.conf import settings

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_management.settings')
django.setup()
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from library.models import Book  # 导入 Book 模型

# 下载image
def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    cleaned_filename = ''.join(c for c in filename if c in valid_chars)
    return cleaned_filename.strip()



def download_and_save_image(image_url,title):
    """
    下载图片并保存到media目录，使用原始URL中的文件名
    返回保存的相对路径
    """
    if not image_url:
        return None

    try:
        # 从URL提取文件名
        filename = f'{title}.png'
        if not filename:
            return None


        # 存储在media/book_covers/目录下
        relative_path = f"book_covers/{filename}"
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        # 确保目录存在
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        headers = {
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Referer': 'https://findecnu.libsp.cn/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Not;A=Brand";v="24", "Chromium";v="128"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
        }
        # 下载图片
        response = requests.get(image_url, stream=True, timeout=10,headers=headers)
        response.raise_for_status()

        # 检查是否为有效图片
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            print(f"URL返回的不是图片: {content_type}")
            return None

        # 保存图片
        with open(full_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        return relative_path  # 返回相对media的路径

    except requests.exceptions.RequestException as e:
        print(f"下载图片失败: {e}")
    except Exception as e:
        print(f"保存图片失败: {e}")
    return None


def get_image(title, isbn, recordId):
    """获取图书封面图片"""
    params = {
        'isbn': isbn,
        'title': title,
        'recordId': recordId,
    }

    try:
        response = requests.get(
            'https://findecnu.libsp.cn/find/book/getDuxiuImageUrl',
            params=params,
            cookies=cookies,
            headers=headers
        )
        if response.status_code == 200:
            image_url = response.json().get('data', {})
            if image_url:
                return download_and_save_image(image_url,title)
    except Exception as e:
        print(f"获取图片URL失败: {e}")
    return None

def get_detail(recordId):
    params = {
        'recordId': str(recordId),
    }

    response = requests.get(
        'https://findecnu.libsp.cn/find/searchResultDetail/getDetail',
        params=params,
        cookies=cookies,
        headers=headers,
    )
    data = response.json()['data']
    baseMarcInfoDto = data['baseMarcInfoDto']
    cleanAuthor = baseMarcInfoDto['cleanAuthor']
    isbn = baseMarcInfoDto['isbn']
    publisher = baseMarcInfoDto['publisher']
    publishYear = baseMarcInfoDto['publishYear']
    title = baseMarcInfoDto['titles']
    bean2List = data['bean2List']
    book_data = {}
    for bena2 in bean2List:
        soup = BeautifulSoup(bena2['fieldVal'], 'html.parser')
        fieldVal = soup.get_text()  # 提取<a>标签内的文本
        book_data[bena2['description']] =fieldVal
    # 获取图书封面
    image_file = get_image(title, isbn, recordId)
    # 保存到 Django 数据库
    print(book_data)
    print(image_file)
    # 创建图书对象
    book = Book(
        title=book_data.get('题名/责任者', title),
        publisher_info=book_data.get('出版发行项', f"{publisher}, {publishYear}"),
        isbn=book_data.get('ISBN及定价', isbn),
        physical_description=book_data.get('载体形态项', ''),
        other_titles=book_data.get('其它题名', ''),
        series=book_data.get('丛编项', ''),
        authors=book_data.get('个人责任者', cleanAuthor),
        subjects=book_data.get('学科主题', ''),
        classification=book_data.get('中图法分类号', ''),
        notes=book_data.get('内容附注',book_data.get('一般附注')),
        location="图书馆一楼",  # 设置默认馆藏位置
        total_copies=100,  # 设置默认总数
        available_copies=100,  # 设置默认可借数
    )
    # 如果有封面图片，则保存
    if image_file:
        book.image.name = image_file

    book.save()


cookies = {
    'SameSite': 'None',
    'route': '44d2b14d8097040453ed523687aa3ccc',
}

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json;charset=UTF-8',
    # 'Cookie': 'SameSite=None; route=44d2b14d8097040453ed523687aa3ccc',
    'Origin': 'https://findecnu.libsp.cn',
    'Pragma': 'no-cache',
    'Referer': 'https://findecnu.libsp.cn/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'content-language': 'zh_CN',
    'groupCode': '200300',
    'mappingPath': '',
    'sec-ch-ua': '"Not;A=Brand";v="24", "Chromium";v="128"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'x-lang': 'CHI',
}



json_data = {
    'libCode': '',
    'disCode': '',
    'statRange': 7,
    'page': 1,
    'rows': 10,
    'sortType': 1,
    'classNo': '',
}

response = requests.post('https://findecnu.libsp.cn/find/index/getHotLoan', cookies=cookies, headers=headers, json=json_data)
# print(response.json())
datas = response.json()['data']['result']
for data in datas:
    recordId = data['recordId']
    get_detail(recordId)

