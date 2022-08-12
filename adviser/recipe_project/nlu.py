import re
from datetime import datetime, timedelta
from typing import List

from utils import UserAct, UserActionType, DiasysLogger, SysAct, BeliefState
from services.service import Service, PublishSubscribe

class RecipeNLU(Service):
    """NLU for the recipe bot."""

    def __init__(self, domain, logger=DiasysLogger()):
        # only calls super class' constructor
        super(RecipeNLU, self).__init__(domain, debug_logger=logger)

    @PublishSubscribe(sub_topics=["user_utterance"], pub_topics=["user_acts"])
    def extract_user_acts(self, user_utterance: str = None) -> dict(user_acts=List[UserAct]):
        """Main function for detecting and publishing user acts.

        Args:
            user_utterance: the user input string

        Returns:
            dict with key 'user_acts' and list of user acts as value
        """
        self.debug_logger.info(f"NLU(): extract_user_acts('{user_utterance}')")
        user_acts = []
        if not user_utterance or len(user_utterance) == 0:
            return {'user_acts': None}
        user_utterance = ' '.join(user_utterance.lower().split())

        for bye in ('bye', 'goodbye', 'byebye', 'seeyou'):
            if user_utterance.replace(' ', '').endswith(bye):
                return {'user_acts': [UserAct(user_utterance, UserActionType.Bye)]}

        # request a random recipe
        if re.match("(\\b|^| )random (recipe|meal|food).*", user_utterance, flags=re.I):
            return {'user_acts': [UserAct(user_utterance, UserActionType.RequestRandom)]}

        # start over (useful for debugging)
        if re.match("(\\b|^| )start (over|from the beginning).*", user_utterance, flags=re.I):
            return {'user_acts': [UserAct(user_utterance, UserActionType.StartOver)]}

        # save as favorite
        if re.match("(\\b|^| )((can you( please)?|please )?(save|mark) (this|that)( recipe|food|meal)? (as a favorite|to my favorites)"
            "|save to favorites?)", user_utterance, flags=re.I):
            return {'user_acts': [UserAct(user_utterance, UserActionType.SaveAsFav)]}

        # list favorites
        if re.match("(\\b|^| )(list my favorite|what are my favorite)", user_utterance, flags=re.I):
            return {'user_acts': [UserAct(user_utterance, UserActionType.ListFavs)]}
        
        self.debug_logger.dialog_turn("User Actions: %s" % str(user_acts))
        return {'user_acts': user_acts}
