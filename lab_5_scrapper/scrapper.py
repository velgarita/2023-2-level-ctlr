"""
Crawler implementation.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable
import datetime
import json
import pathlib
import re
import shutil
from random import randrange
from time import sleep
from typing import Pattern, Union

import requests
from bs4 import BeautifulSoup

from core_utils import constants
from core_utils.article.article import Article
from core_utils.article.io import to_meta, to_raw
from core_utils.config_dto import ConfigDTO


class IncorrectSeedURLError(Exception):
    """
    Seed URL does not match standard pattern
    """


class NumberOfArticlesOutOfRangeError(Exception):
    """
    Total number of articles is out of range
    """


class IncorrectNumberOfArticlesError(Exception):
    """
    Total number of articles to parse is not integer
    """


class IncorrectHeadersError(Exception):
    """
    Headers are not in a form of dictionary
    """


class IncorrectEncodingError(Exception):
    """
    Encoding must be specified as a string
    """


class IncorrectTimeoutError(Exception):
    """
    Timeout value must be a positive integer less than 60
    """


class IncorrectVerifyError(Exception):
    """
    Verify certificate and Headless mode values must boolean
    """


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        self._validate_config_content()

        self.config = self._extract_config_content()

        self._seed_urls = self.config.seed_urls
        self._num_articles = self.config.total_articles
        self._headers = self.config.headers
        self._encoding = self.config.encoding
        self._timeout = self.config.timeout
        self._should_verify_certificate = self.config.should_verify_certificate
        self._headless_mode = self.config.headless_mode


    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, 'r', encoding='utf-8') as file:
            config_content = json.load(file)
        return ConfigDTO(
            seed_urls=config_content['seed_urls'],
            total_articles_to_find_and_parse=config_content['total_articles_to_find_and_parse'],
            headers=config_content['headers'],
            encoding=config_content['encoding'],
            timeout=config_content['timeout'],
            should_verify_certificate=config_content['should_verify_certificate'],
            headless_mode=config_content['headless_mode']
        )



    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        config = self._extract_config_content()

        if not(
                isinstance(config.seed_urls, list)
                and all(re.match('https?://(www.)?', url) for url in config.seed_urls)
        ):
            raise IncorrectSeedURLError

        if not (
            isinstance(config.total_articles, int)
            and config.total_articles > 0
        ) or isinstance(config.total_articles, bool):
            raise IncorrectNumberOfArticlesError

        if not (
                1 < config.total_articles < 150
        ):
            raise NumberOfArticlesOutOfRangeError

        if not (
                isinstance(config.headers, dict)
                and all(isinstance(key, str) and isinstance(value, str) for key, value in config.headers.items())
            ):
            raise IncorrectHeadersError

        if not isinstance(config.encoding, str):
            raise IncorrectEncodingError

        if not(
            isinstance(config.timeout, int)
            and 0 <= config.timeout <= 60
        ):
            raise IncorrectTimeoutError

        if not (
            isinstance(config.should_verify_certificate, bool)
            and isinstance(config.headless_mode, bool)
        ):
            raise IncorrectVerifyError


    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self._headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    sleep(randrange(3))

    headers = config.get_headers()
    timeout = config.get_timeout()

    response = requests.get(url=url, headers=headers, timeout=timeout)

    return response


class Crawler:
    """
    Crawler implementation.
    """

    url_pattern: Union[Pattern, str]

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """

        self.config = config
        self.urls = []
        self.url_pattern = 'https://baikal24.ru'

    def _extract_url(self, article_bs: BeautifulSoup) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.BeautifulSoup): BeautifulSoup instance

        Returns:
            str: Url from HTML
        """
        links = article_bs.find_all(class_='news-teaser__link')
        url = ''
        for link in links:
            url = self.url_pattern + link['href']
            if url and url not in self.urls:
                break

        return url


    def find_articles(self) -> None:
        """
        Find articles.
        """
        seed_urls = self.get_search_urls()

        while len(self.urls) < self.config.get_num_articles():

            for seed_url in seed_urls:
                response = make_request(seed_url, self.config)
                if not response.ok:
                    continue

                article_soap = BeautifulSoup(response.text, features='html.parser')
                new_url = self._extract_url(article_soap)

                while new_url:
                    self.urls.append(new_url)
                    new_url = self._extract_url(article_soap)


    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """

        return self.config.get_seed_urls()


# 10
# 4, 6, 8, 10


class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.full_url = full_url
        self.article_id = article_id
        self.config = config
        self.article = Article(full_url, article_id)

    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        main_div = article_soup.find('div', class_='article__content clearfix')
        texts = []
        if main_div:
            all_ps = main_div.find_all('p', class_='article__text')
            for p in all_ps:
                texts.append(p.text)

        self.article.text = ''.join(texts)

    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """
        title = article_soup.find(class_='article__title')
        if title:
            self.article.title = title.text

        author = article_soup.find(class_='article__author')
        if not author:
            self.article.author.append('NOT FOUND')
        else:
            self.article.author.append(author.text)

        date_str = article_soup.find(class_='article__date')
        if date_str:
            self.article.date = self.unify_date_format(date_str.text)

        tags = article_soup.find_all(class_='article__tag')
        for tag in tags:
            self.article.topics.append(tag.text)

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """
        dt_object = datetime.datetime.strptime(date_str, '%d.%m.%Y %H:%M')

        return dt_object


    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """

        response = make_request(self.full_url, self.config)
        if response.ok:
            article_bs = BeautifulSoup(response.text, features='html.parser')
            self._fill_article_with_text(article_bs)
            self._fill_article_with_meta_information(article_bs)

        return self.article


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """

    if not base_path.is_dir():
        base_path.mkdir(parents=True, exist_ok=True)

    if any(base_path.iterdir()):
        shutil.rmtree(base_path)
        base_path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """
    Entrypoint for scrapper module.
    """

    configuration = Config(constants.CRAWLER_CONFIG_PATH)
    crawler = Crawler(configuration)
    base_path = constants.ASSETS_PATH

    prepare_environment(base_path)

    crawler.find_articles()

    all_urls = crawler.get_search_urls()

    for index, url in enumerate(all_urls):
        article_id = index + 1
        html_parser = HTMLParser(full_url=url, article_id=article_id, config=configuration)
        article = html_parser.parse()
        if not (
                article.title and article.date and article.text
        ):
            continue

        if isinstance(article, Article):
            to_raw(article)
            to_meta(article)

    print('Ready!')
    print(len(crawler.urls))


if __name__ == "__main__":
    main()