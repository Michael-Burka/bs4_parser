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
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session: CachedSession) -> List[Tuple[str, str, str]]:
    """
    Fetch a list of Python's new features from the official website.

    Args:
        session (CachedSession): Session object with caching for HTTP requests.

    Returns:
        List of tuples with new feature information
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
        List of tuples with the latest version information
        (documentation link, version, status), or None if unable to fetch.
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
    Downloads the latest Python documentation in PDF (A4 format).

    This function retrieves the PDF archive of Python's documentation using a
    session with caching enabled. It saves the archive within the 'downloads'
    directory of BASE_DIR. If this directory does not exist, it will be
    automatically created. Logs the success of the download operation.

    Args:
        session (CachedSession): A session object for making HTTP requests
        with caching.

    Returns:
        None. The function writes the PDF archive to the filesystem and logs
        the path where the archive is saved but does not return any value.
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


def pep(session: CachedSession) -> Optional[List[Tuple[str, int]]]:
    """
    Pars the PEP index for status counts and logs mismatches.

    Iterates over PEPs, extracts and compares statuses from the index and
    PEP pages. Tallies status occurrences and logs discrepancies. Returns
    status counts and total processed PEPs or None if unreachable.

    Args:
        session (CachedSession): Session for cached HTTP requests.

    Returns:
        List of tuples with status counts and total PEPs or None.
    """
    response = get_response(session, PEP_DOC_URL)
    if response is None:
        return

    soup = BeautifulSoup(response.text, 'lxml')
    index_section = find_tag(soup, 'section', attrs={'id': 'numerical-index'})
    peps_table_body = find_tag(index_section, 'tbody')
    pep_rows = peps_table_body.find_all('tr')

    results = [('Status', 'Count')]
    status_counter = defaultdict(int)
    mismatch_log = []

    for pep_row in tqdm(pep_rows, desc="Processing PEPs"):
        status_abbr = find_tag(pep_row, 'abbr')
        listed_status = status_abbr.text[1:]
        pep_link_tag = find_tag(pep_row, 'a')
        pep_url = urljoin(PEP_DOC_URL, pep_link_tag['href'])

        pep_response = get_response(session, pep_url)
        if pep_response is None:
            continue

        pep_page_soup = BeautifulSoup(pep_response.text, 'lxml')
        status_section = find_tag(
            pep_page_soup, 'dl', attrs={'class': 'rfc2822 field-list simple'}
        )
        actual_status = (
            status_section.find(string='Status').find_next('dd').text
        )

        if actual_status not in EXPECTED_STATUS.get(listed_status, []):
            error_message = (
                f"Mismatched statuses: {pep_url}"
                f"Status on page: {actual_status}"
                f"Expected statuses: {EXPECTED_STATUS.get(listed_status)}"
            )
            mismatch_log.append(error_message)

        status_counter[actual_status] += 1

    if mismatch_log:
        logging.info('\n'.join(mismatch_log))

    count_peps = sum(status_counter.values())
    results.extend(status_counter.items())
    results.append(('Total', count_peps))

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
