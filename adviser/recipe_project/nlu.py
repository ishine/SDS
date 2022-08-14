import re
import json
import os
from typing import List, Optional

from utils import UserAct, UserActionType, DiasysLogger, SysAct, SysActionType, BeliefState
from services.service import Service, PublishSubscribe
from .policy import BotStateView

def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UNK_ING : str        = "UNK_ING"

class RecipeNLU(Service):
    """NLU for the recipe bot. Code mostly taken from HandcraftedNLU, with some added checks that 
        would not fit well into GeneralRules.json.
    """

    def __init__(self, domain, logger=DiasysLogger()):
        Service.__init__(self, domain=domain)

        self.logger                                         = logger
        self.domain_name                                    = domain.get_domain_name()
        self.domain_key                                     = domain.get_primary_key()

        # Getting lists of informable and requestable slots
        self.USER_INFORMABLE                                = domain.get_informable_slots()
        self.USER_REQUESTABLE                               = domain.get_requestable_slots()

        # Getting the relative path where regexes are stored
        self.base_folder                                    = os.path.join(get_root_dir(), 'resources', 'nlu_regexes')

        # having the current system state available can be helpful in some cases
        self.bot_state_view : Optional[BotStateView]  = None

        # Holds a set of all ingredients occurring in the domain db after initialization
        self.ingredients                                    = set()

        self._initialize()

    def dialog_start(self) -> dict:
        """
        Sets the previous system act as None.
        This function is called when the dialog starts

        Returns:
            Empty dictionary

        """
        self.user_acts = []
        self.slots_informed = set()
        self.slots_requested = set()


    @PublishSubscribe(sub_topics=["user_utterance"], pub_topics=["user_acts"])
    def extract_user_acts(self, user_utterance: str = None) -> dict(user_acts=List[UserAct]):

        """
        Responsible for detecting user acts with their respective slot-values from the user
        utterance through regular expressions.

        Args:
            user_utterance (BeliefState) - a BeliefState obejct representing current system
                                           knowledge

        Returns:
            dict of str: UserAct - a dictionary with the key "user_acts" and the value
                                            containing a list of user actions
        """
        result              = {}
        self.user_acts      = []

        # slots_requested & slots_informed store slots requested and informed in this turn
        # they are used later for later disambiguation
        self.slots_requested, self.slots_informed = set(), set()
        if user_utterance is not None:
            user_utterance = user_utterance.strip()
            self._match_general_act(user_utterance)
            self._match_domain_specific_act(user_utterance)

        self._solve_informable_values()


        for bye in ('bye', 'goodbye', 'byebye', 'seeyou'):
            if user_utterance.replace(' ', '').endswith(bye):
                self.user_acts.append(UserAct(user_utterance, UserActionType.Bye))
        
        # Case: user selected recipe, denies wanting any more information
        if (self.bot_state_view is not None 
        and self.bot_state_view.last_sys_act() == SysActionType.Select 
        and re.match("(no ?)?(thanks|thank you)?", user_utterance.strip(), flags=re.I)):
            self.user_acts.append(UserAct(user_utterance, UserActionType.Bye))


        # Case: user requests a random recipe
        if (re.search("(\\b|^| )random (recipe|meal|food).*", user_utterance, flags=re.I)
            or re.search("(\\b|^| )(tell|suggest)( me)? (a|some) (recipe|meal|food)$", user_utterance, flags=re.I)):
            self.user_acts.append(UserAct(user_utterance, UserActionType.RequestRandom))

        # Case: start over (useful for debugging or if the bot reaches a dead-end)
        if re.search("(\\b|^| )(start (over|from the beginning)|restart)$", user_utterance, flags=re.I):
            self.user_acts.append(UserAct(user_utterance, UserActionType.StartOver))

        # Case: user wants to save chosen recipe as favorite
        if re.search("(\\b|^| )((can you( please)?|please )?(save|mark) (this|that)( recipe|food|meal)? (as a favorite|to my favorites)"
            "|save to favorites?)", user_utterance, flags=re.I):
            self.user_acts.append(UserAct(user_utterance, UserActionType.SaveAsFav))

        # Case: user wants to have listed all favorites
        if re.search("(\\b|^| )((list|show)( me)? my favorite|what are my favorite)", user_utterance, flags=re.I):
            self.user_acts.append(UserAct(user_utterance, UserActionType.ListFavs))

        # Case: user informs about how the recipe should be rated 
        # because the ratings in the database are star-based (1-5), we translate some other utterances to stars
        if re.search("(\\b|^| )(that is (highly|well) rated|(that has|with) a (high|good) rating)", user_utterance, flags=re.I):
            self.user_acts.append(UserAct(user_utterance, UserActionType.Inform, slot="rating", value="4"))

        # Case: user informs about how long the recipe should be take to prepare
        # analogous case to rating, prep_time is given in minutes in the database, so we are translating some common utterances
        if re.search("(\\b|^| )(takes little time|(quick|fast|uncomplicated) to (cook|prepare|make|do))", user_utterance, flags=re.I):
            self.user_acts.append(UserAct(user_utterance, UserActionType.Inform, slot="prep_time", value="30"))

        # If nothing else has been matched, see if the user chose a domain; otherwise if it's
        # not the first turn, it's a bad act
        if len(self.user_acts) == 0:
            if self.bot_state_view is not None and self.bot_state_view.last_sys_act() is not None:
                # start of dialogue or no regex matched
                self.user_acts.append(UserAct(text=user_utterance if user_utterance else "", act_type=UserActionType.Bad))


        self._assign_scores()
        self.logger.dialog_turn("User Actions: %s" % str(self.user_acts))
        result['user_acts'] = self.user_acts

        return result

    @PublishSubscribe(sub_topics=["bot_state"])
    def _update_bot_state(self, bot_state: BotStateView):
        """ Listen to system state changes. """

        self.bot_state_view = bot_state

    def _match_general_act(self, user_utterance: str):
        """
        Finds general acts (e.g. Hello, Bye) in the user input

        Args:
            user_utterance {str} --  text input from user

        Returns:

        """

        # Iteration over all general acts
        for act in self.general_regex:
            # Check if the regular expression and the user utterance match
            if re.search(self.general_regex[act], user_utterance, re.I):
                # Mapping the act to User Act
                print(f"matched: {act}")
                if act != 'dontcare' and act != 'req_everything':
                    user_act_type = UserActionType(act)
                else:
                    user_act_type = act
               
                user_act = UserAct(act_type=user_act_type, text=user_utterance)
                self.user_acts.append(user_act)

    def _match_domain_specific_act(self, user_utterance: str):
        """
        Matches in-domain user acts
        Calls functions to find user requests and informs

        Args:
            user_utterance {str} --  text input from user

        Returns:

        """
        # Find Requests
        self._match_request(user_utterance)
        # Find Informs
        self._match_inform(user_utterance)

    def _match_request(self, user_utterance: str):
        """
        Iterates over all user request regexes and find matches with the user utterance

        Args:
            user_utterance {str} --  text input from user

        Returns:

        """
        # Iteration over all user requestable slots
        for slot in self.USER_REQUESTABLE:
            if self._check(re.search(self.request_regex[slot], user_utterance, re.I)):
                self._add_request(user_utterance, slot)

    def _add_request(self, user_utterance: str, slot: str):
        """
        Creates the user request act and adds it to the user act list
        Args:
            user_utterance {str} --  text input from user
            slot {str} -- requested slot

        Returns:

        """
        # New user act -- Request(slot)
        user_act = UserAct(text=user_utterance, act_type=UserActionType.Request, slot=slot)
        self.user_acts.append(user_act)
        # Storing user requested slots during the whole dialog
        self.slots_requested.add(slot)

    def _match_inform(self, user_utterance: str):
        """
        Iterates over all user inform slot-value regexes and find matches with the user utterance

        Args:
            user_utterance {str} --  text input from user

        Returns:

        """

        # Iteration over all user informable slots and their slots
        for slot in self.USER_INFORMABLE:
            for value in self.inform_regex[slot]:
                if self._check(re.search(self.inform_regex[slot][value], user_utterance, re.I)):
                    if slot == self.domain_key and self.req_everything:
                        # Adding all requestable slots because of the req_everything
                        for req_slot in self.USER_REQUESTABLE:
                            # skipping the domain key slot
                            if req_slot != self.domain_key:
                                # Adding user request act
                                self._add_request(user_utterance, req_slot)
                    # Adding user inform act
                    self._add_inform(user_utterance, slot, value)
        
    def _add_inform(self, user_utterance: str, slot: str, value: str):
        """
        Creates the user request act and adds it to the user act list

        Args:
            user_utterance {str} --  text input from user
            slot {str} -- informed slot
            value {str} -- value for the informed slot

        Returns:

        """
        user_act = UserAct(text=user_utterance, act_type=UserActionType.Inform,
                           slot=slot, value=value)
        self.user_acts.append(user_act)
        # Storing user informed slots in this turn
        self.slots_informed.add(slot)

    @staticmethod
    def _exact_match(phrases: List[str], user_utterance: str) -> bool:
        """
        Checks if the user utterance is exactly like one in the

        Args:
            phrases List[str] --  list of contextual don't cares
            user_utterance {str} --  text input from user

        Returns:

        """

        # apostrophes are removed
        if user_utterance.lstrip().lower().replace("'", "") in phrases:
            return True
        return False

    def _match_affirm(self, user_utterance: str):
        """TO BE DEFINED AT A LATER POINT"""
        pass

    def _match_negative_inform(self, user_utterance: str):
        """TO BE DEFINED AT A LATER POINT"""
        pass

    @staticmethod
    def _check(re_object) -> bool:
        """
        Checks if the regular expression and the user utterance matched

        Args:
            re_object: output from re.search(...)

        Returns:
            True/False if match happened

        """

        if re_object is None:
            return False
        for o in re_object.groups():
            if o is not None:
                return True
        return False

    def _assign_scores(self):
        """
        Goes over the user act list, checks concurrencies and assign scores

        Returns:

        """

        for i in range(len(self.user_acts)):
            # TODO: Create a clever and meaningful mechanism to assign scores
            # Since the user acts are matched, they get 1.0 as score
            self.user_acts[i].score = 1.0


    def _solve_informable_values(self):
        # Verify if two or more informable slots with the same value were caught
        # Cases:
        # If a system request precedes and the slot is the on of the two informable, keep that one.
        # If there is no preceding request, take
        informed_values = {}
        for i, user_act in enumerate(self.user_acts):
            if user_act.type == UserActionType.Inform:
                if user_act.value != "true" and user_act.value != "false":
                    if user_act.value not in informed_values:
                        informed_values[user_act.value] = [(i, user_act.slot)]
                    else:
                        informed_values[user_act.value].append((i, user_act.slot))

        informed_values = {value: informed_values[value] for value in informed_values if
                           len(informed_values[value]) > 1}
        if "6" in informed_values:
            self.user_acts = []

    def _initialize(self):
        """
            Loads the correct regex files based on which language has been selected
            this should only be called on the first turn of the dialog

            Args:
                language (Language): Enum representing the language the user has selected
        """
        self.general_regex = json.load(open(self.base_folder + '/GeneralRules.json'))
        self.request_regex = json.load(open(self.base_folder + '/' + self.domain_name
                                            + 'RequestRules.json'))
        self.inform_regex = json.load(open(self.base_folder + '/' + self.domain_name
                                            + 'InformRules.json'))

        # construct a special rule for unknown ingredients
        # 1. take any rule from the ingredients informs
        (dummy_ing, reg)    = list(self.inform_regex['ingredients'].items())[0]
        # 2. replace the {ingredients} part with a regex matching any word
        unk_re              = reg.replace(dummy_ing, "[^ ]+")
        # 3. register the new rule for the ingredient UNK_ING
        self.inform_regex['ingredients'][UNK_ING] = unk_re
        
        # load all ingredients
        self.ingredients = self.domain.get_all_ingredients()