from RPA.Browser.Selenium import Selenium   
from robocorp.tasks import task
from RPA.Robocorp.Vault import Vault
from RPA.JSON import JSON

from pathlib import Path
import inspect
import os

FILE_NAME = "challenge.xlsx"
OUTPUT_DIR = Path(str(os.environ.get('ROBOT_ARTIFACTS')))
INPUT_URL = "input/keywords.json"


class APNewsScrapper:
    def __init__(self) -> None:
        """
        Since the flow is continuous, im using a common browser and http client
        to be more memort efficient.
        """
        self.vault = Vault()
        self.browser = Selenium()
        self.browser.set_screenshot_directory(str(OUTPUT_DIR / 'screenshots'))
        
    def search_by_keyword(self) -> None:
        """
        search news by common keywords
        """
        try:
            json = JSON()
            keywords = json.load_json_from_file(INPUT_URL)['keywords'] # type: ignore
            for word in keywords: # type: ignore
                self.browser.open_browser(url="https://apnews.com/")
                self.__search_by_keyword(word)

        except Exception as exc:
            self.browser.screenshot(f'error_{inspect.stack()[0][3]}.png')
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

            self.__handle_search_page(word)

        except Exception as exc:
            print(exc)

    def __handle_search_page(self, search:str) -> None:
        """
        handle the search result page. Follows the steps:
        1. filter for the latest news
        2. get all items on the page
        """
        if not self.__check_if_results_found():
            print("No Result Found for", search)
            return
        # get total number of results
        total = self.browser.get_webelement('//*[@class="SearchResultsModule-count-desktop"]').text # type: ignore
        print("Total", total, "results found for", search)
        # select latest news
        self.browser.click_element('//*[@class="Select-input"]') # type: ignore
        self.browser.click_element('//*[@value="3"]') # type: ignore
        
        import time
        time.sleep(2)

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