# What's left before v1.0

A review on 2026-11-20 of what's been done and what a first release on RHDN still needs.
`TODO.md` remains the working list; this sorts its open items, and a few that aren't on it,
by whether they should hold up the release.

## Where things stand

On `main`: faster object graphics, background scrolling, sprite masking and camera steps; the
torch flame and stray-pixel fixes; the music-restart fix; fights held to the original's pace;
held-button text speed; battery saves with a level picker; "Try this level again?" at Game
Over; the 1 MB ROM and the BPS patch maker.

On `fix/deaths-ladders-bugs`, not merged (12 commits): the 3-second "Prepare to continue...",
any button ending a message's pauses again, the level 5 soft-lock fix, the retry test and the
dead-code survey.

All of it has been checked by script: both whole-game runs, the save check, typing speed and
the retry test. Almost none of it has been seen or heard by a person playing.

## Should hold up the release

1. **Merge `fix/deaths-ladders-bugs`** into `main`. Needs Chris's go-ahead.
2. **A full play-through by hand** on an ordinary emulator, start to finish, with saves used
   for real. The scripts can't judge feel, sound or looks, and several changes are marked as
   never seen or heard:
   - a level's end with "Game saved.", the level picker, and Game Over's "Try this level
     again?" (`TODO.md`, Fairness);
   - the music-restart fix ("Not yet listened to");
   - sampled sounds on levels 3, 4 and 7 against the original;
   - the death pause and message pauses, for feel.
3. **50 Hz.** The dump is "USA, Europe", so some players will run it as a PAL machine. Every
   test so far ran at 60 Hz. Play at least a level or two and a fight at 50 Hz on both ROMs
   and check nothing runs faster than the original or breaks. The patch's own waits count
   frames, so the death pause is 3.6 seconds there; that's fine, but worth knowing.
4. **Patchers.** Apply the BPS with Flips and at least one other common patcher (the
   browser-based ones people use, such as RomPatcher.js), and check the result's hash
   against our build.
5. **Battery saves on other emulators.** Only the BlastEm fork has run the saves. Try the
   ones players use most: Genesis Plus GX (RetroArch), standalone BlastEm, Kega Fusion, Ares,
   and PicoDrive if anyone will run it there. The header declares battery RAM on odd bytes at
   `200001`, the usual layout, but emulators differ on how they read it.
6. **Release notes and package.** RHDN wants a readme in the archive and the ROM's details
   on the page. Needed:
   - the readme: what the patch changes, what it doesn't, the required ROM (name, CRC32,
     SHA-1), how to apply it, the save and retry behavior, credits, version;
   - a name for the BPS file;
   - screenshots for the page (title, the save picker, play);
   - the RHDN page text.
7. **Update `README.md`.** It still says the harness runs PicoDrive, and its list of what the
   patch does stops at saves and Game Over.

## Worth doing first, if time allows

8. **Real hardware.** On a flash cart (an Everdrive or similar): boot, saves to its battery
   RAM, a level or two. Two open questions only hardware answers well: whether drawing that
   finishes after vertical blank shows as tearing (16% of plain ticks, 52% of camera steps
   finish late), and how the sampled sounds sound.
9. **Retry spots the test never reached.** By Chris's measure, the only bug that matters
   here is a soft-lock. The test covered every room the routes pass through; it didn't try
   the retry spots of rooms they skip (level 1's room 5, several on levels 3, 4 and 7). Each
   could be checked by putting the wizard in that room, dying, and walking around as the
   flood search did. That would close the question of other soft-locks like level 5's.
10. **The retry test's remaining failures.** Thirteen haven't been looked at. Those looked
    at so far were the test's own, so they're unlikely to hide a soft-lock, but level 7's
    two timeouts and level 5's "did not get up" are the least explained.
11. **A version mark in the game**, so a player or a bug report can tell which version is
    running: for example "v1.0" on the title screen or under the "Continue a saved game?"
    prompt. Not done; Chris's call.

## Can wait for a later version

- Controls said to feel less responsive than the NES version: measure button-to-screen.
- The last 2% of slow ticks, mostly deliberate waits in animations on levels 2, 6 and 7.
- Whether the 13 never-run kind handlers belong to things placed on some level.
- Tracing how a room reaches the screen.
- Offering the BlastEm fork fixes upstream. Separate from the release.
- Typing a certificate in by hand, digit by digit, beyond the one already tried.
