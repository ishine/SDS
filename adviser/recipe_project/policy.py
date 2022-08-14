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

from typing import List, Dict, Optional
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

class BotState(Enum):
    """ Represents the bots internal state. """
    
    START           = 0
    LISTED_FAV      = 1
    LISTED_FOUND    = 2
    LISTED_RAND     = 3
    CHOSEN          = 4
    ASKED_FOR_PART  = 5

class BotStateView:

    """ Wrapper around the bots state + a history of sys acts, with some convenience methods. """

    def __init__(self):

        self.state_history   : List[BotState]       = []
        self.current_state   : BotState             = BotState.START
        self.sys_act_history : List[SysActionType]  = []
    
    def update(self, new_bot_state: Optional[BotState], new_sys_act: SysActionType):
        """ Update the internal state. If new_bot_state is None, old state is kept. """

        if self.current_state != new_bot_state and new_bot_state is not None:
            self.state_history.append(self.current_state)
            self.current_state = new_bot_state

        self.sys_act_history.append(new_sys_act)
    
    def current(self) -> BotState:
        """ Get the current bot state. """
        return self.current_state

    def previous_state(self) -> Optional[BotState]:
        """ Get the previous bot state. """
        if len(self.state_history) > 0:
            return self.state_history[-1]
        return None

    def last_sys_act(self) -> Optional[SysActionType]:
        """ Get the last sys act. """
        if len(self.sys_act_history) > 0:
            return self.sys_act_history[-1]
        return None
    
    def match_last_sys_acts(self, to_match: List[SysActionType]) -> bool:
        """ 
            Convenience method to pattern match against the sys act history. 
            This will start with the last entry in the sys act history, and try to match each of the given sys acts.
            Returns True if all given sys acts matched.
        """
        if len(self.sys_act_history) < len(to_match):
            return False
        for ix, a in enumerate(to_match):
            if not self.sys_act_history[-(ix+1)] == a:
                return False
        return True
        


class RecipePolicy(Service):
    """Policy module for recipe lookup dialogues.  """

    def __init__(self, domain: RecipeDomain, logger: DiasysLogger = DiasysLogger()):
        Service.__init__(self, domain=domain, debug_logger=logger)

        self.state      = BotStateView()

    
    @PublishSubscribe(sub_topics=["beliefstate"], pub_topics=["sys_act", "bot_state"])
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
            return self.answer(None, SysActionType.Welcome)

        ua              = list(user_acts)[0]

        self.debug_logger.error(f"[policy] UAs={user_acts}")
        if ua == UserActionType.Hello:
            return self.answer(None, SysActionType.Welcome)

        if ua == UserActionType.Thanks:
            return self.answer(BotState.START, SysActionType.RequestMore)

        if ua == UserActionType.Bye:
            return self.answer(BotState.START, SysActionType.Bye)

        if ua == UserActionType.Bad:
            return self.answer(None, SysActionType.Bad)


        # user was presented some selection (2-4) and now picks one
        if ua == UserActionType.PickFirst and num_matches > 0 and num_matches < 5:
            return self.answer(BotState.CHOSEN, SysActionType.Select)
        if ua == UserActionType.PickSecond and num_matches > 0 and num_matches < 5:
            return self.answer(BotState.CHOSEN, SysActionType.Select)
        if ua == UserActionType.PickLast and num_matches > 0 and num_matches < 5:
            return self.answer(BotState.CHOSEN, SysActionType.Select)
        if ua == UserActionType.Affirm and self._has_chosen(bs):
            return self.answer(BotState.CHOSEN, SysActionType.Select)

        if ua == UserActionType.RequestRandom:
            return self._suggest_one(bs['chosen'])
        if ua == UserActionType.Deny and self.state.current() == BotState.LISTED_RAND:
            return self._suggest_one(bs['chosen'])

        if ua == UserActionType.ListFavs:
            favs = self.domain.get_users_favs()
            m    = None
            st   = None
            if len(favs) == 0:
                m = "You have not set any favorites yet."
            elif len(favs) == 1:
                st  = BotState.LISTED_FAV
                m   = f"Your only favorite recipe is {favs[0]}."
            elif len(favs) == 2:
                st  = BotState.LISTED_FAV
                m   = f"Your have set 2 recipes as favorites, {favs[0]} and {favs[1]}."
            else:
                st  = BotState.LISTED_FAV
                m   = "Your favorites are: " + ", ".join([r.name for r in favs]) + "."
            

            return self.answer(st, SysActionType.Inform, slot_values={'message': m})

        # save as favorite 
        if ua == UserActionType.SaveAsFav:
            if not self.state.current() == BotState.CHOSEN:
                return self.answer(BotState.CHOSEN, SysActionType.NotYetChosen)

            self.domain.set_favorite(self.bs['chosen'].name)
            return self.answer(BotState.CHOSEN, SysActionType.Inform, slot_values={'message': "I set the recipe as a favorite."})
        # remove from favorites 
        if ua == UserActionType.RemoveFromFavs:
            if not self.state.current() == BotState.CHOSEN:
                return self.answer(None, SysActionType.NotYetChosen)
            self.domain.unset_favorite(self.bs['chosen'].name)
            return self.answer(None, SysActionType.Inform, slot_values={'message': "I removed the recipe from your favorites."})
        
        if ua == UserActionType.Request:

            if self.state.current() not in (BotState.CHOSEN, BotState.LISTED_RAND):
                return self.answer(None, SysActionType.NotYetChosen)


            chosen  = bs['chosen']

            slot    = list(bs['requests'].keys())[0]
            m       = "Sorry, I did not understand that request."
            if slot == 'ease':
                m = self._inform_ease(chosen.ease)
            elif slot == 'name':
                m = self._inform_ease(chosen.name)
            elif slot == 'cookbook':
                m = self._inform_book(chosen.cookbook)
            elif slot == 'page':
                m = self._inform_page(chosen.page)
            elif slot == 'ingredients':
                m = self._inform_ingredients(chosen.ingredients)
            elif slot == 'rating':
                m = self._inform_rating(chosen.rating)
            elif slot == 'prep_time':
                m = self._inform_prep_time(chosen.prep_time)
            return self.answer(None, SysActionType.Inform, slot_values={'message': m})

        if ua == UserActionType.Affirm and self.state.current() == BotState.ASKED_FOR_PART:

            req     = RecipeReq.from_informs(informs)
            found   = self.domain.find_recipes(req, partial=True)
            cnt     = len(found)

            if cnt == 0:
                return self._not_found()
            if cnt == 1:
                return self._narrowed_down_to_one(found[0])
            return self._found_some(found)
            
        if ua == UserActionType.Deny and self.state.current() == BotState.ASKED_FOR_PART:
            return self.answer(BotState.START, SysActionType.StartOver)

        if ua == UserActionType.Inform:

            if bs['unknown_ingredient']:
                return self.answer(None, SysActionType.UnknownIngredient)


            req     = RecipeReq.from_informs(informs)
            found   = self.domain.find_recipes(req)
            cnt     = len(found)

            if cnt == 0:
                if sum(len(v.keys()) for v in informs.values()) > 1:
                    partially_matching = self.domain.find_recipes(req, partial = True)
                    if len(partially_matching) > 0 and len(partially_matching) < 100:
                        return self.answer(BotState.ASKED_FOR_PART, SysActionType.AskForPartialSearch)

                return self._not_found()
            if cnt == 1:
                if 'name' in informs and len(informs['name'].keys()) > 0 and list(informs['name'].keys())[0].casefold() == found[0].name.casefold():
                    return self.answer(BotState.CHOSEN, SysActionType.Select)

                if not self._has_chosen(bs):
                    return self._narrowed_down_to_one(found[0])

                return self._found_one(found[0])

            if cnt < 5:
                return self._found_some(found)
            
            return self._found_too_many()

        if ua == UserActionType.StartOver:
            return self.answer(BotState.START, SysActionType.StartOver)

        return self.answer(None, SysActionType.Bad)

    def answer(self, new_bot_state: Optional[BotState], sys_action_type: SysActionType, slot_values: Optional[dict] = None) -> dict:
        self.state.update(new_bot_state, sys_action_type)
        return { 'bot_state': self.state, 'sys_act': SysAct(sys_action_type, slot_values)}

    def _has_chosen(self, bs: BeliefState) -> bool:
        """ Check in the beliefstate if the dialog partner has already decided on a recipe. """
        return 'chosen' in bs and bs['chosen'] is not None

    #
    # Helpers for returning SysActs
    #

    def _not_found(self) -> dict:
        return self.answer(None, SysActionType.NotFound)

    def _found_some(self, recipes: List[Recipe]) -> dict:
        
        if len(recipes) == 2:
            return self.answer(BotState.LISTED_FOUND, SysActionType.FoundSome, slot_values={'names': f"{recipes[0].name} or {recipes[1].name}"})
        return self.answer(BotState.LISTED_FOUND, SysActionType.FoundSome, slot_values={'names': ", ".join([r.name for r in recipes])})

    def _found_one(self, recipe: Recipe) -> dict:

        return self.answer(BotState.LISTED_FOUND, SysActionType.FoundOne, slot_values={'name': recipe.name})

    def _found_too_many(self) -> dict:

        return self.answer(BotState.LISTED_FOUND, SysActionType.FoundTooMany)

    def _narrowed_down_to_one(self, recipe: Recipe) -> dict:

        return self.answer(BotState.LISTED_FOUND, SysActionType.NarrowedDownToOne, slot_values={'name': recipe.name})

    def _suggest_one(self, recipe: Recipe) -> dict:

        return self.answer(BotState.LISTED_RAND, SysActionType.Inform, slot_values={'message': f"How about {recipe.name}?"})


    #
    # Helpers to inform about different informables
    #

    def _inform_ease(self, ease: Optional[str] = None) -> str:
        if ease is None:
            return random.choice([
                "It cannot tell you how easy this recipe is, sorry.",
                "I do not have that information, sorry."
            ])
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

    def _inform_book(self, book: Optional[str] = None) -> str:
        return random.choice([
                "It is in the book named {}.",
                "The name of the book is {}.",
                "It's {}."
        ]).format(book)

    def _inform_page(self, page: Optional[str] = None) -> str:
        return random.choice([
                "It is on page {}.",
                "It's page {}."
        ]).format(page)

    def _inform_prep_time(self, time: Optional[str] = None) -> str:
        if time is None:
            return random.choice([
                "I haven't stored any preparation time for this recipe, sorry.",
                "I do not have that information, sorry."
            ])
        return random.choice([
                "This recipe takes {} minutes to prepare.",
                "It takes about {} minutes."
        ]).format(time)

    def _inform_rating(self, rating: Optional[str] = None) -> str:
        if rating is None:
            return random.choice([
                "I haven't stored any rating for this recipe, sorry.",
                "I do not have that information, sorry."
            ])
        return random.choice([
                "This recipe is rated with {} stars.", 
                "It has {} stars."
        ]).format(rating)

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




