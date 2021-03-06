import requests
import openpyxl
import codecs
import os
import shutil
import jaconv
import re
import time

from io import BytesIO
from bs4 import BeautifulSoup
from json import dumps
from datetime import datetime, timezone, timedelta
from pdfminer.high_level import extract_text

from typing import Union, Dict, List


base_url = "https://web.pref.hyogo.lg.jp"
jst = timezone(timedelta(hours=9), 'JST')

SUMMARY_INIT = {
    'attr': '検査実施人数',
    'value': 0,
    'children': [
        {
            'attr': '陽性患者数',
            'value': 0,
            'children': [
                {
                    'attr': '入院中',
                    'value': 0,
                    'children': [
                        {
                            'attr': '軽症・中等症',
                            'value': 0,
                        },
                        {
                            'attr': '重症',
                            'value': 0,
                        }
                    ]
                },
                {
                    'attr': '死亡',
                    'value': 0,
                },
                {
                    'attr': '退院',
                    'value': 0,
                }
            ]
        }
    ],
    'last_update': ''
}


def print_log(type: str, message: str) -> None:
    print(f"[{datetime.now().astimezone(jst).strftime('%Y-%m-%d %H:%M:%S+09:00')}][covid19-scraping:{type}]: {message}")


def get_file(url: str, file_type: str, save_file: bool = False) \
        -> Union[openpyxl.workbook.workbook.Workbook, List[str]]:
    print_log("file", "get html file...")
    html_doc = ""
    failed_count = 0
    while not html_doc:
        try:
            html_doc = requests.get(base_url + url).text
        except Exception:
            if failed_count >= 5:
                raise Exception(f"Failed get html file from \"{base_url + url}\"!")
            print_log("file", f"Failed get html file from \"{base_url + url}\". retrying...")
            failed_count += 1
            time.sleep(5)
    soup = BeautifulSoup(html_doc, 'html.parser')

    real_page_tags = soup.find_all("a")

    file_url = ""
    for tag in real_page_tags:
        if tag.get("href")[-len(file_type):] == file_type:
            file_url = base_url + tag.get("href")
            break

    assert file_url, f"Can't get {file_type} file!"

    failed_count = 0
    if save_file or file_type == "pdf":
        status_code = 404
        while not status_code == 200:
            try:
                res = requests.get(file_url, stream=True)
                status_code = res.status_code
            except Exception:
                if failed_count >= 5:
                    raise Exception(f"Failed get {file_type} file from \"{file_url}\"!")
                print_log("file", f"Failed get {file_type} file from \"{file_url}\". retrying...")
                failed_count += 1
                time.sleep(5)
        filename = './data/' + os.path.basename(file_url)
        with open(filename, 'wb') as f:
            res.raw.decode_content = True
            shutil.copyfileobj(res.raw, f)
        if file_type == "pdf":
            return extract_text(filename).split('\n')
        elif file_type == "xlsx":
            return openpyxl.load_workbook(filename)
        else:
            raise Exception(f"Not support file type: {file_type}")
    else:
        file_bin = b""
        while failed_count < 5 and not file_bin:
            try:
                file_bin = requests.get(file_url).content
            except Exception:
                if failed_count >= 5:
                    raise Exception(f"Failed get {file_type} file from \"{file_url}\"!")
                print_log("file", f"Failed get {file_type} file from \"{file_url}\". retrying...")
                failed_count += 1
                time.sleep(5)
        if file_type == "xlsx":
            return openpyxl.load_workbook(BytesIO(file_bin))
        else:
            raise Exception(f"Not support file type: {file_type}")


def excel_date(num) -> datetime:
    return datetime(1899, 12, 30, tzinfo=jst) + timedelta(days=num)


def dumps_json(file_name: str, json_data: Dict) -> None:
    with codecs.open("./data/" + file_name, "w", "utf-8") as f:
        f.write(dumps(json_data, ensure_ascii=False, indent=4, separators=(',', ': ')))


def get_weekday(day: int) -> str:
    weekday_list = ["月", "火", "水", "木", "金", "土", "日"]
    return weekday_list[day]


def get_numbers_in_text(text: str) -> List[int]:
    return list(map(int, re.findall('[0-9]+', jaconv.z2h(text, digit=True))))
