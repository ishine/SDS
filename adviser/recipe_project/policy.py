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
from enum import Enum

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

class PolicyState(Enum):
    
    START           = 0
    LISTED_FAV      = 1
    LISTED_FOUND    = 2
    LISTED_RAND     = 3
    CHOSEN          = 4


class RecipePolicy(Service):
    """Policy module for recipe lookup dialogues.  """

    def __init__(self, domain: RecipeDomain, logger: DiasysLogger = DiasysLogger()):
        Service.__init__(self, domain=domain, debug_logger=logger)

        self.state = PolicyState.START

    

    @PublishSubscribe(sub_topics=["beliefstate"], pub_topics=["sys_act", "sys_state"])
    def generate_sys_acts(self, beliefstate: BeliefState) -> dict(sys_acts=List[SysAct]):
        """Generates system acts by looking up answers to the given user question.
        Returns:
            dict with 'sys_acts' as key and list of system acts as value
        """

        bs              = beliefstate
        # new informs
        informs         = bs['informs']
        # how many matching recipes found atm in db
        num_matches     = bs['num_matches']

        self.debug_logger.info(f"num_matches={num_matches}, informs.ingredients={len(informs.get('ingredients', []))}")
        # current user act types
        user_acts       = bs['user_acts']

        if user_acts is None or len(user_acts) == 0:
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state}

        ua              = list(user_acts)[0]
        self.debug_logger.error(f"UAs={user_acts}")

        if ua == UserActionType.Hello:
            return { 'sys_act': SysAct(SysActionType.Welcome), 'sys_state': self.sys_state }

        if ua == UserActionType.Thanks:
            self.state = PolicyState.START
            return { 'sys_act': SysAct(SysActionType.RequestMore), 'sys_state': self.sys_state }

        if ua == UserActionType.Bye:
            self.state = PolicyState.START
            return { 'sys_act': SysAct(SysActionType.Bye), 'sys_state': self.sys_state }

        if ua == UserActionType.Bad:
            return { 'sys_act': SysAct(SysActionType.Bad), 'sys_state': self.sys_state }


        # user was presented some selection (2-4) and now picks one
        if ua == UserActionType.PickFirst and num_matches > 0 and num_matches < 5:
            self.state = PolicyState.CHOSEN
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.PickSecond and num_matches > 0 and num_matches < 5:
            self.state = PolicyState.CHOSEN
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.PickLast and num_matches > 0 and num_matches < 5:
            self.state = PolicyState.CHOSEN
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
        if ua == UserActionType.Affirm and self._has_chosen(bs):
            self.state = PolicyState.CHOSEN
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }

        if ua == UserActionType.RequestRandom:
            self.state = PolicyState.LISTED_RAND
            return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }

        if ua == UserActionType.ListFavs:
            favs = self.domain.get_users_favs()
            m    = None
            if len(favs) == 0:
                m = "You have not set any favorites yet."
            elif len(favs) == 1:
                self.state = PolicyState.LISTED_FAV
                m = f"Your only favorite recipe is {favs[0]}."
            elif len(favs) == 2:
                self.state = PolicyState.LISTED_FAV
                m = f"Your have set 2 recipes as favorites, {favs[0]} and {favs[1]}."
            else:
                self.state = PolicyState.LISTED_FAV
                m = "Your favorites are: " + ", ".join([r.name for r in favs]) + "."
            

            return { 'sys_act': SysAct(SysActionType.Inform, slot_values={'message': m}), 'sys_state': self.sys_state }

        # save as favorite 
        if ua == UserActionType.SaveAsFav:
            if not self.state == PolicyState.CHOSEN:
                return { 'sys_act': SysAct(SysActionType.NotYetChosen), 'sys_state': self.sys_state }

            self.state = PolicyState.CHOSEN
            self.domain.set_favorite(self.bs['chosen'].name)
            return { 'sys_act': SysAct(SysActionType.Inform, slot_values={'message': "I set the recipe as a favorite."}), 'sys_state': self.sys_state }
        # remove from favorites 
        if ua == UserActionType.RemoveFromFavs:
            if not self.state == PolicyState.CHOSEN:
                return { 'sys_act': SysAct(SysActionType.NotYetChosen), 'sys_state': self.sys_state }
            self.state = PolicyState.CHOSEN
            self.domain.unset_favorite(self.bs['chosen'].name)
        
        if ua == UserActionType.Request:

            if self.state != PolicyState.CHOSEN:
                return { 'sys_act': SysAct(SysActionType.NotYetChosen), 'sys_state': self.sys_state }

            chosen  = bs['chosen']
            slot    = list(bs['requests'].keys())[0]
            m       = "Sorry, I did not understand that request."
            if slot == 'ease':
                m = self._inform_ease(chosen.ease)
            elif slot == 'name':
                m = self._inform_ease(chosen.name)
            elif slot == 'cookbook':
                m = self._inform_book(chosen.book)
            elif slot == 'page':
                m = self._inform_page(chosen.page)
            elif slot == 'ingredients':
                m = self._inform_ingredients(chosen.ingredients)
            elif slot == 'prep_time':
                m = self._inform_prep_time(chosen.prep_time)
            return { 'sys_act': SysAct(SysActionType.Inform, slot_values={'message': m}), 'sys_state': self.sys_state }


        if informs and len(informs) > 0:

            req     = RecipeReq.from_informs(informs)
            found   = self.domain.find_recipes(req)
            cnt     = len(found)

            if cnt == 0:
                return self._not_found()
            if cnt == 1:
                self.state = PolicyState.LISTED_FOUND
                if 'name' in informs and len(informs['name'].keys()) > 0 and list(informs['name'].keys())[0].casefold() == found[0].name.casefold():
                    return { 'sys_act': SysAct(SysActionType.Select), 'sys_state': self.sys_state }
                if not self._has_chosen(bs):
                    return self._narrowed_down_to_one(found[0])
                return self._found_one(found[0])
            if cnt < 5:
                self.state = PolicyState.LISTED_FOUND
                return self._found_some(found)
            
            self.state = PolicyState.LISTED_FOUND
            return self._found_too_many()

        if ua == UserActionType.StartOver:
            self.state = PolicyState.START
            return { 'sys_act': SysAct(SysActionType.StartOver), 'sys_state': self.sys_state }
        
        return { 'sys_act': SysAct(SysActionType.Bad), 'sys_state': self.sys_state }


    def _has_chosen(self, bs: BeliefState) -> bool:
        """ Check in the beliefstate if the dialog partner has already decided on a recipe. """
        return 'chosen' in bs and bs['chosen'] is not None

    #
    # Helpers for returning SysActs
    #

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

    def _narrowed_down_to_one(self, recipe: Recipe) -> dict:

        return { 'sys_act': SysAct(SysActionType.NarrowedDownToOne, slot_values={'name': recipe.name}), 'sys_state': self.sys_state }

    #
    # Helpers to inform about different informables
    #

    def _inform_ease(self, ease: str) -> str:
        if ease.casefold() == "average":
            ease = random.choice(["neither hard nor simple", "not too difficult, but also not too easy"])

        return random.choice([
            "It is {} to make.",
            "It is {}."
        ]).format(ease)

    def _inform_name(self, name: str) -> str:
        return random.choice([
                "It is named {}.",
                "The name is {}.",
                "It's {}."
        ]).format(name)

    def _inform_book(self, book: str) -> str:
        return random.choice([
                "It is in the book named {}.",
                "The name of the book is {}.",
                "It's {}."
        ]).format(book)

    def _inform_page(self, page: str) -> str:
        return random.choice([
                "It is on page {}.",
                "It's page {}."
        ]).format(page)

    def _inform_prep_time(self, time: str) -> str:
        return random.choice([
                "This recipe takes {} minutes to prepare.",
                "It takes about {} minutes."
        ]).format(time)

    def _inform_ingredients(self, ingredients: str) -> str:
        spl = ingredients.split(',')
        if len(spl) == 2:
            return random.choice([
                    f"The ingredients are {spl[0]} and {spl[1]}.",
                    f"You will need {spl[0]} and {spl[1]}."
            ])
        if len(spl) == 1:
            return random.choice([
                    f"The only ingredient is {spl[0]}.",
                    f"You will only need {spl[0]}."
            ])

        head = ", ".join(spl[:-1])
        tail = spl[-1]
        return random.choice([
                f"The ingredients are {head} and {tail}.",
                f"You will need {head} and {tail}."
        ])




