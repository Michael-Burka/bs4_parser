import logging
import re
from collections import defaultdict
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from requests_cache import CachedSession
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import BASE_DIR, EXPECTED_STATUS, MAIN_DOC_URL, PEP_DOC_URL
from exceptions import NoResponse
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session: CachedSession) -> List[Tuple[str, str, str]]:
    """
    Fetch a list of Python's new features from the official website.

    Args:
        session (CachedSession): Session object with caching for HTTP requests.

    Returns:
        List[Tuple[str, str, str]]: List of tuples with new feature information
        (article link, title, editor and author info).
    """
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')

    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]

    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
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
    Extract the latest Python versions from the official website.

    Args:
        session (CachedSession): Session object with caching for HTTP requests.

    Returns:
        Optional[List[Tuple[str, str, str]]]: List of tuples with the latest
        version information (documentation link, version, status), or None
        if unable to fetch.
    """
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')

    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
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
    Download the latest Python documentation archive in PDF (A4 format).

    Utilizes a session with caching to retrieve the documentation archive,
    saving it within the 'downloads' directory of BASE_DIR. If this directory
    does not exist, it will be created.

    Args:
        session (CachedSession): Session with caching for HTTP requests.
    """
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')

    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]

    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    response = session.get(archive_url)
    if response is None:
        return

    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def parse_pep_page(session: CachedSession, pep_url: str) -> Optional[str]:
    """
    Extract the status of a specific PEP from its page.

    Makes an HTTP request to a given PEP's URL and parses the page to find
    the PEP's status. Useful for verifying the status of PEPs listed in the
    index against their detailed page.

    Args:
        session (CachedSession): Session for HTTP requests with caching.
        pep_url (str): URL of the PEP page to parse.

    Returns:
        Optional[str]: The status of the PEP if found, None otherwise.
    """
    try:
        response = get_response(session, pep_url)
        if response is None:
            return
        soup = BeautifulSoup(response.text, features='lxml')
        status_tag = find_tag(
            soup, 'abbr', attrs={'title': re.compile(r'\w+')}
        )
        return status_tag.text if status_tag else None
    except NoResponse:
        return None


def pep(session: CachedSession) -> Optional[List[Tuple[str, int]]]:
    """
    Parse PEP (Python Enhancement Proposals) page for status counts.

    Navigates through the PEP index, collecting individual PEP page links,
    extracting the status, and tallying the status occurrences across all PEPs.

    Args:
        session (CachedSession): Session for HTTP requests with caching.

    Returns:
        Optional[List[Tuple[str, int]]]:
            List of status labels with their counts,
            or None if unable to fetch data.
    """
    response = get_response(session, PEP_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    section = find_tag(soup, 'section', attrs={'id': 'index-by-category'})
    tbody = section.find_all('tbody')

    results = [('Status', 'Count')]
    status_counter = defaultdict(int)

    for table_body in tqdm(tbody):
        abbr_tags = table_body.find_all('abbr')
        link_tags = [
            link for link in table_body.find_all(
                'a', attrs={'class': 'pep reference internal'}
            )
            if link.text.isdigit()
        ]

        mismatched_status_logs = []

        for abbr_tag, link_tag in zip(abbr_tags, link_tags):
            table_status = abbr_tag.text[1:]
            pep_url = urljoin(PEP_DOC_URL, link_tag['href'])

            page_status = parse_pep_page(session, pep_url)
            if page_status and page_status not in (
                    EXPECTED_STATUS.get(table_status, [])
            ):
                mismatched_status_logs.append(
                    f"Mismatched statuses: {pep_url} "
                    f"Status in page: {page_status} "
                    f"Expected statuses: {EXPECTED_STATUS.get(table_status)}"
                )
            if page_status:
                status_counter[page_status] += 1

        if mismatched_status_logs:
            logging.info('\n'.join(mismatched_status_logs))

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
    """Run the parser script based on command line arguments."""
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
