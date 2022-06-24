import sys
import os

def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.join("..", (os.path.abspath(__file__)))))

sys.path.append(get_root_dir())
print(sys.path)


# import domain class and logger
from utils.logger import DiasysLogger, LogLevel
from utils.domain.jsonlookupdomain import JSONLookupDomain

# import services needed for the dialog system
from services.domain_tracker import DomainTracker 
from services.hci import ConsoleInput
from services.nlu import HandcraftedNLU
from services.bst import HandcraftedBST
from services.policy import HandcraftedPolicy
from services.nlg import HandcraftedNLG
from services.hci import ConsoleOutput

# import dialog system class
from services.service import DialogSystem

from recipe_project.domain import RecipeDomain
from recipe_project.policy import RecipePolicy
from recipe_project.nlg import RecipeNLG

if __name__ == "__main__":


    # setup logger
    file_log_lvl            = LogLevel["INFO"]
    log_lvl                 = LogLevel["INFO"]
    conversation_log_dir    = './conversation_logs'
    speech_log_dir          = None


    logger = DiasysLogger(file_log_lvl=file_log_lvl,
                          console_log_lvl=log_lvl,
                          logfile_folder=conversation_log_dir,
                          logfile_basename="full_log")


    # logger = None

    #
    # 1. Create a JSONLookupDomain object for the "recipes" domain
    domain = RecipeDomain()


    # 2. For each service, create an object, don't forget to pass the correct domain as an argument
    #    Refer back to the last section of the tutorial if you have trouble

    # todo
    # nlu     = RecipeNLU(domain=domain)
    nlu     = HandcraftedNLU(domain = domain, logger=logger)
    nlg     = RecipeNLG(domain = domain, logger = logger)

    # ?
    # bst     = HandcraftedBST(domain=domain)
    policy  = RecipePolicy(domain = domain, logger = logger)

    user_in = ConsoleInput(domain= "")
    user_out = ConsoleOutput(domain="")

    d_tracker = DomainTracker(domains=[domain])


    # 3. Create a dialog system object and register all the necessary services to it
    system    = DialogSystem(
        services=[d_tracker, user_in, user_out, nlu, policy, nlg], 
        debug_logger=logger)



    if not system.is_error_free_messaging_pipeline():
        system.print_inconsistencies()

    system.draw_system_graph(name='system', show=False)
    # 4. Add code to run your dialog system
    print("run_dialog()")
    system.run_dialog({'gen_user_utterance': ""})
    print("shutdown()")
    system.shutdown()