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
import random



class RecipeNLG(Service):
    """NLG service for our recipe bot"""

    def __init__(self, domain, logger=DiasysLogger()):
        # only calls super class' constructor
        super(RecipeNLG, self).__init__(domain, debug_logger=logger)

    @PublishSubscribe(sub_topics=["sys_act"], pub_topics=["sys_utterance"])
    def generate_system_utterance(self, sys_act: SysAct = None) -> dict(sys_utterance=str):
        """Main function for generating and publishing the system utterance

        Args:
            sys_act: the system act for which to create a natural language realisation

        Returns:
            dict with "sys_utterance" as key and the system utterance as value
        """

        if sys_act is None or sys_act.type == SysActionType.Welcome:
            return {'sys_utterance': random.choice([
                'Hi! This is your friendly recipe bot, how can I help you?',
                'Hello, I am the recipe bot. Let me know if I can help you in any way.'
            ])}

        if sys_act.type == SysActionType.Bad:
            return {'sys_utterance': random.choice([
                'Sorry, I could not understand you.',
                'I\'m afraid I don\'t understand.'
            ])}
        elif sys_act.type == SysActionType.Bye:
            return {'sys_utterance': 
            random.choice(['Thank you, good bye.',
            'I hope I could be of any help, see you.',
            'Always glad to help. Bye!'
            ]) }

        elif sys_act.type == SysActionType.Request:
            slot = list(sys_act.slot_values.keys())[0]
            if slot == 'date':
                return {'sys_utterance': 'For which day are you looking for the weather?'}
            elif slot == 'location':
                return {'sys_utterance': 'Which city are you at?'}
            else:
                assert False, 'Only the date and the location can be requested'

        elif sys_act.type == SysActionType.InformByName:
            answer = sys_act.slot_values['answer']
            return {'sys_utterance': answer }
            
        else:
            return {'sys_utterance': 'nothing defined for this sys act yet' }
