from robocorp.tasks import task
from robocorp import workitems

from src.APNews import APNewsScrapper


@task
def search_by_word():
    challenge = APNewsScrapper()
    item = workitems.inputs.current
    if item:
        challenge.search_by_keyword(item.payload['keywords'])
