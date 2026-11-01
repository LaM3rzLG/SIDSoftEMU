// sid_ref - valodi SID-referencia WAV (libsidplayfp + SIDLite), csak az A/B osszehasonlitashoz.
//   sid_ref fajl.sid aldal masodperc kimenet.wav
// Forditas (Mac): c++ -O2 -std=c++17 sid_ref.cpp -I/opt/homebrew/include -L/opt/homebrew/lib -lsidplayfp -o sid_ref
#include <sidplayfp/sidplayfp.h>
#include <sidplayfp/SidTune.h>
#include <sidplayfp/SidConfig.h>
#include <sidplayfp/builders/sidlite.h>
#include <cstdio>
#include <cstdlib>
#include <vector>

static void w16(FILE *f, int v) { fputc(v & 255, f); fputc((v >> 8) & 255, f); }
static void w32(FILE *f, long v) { w16(f, v & 0xFFFF); w16(f, (v >> 16) & 0xFFFF); }

int main(int argc, char **argv)
{
    if (argc < 5) { fprintf(stderr, "sid_ref fajl.sid aldal masodperc ki.wav\n"); return 1; }
    const int RATE = 44100;
    sidplayfp eng;
    SIDLiteBuilder sb("sidlite");
    SidTune tune(argv[1]);
    if (!tune.getStatus()) { fprintf(stderr, "hibas sid\n"); return 1; }
    tune.selectSong(atoi(argv[2]));
    SidConfig cfg = eng.config();
    cfg.frequency = RATE;
    cfg.sidEmulation = &sb;
    if (!eng.config(cfg)) { fprintf(stderr, "config: %s\n", eng.error()); return 1; }
    if (!eng.load(&tune)) { fprintf(stderr, "load: %s\n", eng.error()); return 1; }
    eng.initMixer(false);
    long total = (long)RATE * atoi(argv[3]);
    std::vector<short> out;
    std::vector<short> buf(20000);
    while ((long)out.size() < total) {
        int n = eng.play(5000);
        if (n < 0) { fprintf(stderr, "play: %s\n", eng.error()); return 1; }
        unsigned m = eng.mix(buf.data(), n);
        out.insert(out.end(), buf.begin(), buf.begin() + m);
    }
    out.resize(total);
    FILE *f = fopen(argv[4], "wb");
    fwrite("RIFF", 1, 4, f); w32(f, 36 + total * 2); fwrite("WAVEfmt ", 1, 8, f);
    w32(f, 16); w16(f, 1); w16(f, 1); w32(f, RATE); w32(f, RATE * 2); w16(f, 2); w16(f, 16);
    fwrite("data", 1, 4, f); w32(f, total * 2);
    fwrite(out.data(), 2, total, f);
    fclose(f);
    return 0;
}
