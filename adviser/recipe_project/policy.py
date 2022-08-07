###############################################################################
#
# Copyright 2019, University of Stuttgart: Institute for Natural Language Processing (IMS)
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

from typing import List, Dict

from .domain import RecipeDomain
from .models.recipe_req import RecipeReq
from .models.recipe import Recipe
from services.service import PublishSubscribe, Service
from utils import SysAct, SysActionType
from utils.logger import DiasysLogger
from utils.useract import UserAct, UserActionType
from utils.beliefstate import BeliefState
from collections import defaultdict

import random


class RecipePolicy(Service):
    """Policy module for recipe lookup dialogues.  """

    def __init__(self, domain: RecipeDomain, logger: DiasysLogger = DiasysLogger()):
        # only call super class' constructor
        Service.__init__(self, domain=domain, debug_logger=logger)

        self.sys_state = { 
            'waiting_for_filter': [],
            'last_user_act': None,
            'current_suggested_recipe': None
        }

    @PublishSubscribe(sub_topics=["beliefstate"], pub_topics=["sys_act", "sys_state"])
    def generate_sys_acts(self, beliefstate: BeliefState) -> dict(sys_acts=List[SysAct]):
        """Generates system acts by looking up answers to the given user question.
        Returns:
            dict with 'sys_acts' as key and list of system acts as value
        """

        bs              = beliefstate
        # new informs
        informs         = bs['informs']
        # new requests
        requests        = bs['requests']
        # how many matching recipes found atm in db
        num_matches     = bs['num_matches']

        self.debug_logger.error(f"num_matches={num_matches}, informs.ingredients={len(informs.get('ingredients', []))}")
        # current user act types
        user_acts       = bs['user_acts']

        if user_acts is None or len(user_acts) == 0:
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state}

        ua              = list(user_acts)[0]
        self.debug_logger.error(f"UAs={user_acts}")

        if ua == UserActionType.Hello:
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state }

        if ua == UserActionType.Thanks:
            return { 'sys_act': SysAct(SysActionType.RequestMore), 'sys_state': self.sys_state }

        if ua == UserActionType.Bye:
            return { 'sys_act': SysAct(SysActionType.Bye), 'sys_state': self.sys_state }

        if ua == UserActionType.Bad:
            return { 'sys_act': SysAct(SysActionType.Bad), 'sys_state': self.sys_state }

        # user was presented some selection (2-4) and now picks one
        if ua == UserActionType.PickFirst and num_matches > 0 and num_matches < 5:
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.PickSecond and num_matches > 0 and num_matches < 5:
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.PickLast and num_matches > 0 and num_matches < 5:
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.Pick and self._has_chosen(bs):
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        
        if ua == UserActionType.Request:

            if not self._has_chosen(bs):
                return { 'sys_act': SysAct(SysActionType.NotYetChosen), 'sys_state': self.sys_state }

            chosen = bs['chosen']
            slot = list(bs['requests'].keys())[0]
            m = "Sorry, I did not understand that request."
            if slot == 'ease':
                m = random.choice([
                    "It is {} to make.",
                    "It is {}"
                ]).format(chosen.ease)
            elif slot == 'name':
                m = random.choice([
                    "It is named {}.",
                    "The name is {}.",
                    "It's {}."
                ]).format(chosen.name)
            return { 'sys_act': SysAct(SysActionType.Inform, slot_values={message: m}), 'sys_state': self.sys_state }

            return { 'sys_act': SysAct(SysActionType.Bad), 'sys_state': self.sys_state }


        if informs and len(informs) > 0:

            req     = RecipeReq.from_informs(informs)
            found   = self.domain.find_recipes(req)
            cnt     = len(found)

            if cnt == 0:
                return self._not_found()
            if cnt == 1:
                return self._found_one(found[0])
            if cnt < 5:
                return self._found_some(found)

            return self._found_too_many()
        

        return { 'sys_act': SysAct(SysActionType.Bad), 'sys_state': self.sys_state }


    def _has_chosen(self, bs: BeliefState) -> bool:
        return 'chosen' in bs and bs['chosen'] is not None


    def _not_found(self) -> dict:
        return { 'sys_act': SysAct(SysActionType.NotFound), 'sys_state': self.sys_state }

    def _found_some(self, recipes: List[Recipe]) -> dict:
        
        if len(recipes) == 2:
            return { 'sys_act': SysAct(SysActionType.FoundSome, slot_values={'names': "{recipes[0].name} or {recipes[1].name}"}), 'sys_state': self.sys_state }
        return { 'sys_act': SysAct(SysActionType.FoundSome, slot_values={'names': ", ".join([r.name for r in recipes])}), 'sys_state': self.sys_state }

    def _found_one(self, recipe: Recipe) -> dict:

        return { 'sys_act': SysAct(SysActionType.FoundOne, slot_values={'name': recipe.name}), 'sys_state': self.sys_state }

    def _found_too_many(self) -> dict:

        return { 'sys_act': SysAct(SysActionType.FoundTooMany), 'sys_state': self.sys_state }

    def _fetch_by_name(self, value: str) -> dict:

        found   = self.domain.find_recipes_by_name(value)
        flen    = len(found)

        if flen > 1:
            self.sys_state['waiting_for_filter'] = found[0]   
            self.sys_state['current_suggested_recipe'] = None
            return ({ 'name': ',\n'.join(r['name'] for r in found)}, flen)

        elif flen == 1:
            self.sys_state['waiting_for_filter'] = None
            self.sys_state['current_suggested_recipe'] = found[0]
            return ({ 'name':  found[0]['name']}, flen)
        
        return (None, 0)

    def _fetch_by_ease(self, value: str) -> dict:

        found   = self.domain.find_recipes_by_ease(value)
        flen    = len(found)

        if flen > 1:
            self.sys_state['waiting_for_filter'] = found
            self.sys_state['current_suggested_recipe'] = None
            return ({ 'name': ',\n'.join(r['name'] for r in found)}, flen)

        elif flen == 1:
            self.sys_state['waiting_for_filter'] = None
            self.sys_state['current_suggested_recipe'] = found[0]
            return ({ 'name':  found[0]['name']}, flen)
        
        return (None, 0)

    def _inform_ingredients(self, value: str) -> dict:

        if not isinstance(value, str):
            raise Exception(f"value should be a str, but is {str(type(value))}: {str(value)}")

        found = self.domain.find_recipes_by_ingredients([value])

        if len(found) > 1:
            self.sys_state['waiting_for_filter'] = found
            self.sys_state['current_suggested_recipe'] = None
            return ({ 'names': ',\n'.join(r['name'] for r in found)}, len(found))

        elif len(found) == 1:
            self.sys_state['waiting_for_filter'] = None
            self.sys_state['current_suggested_recipe'] = found[0]
            return ({ 'name':  found[0]['name']}, 1)



