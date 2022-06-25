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
from services.service import PublishSubscribe, Service
from utils import SysAct, SysActionType
from utils.logger import DiasysLogger
from utils.useract import UserAct, UserActionType
from collections import defaultdict


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

    @PublishSubscribe(sub_topics=["user_acts"], pub_topics=["sys_act", "sys_state"])
    def generate_sys_acts(self, user_acts: List[UserAct] = None) -> dict(sys_acts=List[SysAct]):
        """Generates system acts by looking up answers to the given user question.

        Args:
            user_acts: The list of user acts containing information about the predicted relation,
                topic entities and relation direction

        Returns:
            dict with 'sys_acts' as key and list of system acts as value
        """
        if user_acts is None or len(user_acts) == 0:
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state}

        # assume one user act for now
        ua                              = user_acts[0]
        last_ua                         = self.sys_state['last_user_act']
        self.sys_state['last_user_act'] = ua

        if ua.type == UserActionType.Hello: 
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state }

        if ua.type == UserActionType.Bye:
            return { 'sys_act': SysAct(SysActionType.Bye), 'sys_state': self.sys_state }

        if ua.type == UserActionType.Inform and ua.slot == 'ingredients':
            a, cnt = self._inform_ingredients(ua.value)
            return self._recipe_answer(a, cnt)

        if ua.type == UserActionType.Inform and ua.slot == 'name':
            a, cnt = self._fetch_by_name(ua.value)
            return self._recipe_answer(a, cnt)

        if ua.type == UserActionType.Inform and ua.slot == 'ease':
            a, cnt = self._fetch_by_ease(ua.value)
            return self._recipe_answer(a, cnt)

    
    def _recipe_answer(self, answer: dict, cnt: int) -> dict:
        if cnt == 0:
            return self._not_found()
        if cnt == 1:
            return self._found_one(answer)
        if cnt < 5:
            return self._found_some(answer)

        return self._found_too_many()


    def _not_found(self) -> dict:
        return { 'sys_act': SysAct(SysActionType.NotFound), 'sys_state': self.sys_state }


    def _found_some(self, answer: dict) -> dict:

        if not isinstance(answer, dict):
            raise Exception(f"answer should be a dictionary, but is {str(type(answer))}")
        
        return { 'sys_act': SysAct(SysActionType.FoundSome, slot_values=answer), 'sys_state': self.sys_state }

    def _found_one(self, answer: dict) -> dict:

        if not isinstance(answer, dict):
            raise Exception(f"answer should be a dictionary, but is {str(type(answer))}")
        
        return { 'sys_act': SysAct(SysActionType.FoundOne, slot_values=answer), 'sys_state': self.sys_state }

    def _found_too_many(self) -> dict:

        return { 'sys_act': SysAct(SysActionType.FoundTooMany), 'sys_state': self.sys_state }

    def _fetch_by_name(self, value: str) -> dict:

        found   = self.domain.find_recipes_by_name(value)
        flen    = len(found)

        if flen > 1:
            self.sys_state['waiting_for_filter'] = foun    
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

        found = self.domain.find_recipes_by_ingredients([value])

        if len(found) > 1:
            self.sys_state['waiting_for_filter'] = found
            self.sys_state['current_suggested_recipe'] = None
            return ({ 'names': ',\n'.join(r['name'] for r in found)}, len(found))

        elif len(found) == 1:
            self.sys_state['waiting_for_filter'] = None
            self.sys_state['current_suggested_recipe'] = found[0]
            return ({ 'name':  found[0]['name']}, 1)



