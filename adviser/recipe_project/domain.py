###############################################################################
#
# Copyright 2020, University of Stuttgart: Institute for Natural Language Processing (IMS)
#
# This file is part of Adviser.
# Adviser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3.
#
# Adviser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Adviser.  If not, see <https://www.gnu.org/licenses/>.
#
###############################################################################

from typing import List, Iterable
from utils.domain.jsonlookupdomain import JSONLookupDomain
from examples.webapi.mensa.parser import MensaParser, DishType

SLOT_VALUES = {
    'day': ['today', 'tomorrow', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
    'type': [DishType.Starter.value, DishType.Buffet.value, DishType.MainDish.value,
             DishType.SideDish.value, DishType.Dessert.value],
    'vegan': ['true', 'false'],
    'vegetarian': ['true', 'false'],
    'fish': ['true', 'false'],
    'pork': ['true', 'false'],
}

def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



class RecipeDomain(JSONLookupDomain):
    """Domain for the Mensa API

    Attributes:
        last_results (List[dict]): Current results which the user might request info about
    """

    def __init__(self):
        JSONLookupDomain.__init__(self, 'recipes', 'resources/ontologies/recipes.json', 'resources/databases/recipes.db', 'Recipes')
        self.last_results = []


    def find_info_about_entity(self, entity_id: str, requested_slots: Iterable):
        """ Returns the values (stored in the data backend) of the specified slots for the
            specified entity.

        Args:
            entity_id (str): primary key value of the entity
            requested_slots (dict): slot-value mapping of constraints
        """
        result = {slot: self.last_results[int(entity_id)-1][slot] for slot in requested_slots}
        result['artificial_id'] = entity_id
        return [result]

    def find_recipes_by_ingredients(self, ingredients: List[str]):

        iq      = " OR lower(ingredients) LIKE ".join([f"'%{i.lower()}%'" for i in ingredients])
        query   = f"SELECT * FROM data WHERE ingredients LIKE {iq}"

        return self.query_db(query)


    def get_requestable_slots(self) -> List[str]:
        """ Returns a list of all slots requestable by the user. """
        return self.ontology_json['requestable']

    def get_system_requestable_slots(self) -> List[str]:
        """ Returns a list of all slots requestable by the system. """
        return self.ontology_json['system_requestable']

    def get_informable_slots(self) -> List[str]:
        """ Returns a list of all informable slots. """
        return self.ontology_json['informable'].keys()

    def get_possible_values(self, slot: str) -> List[str]:
        """ Returns all possible values for an informable slot

        Args:
            slot (str): name of the slot

        Returns:
            a list of strings, each string representing one possible value for
            the specified slot.
         """
        return self.ontology_json['informable'][slot]

    def get_primary_key(self):
        """ Returns the name of a column in the associated database which can be used to uniquely
            distinguish between database entities.
            Could be e.g. the name of a restaurant, an ID, ... """
        return self.ontology_json['key']

    def get_pronouns(self, slot):
        if slot in self.ontology_json['pronoun_map']:
            return self.ontology_json['pronoun_map'][slot]
        else:
            return []

    def get_keyword(self):
        return 'recipes'