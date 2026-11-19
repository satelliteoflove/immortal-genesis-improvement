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
WIZARD_LIST = 0x10                      # only true after a new game; carried() looks it up
CREATURE_LIST = 0x08F8                  # 20 bytes: which list holds what each creature carries
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

SHRINK_TIMER, SIZE = 0x0A1C, 0x0A1D      # see shrunk()
CREATURE_FLAGS = 0x0970                 # a byte for each creature; bit 6 is poisoned()

ACTION = 0x09FC                         # a byte for each creature: see action()
THING_FRAME = 0x0AC4                    # 42 bytes: the picture each thing is showing
ARMED = 0x0A17                          # the spell A casts: its thing number, FF for none
ANIM_POSITION, ANIM_ID = 0x0E68, 0x0E88 # 32 slots of running animations: see animation()
TEXT_ADDRESS = 0x0600                   # where the text in the box is in the ROM, low byte first

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


def shrunk(g):
    """True while the wizard is small from the shrinking potion and can be steered (it takes
    about 10 updates to shrink and as many to grow back, and he can't move in either)."""
    return g.byte(SIZE) == 3


def shrink_left(g):
    """Updates left of being small: about 126 when the shrinking is done, less 1 an update."""
    return g.byte(SHRINK_TIMER)


def poisoned(g):
    """True while something is taking a point of the wizard's health every 16 updates of
    walking (not in text boxes or fights): level 5's potion does, from when he has grown
    back until he drinks the water."""
    return g.byte(CREATURE_FLAGS) & 0x40 != 0


def action(g, creature=0):
    """What a creature is in the middle of having done to it, the wizard by default: 0 when
    he is free, otherwise the number of the thing happening (landing from a fall, a spell
    he has cast on himself, a blow that is killing him). The game posts a number here and
    the creature's own routine takes it up when it is next free, then clears it at the end.
    While it isn't 0 the wizard can't walk and C doesn't open the inventory."""
    return g.byte(ACTION + creature)


def armed(g):
    """The thing number of the spell a press of A will cast (a fireball scroll or a spell
    book that has been used from the inventory), or None."""
    thing = g.byte(ARMED)
    return None if thing == 0xFF else thing


def thing_frame(g, thing):
    """The picture a thing is showing. An enemy that is a thing (see "people are things
    too") steps through these as it moves, so this is how far through a move it is."""
    return g.byte(THING_FRAME + thing)


def animation(g, slot):
    """The scripted animation running in a slot: (which one, how far through), or None.

    An enemy's routine starts an animation, keeps the slot's number in a byte of its own
    (FF for none) and steps it once an update, so `slot` is that byte's value:
    animation(g, g.byte(0x0BC3)) for level 8's dragon. The position starts at 3 and goes up
    by one each update until the animation is over, whatever the ROM's speed, which makes
    it the thing to time a dodge by."""
    if slot > 31 or g.byte(ANIM_POSITION + slot) == 0xFF:
        return None
    return g.byte(ANIM_ID + slot), g.byte(ANIM_POSITION + slot)


def text_address(g):
    """While a text box is up, the ROM address its text began at (the same on both ROMs for
    the game's own messages). It tells one message from another; None when no box is up."""
    if not busy(g):
        return None
    return g.byte(TEXT_ADDRESS) | g.byte(TEXT_ADDRESS + 1) << 8


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
    which = g.byte(CREATURE_LIST)           # the wizard is creature 0
    count = g.byte(LIST_COUNT + which)
    start = g.byte(LIST_START + which)
    if count == 0xFF:
        return []
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


def press_a(g, limit=40):
    """A fresh press of A while walking: fire, or cast the armed spell. A is held until the
    game has seen it, then let go. True if it was seen.

    The game looks at the pad once an update, so the cast begins up to an update later."""
    for _ in range(12):
        if not g.byte(PRESSED) & 4:
            break
        g.step(1)
    for _ in range(limit):
        g.step(1, 'A')
        if g.byte(PRESSED) & 4:
            return True
    return False


def shots(g):
    """Fireballs left in the scroll that has been armed, 0 if none is armed. The count is
    the scroll's byte in the table at FF0B6C (which for a chest or body is its list)."""
    scroll = armed(g)
    return 0 if scroll is None else g.byte(0x0B6C + scroll)


def fire(g, buttons):
    """Throw a fireball the way `buttons` points: one update of walking that way to turn the
    wizard, then a fresh press of A. Raises unless a shot left the scroll.

    The fireball flies straight on from the wizard, and the first creature in its way is
    killed outright, so stand where the target is the nearest thing in the line."""
    before = shots(g)
    if not before:
        raise RouteError(f'fire: no scroll is armed, or it is empty (frame {g.frame})')
    if not tick(g, buttons):
        raise RouteError(f'fire: the game is busy at frame {g.frame}')
    for _ in range(3):
        press_a(g)
        for _ in range(20):
            if shots(g) < before:
                return
            g.step(1)
    raise RouteError(f'fire({buttons}): no shot was fired at {xy(g)} in room {g.room}, '
                     f'frame {g.frame}')


def ray(dx, dy, slack=5):
    """The buttons for the one of the wizard's eight directions that passes within `slack`
    of a spot dx across and dy down from him, or None if none does."""
    across, down = abs(dx), abs(dy)
    if down <= slack < across:
        return 'LEFT' if dx < 0 else 'RIGHT'
    if across <= slack < down:
        return 'UP' if dy < 0 else 'DOWN'
    if abs(across - down) <= slack < across:
        return ('UP' if dy < 0 else 'DOWN') + '+' + ('LEFT' if dx < 0 else 'RIGHT')
    return None


def hunt(g, creatures, limit=900, log=None, inside=None):
    """Kill flying creatures with fireballs: level 5's lizards, which sit still for a while,
    fly about, and at times swoop back and forth through the wizard, biting on each pass.
    A scroll or book must be armed. Returns the number of shots; raises Died or RouteError.

    Each update it looks at where each creature is from the wizard. One sitting still on
    one of his eight lines is shot from up to 110 away. One in the air is shot when it is on
    a line, 10 to 34 away, and either turning (slow) or coming at him: its swoops run along
    his lines, so the ball meets it head on. With nothing to shoot he walks onto a line
    of one that is sitting, and otherwise stands still, which keeps a swoop regular.

    inside(x, y), if given, says where he may step: hunt knows nothing of walls, doors or
    traps, so fence it in where a step could leave the room."""
    creatures = list(creatures)
    last, still = {}, dict.fromkeys(creatures, 0)
    fired = 0
    for _ in range(limit):
        alive = [n for n in creatures if creature_health(g, n)]
        if not alive:
            return fired
        if dead(g):
            raise Died(f'hunt: the wizard died in room {g.room} after {fired} shots, '
                       f'frame {g.frame}')
        wx, wy = xy(g)
        shot = walk = None
        for n in alive:
            cx, cy = creature_xy(g, n)
            vx, vy = (cx - last[n][0], cy - last[n][1]) if n in last else (9, 9)
            still[n] = still[n] + 1 if (vx, vy) == (0, 0) else 0
            last[n] = cx, cy
            dx, dy = cx - wx, cy - wy
            far = max(abs(dx), abs(dy))
            line = ray(dx, dy)
            if still[n] >= 2:
                if line and 10 <= far <= (70 if '+' in line else 110):
                    shot = n, line, far
                    break
                if still[n] >= 3 and not walk:
                    walk = _onto_a_line(dx, dy)
            elif line and 10 <= far <= 34 and (
                    max(abs(vx), abs(vy)) <= 2 or dx * vx + dy * vy < 0):
                shot = n, line, far
                break
        if shot and not _may_step(inside, wx, wy, shot[1]):
            shot = None
        if not shot:
            tick(g, walk if walk and _may_step(inside, wx, wy, walk) else '')
            continue
        n, line, far = shot
        fire(g, line)
        fired += 1
        if log:
            log(f'fired {line} at creature {n}, {far} away')
        for _ in range(far // 4 + 6):           # the slowest ball covers 4 an update
            tick(g)
            for m in alive:
                last[m] = creature_xy(g, m)
            if not creature_health(g, n):
                break
    raise RouteError(f'hunt: creatures {creatures} not all dead after {limit} updates and '
                     f'{fired} shots, room {g.room}, frame {g.frame}')


def _may_step(inside, x, y, buttons):
    """Whether inside() allows the spot one update of walking with buttons leads to."""
    if not inside:
        return True
    across = -1 if 'LEFT' in buttons else 1 if 'RIGHT' in buttons else 0
    down = -1 if 'UP' in buttons else 1 if 'DOWN' in buttons else 0
    size = 2 if across and down else 3 if across else 4
    return bool(inside(x + across * size, y + down * size))


def _onto_a_line(dx, dy, slack=3):
    """The step that brings the wizard soonest onto a line through a spot dx, dy away, or
    toward it when he is on one already but too far off."""
    across, down = abs(dx), abs(dy)
    left_right = 'LEFT' if dx < 0 else 'RIGHT'
    up_down = 'UP' if dy < 0 else 'DOWN'
    choices = [(down, up_down), (across, left_right),
               (abs(across - down), left_right if across > down else up_down)]
    need, step = min(choices)
    if need <= slack:
        return left_right if across > down else up_down
    return step


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


def bump(g, buttons, limit=400):
    """Hold buttons until a text box (or anything else that stops the game) comes up.

    For things that speak only after the wizard has pushed against them for a while, where
    walk_to would raise Stuck first: the candle in level 1's first room takes 16 updates."""
    for _ in range(limit):
        if dead(g):
            raise Died(f'bump: the wizard died at {xy(g)} in room {g.room}, frame {g.frame}')
        g.step(1, buttons)
        if busy(g):
            return
    raise RouteError(f'bump({buttons}): nothing happened in {limit} frames at {xy(g)} in '
                     f'room {g.room}, frame {g.frame}')


def walking_in(g):
    """True while the wizard is walking through a doorway by himself, deaf to the pad. The
    game's own note of where he is (FF0A4C, FF0A4D) stands still until he has control again."""
    return (g.byte(0x0A4C), g.byte(0x0A4D)) != xy(g)


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
    for _ in range(12):                 # he walks in by himself for about 4 updates
        if not walking_in(g):
            break
        tick(g)
    return g.room


# --- flying ---

FLYING = 0x0A1D                         # 1 while the wizard rides the carpet
FLY_VX, FLY_VY = 0x0A3E, 0x0A3F         # the carpet's speed across and down, signed, 5 at most
FLY_TIME = 0x1042                       # the carpet's life left: 25 new, 1 less every 16 updates
FLY_TOP = 5


def flying(g):
    """True on the carpet (the byte is 1) and under level 6's levitation spell (0E)."""
    return g.byte(FLYING) in (1, 0x0E)


def fly_speed(g):
    """The carpet's speed as (across, down), each -5 to 5, in the wizard's coordinates."""
    vx, vy = g.byte(FLY_VX), g.byte(FLY_VY)
    return (vx - 256 if vx > 127 else vx), (vy - 256 if vy > 127 else vy)


def fly_time(g):
    """What is left of the carpet's life. It only runs down while he is on it."""
    return g.byte(FLY_TIME)


WORM_STEPS = 0x1043                     # steps on foot left before the worm comes; see worm_steps


def worm_steps(g):
    """In a room with worms under the floor (level 4's two flame rooms), the updates of
    walking left before one comes up and eats the wizard. 16 on coming into the room; only
    walking counts, not standing or flying, and getting on the carpet doesn't set it back."""
    return g.byte(WORM_STEPS)


def _steer(d, v, near, top):
    """One axis of the carpet: 1 to press toward the bigger coordinate, -1 toward the
    smaller, 0 to leave it. d is how far the target is and v the speed now. A press changes
    the speed by 1 an update and the carpet never slows by itself, so the speed chosen is
    the highest that can still be braked to nothing by the time the target is reached."""
    if abs(d) <= near and v == 0:
        return 0
    if d < 0:
        return -_steer(-d, -v, near, top)
    for press in (1, 0, -1):
        speed = v + press
        if speed <= top and (speed <= 0 or speed * (speed + 1) // 2 <= d):
            return press
    return -1


def fly_to(g, x, y, near=2, rest=True, top=FLY_TOP, limit=200):
    """On the carpet, steer to (x, y) in the wizard's coordinates.

    With rest (the default) it returns 'there' once the carpet is within `near` and standing
    still. With rest=False it returns as soon as it is within `near`, whatever its speed (it
    has been braking for the point all the same, so it is slow by then).
    Also returns 'room' if the room changed, 'busy' if the game stopped, and 'down' if the
    wizard is no longer on the carpet (its life ran out). Raises Died if he dies and Stuck
    if he isn't there after `limit` updates. `top` caps the speed (5 is the carpet's own).

    The carpet keeps its speed when the pad is let go, and each direction held changes
    that axis by 1 an update, so this brakes in good time. Straight lines only, and a wall
    turns the carpet aside, so give it points clear of walls."""
    room = g.room
    for _ in range(limit):
        if dead(g):
            raise Died(f'fly_to({x}, {y}): the wizard died at {xy(g)} in room {g.room}, '
                       f'frame {g.frame}')
        if not flying(g):
            return 'down'
        (wx, wy), (vx, vy) = xy(g), fly_speed(g)
        dx, dy = x - wx, y - wy
        if abs(dx) <= near and abs(dy) <= near and (not rest or (vx, vy) == (0, 0)):
            return 'there'
        across, down = _steer(dx, vx, near, top), _steer(dy, vy, near, top)
        buttons = [('UP', '', 'DOWN')[down + 1], ('LEFT', '', 'RIGHT')[across + 1]]
        if not tick(g, '+'.join(b for b in buttons if b)):
            return 'busy'
        if g.room != room:
            return 'room'
    raise Stuck(f'fly_to({x}, {y}): not there after {limit} updates, at {xy(g)} speed '
                f'{fly_speed(g)} in room {g.room}, frame {g.frame}')


def fly(g, *points, near=2, top=FLY_TOP):
    """Fly to each (x, y) in turn, coming to rest at each. Raises RouteError unless every
    one is reached."""
    for x, y in points:
        result = fly_to(g, x, y, near=near, top=top)
        if result != 'there':
            raise RouteError(f'fly({x}, {y}): {result} at {xy(g)} in room {g.room}, '
                             f'frame {g.frame}')


def mount(g, thing, on=True, limit=60):
    """Get on the carpet (thing is its number in the things table), or off it with on=False,
    by using it from the inventory. Getting off stops the carpet dead where it is."""
    if flying(g) == on:
        raise RouteError(f'mount: the wizard is already {"on" if on else "off"} the carpet')
    use(g, thing)
    for _ in range(limit):
        if flying(g) == on and not busy(g):
            return
        g.step(1)
    raise RouteError(f'mount: the wizard did not get {"on" if on else "off"} the carpet '
                     f'(frame {g.frame})')


# --- sailing (the barrel in level 7's water) ---

SAIL_SPEED = 0x0984                     # low four bits across, high four down, each signed
SAIL_TOP = 5


def sail_speed(g):
    """The barrel's speed as (across, down), each -5 to 5. One of speed is half a step of
    the wizard's coordinates an update."""
    b = g.byte(SAIL_SPEED)
    vx, vy = b & 15, b >> 4
    return (vx - 16 if vx > 7 else vx), (vy - 16 if vy > 7 else vy)


def _sail_want(d, rest):
    """The speed wanted on one axis, d away from the target: flat out when passing through,
    or the most that can still be braked to nothing in d when coming to rest."""
    if abs(d) <= 1:
        return 0
    v = SAIL_TOP
    if rest:
        v = 0
        while v < SAIL_TOP and (v + 1) * (v + 2) / 4 <= abs(d):
            v += 1
    return v if d > 0 else -v


def sail_to(g, x, y, near=4, rest=False, limit=300, stop=None):
    """On the barrel, steer to (x, y) in the wizard's coordinates.

    Returns 'there' when within `near` of both (and standing still, with rest=True), 'busy'
    if the game stopped, 'room' if the room changed, 'stop' if stop(g) became true. Raises
    Died if he dies and Stuck if he isn't there after `limit` updates.

    The barrel keeps its speed when the pad is let go; each direction held changes that axis
    by 1 an update, 5 at most, and 5 is 2.5 of his coordinates an update. Walls throw it
    back at the speed it came. With rest it brakes on both axes to stop on the point.
    Without, the axis with farther to go runs flat out through the point and the other is
    brought to the point's line and held there (both run flat out when they have about as
    far to go, an even diagonal). Give it points clear of walls."""
    room = g.room
    for _ in range(limit):
        if dead(g):
            raise Died(f'sail_to({x}, {y}): the wizard died at {xy(g)} in room {g.room}, '
                       f'frame {g.frame}')
        if stop and stop(g):
            return 'stop'
        (wx, wy), (vx, vy) = xy(g), sail_speed(g)
        if abs(x - wx) <= near and abs(y - wy) <= near and (not rest or (vx, vy) == (0, 0)):
            return 'there'
        dx, dy = x - wx, y - wy
        tx = _sail_want(dx, rest or abs(dx) < abs(dy) - 8)
        ty = _sail_want(dy, rest or abs(dy) < abs(dx) - 8)
        buttons = [('UP' if vy > ty else 'DOWN' if vy < ty else ''),
                   ('LEFT' if vx > tx else 'RIGHT' if vx < tx else '')]
        if not tick(g, '+'.join(b for b in buttons if b)):
            return 'busy'
        if g.room != room:
            return 'room'
    raise Stuck(f'sail_to({x}, {y}): not there after {limit} updates, at {xy(g)} speed '
                f'{sail_speed(g)} in room {g.room}, frame {g.frame}')


def sail(g, *points, near=4, rest=False):
    """Steer the barrel through each (x, y) in turn. Raises RouteError unless every one is
    reached."""
    for x, y in points:
        result = sail_to(g, x, y, near=near, rest=rest)
        if result != 'there':
            raise RouteError(f'sail({x}, {y}): {result} at {xy(g)} in room {g.room}, '
                             f'frame {g.frame}')


# --- the inventory ---

def ladder(g, buttons, room=None, limit=1500):
    """Climb a ladder, up or down: hold buttons (the direction that walks onto it) until the
    room changes, then wait until the wizard has climbed off at the other end and can be
    steered. Returns the new room.

    The climb starts the moment he touches the ladder and takes about 38 updates in the old
    room and up to 45 in the new one, deaf to the pad, with his x and y standing still; then
    he steps off by himself. The room's loading in the middle can take over 40 frames with
    no update, which tick() and through_door() take for the game going busy."""
    before = g.room
    start = g.frame
    while g.room == before:
        if dead(g):
            raise Died(f'ladder({buttons}): the wizard died at {xy(g)} in room {g.room}, '
                       f'frame {g.frame}')
        if g.frame - start > limit:
            raise RouteError(f'ladder({buttons}): still in room {before} at {xy(g)}, '
                             f'frame {g.frame}')
        g.step(1, buttons)
    if room is not None and g.room != room:
        raise RouteError(f'ladder: in room {g.room}, expected {room}')
    arrived = xy(g)
    start = g.frame
    while xy(g) == arrived or walking_in(g):
        if g.frame - start > limit:
            raise RouteError(f'ladder: the wizard never stepped off it in room {g.room}, '
                             f'at {xy(g)}, frame {g.frame}')
        g.step(1)
    return g.room


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

# How long the fight's moves last, by how tired the fighter is (0 to 15), in the fight's own
# time (about 4 to a pass of its loop, 6 frames): the wizard's jab before its last 6, and the
# enemy's recovery after a swing. Copied out of the tables at 011C12 and 011C62.
JAB_TIME = [8, 8, 8, 8, 9, 9, 10, 10, 10, 11, 11, 12, 13, 14, 15, 16]
RECOVERY_TIME = [4, 5, 6, 7, 8, 9, 10, 10, 12, 14, 16, 18, 20, 22, 24, 26]
ENEMY_TIRED, WIZARD_TIRED = 0x10A9, 0x10AA      # 0 to 15, up 1 for each swing finished
ENEMY_SLOW, WIZARD_SLOW = 0x10AB, 0x10AC        # what the fighter starts with, added to tired
ENEMY_TIMER = 0x10B1                            # what is left of the enemy's move


def _jab_is_safe(g):
    """True when a jab begun now will land before the enemy can begin its next swing.

    The enemy has just swung (move 6 or 10) or is recovering from it (7 or 11). Its recovery
    is as long as it is tired, and it swings again the pass after. A jab takes the wizard's
    JAB_TIME and 6 more to land, each rounded up to whole passes, and a pass to be seen."""
    enemy = g.byte(ENEMY_MOVE)
    tired = min(15, g.byte(ENEMY_TIRED) + g.byte(ENEMY_SLOW))
    if enemy in (6, 10):
        left = 4 + RECOVERY_TIME[tired]
    elif enemy in (7, 11):
        left = g.byte(ENEMY_TIMER)
    else:
        return False
    mine = min(15, g.byte(WIZARD_TIRED) + g.byte(WIZARD_SLOW))
    return g.byte(WIZARD_MOVE) == 0 and left >= JAB_TIME[mine] + 11


def fight(g, limit=20000, counter=False, patient=False):
    """Win the fight that has begun. Returns the health left; raises Died if the wizard loses.

    Reads both fighters' moves every frame. The enemy's two swings are each dodged with C
    and the direction away from them; whenever the enemy isn't swinging, the wizard slashes.
    Call it once fighting(g) is true (the opening words, if any, are read first).

    counter=True is for an enemy that swings faster than the wizard slashes (the trolls of
    level 5): the wizard stands still while the enemy is free, dodges its swing, and slashes
    only while it is recovering from a swing or reeling from a hit.

    patient=True is for an enemy that beats both of those (level 3's goblin guard and
    trolls, 12 and 15 health): the wizard only dodges until the enemy has tired itself out
    with swings, then answers each dodged swing with one jab (A), and only when the game's
    own timers say the jab will land first. Slow, about 150 frames a point of the enemy's
    health, but the enemy never lands a blow."""
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
        elif patient:
            buttons = 'A' if _jab_is_safe(g) else ''
        elif counter and enemy not in (1, 6, 7, 10, 11):
            buttons = ''                        # wait for its swing; a slash now would lose
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


def creature_xy(g, creature):
    """Where creature n is, in the room's coordinates (0 is the wizard)."""
    return g.byte(WIZARD_X + creature), g.byte(WIZARD_Y + creature)


def creature_health(g, creature):
    """Creature n's health, 0 when it is dead (0 is the wizard). Out of a fight only: the
    fight keeps its own count at FF10A7 and FF10A8."""
    return g.byte(HEALTH + creature) >> 4


def meet(g, creature, limit=300):
    """Walk at creature n, following it, until it starts a fight or the game stops for a
    text box. Returns 'fight' or 'spoke'. Use it when walk_to(..., stop=fighting) could
    arrive before the creature has reacted, or where it has to be pushed against to speak."""
    for _ in range(limit):
        if fighting(g):
            return 'fight'
        if busy(g):
            return 'spoke'
        if dead(g):
            raise Died(f'meet({creature}): the wizard died at {xy(g)} in room {g.room}, '
                       f'frame {g.frame}')
        (cx, cy), (wx, wy) = creature_xy(g, creature), xy(g)
        tick(g, _toward(cx - wx, cy - wy, 1))
    raise RouteError(f'meet({creature}): it neither fought nor spoke in {limit} updates; '
                     f'wizard at {xy(g)}, it at {creature_xy(g, creature)}, room {g.room}')


def attack(g, creature, limit=300, **how):
    """Walk at creature n until it fights, reading anything said on the way, and win the
    fight. Returns the health left. `how` goes to fight(): attack(g, 1, patient=True)."""
    for _ in range(6):
        if meet(g, creature, limit) == 'fight':
            return fight(g, **how)
        read(g, quiet=0)
        if fighting(g):
            return fight(g, **how)
    raise RouteError(f'attack({creature}): it kept talking and never fought (frame {g.frame})')


def rest(g, limit=900):
    """Sleep on a straw bed the wizard is standing on. He only has to stand still: after
    about 60 updates the dream comes up as text, and by the time he is up again he has 4
    more health, 15 at most. Once a level; a second wait on the bed brings nothing. Returns
    the health gained, once he is back on his feet: he lies there and gets up for about 18
    updates after the text, deaf to the pad (his pose at FF0920 goes 1C, 7, then 4 down to
    0), and the last of the health comes in that time. Walk onto the bed's thing first with walk_to(g, x, y, near=1)."""
    before = health(g)
    try:
        wait_busy(g, limit=limit)
    except TimeoutError:
        raise RouteError(f'rest: no dream came at {xy(g)} in room {g.room}, frame {g.frame}')
    read(g, quiet=0)
    lying = False
    for _ in range(80):
        pose = g.byte(HEALTH + 0x14)            # the wizard's pose, FF0920
        lying = lying or pose == 0x1C
        if lying and pose == 0:
            return health(g) - before
        tick(g)
    raise RouteError(f'rest: the wizard did not get up (frame {g.frame})')


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


ENDING_TEXT = range(0x36D2, 0x3A34)     # the game's closing story: two tellings, five messages


def ending(g):
    """True while the story that ends the game is in the text box. It comes when level 8 is
    won, and nowhere else."""
    return text_address(g) in ENDING_TEXT


def end_of_game(g, limit=6000):
    """Level 8's end_of_level(): wait for the closing story, let it play through, and return
    None, since the game makes no certificate. Nothing is pressed.

    The Genesis game has no screen that says the game was won. The story's pages turn by
    themselves, and after the last one the wizard's routine runs on into the code for a
    death on the last level, which raises the Game Over flag (FF1072): the original then
    shows "Game Over" and asks to play again, as after a death. So the flag going up after
    the story has been seen is where a won game ends, and this returns there, before that
    box is drawn. The level-over flag at FF106F is never set on level 8."""
    start = g.frame
    seen = False
    while not (seen and game_over(g)):
        if g.frame - start > limit:
            raise RouteError(f'end_of_game: {"the story did not finish" if seen else "no closing story"} '
                             f'after {limit} frames (frame {g.frame}, room {g.room})')
        if not seen and (dead(g) or game_over(g)):
            raise Died(f'end_of_game: the wizard died (frame {g.frame})')
        seen = seen or ending(g)
        g.step(1)
    return None


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
