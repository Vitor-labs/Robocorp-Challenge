import os
import inspect
from typing import List
from pathlib import Path

from RPA.Browser.Selenium import Selenium
from RPA.Robocorp.Vault import Vault
from robocorp.tasks import task
from RPA.JSON import JSON
import pandas as pd

OUTPUT_DIR = Path(str(os.environ.get('ROBOT_ARTIFACTS')))
INPUT_URL = "input/keywords.json"


class APNewsScrapper:
    def __init__(self) -> None:
        """
        Since the flow is continuous, im using a common browser and http client
        to be more memort efficient.

        #FIXME: screenshot directory not working
        """
        self.json = JSON()
        self.vault = Vault()
        self.browser = Selenium()
        # self.browser.set_screenshot_directory(str('.'/OUTPUT_DIR/'screenshots'))
        
    def search_by_keyword(self) -> None:
        """
        search news by common keywords
        """
        try:
            keywords = self.json.load_json_from_file(INPUT_URL)['keywords'] # type: ignore
            for word in keywords: # type: ignore
                self.browser.open_browser(url="https://apnews.com/")
                self.__search_by_keyword(word)

        except Exception as exc:
            self.browser.screenshot(filename=f'error_{inspect.stack()[0][3]}.png')
            print(exc)

        finally:
            self.browser.close_all_browsers()
            print('Done')

    def __search_by_keyword(self, word:str) -> None:
        """
        search news by common keyword. Follows the steps:
        1. clicks on search icon
        2. expands search box and puts the keyword
        3. submits the search and redirects to the search result page
        """
        try:
            self.browser.get_webelement('//*[@class="SearchOverlay-search-button"]').click()  # type: ignore
            self.browser.get_webelement('//*[@class="SearchOverlay-search-input"]').send_keys(word)  # type: ignore
            self.browser.get_webelement('//*[@class="SearchOverlay-search-submit"]').click()  # type: ignore
            self.browser.wait_for_condition("return document.readyState === 'complete'")

            result = self.__handle_search_page(word)

            if result:
                df = pd.DataFrame(result, columns=["title", "link", "description", "date", "picture_url", "words_in_title", "words_in_description"])
                df.to_excel(OUTPUT_DIR / f'challenge_{word}.xlsx', index=False)

        except Exception as exc:
            print(exc)

    def __handle_search_page(self, search:str) -> List[List[str | int]] | None:
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
        total = self.browser.get_webelement('//*[@class="SearchResultsModule-count-desktop"]').text # type: ignore
        print("Total", total)
        try:
            # select latest news
            self.browser.click_element('//*[@class="Select-input"]') # type: ignore
            self.browser.click_element('//*[@value="3"]') # type: ignore
            items = []
            pages = self.browser.get_webelement('//*[@class="Pagination-pageCounts"]').text # type: ignore
            for _ in range(int(pages.split(" of ")[1])):
                # find next page button
                next_page = self.browser.get_webelement('//*[@class="Pagination-nextPage"]')        
                # log actual page
                text = self.browser.get_webelement('//*[@class="Pagination-pageCounts"]').text # type: ignore
                print('Page', text) # type: ignore
                # get all items related on this page before proceeding to next page, this fixes stale elements.
                elements = self.browser.get_webelements('//*[@class="PagePromo"]') # type: ignore
                items.extend(self.__collect_data_by_element(elements, search))
                break
                # go to next page
                next_page.click() # type: ignore
                self.browser.wait_for_condition("return document.readyState === 'complete'")
                next_page = self.browser.get_webelement('//*[@class="Pagination-nextPage"]')

            assert len(items) > 0, "Something got wrong, no items found"
            print("Done, Collecting data from items")
            return [ self.__collect_data_by_element(item, search) for item in items ]

        except Exception as exc:
            raise exc

    def __collect_data_by_element(self, elements:List, word:str) -> List[str | int]:
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

        * find_element not working at all 
        """
        try:
            results = []
            for element in elements:
                title = ''
                link = ''
                description = ''
                date = ''
                picture_url = ''
                
                words_in_title = title.count(word)
                words_in_description = description.count(word)

                results.append([title, link, description, date, picture_url, words_in_title, words_in_description])
            return results
        
        except Exception as exc:
            self.browser.screenshot(element, f'output/screenshots/error{inspect.stack()[0][3]}.png')
            self.browser.close_browser()
            raise exc

    def __check_if_results_found(self) -> bool:
        """
        Check if there are any results found by searching hte element present when
        no result is found, if element is present, then there are no results

        Returns:
            bool: value indicating if there are any results
        """
        try:
            result = self.browser.get_webelement('//*[@class="SearchResultsModule-noResults"]')
            return False if result else True
        except Exception:
            return True

@task
def search_by_word():
    challenge = APNewsScrapper()
    challenge.search_by_keyword()
