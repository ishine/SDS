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

from typing import List, Set, Optional
from services.service import PublishSubscribe
from services.service import Service
from utils.beliefstate import BeliefState
from utils.useract import UserActionType, UserAct
from .models.recipe_req import RecipeReq
from .models.recipe import Recipe
from .policy import BotState, BotStateView
from .nlu import UNK_ING


class RecipeBST(Service):
    """
    A rule-based approach to belief state tracking.
    """

    def __init__(self, domain=None, logger=None):
        Service.__init__(self, domain=domain)

        self.logger                             = logger
        self.bs                                 = BeliefState(domain)
        self.state : Optional[BotStateView]  = None

    
    @PublishSubscribe(sub_topics=["bot_state"], pub_topics=[])
    def bot_state_changed(self, bot_state: BotStateView = None):
        """ Listen to new state from Policy. """

        self.logger.info(f"Updating state to {bot_state.current()}")
        self.state = bot_state



    @PublishSubscribe(sub_topics=["user_acts"], pub_topics=["beliefstate"])
    def update_bst(self, user_acts: List[UserAct] = None) \
            -> dict(beliefstate=BeliefState):
        """
            Updates the current dialog belief state (which tracks the system's
            knowledge about what has been said in the dialog) based on the user actions generated
            from the user's utterances

            Args:
                user_acts (list): a list of UserAct objects mapped from the user's last utterance

            Returns:
                (dict): a dictionary with the key "beliefstate" and the value the updated
                        BeliefState object

        """
        # save last turn to memory
        self.bs.start_new_turn()

        self.logger.error(f"[bst] user_acts = {user_acts}")
        if user_acts:
            self._reset_informs(user_acts)
            self._reset_requests()
            self.bs["user_acts"] = self._get_all_usr_action_types(user_acts)

            self.bs["num_matches"] = self.cnt_matching()
            self._handle_user_acts(user_acts)
            self.bs["num_matches"] = self.cnt_matching()
            self.logger.info(f"[bs] after_handle_user_acts({self.bs['informs']})")

        elif not self.bs['start']:
            self.bs["user_acts"] = [UserActionType.Bad]

        self.bs['start'] = False
        return {'beliefstate': self.bs}

    def dialog_start(self):
        """
            Restets the belief state so it is ready for a new dialog

            Returns:
                (dict): a dictionary with a single entry where the key is 'beliefstate'and
                        the value is a new BeliefState object
        """
        # initialize belief state
        self.bs = BeliefState(self.domain)
        self.bs['start'] = True

    def cnt_matching(self) -> int:
        """ Returns the number of recipes matching the currently given informs. """

        return len(self.matching())

    def matching(self) -> List[Recipe]:
        """ Returns all recipes matching the currently given informs. """

        informs = self.bs['informs']
        req     = RecipeReq.from_informs(informs)
        found   = self.domain.find_recipes(req)
        return found


    def _reset_informs(self, acts: List[UserAct]):
        """
            If the user specifies a new value for a given slot, delete the old
            entry from the beliefstate
        """

        slots = {act.slot for act in acts if act.type == UserActionType.Inform}
        for slot in [s for s in self.bs['informs']]:
            # special case: ingredients should not be replaced unless a recipe has already been chosen
            if slot == "ingredients" and self.state != BotState.CHOSEN:
                continue
            if slot in slots:
                del self.bs['informs'][slot]
        self.logger.error(f"reset_informs({self.bs['informs']})")

    def _reset_requests(self):
        """
            gets rid of requests from the previous turn
        """
        self.bs['requests'] = {}

    def _get_all_usr_action_types(self, user_acts: List[UserAct]) -> Set[UserActionType]:
        """ 
        Returns a set of all different UserActionTypes in user_acts.

        Args:
            user_acts (List[UserAct]): list of UserAct objects

        Returns:
            set of UserActionType objects
        """
        action_type_set = set()
        for act in user_acts:
            action_type_set.add(act.type)
        return action_type_set

    def _handle_user_acts(self, user_acts: List[UserAct]):

        """
            Updates the belief state based on the information contained in the user act(s)

            Args:
                user_acts (list[UserAct]): the list of user acts to use to update the belief state

        """
        
        # reset any offers if the user informs any new information
        if self.domain.get_primary_key() in self.bs['informs'] \
                and UserActionType.Inform in self.bs["user_acts"]:
            del self.bs['informs'][self.domain.get_primary_key()]

        num_matches                     = self.bs['num_matches']
        self.bs['unknown_ingredient']   = False

        # Handle user acts
        for act in user_acts:
            if act.type == UserActionType.Request:
                self.bs['requests'][act.slot] = act.score
            elif act.type == UserActionType.Inform or act.type == UserActionType.InformAdd:
                if act.slot == 'ingredients' and act.value == UNK_ING:
                    self.bs['unknown_ingredient'] = len([ua for ua in user_acts if ua.type == UserActionType.Inform and ua.slot == 'ingredients']) == 1
                    self.logger.error(f"bs.unknown_ingredient = {self.bs['unknown_ingredient']}")
                    continue
                # add informs and their scores to the beliefstate
                if act.slot in self.bs["informs"]:
                    self.bs['informs'][act.slot][act.value] = act.score
                else:
                    self.bs['informs'][act.slot] = {act.value: act.score}
                if act.slot == 'name' and self.cnt_matching() == 1:
                    self.bs['chosen'] = self.matching()[0]

            elif act.type == UserActionType.Deny and self.state.current() == BotState.LISTED_RAND:
                self.bs['chosen'] = self.domain.get_random()
            elif act.type == UserActionType.RequestRandom:
                self.bs['chosen'] = self.domain.get_random()
            elif act.type == UserActionType.PickFirst and num_matches > 0 and num_matches < 5:
                self.bs['chosen'] = self.matching()[0]
            elif act.type == UserActionType.PickSecond and num_matches > 0 and num_matches < 5:
                self.bs['chosen'] = self.matching()[1]
            elif act.type == UserActionType.PickLast and num_matches > 0 and num_matches < 5:
                self.bs['chosen'] = self.matching()[-1]
            elif act.type == UserActionType.Affirm and num_matches == 1:
                self.bs['chosen'] = self.matching()[0]

            elif act.type == UserActionType.NegativeInform:
                # reset mentioned value to zero probability
                if act.slot in self.bs['informs']:
                    if act.value in self.bs['informs'][act.slot]:
                        del self.bs['informs'][act.slot][act.value]

            elif act.type == UserActionType.RequestAlternatives:
                # This way it is clear that the user is no longer asking about that one item
                if self.domain.get_primary_key() in self.bs['informs']:
                    del self.bs['informs'][self.domain.get_primary_key()]

            elif act.type == UserActionType.StartOver:
                self.bs = BeliefState(self.domain)