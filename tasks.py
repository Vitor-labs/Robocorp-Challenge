from RPA.HTTP import HTTP
from RPA.Browser.Selenium import Selenium   
from robocorp.tasks import task
from RPA.Robocorp.Vault import Vault
from RPA.JSON import JSON

from pathlib import Path
import os

FILE_NAME = "challenge.xlsx"
OUTPUT_DIR = Path(str(os.environ.get('ROBOT_ARTIFACTS')))
INPUT_URL = "input/keywords.json"


class RobocorpChallenge:
    def __init__(self) -> None:
        """
        Since the flow is continuous, im using a common browser and http client
        to be more memort efficient.
        """
        self.http = HTTP()
        self.browser = Selenium()
        self.vault = Vault()
        
    def search_by_keyword(self) -> None:
        """
        search news by common keywords
        """
        try:
            self.browser.open_browser(url="https://news.yahoo.com/")
            json = JSON()
            rows = json.get_values_from_json(
                json.load_json_from_file(INPUT_URL), 
                "keywords",
            )
            for row in rows:
                self.browser.input_text_when_element_is_visible("css=input[id='ybar-search']", row)
                self.browser.wait_and_click_button("css=button[id='ybar-search']")
        
        except Exception as exc:
            print(exc)

        finally:
            print('Done')

@task
def main():
    challenge = RobocorpChallenge()
    challenge.search_by_keyword()