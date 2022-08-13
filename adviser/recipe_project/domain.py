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

from typing import List, Iterable, Set
from utils.domain.jsonlookupdomain import JSONLookupDomain
from .models.recipe_req import RecipeReq
from .models.recipe import Recipe


class RecipeDomain(JSONLookupDomain):
    """Domain for the Recipe Database

    Attributes:
        last_results (List[dict]): Current results which the user might request info about
    """

    def __init__(self):
        JSONLookupDomain.__init__(self, 'recipes', 'resources/ontologies/recipes.json', 'resources/databases/recipes.db', 'Recipes')
        self.last_results = []
    
    # we override find_entities to be able to better match ingredients
    def find_entities(self, constraints: dict, requested_slots: Iterable = iter(())):
        """ Returns all entities from the data backend that meet the constraints, with values for
            the primary key and the system requestable slots (and optional slots, specifyable
            via requested_slots).

        Args:
            constraints (dict): Slot-value mapping of constraints.
                                If empty, all entities in the database will be returned.
            requested_slots (Iterable): list of slots that should be returned in addition to the
                                        system requestable slots and the primary key

        """
        # values for name and all system requestable slots
        select_clause = ", ".join(set([self.get_primary_key()]) |
                                  set(self.get_system_requestable_slots()) |
                                  set(requested_slots))
        query = "SELECT {} FROM {}".format(select_clause, self.get_domain_name())
        constraints = {slot: value.replace("'", "''") for slot, value in constraints.items()
                       if value is not None and str(value).lower() != 'dontcare'}
        if constraints:
            query += ' WHERE ' + ' AND '.join("{}='{}' COLLATE NOCASE".format(key, str(val)) if key != 'ingredients' else "lower({}) LIKE '%{}%'".format(key, str(val).lower())
                                              for key, val in constraints.items())
        return self.query_db(query)

    def find_recipes(self, request: RecipeReq, partial: bool = False) -> List[Recipe]:

        if request.is_empty():
            return []
        q = ""
        op = "OR" if partial else "AND"
        if len(request.ingredients) > 0:
            q += "".join(f" {op} LOWER(ingredients) LIKE '%{i.lower()}%' " for i in request.ingredients)
        if request.ease is not None:
            q += f" {op} lower(ease) in {self._expand_ease(request.ease)} "
        if request.cookbook is not None:
            q += f" {op} lower(cookbook) = '{request.cookbook.lower()}' "
        if request.name is not None:
            q += f" {op} lower(name) = '{request.name.lower()}' "
        if request.rating is not None:
            q += f" {op} rating = '{request.rating}' "
        if request.prep_time is not None:
            q += f" {op} CAST(prep_time as INTEGER) <= {request.prep_time} "

        if len(q) > 0:
            q = q[4:]
            q = "SELECT * FROM {} where {}".format(self.get_domain_name(), q)
        else:
            q = "SELECT * FROM {}".format(self.get_domain_name())
        return [Recipe.from_db(r) for r in self.query_db(q)]
        

    def get_random(self) -> Recipe:

        q = "SELECT * FROM {} ORDER BY RANDOM() LIMIT 1".format(self.get_domain_name())
        r = self.query_db(q)

        return Recipe.from_db(r[0])

    def get_users_favs(self) -> List[Recipe]:
        q = "SELECT * FROM {} WHERE favorite = true".format(self.get_domain_name())
        r = self.query_db(q)
        return [Recipe.from_db(r) for r in self.query_db(q)]

    def set_favorite(self, name: str):
        q = "UPDATE {} SET favorite = true WHERE name = '{}'".format(self.get_domain_name(), name)
        self.query_db(q)

    def unset_favorite(self, name: str):
        q = "UPDATE {} SET favorite = false WHERE name = '{}'".format(self.get_domain_name(), name)
        self.query_db(q)



    def _expand_ease(self, ease: str):

        if ease.casefold() in ["easy", "simple"]:
            return "('super simple', 'fairly easy')"
        if ease.casefold() in ["not too hard", "not too difficult"]:
            return "('super simple', 'fairly easy', 'average')"
        return f"('{ease}')"

     
    def get_all_ingredients(self) -> Set[str]:
        """ Returns a list of all ingredients in the database """

        q           = "SELECT DISTINCT ingredients from {}".format(self.get_domain_name())
        ingredients = self.query_db(q)
        res_set     = set()
        for i in ingredients:
            for t in i["ingredients"].split(","):
                t = t.strip()
                if not t in res_set:
                    res_set.add(t)

        return res_set

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