from qade_engine import GameDefinition, GameInfo, Services

INFO = GameInfo(
    id="dodge",  # names the save folder: ~/.qade/dodge/
    title="Dodge",
    package=__name__,  # where the resources folder is
    description="Slide left and right. Don't get hit by falling blocks.",
)


def _create(services: Services):
    from .game import Dodge  # imported late: listing a game doesn't build it

    return Dodge(services)


GAME = GameDefinition(INFO, _create)


def main() -> None:
    from qade_engine import run

    run(GAME)
