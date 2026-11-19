"""Helpers every level's route uses. See docs/playthrough.md.

Look here before writing a helper, and put anything another level could use here.

Every helper decides from RAM, never from a frame count, so the same call works on the
original ROM and the patched one. The pad is only looked at when the game gets round to it:
once an update (5 frames, more on the original) while walking, every few frames in a text
box. So a press is held until RAM shows the game has seen it, not for a set time.

    from common import *
    go(g, 133, 92)                  # walk there
    read(g, 'yyy')                  # yes to the next three questions, and through the text
    use(g, 6)                       # open the inventory and use thing 6
    fight(g)                        # win the fight that has just started
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import play

ROOT = play.ROOT

# --- addresses (the notebook's table says what each one is) ---

WIZARD_X, WIZARD_Y = 0x08BC, 0x08D0     # tables of 20 bytes, the wizard first
HEALTH = 0x090C                         # high four bits
COUNT, DEADLINE = 0x9624, 0x12E6        # vertical blanks, and when the next update may begin
THING_X, THING_Y = 0x0A70, 0x0A9A       # 42 bytes each, like the things table at 0AEE
THING_KIND, THING_PLACE = 0x0AEE, 0x0B42
LIST_AREA, LIST_START, LIST_COUNT = 0x0C54, 0x0D54, 0x0DD4  # who holds what; see carried()
WIZARD_LIST = 0x10
PRESSED = 0x0C4E                        # bit 1: the game has seen C down; bit 2: A down
LAST_LETTER, WAIT_LENGTH = 0x0C52, 0x0C4C
QUESTION = 0x0C4D                       # 1 with NO lit, 2 with YES lit
INV_SLOT, INV_COUNT, INV_PAGE, INV_SLOTS = 0x1083, 0x1078, 0x1087, 0x107C
OPPONENT = 0x10AE                       # not zero during a fight
ENEMY_HEALTH, FIGHT_HEALTH = 0x10A7, 0x10A8
ENEMY_POSE, WIZARD_POSE = 0x10A5, 0x10A6
WIZARD_MOVE, ENEMY_MOVE = 0x10B0, 0x10B2
LEVEL_OVER, GAME_OVER, RETRIES = 0x106F, 0x1072, 0x109A
CERTIFICATE = 0x108C

CARRIED = 0x40                          # a thing's place when the wizard has it


class RouteError(Exception):
    """A route found the game somewhere it didn't expect."""


class Died(RouteError):
    """The wizard died."""


def fail(g, level, message):
    """Stop a route: write a picture to scratch/route/levelN/ and raise RouteError."""
    path = os.path.join(ROOT, 'scratch', 'route', f'level{level}', f'fail-{g.frame}.png')
    try:
        g.shot(path)
    except Exception:
        path = 'no picture'
    raise RouteError(f'level {level}, frame {g.frame}, room {g.room}, at {xy(g)}, '
                     f'health {health(g)}: {message} (picture: {path})')


# --- reading the game's state ---

def xy(g):
    return g.byte(WIZARD_X), g.byte(WIZARD_Y)


def health(g):
    return g.byte(HEALTH) >> 4


def busy(g):
    """True when the main loop has stopped going round: a text box, the inventory, a fight,
    a death. It takes about 12 frames to show after the thing begins."""
    return g.long(COUNT) - g.long(DEADLINE) > 12


def fighting(g):
    return g.byte(OPPONENT) != 0


def dead(g):
    """True from the moment the wizard's health reaches 0 until he is put back."""
    return health(g) == 0


def tick(g, buttons='', limit=40):
    """Run one update of the game with buttons held. False if none came (the game is busy)."""
    deadline = g.long(DEADLINE)
    for _ in range(limit):
        g.step(1, buttons)
        if g.long(DEADLINE) != deadline:
            return True
    return False


def ticks(g, count, buttons=''):
    """Run count updates. Stops early, with False, if the game goes busy."""
    for _ in range(count):
        if not tick(g, buttons):
            return False
    return True


def wait_busy(g, buttons='', limit=600):
    """Step until the game is busy (a text box has come up, a fight has begun)."""
    g.until(busy, buttons, limit=limit)


# --- things ---

def place(g, thing):
    """Where a thing is: CARRIED (40) with the wizard, 40+n with creature n, 80+n on the
    floor of room n, anything lower inside the thing of that number (a body, a chest)."""
    return g.byte(THING_PLACE + thing)


def has(g, thing):
    return g.byte(THING_KIND + thing) != 0xFF and place(g, thing) == CARRIED


def search(g, answers, *things, limit=600):
    """Answer the questions of a body or chest the wizard has just walked up to, and check
    that each thing number given is now carried.

    answers is as for read(): 'y' to search, then 'y' or 'n' for each thing offered, in the
    order the container lists them. Call it right after the walk that touches the container
    (walk_to returns 'busy' there, or 'there' a moment before the box comes up)."""
    wait_busy(g, limit=limit)
    read(g, answers, quiet=0)
    missing = [thing for thing in things if not has(g, thing)]
    if missing:
        raise RouteError(f'search: things {missing} were not taken; carrying {carried(g)} '
                         f'(frame {g.frame})')


def thing_xy(g, thing):
    return g.byte(THING_X + thing), g.byte(THING_Y + thing)


def carried(g):
    """The numbers of the things the wizard carries, in the order the inventory shows them."""
    count = g.byte(LIST_COUNT + WIZARD_LIST)
    start = g.byte(LIST_START + WIZARD_LIST)
    return list(g.bytes(LIST_AREA + start, count))


# --- text boxes ---

def _c_seen(g):
    return g.byte(PRESSED) & 2


def _press_c(g, held='', limit=40):
    """Press C, with held, until the game has seen it. Then let go of C. True if it was seen.

    C must be up, and seen to be up, first: the game only acts on a fresh press."""
    for _ in range(12):
        if not _c_seen(g):
            break
        g.step(1, held)
    for _ in range(limit):
        g.step(1, held + '+C' if held else 'C')
        if _c_seen(g) or not busy(g):
            g.step(1, held)
            return True
    g.step(1, held)
    return False


def read(g, answers='', limit=6000, quiet=24):
    """Get through the text on screen until the game is running again.

    answers is a letter for each question that will come, in order: 'y' or 'n'. Pages and
    the wait for a button at the end are dealt with. Returns when the main loop has gone
    round for `quiet` frames with no new box (0 to return the moment it restarts).

    Raises RouteError if a question comes that there's no answer for, if answers are left
    over, or if a fight starts (call fight() for that)."""
    answers = list(answers.lower())
    start = g.frame
    calm = 0
    pressed_at = None           # (frame, what the box looked like) at the last press of C
    while True:
        if g.frame - start > limit:
            raise RouteError(f'read: still in a text box after {limit} frames at frame '
                             f'{g.frame}; a question with no answer given?')
        if fighting(g) and not answers:
            return
        if not busy(g):
            if answers:
                # a question hasn't come yet; keep the game going with nothing pressed
                calm += 1
                if calm > 600:
                    raise RouteError(f'read: no question came for {"".join(answers)!r}')
                g.step(1)
                continue
            calm += 1
            if calm > quiet:
                return
            g.step(1)
            continue
        calm = 0
        if answers:
            want, other = ('RIGHT', 'LEFT') if answers[0] == 'y' else ('LEFT', 'RIGHT')
            lit = 2 if answers[0] == 'y' else 1
            if _question_follows(g, other, 3 - lit) and _question_follows(g, want, lit):
                if not _press_c(g, want):
                    raise RouteError(f'read: the question took no answer at frame {g.frame}')
                answers.pop(0)
                pressed_at = None
                continue
            # no question yet: carry on through the text in front of it
        letter, wait = g.byte(LAST_LETTER), g.byte(WAIT_LENGTH)
        at_end = letter in (0x00, 0x40)
        at_pause = wait in (0x8C, 0x28)
        look = (letter, wait, g.var(0x94A), g.var(0x300), g.var(0x301))
        if at_end or at_pause:
            # one press, then leave it alone until the box changes or 24 frames pass: a
            # second press arriving as the game restarts would open the inventory
            if pressed_at and pressed_at[1] == look and g.frame - pressed_at[0] < 24:
                g.step(1)
                continue
            _press_c(g, limit=12)
            pressed_at = (g.frame, look)
        else:
            g.step(1, 'B')      # a held button hurries the typing; B does nothing else


def _question_follows(g, direction, lit, limit=10):
    """Hold a direction and see whether the question's lit answer becomes `lit`. Only a
    question that is really on screen moves it."""
    for _ in range(limit):
        if g.byte(QUESTION) == lit:
            return True
        if not busy(g):
            return False
        g.step(1, direction + '+B')
    return g.byte(QUESTION) == lit


# --- walking ---

class Stuck(RouteError):
    pass


def _toward(dx, dy, near):
    buttons = []
    if dy < -near:
        buttons.append('UP')
    elif dy > near:
        buttons.append('DOWN')
    if dx < -near:
        buttons.append('LEFT')
    elif dx > near:
        buttons.append('RIGHT')
    return '+'.join(buttons)


def walk_to(g, x, y, near=2, limit=300, stop=None):
    """Walk toward (x, y) in the wizard's coordinates, one update at a time.

    Returns 'there' when within `near` of both, 'busy' if a text box or fight got in the
    way, 'room' if the room changed, or 'stop' if stop(g) became true. Raises Stuck if the
    wizard doesn't move for 6 updates or `limit` updates pass. Straight lines only: a wall
    in the way makes the wizard slide along it or stop, so give it points to walk between.

    A step is 3 across, 4 up or down, or 2 and 2 on a diagonal."""
    room = g.room
    still = 0
    for _ in range(limit):
        wx, wy = xy(g)
        buttons = _toward(x - wx, y - wy, near)
        if not buttons:
            return 'there'
        if stop and stop(g):
            return 'stop'
        if dead(g):
            raise Died(f'walk_to({x}, {y}): the wizard died at {xy(g)} in room {g.room}, '
                       f'frame {g.frame}')
        if not tick(g, buttons):
            return 'busy'
        if g.room != room:
            return 'room'
        still = still + 1 if xy(g) == (wx, wy) else 0
        if still >= 6:
            raise Stuck(f'walk_to({x}, {y}): stuck at {xy(g)} in room {g.room}, '
                        f'frame {g.frame}')
    raise Stuck(f'walk_to({x}, {y}): not there after {limit} updates, at {xy(g)} '
                f'in room {g.room}, frame {g.frame}')


def go(g, *points, near=2):
    """Walk through each (x, y) in turn. Raises RouteError unless every one is reached."""
    for x, y in points:
        result = walk_to(g, x, y, near=near)
        if result != 'there':
            raise RouteError(f'go({x}, {y}): {result} at {xy(g)} in room {g.room}, '
                             f'frame {g.frame}')


def through_door(g, buttons, room=None, limit=80):
    """Hold buttons until the room number changes, then let the wizard come to rest.

    Stand in front of the door first and give the direction that walks into it. `room` is
    the room expected on the other side. Returns the new room."""
    before = g.room
    for _ in range(limit):
        if not tick(g, buttons):
            raise RouteError(f'through_door: the game went busy at {xy(g)} in room '
                             f'{g.room}, frame {g.frame}')
        if g.room != before:
            break
    else:
        raise RouteError(f'through_door({buttons}): still in room {before} at {xy(g)}, '
                         f'frame {g.frame}')
    if room is not None and g.room != room:
        raise RouteError(f'through_door: in room {g.room}, expected {room}')
    tick(g)
    return g.room


# --- the inventory ---

SLOT_DIRECTION = ['', 'LEFT', 'RIGHT', 'DOWN+LEFT', 'DOWN', 'DOWN+RIGHT']


def _point_at(g, slot, limit=40):
    """In the inventory, hold the direction for a slot until the game's cursor is on it."""
    direction = SLOT_DIRECTION[slot]
    for _ in range(limit):
        g.step(1, direction)
        if g.byte(INV_SLOT) == slot:
            return direction
    raise RouteError(f'inventory: the cursor never reached slot {slot} (frame {g.frame})')


def use(g, thing):
    """Open the inventory (C), point at a thing by its number in the things table, use it (A).

    The game must be running, not busy. Returns once the game has taken the press; what the
    thing does then (a text box, most often) is the caller's: call read(g) and check RAM."""
    if busy(g):
        raise RouteError(f'use({thing}): the game is busy at frame {g.frame}')
    things = carried(g)
    if thing not in things:
        raise RouteError(f'use({thing}): not carried; the wizard has {things}')
    index = things.index(thing)
    for _ in range(12):                         # C has to be seen up before it counts
        if not _c_seen(g):
            break
        g.step(1)
    for _ in range(60):
        g.step(1, 'C')
        if busy(g):
            break
    else:
        raise RouteError(f'use({thing}): the inventory did not open (frame {g.frame})')
    # The cursor follows the pad only while the inventory is really up, so move it off the
    # slot wanted and back on: that proves the screen is there and listening.
    page = 0
    while True:
        slot = index - page if index - page < 5 else 5      # slot 5 is "more"
        _point_at(g, 1 if slot != 1 else 0)
        direction = _point_at(g, slot)
        for _ in range(12):
            if not g.byte(PRESSED) & 4:
                break
            g.step(1, direction)
        for _ in range(40):
            g.step(1, direction + '+A' if direction else 'A')
            if g.byte(PRESSED) & 4:
                break
        else:
            raise RouteError(f'use({thing}): A was not taken (frame {g.frame})')
        g.step(2, direction)
        if slot != 5:
            return
        page += 5


# --- fights ---

def fight(g, limit=20000):
    """Win the fight that has begun. Returns the health left; raises Died if the wizard loses.

    Reads both fighters' moves every frame. The enemy's two swings are each dodged with C
    and the direction away from them; whenever the enemy isn't swinging, the wizard slashes.
    Call it once fighting(g) is true (the opening words, if any, are read first)."""
    start = g.frame
    while not fighting(g):
        if g.frame - start > 600:
            raise RouteError(f'fight: no fight began (frame {g.frame})')
        g.step(1)
    side = 'LEFT'
    while fighting(g):
        if g.frame - start > limit:
            raise RouteError(f'fight: not over after {limit} frames')
        mine, theirs = g.byte(FIGHT_HEALTH), g.byte(ENEMY_HEALTH)
        if mine == 0 or theirs == 0:
            g.step(1)                           # the ending plays by itself
            continue
        enemy = g.byte(ENEMY_MOVE)
        if enemy in (4, 5):
            buttons = 'C+LEFT'                  # dodge the swing from one side
        elif enemy in (8, 9):
            buttons = 'C+RIGHT'                 # and from the other
        else:
            pose = g.byte(WIZARD_POSE)
            if pose == 0:
                side = 'LEFT'                   # already wound up on that side
            elif pose == 2:
                side = 'RIGHT'
            buttons = side
        g.step(1, buttons)
    if g.byte(FIGHT_HEALTH) == 0 or health(g) == 0:
        raise Died(f'fight: the wizard lost (frame {g.frame})')
    return health(g)


# --- deaths and the end of the level ---

def retries(g):
    """Retries left on this level: 2 at its start, one fewer after each death."""
    return g.byte(RETRIES)


def revive(g, limit=3000):
    """After a death, wait until the wizard is back on his feet at the room's entrance and
    the game is running. Returns the retries left; raises Died if that was the last life.

    Nothing needs pressing. From health 0 to walking again is about 6 seconds."""
    start = g.frame
    while dead(g) or busy(g):
        if game_over(g):
            raise Died(f'the retries ran out (frame {g.frame})')
        if g.frame - start > limit:
            raise RouteError(f'revive: the wizard did not come back (frame {g.frame})')
        g.step(1)
    return retries(g)


def game_over(g):
    return g.byte(GAME_OVER) != 0


def level_over(g):
    return g.byte(LEVEL_OVER) != 0


def certificate(g):
    """The 13 letters of the certificate the game last made."""
    return ''.join('%x' % (b & 15) for b in g.bytes(CERTIFICATE, 13))


def level_ended(g):
    """True at the "End of level!" screen. The game has made the next level's certificate
    by then, so its level digit is one more than the level being played."""
    return busy(g) and g.byte(CERTIFICATE + 5) == g.level + 1


def end_of_level(g, limit=3000):
    """Wait for the "End of level!" screen to be up and waiting for a button, and return the
    certificate on it. A route's play() ends with this. Not for level 8, which has no
    certificate. Nothing is pressed, so the level counter still shows the level just played.

    The flag at FF106F is only set for an instant, so don't wait on it."""
    start = g.frame
    while not (level_ended(g) and g.byte(LAST_LETTER) in (0x00, 0x40)):
        if g.frame - start > limit:
            raise RouteError(f'end_of_level: no "End of level!" screen after {limit} frames '
                             f'(frame {g.frame}, room {g.room})')
        if dead(g):
            raise Died(f'end_of_level: the wizard died (frame {g.frame})')
        g.step(1)
    return certificate(g)


# --- running a level's file by itself ---

def main(level, play_level, start_certificate=None):
    """What `tools/harness/route/levelN.py [--original] [--delay N] [--quiet]` runs.

    Starts the game on the level (a new game when there's no certificate), waits --delay
    frames, calls play_level(g, log) and prints the certificate it returns. Exits 1 with the
    message, and a picture in scratch/route/levelN/, if the route raises."""
    import argparse
    import time
    parser = argparse.ArgumentParser(description=f'Play level {level} from start to finish.')
    parser.add_argument('--original', action='store_true', help='the original ROM, not the patched')
    parser.add_argument('--delay', type=int, default=0, help='frames to wait before the first press')
    parser.add_argument('--quiet', action='store_true', help="don't print the route's log")
    args = parser.parse_args()
    name = 'original' if args.original else 'patched'
    began = time.time()
    with play.Game(play.original() if args.original else play.PATCHED) as g:
        if start_certificate:
            g.start_level(start_certificate)
        else:
            g.new_game()
        g.step(args.delay)
        first = g.frame

        def log(*words):
            if not args.quiet:
                print(f'  [{g.frame - first:6d}] room {g.room:2d} {xy(g)} health {health(g):2d}:',
                      *words, flush=True)
        try:
            result = play_level(g, log)
        except Exception as error:
            path = os.path.join(ROOT, 'scratch', 'route', f'level{level}',
                                f'fail-{name}-delay{args.delay}.png')
            try:
                g.shot(path)
            except Exception:
                path = 'no picture'
            print(f'level {level} {name} delay {args.delay}: FAILED {g.frame - first} frames in, '
                  f'room {g.room}, {xy(g)}: {type(error).__name__}: {error} (picture: {path})')
            sys.exit(1)
        print(f'level {level} {name} delay {args.delay}: passed, certificate {result}, '
              f'{g.frame - first} frames, health {health(g)}, retries left {retries(g)}, '
              f'{time.time() - began:.0f} s')
