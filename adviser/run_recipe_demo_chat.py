from services.domain_tracker import DomainTracker
from recipe_project.nlg import RecipeNLG
from recipe_project.policy import RecipePolicy
from recipe_project.domain import RecipeDomain
from recipe_project.nlu import RecipeNLU
from recipe_project.bst import RecipeBST
from services.service import DialogSystem
from services.hci import ConsoleOutput
from services.nlg import HandcraftedNLG
from services.policy import HandcraftedPolicy
from services.bst import HandcraftedBST
from services.hci import ConsoleInput
from utils.domain.jsonlookupdomain import JSONLookupDomain
from utils.logger import DiasysLogger, LogLevel
import sys
import os


def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.join("..", (os.path.abspath(__file__)))))


sys.path.append(get_root_dir())
print(sys.path)


# import domain class and logger

# import services needed for the dialog system

# import dialog system class

from services.hci.speech import SpeechInputDecoder, SpeechInputFeatureExtractor, SpeechOutputGenerator
from services.hci.speech import SpeechOutputPlayer, SpeechRecorder

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


    # use_cuda = False
    # recorder = SpeechRecorder(conversation_log_dir=conversation_log_dir)
    # speech_in_feature_extractor = SpeechInputFeatureExtractor()
    # speech_in_decoder = SpeechInputDecoder(conversation_log_dir=conversation_log_dir, use_cuda=use_cuda)


    #
    # 1. Create a JSONLookupDomain object for the "recipes" domain
    domain      = RecipeDomain()

    nlu         = RecipeNLU(domain=domain, logger=logger)
    # nlu         = HandcraftedNLU(domain=domain, logger=logger)
    nlg         = RecipeNLG(domain=domain, logger=logger)

    bst         = RecipeBST(domain=domain, logger=logger)
    policy      = RecipePolicy(domain=domain, logger=logger)

    user_in     = ConsoleInput(domain="")
    user_out    = ConsoleOutput(domain="")

    # speech_out_generator = SpeechOutputGenerator(domain="", use_cuda=False)  # (GPU: 0.4 s/per utterance, CPU: 11 s/per utterance)
    # speech_out_player = SpeechOutputPlayer(domain="", conversation_log_dir=conversation_log_dir)

    d_tracker   = DomainTracker(domains=[domain])

    # recorder.start_recorder()

    # 3. Create a dialog system object and register all the necessary services to it
    system = DialogSystem(
        # services=[d_tracker, user_in, user_out, speech_out_generator, speech_out_player, nlu, bst, policy, nlg],
        services=[d_tracker, user_in, user_out, nlu, bst, policy, nlg],
        # services=[d_tracker, speech_out_generator, speech_out_player, nlu, bst, policy, nlg],
        debug_logger=logger)

    if not system.is_error_free_messaging_pipeline():
        system.print_inconsistencies()

    # system.draw_system_graph(name='system', show=False)
    # 4. Add code to run your dialog system
    print("run_dialog()")
    system.run_dialog({'gen_user_utterance': ""})
    print("shutdown()")
    system.shutdown()
