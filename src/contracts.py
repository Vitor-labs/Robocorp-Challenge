from typing import List, NamedTuple

"""
A named tuple representing the contract for extracting data.
Args:
    raw_info: The raw information to be extracted.
    extract_date: The date of extraction.
"""
ExtractContract=NamedTuple('ExtractContract', content=List[List[str | int]], id=str)

