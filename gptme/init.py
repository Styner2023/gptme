import atexit
import logging
import readline

from dotenv import load_dotenv

from .config import config_path, load_config, set_config_value
from .dirs import get_readline_history_file
from .llm import get_recommended_model, init_llm
from .models import set_default_model
from .tabcomplete import register_tabcomplete
from .tools import init_tools

logger = logging.getLogger(__name__)
_init_done = False

PROVIDERS = ["openai", "anthropic", "azure", "local"]


def init(provider: str | None, model: str | None, interactive: bool):
    global _init_done
    if _init_done:
        logger.warning("init() called twice, ignoring")
        return
    _init_done = True

    # init
    logger.debug("Started")
    load_dotenv()

    config = load_config()

    # get from config
    if not provider:
        provider = config.get_env("PROVIDER")

    if not provider:
        # auto-detect depending on if OPENAI_API_KEY or ANTHROPIC_API_KEY is set
        if config.get_env("OPENAI_API_KEY"):
            print("Found OpenAI API key, using OpenAI provider")
            provider = "openai"
        elif config.get_env("ANTHROPIC_API_KEY"):
            print("Found Anthropic API key, using Anthropic provider")
            provider = "anthropic"
        # ask user for API key
        elif interactive:
            provider, _ = ask_for_api_key()

    # fail
    if not provider:
        raise ValueError("No API key found, couldn't auto-detect provider")

    # set up API_KEY and API_BASE, needs to be done before loading history to avoid saving API_KEY
    init_llm(provider)

    if not model:
        model = config.get_env("MODEL") or get_recommended_model()
    set_default_model(model)

    if interactive:  # pragma: no cover
        _load_readline_history()

        # for some reason it bugs out shell tests in CI
        register_tabcomplete()

    init_tools()


def init_logging(verbose):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    # set httpx logging to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)


# default history if none found
# NOTE: there are also good examples in the integration tests
history_examples = [
    "What is love?",
    "Have you heard about an open-source app called ActivityWatch?",
    "Explain 'Attention is All You Need' in the style of Andrej Karpathy.",
    "Explain how public-key cryptography works as if I'm five.",
    "Write a Python script that prints the first 100 prime numbers.",
    "Find all TODOs in the current git project",
]


def _load_readline_history() -> None:
    logger.debug("Loading history")
    # enabled by default in CPython, make it explicit
    readline.set_auto_history(True)
    # had some bugs where it grew to gigs, which should be fixed, but still good precaution
    readline.set_history_length(100)
    history_file = get_readline_history_file()
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        for line in history_examples:
            readline.add_history(line)

    atexit.register(readline.write_history_file, history_file)


def ask_for_api_key():
    """Interactively ask user for API key"""
    print("No API key set for OpenAI or Anthropic.")
    print(
        """You can get one at:
 - OpenAI: https://platform.openai.com/account/api-keys
 - Anthropic: https://console.anthropic.com/settings/keys
 """
    )
    api_key = input("Your OpenAI or Anthropic API key: ").strip()

    if api_key.startswith("sk-ant-"):
        provider = "anthropic"
        env_var = "ANTHROPIC_API_KEY"
    else:
        provider = "openai"
        env_var = "OPENAI_API_KEY"

    # TODO: test API key
    # Save to config
    set_config_value(f"env.{env_var}", api_key)
    print(f"API key saved to config at {config_path}")
    return provider, api_key
