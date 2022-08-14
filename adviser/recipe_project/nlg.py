############################################################################################
#
# Copyright 2020, University of Stuttgart: Institute for Natural Language Processing (IMS)
#
# This file is part of Adviser.
# Adviser is free software: you can redistribute it and/or modify'
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
############################################################################################

from utils import DiasysLogger
from utils import SysAct, SysActionType
from services.service import Service, PublishSubscribe
from services.nlg.templates.templatefile import TemplateFile
from .policy import PolicyStateView, PolicyState
from typing import Optional
import random
import os



class RecipeNLG(Service):
    """NLG service for our recipe bot"""

    def __init__(self, domain, logger=DiasysLogger()):
        # only calls super class' constructor
        super(RecipeNLG, self).__init__(domain, debug_logger=logger)
        self.domain = domain
        self.templates = None
        self.logger = logger
        self.template_filename = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'resources/nlg_templates/%sMessages.nlg' % self.domain.get_domain_name())
        
        self.policy_state_view : Optional[PolicyStateView] = None
        self.templates = TemplateFile(self.template_filename, self.domain)


    # @PublishSubscribe(sub_topics=["policy_state"])
    # def _update_policy_state(self, policy_state: PolicyStateView):

    #     self.policy_state_view = policy_state


    @PublishSubscribe(sub_topics=["sys_act", "policy_state"], pub_topics=["sys_utterance"])
    def publish_system_utterance(self, sys_act: SysAct = None, policy_state: PolicyStateView = None) -> dict(sys_utterance=str):
        """Generates the system utterance and publishes it.

        Args:
            sys_act (SysAct): The system act published by the policy

        Returns:
            dict: a dict containing the system utterance
        """
        self.policy_state_view = policy_state
        return {'sys_utterance': self.generate_system_utterance(sys_act)}

    def generate_system_utterance(self, sys_act: SysAct = None) -> dict(sys_utterance=str):
        """Main function for generating and publishing the system utterance

        Args:
            sys_act: the system act for which to create a natural language realisation

        Returns:
            dict with "sys_utterance" as key and the system utterance as value
        """

        # don't know how to introduce randomness in NLG template, so for some actions,
        # we don't use the nlg templates.
        if sys_act is None or sys_act.type == SysActionType.Welcome:
            return random.choice([
                'Hi! This is your friendly recipe bot, how can I help you?',
                'Hello, I am the recipe bot. Let me know if I can help you in any way.',
                'Hi, this is the recipe bot. How can I help you?',
            ])

        if sys_act.type == SysActionType.Bad:
            return random.choice([
                'Sorry, I could not understand you.',
                'I\'m afraid I don\'t understand.'
            ])
        if sys_act.type == SysActionType.Bye:
            return  random.choice(['Thank you, good bye.',
            'I hope I could be of any help, see you.',
            'Always glad to help. Bye!'
            ]) 

        if sys_act.type == SysActionType.NotFound:
            self.logger.error(f"{self.policy_state_view.sys_act_history}")
            if self.policy_state_view.match_last_sys_acts([SysActionType.NotFound, SysActionType.FoundTooMany]):
                return "Sorry, that would narrow it down to 0 results."

            return random.choice(
                ["Sorry, I did not find anything in my database.",
                "Sorry, I cannot find anything in my database for that."])

        if sys_act.type == SysActionType.StartOver:
            return random.choice(
                ["Okay, let's start again from the beginning. How can I help you?",
                "Okay, let's start over. How can I help you?"])

        if sys_act.type == SysActionType.NotYetChosen:
            return random.choice(
                ["Please choose a recipe first.",
                "You have to first pick a recipe."])

        if sys_act.type == SysActionType.UnknownIngredient:
            return random.choice(
                ["I don't know that ingredient, sorry.",
                "I don't have anything with that ingredient in my database, sorry."])

        if sys_act.type == SysActionType.AskForPartialSearch:
            return "I found no exact matches. But there are recipes that satisfy at least some of your constraints. Do you want to hear them?"

        if sys_act.type == SysActionType.FoundTooMany:
            if self.policy_state_view.match_last_sys_acts([SysActionType.FoundTooMany, SysActionType.FoundTooMany]):
                return random.choice(
                ["I still found many recipes matching your criteria, please provide more information.",
                "There are still too many recipes matching your request, please give me more information."])
            return random.choice(
                ["I found many recipes, maybe you can give me some more information?",
                "A lot of recipes are fitting your request. Can you give me some more information?"])

        rule_found      = True
        message         = ""
        try:
            message = self.templates.create_message(sys_act)
        except BaseException as error:
            rule_found = False
            self.logger.error(error)
            raise(error)

        # inform if no applicable rule could be found in the template file
        if not rule_found:
            self.logger.error('Could not find a fitting rule for the given system act!')
            self.logger.error("System Action: " + str(sys_act.type)
                             + " - Slots: " + str(sys_act.slot_values))

        # self.logger.dialog_turn("System Action: " + message)
        return message


        # elif sys_act.type == SysActionType.InformByName:
        #     answer = sys_act.slot_values['answer']
        #     return {'sys_utterance': answer }
            
        # else:
        #     return {'sys_utterance': 'nothing defined for this sys act yet' }
