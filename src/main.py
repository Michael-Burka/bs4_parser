import re
import logging
from requests_cache import CachedSession
from typing import List, Tuple, Optional
from collections import defaultdict
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BASE_DIR, MAIN_DOC_URL, PEP_DOC_URL, EXPECTED_STATUS
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import get_response, find_tag
from exceptions import NoResponse


def whats_new(session: CachedSession) -> List[Tuple[str, str, str]]:
    """
    Получает список нововведений Python с официального сайта.

    Args:
        session (CachedSession):
            Сессия с кешированием для выполнения HTTP-запросов.

    Returns:
        List[Tuple[str, str, str]]:
            Список кортежей с информацией о нововведениях
            (ссылка, заголовок, информация о редакторе и авторе).
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    soup = BeautifulSoup(response.text, features='lxml')

    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]

    for section in tqdm(sections_by_python):
        version_a_tag = section.find('a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )

    return results


def latest_versions(
        session: CachedSession
) -> Optional[List[Tuple[str, str, str]]]:
    """
    Извлекает последние версии Python с официального сайта.

    Args:
        session (CachedSession):
            Сессия с кешированием для выполнения HTTP-запросов.

    Returns:
        List[Tuple[str, str, str]]:
            Список кортежей с информацией о нововведениях
            (ссылка, заголовок, информация о редакторе и авторе).
    """
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')

    sidebar = soup.find('div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')

    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )

    return results


def download(session: CachedSession) -> None:
    """
    Загружает последний доступный архив документации Python.

    Args:
        session (CachedSession):
            Сессия с кешированием для выполнения HTTP-запросов.
    """
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    soup = BeautifulSoup(response.text, features='lxml')

    main_tag = soup.find('div', {'role': 'main'})
    table_tag = main_tag.find('table', {'class': 'docutils'})
    pdf_a4_tag = table_tag.find('a', {'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]

    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def parse_pep_page(session, pep_url):
    """
    Анализирует статусы PEP с официального сайта Python.

    Args:
        session (CachedSession):
            Сессия с кешированием для выполнения HTTP-запросов.

    Returns:
        List[Tuple[str, int]]:
            Список кортежей со статусами PEP и их количеством.
    """
    try:
        response = get_response(session, pep_url)
        soup = BeautifulSoup(response.text, features='lxml')
        status_tag = find_tag(soup, 'abbr', attrs={'title': re.compile(r'\w+')})
        return status_tag.text if status_tag else None
    except NoResponse:
        return None


def pep(session):
    """
    Парсит страницу PEP и возвращает статус PEP.

    Args:
        session (CachedSession):
            Сессия для выполнения HTTP-запросов.
        pep_url (str):
            URL страницы PEP для парсинга.

    Returns:
        Optional[str]:
            Статус PEP или None, если статус не найден или произошла ошибка.
    """
    response = get_response(session, PEP_DOC_URL)
    soup = BeautifulSoup(response.text, features='lxml')
    section = find_tag(soup, 'section', attrs={'id': 'index-by-category'})
    tbody = section.find_all('tbody')

    results = [('Status', 'Count')]
    status_counter = defaultdict(int)

    for t in tqdm(tbody):
        abbr_tags = t.find_all('abbr')
        a_tags = [
            a for a in t.find_all('a', attrs={'class': 'pep reference internal'})
            if a.text.isdigit()
        ]
        for abbr_tag, a_tag in zip(abbr_tags, a_tags):
            table_status = abbr_tag.text[1:]
            pep_url = urljoin(PEP_DOC_URL, a_tag['href'])

            page_status = parse_pep_page(session, pep_url)

            if page_status and page_status not in EXPECTED_STATUS.get(
                    table_status, []
            ):
                logging.info(
                    f"Несовпадающие статусы: {pep_url} "
                    f"Статус в карточке: {page_status} "
                    f"Ожидаемые статусы: "
                    f"{EXPECTED_STATUS.get(table_status)}"
                )
            if page_status:
                status_counter[page_status] += 1

    count_pep = sum(status_counter.values())
    results.extend(status_counter.items())
    results.append(('Total', count_pep))

    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен')

    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)

    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу')


if __name__ == '__main__':
    main()
