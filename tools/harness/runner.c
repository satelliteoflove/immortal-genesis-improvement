/* Headless libretro frontend for testing the ROM in PicoDrive.
 *
 *   runner CORE ROM [-n frames] [-s frame:file.png]... [-i script] [-4] [-r] [-q]
 *
 * -4   plug the EA 4-Way Play into port 1 (otherwise two 3-button pads)
 * -t   plug the Sega Team Player into port 1
 * -v   write every second frame, raw RGB, to a file (for ffmpeg)
 * -r   netplay check: every frame, save state, run, load, run again, and
 *      compare the two pictures. RetroArch's rollback needs these to match.
 * -c   write the CRC of the saved state before every frame to a file, one a
 *      line. Two runs that ought to be the same game can be compared with it.
 *      Two CRCs: the whole state, and the state without the things
 *      PicoDrive doesn't put back exactly after a load and the game can't
 *      see (the FM chip's insides, a count of how often the 32X's video
 *      status was read, and its note of how far each SH-2 has been run).
 *      The second is the one that has to match.
 * -R   rewind as netplay does, n frames deep: every third frame, save state,
 *      run n frames with the wrong buttons held, load, and carry on. With -c,
 *      the file should come out the same as a run without -R.
 * -S   frame:file  write the saved state before that frame to a file
 * -l   file  load a saved state before the first frame
 * -L   file  write "frame picture-crc pad1" for every frame
 * -M   file  append the 68000's 64K of RAM after every frame, in the 68000's
 *      own byte order (big: 64K a frame)
 * -m   file  the same RAM, once, at the end
 * -P   from:to:file  with the profiling core (build_trace_core.sh), write
 *      "address executions cycles" for each 68000 instruction run in those frames
 * -T   tick,lo,hi:file  with the profiling core, write for each frame
 *      "frame ticks idle": how many times the instruction at hex address tick
 *      ran, and the cycles spent in the hex range lo..hi (the wait loop)
 * -W   addr:file  write the 32-bit value at hex RAM address addr after every
 *      frame, one a line. Works on any core, unlike -T.
 * -p   frame:addr=value  before that frame, set the byte at hex 68000 address
 *      addr (in 0xff0000-0xffffff) to hex value. Can be repeated.
 * -i   input script, one event per line: "frame port BUTTONS", e.g.
 *      "120 0 B+RIGHT". The buttons are held until the port's next line.
 *      Buttons: UP DOWN LEFT RIGHT A B C START, or #n for libretro button n.
 *      "-" releases everything.
 * -b   a,b,c  libretro button numbers for the pad's A, B and C, for cores that
 *      lay the pad out differently from PicoDrive (give it before -i)
 */
#include <dlfcn.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include "libretro.h"

static struct {
    void *h;
    void (*init)(void);
    void (*deinit)(void);
    void (*run)(void);
    bool (*load_game)(const struct retro_game_info *);
    void (*set_env)(retro_environment_t);
    void (*set_video)(retro_video_refresh_t);
    void (*set_audio)(retro_audio_sample_t);
    void (*set_audio_batch)(retro_audio_sample_batch_t);
    void (*set_poll)(retro_input_poll_t);
    void (*set_state)(retro_input_state_t);
    void (*set_port)(unsigned, unsigned);
    size_t (*ser_size)(void);
    bool (*ser)(void *, size_t);
    bool (*unser)(const void *, size_t);
} core;

static enum retro_pixel_format fmt = RETRO_PIXEL_FORMAT_0RGB1555;
static uint8_t *frame;              /* RGB888 */
static unsigned fw, fh;
static uint16_t pads[4];            /* bit per RETRO_DEVICE_ID_JOYPAD_* */
static int quiet;
static long audio_frames;
static FILE *audio_out, *video_out;

static void logcb(enum retro_log_level lvl, const char *f, ...)
{
    va_list ap;
    if (quiet && lvl < RETRO_LOG_WARN) return;
    va_start(ap, f);
    vfprintf(stderr, f, ap);
    va_end(ap);
}

static const char *opts[16];
static int nopts;

static bool env(unsigned cmd, void *data)
{
    switch (cmd) {
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
        ((struct retro_log_callback *)data)->log = logcb;
        return true;
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
        fmt = *(enum retro_pixel_format *)data;
        return true;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
        *(const char **)data = "/tmp";
        return true;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE:
        *(bool *)data = true;
        return true;
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
        /* core options given with -o key=value */
        struct retro_variable *v = data;
        for (int i = 0; i < nopts; i++) {
            size_t n = strlen(v->key);
            if (!strncmp(opts[i], v->key, n) && opts[i][n] == '=') {
                v->value = opts[i] + n + 1;
                return true;
            }
        }
        v->value = NULL;
        return false;
    }
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:
        *(bool *)data = false;
        return true;
    default:
        return false;
    }
}

static void video(const void *data, unsigned w, unsigned h, size_t pitch)
{
    if (!data) return;
    if (w != fw || h != fh) {
        free(frame);
        frame = malloc(w * h * 3);
        fw = w; fh = h;
    }
    for (unsigned y = 0; y < h; y++) {
        const uint8_t *row = (const uint8_t *)data + y * pitch;
        uint8_t *o = frame + y * w * 3;
        for (unsigned x = 0; x < w; x++, o += 3) {
            if (fmt == RETRO_PIXEL_FORMAT_RGB565) {
                uint16_t p = ((const uint16_t *)row)[x];
                o[0] = (p >> 11) * 255 / 31; o[1] = ((p >> 5) & 63) * 255 / 63; o[2] = (p & 31) * 255 / 31;
            } else if (fmt == RETRO_PIXEL_FORMAT_XRGB8888) {
                uint32_t p = ((const uint32_t *)row)[x];
                o[0] = p >> 16; o[1] = p >> 8; o[2] = p;
            } else {
                uint16_t p = ((const uint16_t *)row)[x];
                o[0] = ((p >> 10) & 31) * 255 / 31; o[1] = ((p >> 5) & 31) * 255 / 31; o[2] = (p & 31) * 255 / 31;
            }
        }
    }
}

static void audio(int16_t l, int16_t r) { (void)l; (void)r; audio_frames++; }
static size_t audio_batch(const int16_t *d, size_t n)
{
    audio_frames += n;
    if (audio_out) fwrite(d, 4, n, audio_out);
    return n;
}
static void poll(void) {}
static int16_t state(unsigned port, unsigned dev, unsigned idx, unsigned id)
{
    (void)idx;
    if (port > 3 || (dev & 0xff) != RETRO_DEVICE_JOYPAD) return 0;
    if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return pads[port];
    return (pads[port] >> id) & 1;
}

static void png_chunk(FILE *f, const char *tag, const uint8_t *d, uint32_t n)
{
    uint8_t b[4] = { n >> 24, n >> 16, n >> 8, n };
    uint32_t c = crc32(0, (const uint8_t *)tag, 4);
    if (n) c = crc32(c, d, n);
    fwrite(b, 1, 4, f); fwrite(tag, 1, 4, f);
    if (n) fwrite(d, 1, n, f);
    b[0] = c >> 24; b[1] = c >> 16; b[2] = c >> 8; b[3] = c;
    fwrite(b, 1, 4, f);
}

static void save_png(const char *path, int scale)
{
    unsigned w = fw * scale, h = fh * scale;
    size_t rawn = (size_t)h * (w * 3 + 1);
    uint8_t *raw = malloc(rawn), *p = raw;
    for (unsigned y = 0; y < h; y++) {
        *p++ = 0;
        for (unsigned x = 0; x < w; x++, p += 3)
            memcpy(p, frame + ((y / scale) * fw + x / scale) * 3, 3);
    }
    uLongf zn = compressBound(rawn);
    uint8_t *z = malloc(zn);
    compress2(z, &zn, raw, rawn, 6);
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); exit(1); }
    fwrite("\x89PNG\r\n\x1a\n", 1, 8, f);
    uint8_t ih[13] = { w >> 24, w >> 16, w >> 8, w, h >> 24, h >> 16, h >> 8, h, 8, 2, 0, 0, 0 };
    png_chunk(f, "IHDR", ih, 13);
    png_chunk(f, "IDAT", z, zn);
    png_chunk(f, "IEND", NULL, 0);
    fclose(f);
    free(raw); free(z);
}

/* PicoDrive keeps RAM as 16-bit words in the host's order; swap each back. */
static void write_ram(FILE *f)
{
    void *(*data)(unsigned) = dlsym(core.h, "retro_get_memory_data");
    size_t (*size)(unsigned) = dlsym(core.h, "retro_get_memory_size");
    static uint8_t out[0x10000];
    const uint8_t *ram = data ? data(RETRO_MEMORY_SYSTEM_RAM) : NULL;
    size_t n = size ? size(RETRO_MEMORY_SYSTEM_RAM) : 0;
    if (!ram || n > sizeof out) return;
    for (size_t i = 0; i + 1 < n; i += 2) { out[i] = ram[i + 1]; out[i + 1] = ram[i]; }
    fwrite(out, 1, n, f);
}

static unsigned *trace_hits, *trace_cycles;
#define TRACE_WORDS 0x800000

static void write_profile(const char *path)
{
    FILE *f = fopen(path, "w");
    if (!f) { perror(path); exit(1); }
    for (unsigned i = 0; i < TRACE_WORDS; i++)
        if (trace_hits[i])
            fprintf(f, "%06x %u %u\n", i * 2, trace_hits[i], trace_cycles[i]);
    fclose(f);
}

static unsigned long peek32(unsigned addr)
{
    uint8_t *(*data)(unsigned) = dlsym(core.h, "retro_get_memory_data");
    uint8_t *ram = data ? data(RETRO_MEMORY_SYSTEM_RAM) : NULL;
    unsigned long v = 0;
    if (ram)
        for (unsigned i = 0; i < 4; i++)
            v = v << 8 | ram[((addr + i) & 0xffff) ^ 1];
    return v;
}

static void poke(unsigned addr, unsigned value)
{
    uint8_t *(*data)(unsigned) = dlsym(core.h, "retro_get_memory_data");
    uint8_t *ram = data ? data(RETRO_MEMORY_SYSTEM_RAM) : NULL;
    if (ram) ram[(addr & 0xffff) ^ 1] = value;
}

struct pokeval { int frame; unsigned addr, value; };

static int id_a = RETRO_DEVICE_ID_JOYPAD_Y, id_b = RETRO_DEVICE_ID_JOYPAD_B, id_c = RETRO_DEVICE_ID_JOYPAD_A;

static uint16_t parse_buttons(const char *s)
{
    const struct { const char *n; int id; } map[] = {
        { "UP", RETRO_DEVICE_ID_JOYPAD_UP }, { "DOWN", RETRO_DEVICE_ID_JOYPAD_DOWN },
        { "LEFT", RETRO_DEVICE_ID_JOYPAD_LEFT }, { "RIGHT", RETRO_DEVICE_ID_JOYPAD_RIGHT },
        { "A", id_a }, { "B", id_b },
        { "C", id_c }, { "START", RETRO_DEVICE_ID_JOYPAD_START },
    };
    uint16_t v = 0;
    char buf[128], *t;
    strncpy(buf, s, sizeof buf - 1); buf[sizeof buf - 1] = 0;
    for (t = strtok(buf, "+ \t\r\n"); t; t = strtok(NULL, "+ \t\r\n"))
        if (t[0] == '#') v |= 1 << atoi(t + 1);
        else for (unsigned i = 0; i < sizeof map / sizeof map[0]; i++)
            if (!strcmp(t, map[i].n)) v |= 1 << map[i].id;
    return v;
}

/* The CRC of a PicoDrive state without the parts that differ harmlessly. A
 * state is a 12-byte header and then chunks: a number, a length, the data. */
static unsigned long game_crc(const uint8_t *st, size_t n)
{
    unsigned long c = crc32(0, NULL, 0);
    size_t p = 12;
    while (p + 5 <= n) {
        const unsigned id = st[p];
        const size_t len = st[p + 1] | st[p + 2] << 8 | st[p + 3] << 16 | (size_t)st[p + 4] << 24;
        if (!id || p + 5 + len > n) break;
        if (id == 32 && len >= 0x9a) {          /* the 32X's own registers, but not vdp_fbcr_fake */
            c = crc32(c, st + p + 5, 0x98);
            c = crc32(c, st + p + 5 + 0x9a, len - 0x9a);
        } else if ((id == 26 || id == 29) && len >= 0x6c) {
            /* an SH-2: its registers, but not how far the emulator has run it */
            c = crc32(c, st + p + 5, 0x68);
            c = crc32(c, st + p + 5 + 0x6c, len - 0x6c);
        } else if (id != 60)                    /* 60 is the FM chip's envelopes and phases */
            c = crc32(c, st + p + 5, len);
        p += 5 + len;
    }
    return c;
}

struct ev { int frame, port; uint16_t b; };
struct shot { int frame; const char *path; };

#define SYM(field, name) do { *(void **)&core.field = dlsym(core.h, name); \
    if (!core.field) { fprintf(stderr, "missing %s\n", name); return 1; } } while (0)

int main(int argc, char **argv)
{
    int video_from = 0, nframes = 600, nshots = 0, nev = 0, rollback = 0, dev = 0, scale = 2;
    int rewind_n = 0, state_frame = -1;
    const char *state_path = NULL;
    FILE *crc_out = NULL;
    struct shot shots[256];
    static struct ev evs[65536];
    const char *script = NULL, *audio_path = NULL, *ram_path = NULL, *load_path = NULL;
    FILE *log_out = NULL, *ram_out = NULL, *watch_out = NULL;
    unsigned watch_addr = 0;
    static struct pokeval pokes[64];
    int npokes = 0;
    int prof_from = -1, prof_to = -1;
    const char *prof_path = NULL;
    unsigned tick_at = 0, idle_lo = 0, idle_hi = 0, last_ticks = 0;
    unsigned long long last_idle = 0;
    FILE *tick_out = NULL;

    if (argc < 3) { fprintf(stderr, "usage: runner core rom [options]\n"); return 1; }
    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "-n")) nframes = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-s")) {
            char *c = strchr(argv[++i], ':');
            shots[nshots].frame = atoi(argv[i]);
            shots[nshots++].path = c + 1;
        }
        else if (!strcmp(argv[i], "-i")) script = argv[++i];
        else if (!strcmp(argv[i], "-a")) audio_path = argv[++i];
        else if (!strcmp(argv[i], "-m")) ram_path = argv[++i];     /* the 68000's RAM at the end, for debugging */
        else if (!strcmp(argv[i], "-v")) { video_out = fopen(argv[++i], "wb"); video_from = atoi(argv[++i]); }
        else if (!strcmp(argv[i], "-x")) scale = atoi(argv[++i]);
        /* The multitap is chosen by controller type in newer PicoDrive and by
         * a core option in the build RetroArch's updater hands out: do both. */
        else if (!strcmp(argv[i], "-4")) { dev = RETRO_DEVICE_SUBCLASS(RETRO_DEVICE_JOYPAD, 3); opts[nopts++] = "picodrive_input1=4way play"; }
        else if (!strcmp(argv[i], "-t")) { dev = RETRO_DEVICE_SUBCLASS(RETRO_DEVICE_JOYPAD, 2); opts[nopts++] = "picodrive_input1=team player"; }
        else if (!strcmp(argv[i], "-o") && nopts < 16) opts[nopts++] = argv[++i];
        else if (!strcmp(argv[i], "-r")) rollback = 1;
        else if (!strcmp(argv[i], "-c")) crc_out = fopen(argv[++i], "w");
        else if (!strcmp(argv[i], "-R")) rewind_n = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-S")) { state_frame = atoi(argv[++i]); state_path = strchr(argv[i], ':') + 1; }
        else if (!strcmp(argv[i], "-l")) load_path = argv[++i];
        else if (!strcmp(argv[i], "-L")) log_out = fopen(argv[++i], "w");
        else if (!strcmp(argv[i], "-M")) ram_out = fopen(argv[++i], "wb");
        else if (!strcmp(argv[i], "-P")) {
            static char pbuf[4096];
            int used = 0;
            snprintf(pbuf, sizeof pbuf, "%s", argv[++i]);
            if (sscanf(pbuf, "%d:%d:%n", &prof_from, &prof_to, &used) < 2 || !used) { fprintf(stderr, "-P from:to:file\n"); return 1; }
            prof_path = pbuf + used;
        }
        else if (!strcmp(argv[i], "-T")) {
            int used = 0;
            if (sscanf(argv[++i], "%x,%x,%x:%n", &tick_at, &idle_lo, &idle_hi, &used) < 3 || !used) { fprintf(stderr, "-T tick,lo,hi:file\n"); return 1; }
            tick_out = fopen(argv[i] + used, "w");
        }
        else if (!strcmp(argv[i], "-p") && npokes < 64) {
            struct pokeval *q = &pokes[npokes++];
            if (sscanf(argv[++i], "%d:%x=%x", &q->frame, &q->addr, &q->value) != 3) { fprintf(stderr, "-p frame:addr=value\n"); return 1; }
        }
        else if (!strcmp(argv[i], "-W")) {
            int used = 0;
            if (sscanf(argv[++i], "%x:%n", &watch_addr, &used) < 1 || !used) { fprintf(stderr, "-W addr:file\n"); return 1; }
            watch_out = fopen(argv[i] + used, "w");
        }
        else if (!strcmp(argv[i], "-b")) {
            if (sscanf(argv[++i], "%d,%d,%d", &id_a, &id_b, &id_c) != 3) { fprintf(stderr, "-b a,b,c\n"); return 1; }
        }
        else if (!strcmp(argv[i], "-q")) quiet = 1;
    }
    if (script) {
        FILE *f = fopen(script, "r");
        char line[256], b[128];
        if (!f) { perror(script); return 1; }
        while (fgets(line, sizeof line, f)) {
            if (line[0] == '#' || sscanf(line, "%d %d %127[^\n]", &evs[nev].frame, &evs[nev].port, b) != 3)
                continue;
            evs[nev].b = parse_buttons(b);
            if (++nev == 65536) break;
        }
        fclose(f);
    }
    if (audio_path) audio_out = fopen(audio_path, "wb");

    core.h = dlopen(argv[1], RTLD_NOW);
    if (!core.h) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    SYM(init, "retro_init"); SYM(deinit, "retro_deinit"); SYM(run, "retro_run");
    SYM(load_game, "retro_load_game"); SYM(set_env, "retro_set_environment");
    SYM(set_video, "retro_set_video_refresh"); SYM(set_audio, "retro_set_audio_sample");
    SYM(set_audio_batch, "retro_set_audio_sample_batch"); SYM(set_poll, "retro_set_input_poll");
    SYM(set_state, "retro_set_input_state"); SYM(set_port, "retro_set_controller_port_device");
    SYM(ser_size, "retro_serialize_size"); SYM(ser, "retro_serialize"); SYM(unser, "retro_unserialize");

    core.set_env(env);
    core.init();
    core.set_video(video); core.set_audio(audio); core.set_audio_batch(audio_batch);
    core.set_poll(poll); core.set_state(state);

    FILE *rf = fopen(argv[2], "rb");
    if (!rf) { perror(argv[2]); return 1; }
    fseek(rf, 0, SEEK_END);
    long rn = ftell(rf);
    rewind(rf);
    void *rom = malloc(rn);
    if (fread(rom, 1, rn, rf) != (size_t)rn) return 1;
    fclose(rf);
    struct retro_game_info gi = { argv[2], rom, rn, NULL };
    if (!core.load_game(&gi)) { fprintf(stderr, "load_game failed\n"); return 1; }
    if (dev) core.set_port(0, dev);

    size_t sn = 0;
    void *sbuf = NULL;
    if (load_path) {
        FILE *lf = fopen(load_path, "rb");
        if (!lf) { perror(load_path); return 1; }
        sn = core.ser_size();
        sbuf = calloc(1, sn);
        size_t got = fread(sbuf, 1, sn, lf);
        fclose(lf);
        core.run();                     /* the core finishes starting up on its first frame */
        if (!got || !core.unser(sbuf, got)) { fprintf(stderr, "couldn't load %s\n", load_path); return 1; }
    }
    uint8_t *keep = NULL;
    int mismatches = 0;

    if (prof_path || tick_out) {
        trace_hits = dlsym(core.h, "retro_trace_hits");
        trace_cycles = dlsym(core.h, "retro_trace_cycles");
        if (!trace_hits || !trace_cycles) { fprintf(stderr, "-P and -T need the profiling core\n"); return 1; }
    }

    for (int f = 0; f < nframes; f++) {
        if (prof_path && f == prof_from && !tick_out) {
            memset(trace_hits, 0, TRACE_WORDS * sizeof *trace_hits);
            memset(trace_cycles, 0, TRACE_WORDS * sizeof *trace_cycles);
        }
        for (int i = 0; i < nev; i++)
            if (evs[i].frame == f) pads[evs[i].port] = evs[i].b;
        for (int i = 0; i < npokes; i++)
            if (pokes[i].frame == f) poke(pokes[i].addr, pokes[i].value);
        if ((crc_out || rewind_n || f == state_frame) && (f > 30 || load_path)) {
            if (!sbuf) { sn = core.ser_size(); sbuf = malloc(sn); }
            memset(sbuf, 0, sn);
            if (!core.ser(sbuf, sn)) { fprintf(stderr, "serialize failed\n"); return 1; }
            if (crc_out) fprintf(crc_out, "%d %08lx %08lx\n", f, crc32(0, sbuf, sn), game_crc(sbuf, sn));
            if (f == state_frame) {
                FILE *sf = fopen(state_path, "wb");
                if (sf) { fwrite(sbuf, 1, sn, sf); fclose(sf); }
            }
            if (rewind_n && f % 3 == 0) {
                /* what a netplay machine does when it guessed the others'
                 * buttons wrong: runs on, then comes back and does it again */
                uint16_t real[4];
                FILE *ao = audio_out;
                memcpy(real, pads, sizeof real);
                audio_out = NULL;
                for (int i = 0; i < 4; i++)
                    pads[i] ^= (1 << RETRO_DEVICE_ID_JOYPAD_B) | (1 << RETRO_DEVICE_ID_JOYPAD_LEFT) | (1 << RETRO_DEVICE_ID_JOYPAD_A);
                for (int i = 0; i < rewind_n; i++)
                    core.run();
                memcpy(pads, real, sizeof real);
                audio_out = ao;
                if (!core.unser(sbuf, sn)) { fprintf(stderr, "unserialize failed\n"); return 1; }
            }
            core.run();
        } else if (rollback && f > 30) {
            if (!sbuf) { sn = core.ser_size(); sbuf = malloc(sn); }
            if (!core.ser(sbuf, sn)) { fprintf(stderr, "serialize failed\n"); return 1; }
            core.run();
            keep = realloc(keep, fw * fh * 3);
            memcpy(keep, frame, fw * fh * 3);
            /* run two more frames ahead, as a rollback would, then rewind */
            core.run(); core.run();
            if (!core.unser(sbuf, sn)) { fprintf(stderr, "unserialize failed\n"); return 1; }
            core.run();
            if (memcmp(keep, frame, fw * fh * 3)) {
                if (mismatches++ < 5) fprintf(stderr, "rollback mismatch at frame %d\n", f);
            }
        } else
            core.run();
        if (log_out && frame)
            fprintf(log_out, "%d %08lx %04x\n", f, crc32(0, frame, fw * fh * 3), pads[0]);
        if (ram_out) write_ram(ram_out);
        if (watch_out) fprintf(watch_out, "%lu\n", peek32(watch_addr));
        if (prof_path && f == prof_to) write_profile(prof_path);
        if (tick_out) {
            unsigned long long idle = 0;
            for (unsigned a = idle_lo / 2; a <= idle_hi / 2; a++) idle += trace_cycles[a];
            fprintf(tick_out, "%d %u %llu\n", f, trace_hits[tick_at / 2] - last_ticks, idle - last_idle);
            last_ticks = trace_hits[tick_at / 2];
            last_idle = idle;
        }
        for (int i = 0; i < nshots; i++)
            if (shots[i].frame == f && frame) save_png(shots[i].path, scale);
        if (video_out && frame && f >= video_from && (f & 1) == 0) fwrite(frame, 3, fw * fh, video_out);
    }
    if (rollback)
        printf("rollback check: %d mismatching frames of %d (state %zu bytes)\n", mismatches, nframes - 31, sn);
    if (audio_out) fclose(audio_out);
    if (crc_out) fclose(crc_out);
    if (ram_path) {
        FILE *f = fopen(ram_path, "wb");
        if (f) { write_ram(f); fclose(f); }
    }
    if (log_out) fclose(log_out);
    if (watch_out) fclose(watch_out);
    if (tick_out) fclose(tick_out);
    if (ram_out) fclose(ram_out);
    if (video_out) fclose(video_out);
    if (!quiet) fprintf(stderr, "ran %d frames, %ux%u, %ld audio frames\n", nframes, fw, fh, audio_frames);
    return mismatches ? 2 : 0;
}
