import logging
from typing import Optional, Any, Dict

from requests import RequestException, Session, Response
from bs4 import BeautifulSoup

from exceptions import ParserFindTagException


def get_response(session: Session, url: str) -> Optional[Response]:
    """
    Send a GET request to URL using the given session.

    Args:
        session (Session): The session object for the request.
        url (str): The target URL for the GET request.

    Returns:
        Optional[Response]: Response object or None if an exception occurs.
    """
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}',
            stack_info=True
        )
        return None


def find_tag(
        soup: BeautifulSoup, tag: str, attrs: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Search for the first tag with specified name and attributes.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object to search within.
        tag (str): The tag name to search for.
        attrs (Optional[Dict[str, Any]]): Attributes to match in the search.

    Returns:
        Any: The first matching tag found.

    Raises:
        ParserFindTagException: If no matching tag is found.
    """
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag
