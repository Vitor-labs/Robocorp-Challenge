from robocorp.tasks import task
from robocorp import workitems

from APNews import APNewsScrapper


@task
def search_by_word():
    challenge = APNewsScrapper()
    
    item = workitems.inputs.current
    if item:
        print("Received payload:", item.payload)
    challenge.search_by_keyword(item.payload['keywords']) # type: ignore
