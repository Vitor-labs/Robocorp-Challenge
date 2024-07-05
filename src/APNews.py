import inspect
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
from robocorp import workitems
from RPA.Browser.Selenium import Selenium
from RPA.Excel.Files import Files
from RPA.JSON import JSON
from RPA.Robocorp.Vault import Vault
from RPA.Tables import Tables
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from src.contracts import ExtractContract
from src.errors import ExtractError

OUTPUT_DIR = Path(str(os.environ.get("ROBOT_ARTIFACTS")))
INPUT_URL = "input/keywords.json"


class APNewsScrapper:
    def __init__(self, n_newest: int = 50) -> None:
        """
        Since the flow is continuous, im using a common browser and http client
        to be more memort efficient.

        Args:
            n_newest (int, optional): Number of news to collect. Defaults to 50.
        """
        self.n_newest = n_newest
        self.json = JSON()
        self.vault = Vault()
        self.browser = Selenium()
        self.tables = Tables()
        # self.browser.set_screenshot_directory(str('.'/OUTPUT_DIR/'screenshots'))

    def search_by_keyword(self, keywrds: List[str] = []) -> None:
        """
        search news by common keywords

        Args:
            keywrds (List[str], optional): list of keywords to search. Defaults to [].
        """
        opts = FirefoxOptions()
        opts.add_argument("--headless")
        self.browser.open_browser(
            url="https://apnews.com/",
            options=opts,
        )
        keywords = (
            keywrds
            if len(keywrds) > 0
            else self.json.load_json_from_file(INPUT_URL)["keywords"]
        )
        try:
            for word in keywords:
                self.__search_by_keyword(word)

        except Exception as exc:
            print(exc)
            self.browser.screenshot(
                filename=f"output/screenshots/error_{inspect.stack()[0][3]}.png"
            )
        finally:
            self.browser.close_all_browsers()
            print("Done")

    def __search_by_keyword(self, word: str) -> None:
        """
        search news by common keyword. Follows the steps:
        1. clicks on search icon
        2. expands search box and puts the keyword
        3. submits the search and redirects to the search result page
        4. get all the news and store in an excel file

        Args:
            word (str): keyword to search

        Notes:
        * if keyword is not found, then no results are found
        * generates a pandas Dataframe with columsn: title, link, description,
        * date, picture_src, contains_money, words_in_title, words_in_dscr
        """
        try:
            self.browser.get_webelement(
                '//*[@class="SearchOverlay-search-button"]'
            ).click()
            self.browser.get_webelement(
                '//*[@class="SearchOverlay-search-input"]'
            ).send_keys(word)
            self.browser.get_webelement(
                '//*[@class="SearchOverlay-search-submit"]'
            ).click()
            self.browser.wait_for_condition("return document.readyState === 'complete'")

            result = self.__handle_search_page(word)
            if result:
                df = pd.DataFrame(
                    result.content,
                    columns=[
                        "title",
                        "link",
                        "description",
                        "date",
                        "picture_src",
                        "contains_money",
                        "words_in_title",
                        "words_in_description",
                    ],
                )
                path = f"output/challenge_{word}.xlsx"
                lib = Files()
                lib.create_workbook(sheet_name=f"challenge_{word}.xlsx")
                lib.append_rows_to_worksheet(df.to_dict(orient="records"))
                lib.save_workbook(path=path)
                print(f"Saved {df.shape[0]} records")

        except Exception as exc:
            raise ExtractError(str(exc)) from exc

    def __handle_search_page(self, search: str) -> ExtractContract | None:
        """
        handle the search result page. Follows the steps:
        1. filter for the latest news
        2. get all items on the page
        3. goes to next page
        4. repeat 2 and 3 until there are no more pages

        TODO: add stop condition to avoid gathering all data

        Args:
            search (str): word to search

        Returns:
            List[List[str | int]] | None: List with data or None if there are no results
        """
        if not self.__check_if_results_found():
            print("No Result Found for", search)
            return
        # get total number of results
        total = self.browser.get_webelement(
            '//*[@class="SearchResultsModule-count-desktop"]'
        ).text
        print("Total", total)
        try:
            # select latest news
            self.browser.click_element('//*[@class="Select-input"]')
            self.browser.click_element('//*[@value="3"]')
            items = []
            pages = self.browser.get_webelement(
                '//*[@class="Pagination-pageCounts"]'
            ).text
            for _ in range(int(pages.split(" of ")[1])):
                time.sleep(
                    1
                )  # Since the images are lazy loaded, we need to wait for them to load.
                # find next page button
                next_page = self.browser.get_webelement(
                    '//*[@class="Pagination-nextPage"]'
                )
                text = self.browser.get_webelement(
                    '//*[@class="Pagination-pageCounts"]'
                ).text
                print("Page", text)
                # get all items related on this page before proceeding to next page, this fixes stale elements.
                elements = self.browser.get_webelements('//*[@class="PagePromo"]')
                items.extend(self.__collect_data_by_element(elements, search))
                # go to next page and refresh the element
                break
                next_page.click()
                self.browser.wait_for_condition(
                    "return document.readyState === 'complete'"
                )
                next_page = self.browser.get_webelement(
                    '//*[@class="Pagination-nextPage"]'
                )

            assert len(items) > 0, "Something got wrong, no items found"
            print("Done, Collecting data from items")
            return ExtractContract(content=items, id=search)

        except Exception as exc:
            raise exc

    def __collect_data_by_element(
        self, elements: List[WebElement], word: str
    ) -> List[str | int]:
        """
        collect data (title, link, descrition, date, picture, count of word in
        the title, count of word in the description, title or description
        contains money or not) from an elements

        TODO: download picture to output/pictures
        Args:
            elements (List[WebElement]): list of elements to collect data
            word (str): word to search in title and description

        Returns:
            List[str | int]: list of data gathered

        Notes:
        * find_element not working at all, trying with just selenium.
        * SeleniumLibrary WebElement works diferently from pure Selenium WebElement
        """
        results = []
        money_pattern = re.compile(
            r"""
                \$\d{1,3}(,\d{3})*(\.\d{2})? | # Matches $ followed by digits, commas, and optional cents
                \d+(\.\d{2})?\s*dollars |      # Matches number followed by 'dollars'
                \d+(\.\d{2})?\s*USD            # Matches number followed by 'USD'
            """,
            re.VERBOSE,
        )

        def contains_money_format(text):
            return bool(money_pattern.search(text))

        for element in elements:
            try:
                title = element.find_element(
                    By.CLASS_NAME, "PagePromoContentIcons-text"
                ).text
                link = element.find_element(By.TAG_NAME, "a").get_attribute("href")
                dscr = element.find_element(By.CLASS_NAME, "PagePromo-description").text
                date = self.__try_to_find_date(element)

                contains_money = contains_money_format(title) or contains_money_format(
                    dscr
                )
                picture_src = self.__check_if_news_has_img(element, title, date)
                words_in_title = title.count(word)
                words_in_dscr = dscr.count(word)

                results.append(
                    [
                        title,
                        link,
                        dscr,
                        date,
                        picture_src,
                        contains_money,
                        words_in_title,
                        words_in_dscr,
                    ]
                )
            except Exception as exc:
                path = f"output/screenshots/error{inspect.stack()[0][3]}.png"
                item = workitems.outputs.create(save=False)
                self.browser.screenshot(element, path)
                item.add_file(path)
                item.save()
                print(exc)
                continue

        return results

    def __try_to_find_date(self, element: WebElement) -> str:
        try:
            date = element.find_element(By.CLASS_NAME, "PagePromo-date").text
            if not date:
                date = element.find_element(
                    By.CLASS_NAME, "TodayInHistoryPromo-date"
                ).text
            return datetime.strptime(date, "%B %d").strftime(
                "%m-%d"
            )  # TODO: get the year
        except Exception:
            return "No date found"

    def __check_if_news_has_img(
        self, element: WebElement, title: str, date: str
    ) -> str:
        """
        Takes in a WebElement, a title string, and a date string and attempts
        to take a screenshot of the element's 'Image' element. If successful,
        returns a path for the screenshot. Else returns 'no image found'.

        Args:
            element (WebElement): The WebElement to take a screenshot of.
            title (str): The title of the news article.
            date (str): The date of the news article.

        Returns:
            str: The file path of the screenshot, or 'no image found'.
        """
        try:
            path = f'output/pictures/{title.lower().replace(" ", "_")}_{date}.png'
            item = workitems.outputs.create(save=False)
            self.browser.screenshot(element.find_element(By.CLASS_NAME, "Image"), path)
            item.add_file(path)
            item.save()
            return path

        except Exception:
            return "no image found"

    def __check_if_results_found(self) -> bool:
        """
        Check if there are any results found by searching hte element present when
        no result is found, if element is present, then there are no results

        Returns:
            bool: value indicating if there are any results
        """
        try:
            result = self.browser.get_webelement(
                '//*[@class="SearchResultsModule-noResults"]'
            )
            return False if result else True
        except Exception:
            return True
