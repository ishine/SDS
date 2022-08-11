# 
# Just some simple tests to confirm that all basic interactions are working
#


from services.domain_tracker import DomainTracker
from recipe_project.nlg import RecipeNLG
from recipe_project.policy import RecipePolicy
from recipe_project.domain import RecipeDomain
from recipe_project.bst import RecipeBST
from services.service import DialogSystem
from services.hci import ConsoleOutput
from services.nlg import HandcraftedNLG
from services.policy import HandcraftedPolicy
from services.bst import HandcraftedBST
from services.nlu import HandcraftedNLU
from services.hci import ConsoleInput
from utils.domain.jsonlookupdomain import JSONLookupDomain
from utils.logger import DiasysLogger, LogLevel
from utils.useract import UserActionType
import sys
import os


def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.join("..", (os.path.abspath(__file__)))))


sys.path.append(get_root_dir())
print(sys.path)


# import domain class and logger

# import services needed for the dialog system

# import dialog system class


if __name__ == "__main__":

    # setup logger
    file_log_lvl            = LogLevel["ERRORS"]
    log_lvl                 = LogLevel["ERRORS"]
    conversation_log_dir    = './conversation_logs'
    speech_log_dir          = None

    logger                  = DiasysLogger(file_log_lvl=file_log_lvl,
                                            console_log_lvl=log_lvl,
                                            logfile_folder=conversation_log_dir,
                                            logfile_basename="full_log")

    # 1. Create a JSONLookupDomain object for the "recipes" domain
    domain      = RecipeDomain()

    # nlu     = RecipeNLU(domain=domain)
    nlu         = HandcraftedNLU(domain=domain, logger=logger)
    nlg         = RecipeNLG(domain=domain, logger=logger)

    bst         = RecipeBST(domain=domain, logger=logger)
    policy      = RecipePolicy(domain=domain, logger=logger)

    user_in     = ConsoleInput(domain="")
    user_out    = ConsoleOutput(domain="")
    d_tracker   = DomainTracker(domains=[domain])


    # 3. Create a dialog system object and register all the necessary services to it
    system = DialogSystem(
        services=[d_tracker, user_in, user_out, nlu, bst, policy, nlg],
        debug_logger=logger)

    if not system.is_error_free_messaging_pipeline():
        system.print_inconsistencies()

    print("running inform(ingredient) tests...")
    for utterance in [
        "suggest me a recipe with mango", 
        "find a meal with tuna", 
        "can you suggest a recipe that contains yeast?",
        "I want to cook something with spinach" 
        ]:
        ua = nlu.extract_user_acts(utterance)['user_acts']
        print(ua)
        assert len(ua) == 1
        assert ua[0].type == UserActionType.Inform
    print("finished inform(ingredient) tests. all ok.")

    print("running inform(name) tests...")
    for utterance in [
        "do you have the recipe for black bean soup?"
        ]:
        ua = nlu.extract_user_acts(utterance)['user_acts']
        print(ua)
        assert len(ua) == 1
        assert ua[0].type == UserActionType.Inform
    print("finished inform(name) tests. all ok.")

    print("running inform(name) tests...")
    for utterance in [
        "do you have the recipe for black bean soup?"
        ]:
        ua = nlu.extract_user_acts(utterance)['user_acts']
        print(ua)
        assert len(ua) == 1
        assert ua[0].type == UserActionType.Inform
    print("finished inform(name) tests. all ok.")

    print("finished tests.")
