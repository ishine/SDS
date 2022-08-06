from typing import Dict

class Recipe:

    def __init__(self):
        pass

    def from_db(db_dict: Dict):
        m               = Recipe()
        m.name          = db_dict['name']
        m.ease          = db_dict['ease']
        m.cookbook      = db_dict['cookbook']
        m.ingredients   = db_dict['ingredients']
        m.last_made     = db_dict['last_made']
        m.make_it_next  = db_dict['last_made']
        m.type          = db_dict['type']
        m.prep_time     = db_dict['prep_time']
        m.page          = db_dict['page']

        return m
